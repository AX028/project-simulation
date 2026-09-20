"""Deterministic daily routines that can coexist with goal-oriented planning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoutineBlock:
    start_hour: float
    end_hour: float
    activity: str
    location_id: str
    priority: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.start_hour < 24.0:
            raise ValueError("start_hour must be within a day")
        if not 0.0 <= self.end_hour < 24.0:
            raise ValueError("end_hour must be within a day")

    def contains(self, hour: float) -> bool:
        hour %= 24.0
        if self.start_hour == self.end_hour:
            return True
        if self.start_hour < self.end_hour:
            return self.start_hour <= hour < self.end_hour
        return hour >= self.start_hour or hour < self.end_hour


@dataclass(frozen=True, slots=True)
class RoutineDecision:
    activity: str
    location_id: str
    priority: float


@dataclass(slots=True)
class RoutineSchedule:
    blocks: tuple[RoutineBlock, ...]
    fallback_activity: str = "idle"
    fallback_location_id: str = "home"

    def __post_init__(self) -> None:
        self._validate_no_overlaps()

    def activity_at(self, world_hour: float) -> RoutineDecision:
        hour = world_hour % 24.0
        matches = [block for block in self.blocks if block.contains(hour)]
        if not matches:
            return RoutineDecision(
                self.fallback_activity,
                self.fallback_location_id,
                0.0,
            )
        block = max(matches, key=lambda item: (item.priority, item.activity))
        return RoutineDecision(block.activity, block.location_id, block.priority)

    def next_transition_after(self, world_hour: float) -> float:
        day_start = world_hour - (world_hour % 24.0)
        candidates: list[float] = []
        for day_offset in (0.0, 24.0, 48.0):
            for block in self.blocks:
                for boundary in (block.start_hour, block.end_hour):
                    candidate = day_start + day_offset + boundary
                    if candidate > world_hour + 1e-9:
                        candidates.append(candidate)
        if not candidates:
            return world_hour + 24.0
        return min(candidates)

    def _validate_no_overlaps(self) -> None:
        sample_points = [index / 4.0 for index in range(96)]
        for hour in sample_points:
            active = [block for block in self.blocks if block.contains(hour)]
            if len(active) <= 1:
                continue
            priorities = [block.priority for block in active]
            if len(priorities) != len(set(priorities)):
                raise ValueError(
                    "overlapping routine blocks require distinct priorities"
                )
