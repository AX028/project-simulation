"""Beliefs, memories, emotions, relationships, and utility reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp
from collections.abc import Iterable


@dataclass(slots=True)
class Memory:
    subject: str
    proposition: str
    importance: float
    emotional_intensity: float
    confidence: float
    accuracy: float
    source: str
    created_at: float
    decay_rate: float = 0.02
    tags: frozenset[str] = frozenset()

    def accessibility(self, now: float, relevance: float = 1.0) -> float:
        age = max(0.0, now - self.created_at)
        return (
            self.importance
            * (0.3 + 0.7 * self.emotional_intensity)
            * exp(-self.decay_rate * age)
            * max(0.0, relevance)
        )


@dataclass(slots=True)
class Belief:
    subject: str
    proposition: str
    confidence: float
    source: str
    updated_at: float


@dataclass(slots=True)
class EmotionState:
    fear: float = 0.0
    anger: float = 0.0
    grief: float = 0.0
    shame: float = 0.0
    hope: float = 0.0
    affection: float = 0.0
    curiosity: float = 0.0
    frustration: float = 0.0

    def clamp(self) -> None:
        for key in self.__dataclass_fields__:
            setattr(self, key, max(0.0, min(100.0, float(getattr(self, key)))))

    def decay(self, hours: float, rate: float = 0.035) -> None:
        factor = exp(-rate * max(0.0, hours))
        for key in self.__dataclass_fields__:
            setattr(self, key, getattr(self, key) * factor)


@dataclass(slots=True)
class Relationship:
    affection: float = 0.0
    trust: float = 0.0
    respect: float = 0.0
    fear: float = 0.0
    resentment: float = 0.0
    familiarity: float = 0.0
    dependency: float = 0.0

    def update(self, *, trust: float = 0.0, respect: float = 0.0, fear: float = 0.0) -> None:
        self.trust = max(-100.0, min(100.0, self.trust + trust))
        self.respect = max(-100.0, min(100.0, self.respect + respect))
        self.fear = max(0.0, min(100.0, self.fear + fear))
        self.familiarity = max(0.0, min(100.0, self.familiarity + 1.0))


@dataclass(slots=True)
class Goal:
    name: str
    weight: float


@dataclass(slots=True)
class CandidateAction:
    name: str
    goal_effects: dict[str, float] = field(default_factory=dict)
    risk: float = 0.0
    cost: float = 0.0
    emotion_bias: float = 0.0
    habit_bias: float = 0.0


@dataclass(slots=True)
class Mind:
    memories: list[Memory] = field(default_factory=list)
    beliefs: dict[str, Belief] = field(default_factory=dict)
    emotions: EmotionState = field(default_factory=EmotionState)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    goals: dict[str, Goal] = field(default_factory=dict)
    knowledge: set[str] = field(default_factory=set)

    def remember(self, memory: Memory) -> None:
        self.memories.append(memory)

    def recall(self, now: float, tags: Iterable[str] = (), limit: int = 5) -> list[Memory]:
        required = set(tags)
        scored = []
        for memory in self.memories:
            if required and not required.intersection(memory.tags):
                continue
            relevance = 1.25 if required.intersection(memory.tags) else 1.0
            scored.append((memory.accessibility(now, relevance), memory))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:limit]]

    def learn_claim(
        self,
        *,
        key: str,
        subject: str,
        proposition: str,
        confidence: float,
        source: str,
        now: float,
        source_trust: float = 1.0,
    ) -> None:
        incoming = max(0.0, min(1.0, confidence * max(0.0, source_trust)))
        current = self.beliefs.get(key)
        if current is None:
            self.beliefs[key] = Belief(subject, proposition, incoming, source, now)
            return
        if current.proposition == proposition:
            combined = 1.0 - (1.0 - current.confidence) * (1.0 - incoming)
            current.confidence = min(1.0, combined)
            current.source = source
            current.updated_at = now
        elif incoming > current.confidence:
            current.proposition = proposition
            current.confidence = incoming
            current.source = source
            current.updated_at = now
        else:
            current.confidence *= max(0.0, 1.0 - incoming * 0.45)

    def relationship(self, entity_id: str) -> Relationship:
        return self.relationships.setdefault(entity_id, Relationship())

    def choose_action(self, actions: Iterable[CandidateAction]) -> CandidateAction:
        ranked: list[tuple[float, str, CandidateAction]] = []
        for action in actions:
            utility = sum(
                self.goals.get(name, Goal(name, 0.0)).weight * delta
                for name, delta in action.goal_effects.items()
            )
            utility -= action.risk + action.cost
            utility += action.emotion_bias + action.habit_bias
            ranked.append((utility, action.name, action))
        if not ranked:
            raise ValueError("at least one candidate action is required")
        return max(ranked, key=lambda item: (item[0], item[1]))[2]
