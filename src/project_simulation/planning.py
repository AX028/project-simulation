"""Small deterministic goal-oriented action planner for NPC multi-step behavior."""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from collections.abc import Iterable


@dataclass(frozen=True, slots=True)
class WorldFact:
    key: str
    value: object


@dataclass(frozen=True, slots=True)
class PlanAction:
    name: str
    preconditions: tuple[WorldFact, ...] = ()
    effects: tuple[WorldFact, ...] = ()
    cost: float = 1.0
    risk: float = 0.0

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
        self.max_expansions = max_expansions

    @staticmethod
    def _matches(state: dict[str, object], facts: Iterable[WorldFact]) -> bool:
        return all(state.get(fact.key) == fact.value for fact in facts)

    @staticmethod
    def _apply(state: dict[str, object], effects: Iterable[WorldFact]) -> dict[str, object]:
        result = dict(state)
        for effect in effects:
            result[effect.key] = effect.value
        return result

    @staticmethod
    def _key(state: dict[str, object]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((key, repr(value)) for key, value in state.items()))

    def make_plan(
        self,
        initial_state: dict[str, object],
        goal: Iterable[WorldFact],
        actions: Iterable[PlanAction],
    ) -> Plan | None:
        goal = tuple(goal)
        actions = tuple(actions)
        if self._matches(initial_state, goal):
            return Plan((), 0.0)

        serial = count()
        frontier: list[
            tuple[float, int, dict[str, object], tuple[PlanAction, ...]]
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
                    (next_cost, next(serial), next_state, path + (action,)),
                )
        return None
