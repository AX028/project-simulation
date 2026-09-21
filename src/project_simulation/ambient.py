"""Ambient NPC routine execution in physical world space."""

from __future__ import annotations

from dataclasses import dataclass, field

from .npc_controller import GoalRequest, NPCController
from .spatial import Vec3
from .worldstate import WorldActor


@dataclass(slots=True)
class AmbientAgent:
    actor: WorldActor
    controller: NPCController
    locations: dict[str, Vec3]
    action_locations: dict[str, str] = field(default_factory=dict)
    arrival_tolerance_m: float = 0.05

    def __post_init__(self) -> None:
        if self.arrival_tolerance_m < 0:
            raise ValueError("arrival_tolerance_m may not be negative")


@dataclass(frozen=True, slots=True)
class AmbientEvent:
    actor_id: str
    activity: str
    source: str
    seconds: float
    distance_moved: float
    location_id: str | None


@dataclass(slots=True)
class AmbientNPCSimulation:
    agents: dict[str, AmbientAgent] = field(default_factory=dict)
    urgent_goals: dict[str, GoalRequest] = field(default_factory=dict)

    @property
    def actor_ids(self) -> frozenset[str]:
        return frozenset(self.agents)

    def add_agent(self, agent: AmbientAgent) -> None:
        actor_id = agent.actor.actor_id
        if actor_id in self.agents:
            raise ValueError(f"ambient actor already registered: {actor_id}")
        self.agents[actor_id] = agent

    def set_urgent_goal(self, actor_id: str, goal: GoalRequest) -> None:
        if actor_id not in self.agents:
            raise KeyError(actor_id)
        self.urgent_goals[actor_id] = goal

    def clear_urgent_goal(self, actor_id: str) -> None:
        self.urgent_goals.pop(actor_id, None)

    def advance(
        self,
        *,
        start_world_hour: float,
        seconds: float,
        skip_actor_ids: frozenset[str] = frozenset(),
        ambient_c: float = 20.0,
        speed_multiplier: float = 1.0,
    ) -> tuple[AmbientEvent, ...]:
        if seconds < 0:
            raise ValueError("seconds may not be negative")
        if seconds == 0:
            return ()

        events: list[AmbientEvent] = []
        for actor_id in sorted(self.agents):
            if actor_id in skip_actor_ids:
                continue
            events.extend(
                self._advance_agent(
                    self.agents[actor_id],
                    start_world_hour=start_world_hour,
                    seconds=seconds,
                    urgent_goal=self.urgent_goals.get(actor_id),
                    ambient_c=ambient_c,
                    speed_multiplier=speed_multiplier,
                )
            )
        return tuple(events)

    def _advance_agent(
        self,
        agent: AmbientAgent,
        *,
        start_world_hour: float,
        seconds: float,
        urgent_goal: GoalRequest | None,
        ambient_c: float,
        speed_multiplier: float,
    ) -> list[AmbientEvent]:
        remaining = seconds
        current_hour = start_world_hour
        events: list[AmbientEvent] = []

        while remaining > 1e-9:
            directive = agent.controller.choose_directive(
                current_hour,
                urgent_goal=urgent_goal,
            )
            next_transition = agent.controller.schedule.next_transition_after(
                current_hour
            )
            until_transition = max(
                1e-6,
                (next_transition - current_hour) * 3600.0,
            )
            segment = min(remaining, until_transition)

            location_id = directive.location_id
            if location_id is None:
                location_id = agent.action_locations.get(directive.activity)

            moved = 0.0
            if location_id is not None:
                try:
                    destination = agent.locations[location_id]
                except KeyError as exc:
                    raise KeyError(
                        f"unknown ambient location {location_id!r} "
                        f"for {agent.actor.actor_id}"
                    ) from exc

                distance = agent.actor.spatial.position.distance_to(destination)
                if distance > agent.arrival_tolerance_m:
                    speed = max(
                        0.001,
                        agent.actor.effective_speed() * max(0.0, speed_multiplier),
                    )
                    movement_seconds = min(segment, distance / speed)
                    moved = agent.actor.move_toward(
                        destination,
                        movement_seconds,
                        exertion=0.25,
                        ambient_c=ambient_c,
                        speed_multiplier=speed_multiplier,
                    )
                    idle_seconds = segment - movement_seconds
                    if idle_seconds > 0:
                        agent.actor.physiology.tick(
                            idle_seconds / 60.0,
                            exertion=0.05,
                            ambient_c=ambient_c,
                        )
                else:
                    agent.actor.physiology.tick(
                        segment / 60.0,
                        exertion=0.05,
                        ambient_c=ambient_c,
                    )

                arrived = (
                    agent.actor.spatial.position.distance_to(destination)
                    <= agent.arrival_tolerance_m
                )
                if arrived and directive.action is not None:
                    agent.controller.apply_action(directive.action)
                    if urgent_goal is not None and all(
                        agent.controller.facts.get(fact.key) == fact.value
                        for fact in urgent_goal.facts
                    ):
                        self.urgent_goals.pop(agent.actor.actor_id, None)
            else:
                agent.actor.physiology.tick(
                    segment / 60.0,
                    exertion=0.05,
                    ambient_c=ambient_c,
                )

            events.append(
                AmbientEvent(
                    actor_id=agent.actor.actor_id,
                    activity=directive.activity,
                    source=directive.source,
                    seconds=segment,
                    distance_moved=moved,
                    location_id=location_id,
                )
            )
            remaining -= segment
            current_hour += segment / 3600.0

        return events
