"""Deterministic skill learning, practice, transfer, and performance."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, sqrt

from .validation import bounded_number, nonnegative_number, positive_number


@dataclass(frozen=True, slots=True)
class PracticeEvent:
    difficulty: float
    duration_hours: float
    quality: float = 1.0
    instruction: float = 0.0
    context: str = "general"

    def __post_init__(self) -> None:
        bounded_number(self.difficulty, "practice difficulty", 0.0, 100.0)
        positive_number(self.duration_hours, "practice duration")
        bounded_number(self.quality, "practice quality", 0.0, 1.0)
        bounded_number(self.instruction, "instruction quality", 0.0, 1.0)
        if not self.context:
            raise ValueError("practice context may not be empty")


@dataclass(frozen=True, slots=True)
class SkillGain:
    skill_id: str
    knowledge: float
    technique: float
    automaticity: float
    experience_hours: float

    @property
    def total_component_gain(self) -> float:
        return self.knowledge + self.technique + self.automaticity


@dataclass(frozen=True, slots=True)
class PracticeResult:
    primary: SkillGain
    transfers: tuple[SkillGain, ...]
    novelty_factor: float
    difficulty_factor: float


@dataclass(slots=True)
class SkillState:
    skill_id: str
    knowledge: float = 50.0
    technique: float = 50.0
    automaticity: float = 50.0
    experience_hours: float = 0.0
    practice_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.skill_id:
            raise ValueError("skill_id may not be empty")
        bounded_number(self.knowledge, "skill knowledge", 0.0, 100.0)
        bounded_number(self.technique, "skill technique", 0.0, 100.0)
        bounded_number(
            self.automaticity,
            "skill automaticity",
            0.0,
            100.0,
        )
        nonnegative_number(self.experience_hours, "skill experience")
        for context, count in self.practice_counts.items():
            if not context:
                raise ValueError("practice context may not be empty")
            nonnegative_number(count, "practice count")

    @property
    def level(self) -> float:
        return (
            self.knowledge * 0.25
            + self.technique * 0.45
            + self.automaticity * 0.30
        )

    @property
    def control_modifier(self) -> float:
        return max(0.5, min(1.5, 0.5 + self.level / 100.0))

    def apply_practice(
        self,
        event: PracticeEvent,
        *,
        learning_rate: float,
    ) -> tuple[SkillGain, float, float]:
        learning_rate = positive_number(learning_rate, "learning rate")
        count = self.practice_counts.get(event.context, 0)
        novelty = max(0.08, 1.0 / sqrt(1.0 + count * 0.5))

        gap = event.difficulty - self.level
        difficulty_factor = 0.10 + 0.90 * exp(
            -((gap - 10.0) / 30.0) ** 2
        )
        duration_factor = sqrt(event.duration_hours)
        base_gain = (
            1.2
            * learning_rate
            * event.quality
            * novelty
            * difficulty_factor
            * duration_factor
        )

        repetition = min(1.0, count / 20.0)
        knowledge_gain = base_gain * (0.45 + 0.85 * event.instruction)
        technique_gain = base_gain * (0.70 + 0.30 * event.quality)
        automaticity_gain = base_gain * (0.30 + 0.70 * repetition)

        before_knowledge = self.knowledge
        before_technique = self.technique
        before_automaticity = self.automaticity
        self.knowledge = min(100.0, self.knowledge + knowledge_gain)
        self.technique = min(100.0, self.technique + technique_gain)
        self.automaticity = min(
            100.0,
            self.automaticity + automaticity_gain,
        )
        self.experience_hours += event.duration_hours
        self.practice_counts[event.context] = count + 1

        gain = SkillGain(
            self.skill_id,
            self.knowledge - before_knowledge,
            self.technique - before_technique,
            self.automaticity - before_automaticity,
            event.duration_hours,
        )
        return gain, novelty, difficulty_factor

    def apply_transfer(
        self,
        source_gain: SkillGain,
        weight: float,
    ) -> SkillGain:
        weight = bounded_number(weight, "transfer weight", 0.0, 1.0)
        knowledge_gain = source_gain.knowledge * weight
        technique_gain = source_gain.technique * weight * 0.7
        before_knowledge = self.knowledge
        before_technique = self.technique
        self.knowledge = min(100.0, self.knowledge + knowledge_gain)
        self.technique = min(100.0, self.technique + technique_gain)
        transferred_hours = source_gain.experience_hours * weight * 0.25
        self.experience_hours += transferred_hours
        return SkillGain(
            self.skill_id,
            self.knowledge - before_knowledge,
            self.technique - before_technique,
            0.0,
            transferred_hours,
        )


def default_skill_transfers() -> dict[str, dict[str, float]]:
    return {
        "sword": {
            "greatsword": 0.24,
            "knife": 0.10,
            "spear": 0.08,
        },
        "greatsword": {"sword": 0.26},
        "knife": {"sword": 0.08},
        "archery": {"throwing": 0.06},
        "tracking": {"survival": 0.25},
        "survival": {"tracking": 0.12},
        "medicine": {"anatomy": 0.30},
        "anatomy": {"medicine": 0.18},
    }


@dataclass(slots=True)
class SkillSet:
    skills: dict[str, SkillState] = field(default_factory=dict)
    learning_rate: float = 1.0
    baseline_level: float = 50.0
    transfers: dict[str, dict[str, float]] = field(
        default_factory=default_skill_transfers
    )

    def __post_init__(self) -> None:
        positive_number(self.learning_rate, "learning rate")
        bounded_number(
            self.baseline_level,
            "baseline skill level",
            0.0,
            100.0,
        )
        for source, targets in self.transfers.items():
            if not source:
                raise ValueError("transfer source may not be empty")
            for target, weight in targets.items():
                if not target:
                    raise ValueError("transfer target may not be empty")
                bounded_number(weight, "transfer weight", 0.0, 1.0)

    def ensure(self, skill_id: str) -> SkillState:
        if not skill_id:
            raise ValueError("skill_id may not be empty")
        state = self.skills.get(skill_id)
        if state is None:
            state = SkillState(
                skill_id,
                knowledge=self.baseline_level,
                technique=self.baseline_level,
                automaticity=self.baseline_level,
            )
            self.skills[skill_id] = state
        return state

    def level(self, skill_id: str) -> float:
        state = self.skills.get(skill_id)
        return self.baseline_level if state is None else state.level

    def performance_modifier(
        self,
        skill_id: str,
        *,
        physiology_modifier: float = 1.0,
        context_modifier: float = 1.0,
    ) -> float:
        physiology_modifier = nonnegative_number(
            physiology_modifier,
            "physiology modifier",
        )
        context_modifier = nonnegative_number(
            context_modifier,
            "context modifier",
        )
        state = self.skills.get(skill_id)
        skill_modifier = (
            0.5 + self.baseline_level / 100.0
            if state is None
            else state.control_modifier
        )
        return max(
            0.0,
            min(
                2.0,
                skill_modifier
                * physiology_modifier
                * context_modifier,
            ),
        )

    def practice(
        self,
        skill_id: str,
        event: PracticeEvent,
    ) -> PracticeResult:
        if not skill_id:
            raise ValueError("skill_id may not be empty")
        for weight in self.transfers.get(skill_id, {}).values():
            bounded_number(weight, "transfer weight", 0.0, 1.0)
        state = self.ensure(skill_id)
        primary, novelty, difficulty = state.apply_practice(
            event,
            learning_rate=self.learning_rate,
        )
        transfers: list[SkillGain] = []
        for target_id, weight in sorted(
            self.transfers.get(skill_id, {}).items()
        ):
            target = self.ensure(target_id)
            transfers.append(target.apply_transfer(primary, weight))
        return PracticeResult(
            primary,
            tuple(transfers),
            novelty,
            difficulty,
        )
