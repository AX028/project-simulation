"""Small deterministic goal-oriented action planner for NPC multi-step behavior."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count

from .validation import finite_number, nonnegative_number, positive_number

FactScalar = str | int | float | bool | None
FactValue = FactScalar | tuple["FactValue", ...] | frozenset["FactValue"]
CanonicalFact = tuple[str, object]


def canonical_fact_value(value: object) -> CanonicalFact:
    if value is None:
        return ("none", "")
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, float):
        return ("float", finite_number(value, "fact value"))
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, tuple):
        return (
            "tuple",
            tuple(canonical_fact_value(item) for item in value),
        )
    if isinstance(value, frozenset):
        items = sorted(
            (canonical_fact_value(item) for item in value),
            key=repr,
        )
        return ("frozenset", tuple(items))
    raise ValueError(
        "fact values must be deterministic scalars, tuples, or frozensets"
    )


@dataclass(frozen=True, slots=True)
class WorldFact:
    key: str
    value: FactValue

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("fact key may not be empty")
        canonical_fact_value(self.value)


@dataclass(frozen=True, slots=True)
class PlanAction:
    name: str
    preconditions: tuple[WorldFact, ...] = ()
    effects: tuple[WorldFact, ...] = ()
    cost: float = 1.0
    risk: float = 0.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("plan action name may not be empty")
        nonnegative_number(self.cost, "action cost")
        nonnegative_number(self.risk, "action risk")

    @property
    def total_cost(self) -> float:
        return self.cost + self.risk


@dataclass(frozen=True, slots=True)
class Plan:
    actions: tuple[PlanAction, ...]
    total_cost: float


class Planner:
    """A bounded uniform-cost GOAP planner over compact fact dictionaries."""

    def __init__(self, max_expansions: int = 500) -> None:
        positive_number(max_expansions, "max expansions")
        self.max_expansions = max_expansions

    @staticmethod
    def _matches(state: dict[str, FactValue], facts: Iterable[WorldFact]) -> bool:
        return all(state.get(fact.key) == fact.value for fact in facts)

    @staticmethod
    def _apply(
        state: dict[str, FactValue],
        effects: Iterable[WorldFact],
    ) -> dict[str, FactValue]:
        result = dict(state)
        for effect in effects:
            result[effect.key] = effect.value
        return result

    @staticmethod
    def _key(
        state: dict[str, FactValue],
    ) -> tuple[tuple[str, CanonicalFact], ...]:
        return tuple(
            sorted(
                (key, canonical_fact_value(value))
                for key, value in state.items()
            )
        )

    def make_plan(
        self,
        initial_state: dict[str, FactValue],
        goal: Iterable[WorldFact],
        actions: Iterable[PlanAction],
    ) -> Plan | None:
        goal = tuple(goal)
        actions = tuple(actions)
        for key, value in initial_state.items():
            if not key:
                raise ValueError("fact key may not be empty")
            canonical_fact_value(value)
        if self._matches(initial_state, goal):
            return Plan((), 0.0)

        serial = count()
        frontier: list[
            tuple[
                float,
                int,
                dict[str, FactValue],
                tuple[PlanAction, ...],
            ]
        ] = [(0.0, next(serial), dict(initial_state), ())]
        best_cost = {self._key(initial_state): 0.0}
        expansions = 0

        while frontier and expansions < self.max_expansions:
            cost, _, state, path = heappop(frontier)
            expansions += 1
            if self._matches(state, goal):
                return Plan(path, cost)

            for action in actions:
                if not self._matches(state, action.preconditions):
                    continue
                next_state = self._apply(state, action.effects)
                next_cost = cost + action.total_cost
                key = self._key(next_state)
                if next_cost >= best_cost.get(key, float("inf")):
                    continue
                best_cost[key] = next_cost
                heappush(
                    frontier,
                    (
                        next_cost,
                        next(serial),
                        next_state,
                        path + (action,),
                    ),
                )
        return None
