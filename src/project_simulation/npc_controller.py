"""NPC controller combining routine schedules with bounded GOAP overrides."""

from __future__ import annotations

from dataclasses import dataclass, field

from .planning import FactValue, Plan, PlanAction, Planner, WorldFact
from .validation import nonnegative_number
from .schedules import RoutineDecision, RoutineSchedule


@dataclass(frozen=True, slots=True)
class GoalRequest:
    name: str
    facts: tuple[WorldFact, ...]
    priority: float

    def __post_init__(self) -> None:
        nonnegative_number(self.priority, "goal priority")


@dataclass(frozen=True, slots=True)
class AgentDirective:
    source: str
    activity: str
    location_id: str | None
    plan: Plan | None = None
    action: PlanAction | None = None


@dataclass(slots=True)
class NPCController:
    schedule: RoutineSchedule
    actions: tuple[PlanAction, ...] = ()
    facts: dict[str, FactValue] = field(default_factory=dict)
    planner: Planner = field(default_factory=Planner)

    def choose_directive(
        self,
        world_hour: float,
        *,
        urgent_goal: GoalRequest | None = None,
    ) -> AgentDirective:
        routine = self.schedule.activity_at(world_hour)
        if urgent_goal is None or urgent_goal.priority <= routine.priority:
            return self._routine_directive(routine)

        plan = self.planner.make_plan(
            self.facts,
            urgent_goal.facts,
            self.actions,
        )
        if plan is None or not plan.actions:
            return self._routine_directive(routine)

        action = plan.actions[0]
        return AgentDirective(
            source=f"goal:{urgent_goal.name}",
            activity=action.name,
            location_id=None,
            plan=plan,
            action=action,
        )

    def apply_action(self, action: PlanAction) -> None:
        if not all(self.facts.get(fact.key) == fact.value for fact in action.preconditions):
            raise ValueError(f"preconditions are not satisfied for {action.name}")
        for effect in action.effects:
            self.facts[effect.key] = effect.value

    @staticmethod
    def _routine_directive(routine: RoutineDecision) -> AgentDirective:
        return AgentDirective(
            source="routine",
            activity=routine.activity,
            location_id=routine.location_id,
        )
