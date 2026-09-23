"""Deterministic text-world session orchestration.

Command parsing, command behavior, and demo construction live in focused modules.
This class keeps the stable session API while coordinating shared world state.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .acoustics import HeardSound, HearingProfile, SoundEvent
from .ambient import AmbientNPCSimulation
from .doors import Door
from .environment import EnvironmentState
from .physiology import PhysicalItem
from .ranged import RangedWeapon
from .simulation import SimulationKernel
from .spatial import SpatialEntity, Vec3
from .spatial_combat import SpatialCombatant
from .textworld_commands import (
    CommandKind,
    CommandResult,
    ParsedCommand,
    parse_command,
)
from .validation import positive_number
from .world_objects import SceneContainer
from .worldstate import WorldActor


@dataclass(slots=True)
class TextWorldSession:
    player_id: str
    actors: dict[str, WorldActor]
    combatants: dict[str, SpatialCombatant]
    rng: random.Random
    scenery: tuple[SpatialEntity, ...] = ()
    world_items: dict[str, PhysicalItem] = field(default_factory=dict)
    doors: dict[str, Door] = field(default_factory=dict)
    ranged_weapons: dict[str, RangedWeapon] = field(default_factory=dict)
    hearing_profiles: dict[str, HearingProfile] = field(default_factory=dict)
    sound_events: list[SoundEvent] = field(default_factory=list)
    environment: EnvironmentState = field(default_factory=EnvironmentState)
    kernel: SimulationKernel | None = None
    ambient: AmbientNPCSimulation | None = None
    elapsed_seconds: float = 0.0
    transcript: list[str] = field(default_factory=list)
    seed: int | None = None
    command_history: list[str] = field(default_factory=list)
    scene_containers: dict[str, SceneContainer] = field(default_factory=dict)

    @property
    def player(self) -> WorldActor:
        return self.actors[self.player_id]

    @property
    def entities(self) -> list[SpatialEntity]:
        return [
            *(actor.spatial for actor in self.actors.values()),
            *self.scenery,
            *(container.spatial for container in self.scene_containers.values()),
            *(door.spatial for door in self.doors.values()),
        ]

    def execute(self, text: str) -> CommandResult:
        command = parse_command(text)
        handler = {
            CommandKind.LOOK: self._look,
            CommandKind.MAP: self._map,
            CommandKind.MOVE: self._move,
            CommandKind.ADVANCE: self._advance,
            CommandKind.ATTACK: self._attack,
            CommandKind.INSPECT: self._inspect,
            CommandKind.WAIT: self._wait,
            CommandKind.STATUS: self._status,
            CommandKind.TAKE: self._take,
            CommandKind.PUT: self._put,
            CommandKind.DROP: self._drop,
            CommandKind.INVENTORY: self._inventory,
            CommandKind.TALK: self._talk,
            CommandKind.OPEN: self._open,
            CommandKind.CLOSE: self._close,
            CommandKind.SHOOT: self._shoot,
            CommandKind.HELP: self._help,
            CommandKind.QUIT: self._quit,
        }[command.kind]
        output, quit_requested = handler(command.args)
        result = CommandResult(
            command,
            output,
            self.elapsed_seconds,
            quit_requested,
        )
        self.transcript.append(f"> {text}")
        self.transcript.append(output)
        self.command_history.append(text)
        return result

    def replay(self, commands: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(self.execute(command).output for command in commands)

    def _look(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import look

        return look(self, args)

    def _map(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import map_view

        return map_view(self, args)

    def _move(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_runtime_commands import move

        return move(self, args)

    def _advance(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_combat_commands import advance

        return advance(self, args)

    def _attack(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_combat_commands import attack

        return attack(self, args)

    def _inspect(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import inspect

        return inspect(self, args)

    def _wait(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_runtime_commands import wait

        return wait(self, args)

    def _status(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_runtime_commands import status

        return status(self, args)

    def _take(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import take

        return take(self, args)

    def _drop(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import drop

        return drop(self, args)

    def _put(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import put

        return put(self, args)

    def _inventory(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import inventory

        return inventory(self, args)

    def _talk(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import talk

        return talk(self, args)

    def _open(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import open_door

        return open_door(self, args)

    def _close(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_interactions import close_door

        return close_door(self, args)

    def _require_door_reach(self, door: Door) -> None:
        from .textworld_interactions import require_door_reach

        require_door_reach(self, door)

    def _resolve_door(self, query: str) -> Door:
        from .textworld_interactions import resolve_door

        return resolve_door(self, query)

    def _shoot(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_combat_commands import shoot

        return shoot(self, args)

    def _emit_sound(
        self,
        *,
        category: str,
        description: str,
        position: Vec3,
        loudness_db_at_1m: float,
        source_id: str | None = None,
    ) -> tuple[HeardSound, ...]:
        from .textworld_combat_commands import emit_sound

        return emit_sound(
            self,
            category=category,
            description=description,
            position=position,
            loudness_db_at_1m=loudness_db_at_1m,
            source_id=source_id,
        )

    def _help(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_runtime_commands import help_text

        return help_text(self, args)

    def _quit(self, args: tuple[str, ...]) -> tuple[str, bool]:
        from .textworld_runtime_commands import quit_session

        return quit_session(self, args)

    def _advance_clock(
        self,
        seconds: float,
        *,
        already_advanced: set[str] | None = None,
    ) -> None:
        skipped = already_advanced or set()
        ambient_ids = (
            self.ambient.actor_ids
            if self.ambient is not None
            else frozenset()
        )
        start_world_hour = (
            self.kernel.world.time_hours
            if self.kernel is not None
            else self.elapsed_seconds / 3600.0
        )

        self.environment.world_hour = start_world_hour
        ambient_c = self.environment.ambient_temperature_c
        speed_multiplier = self.environment.movement_speed_multiplier

        for actor_id, actor in self.actors.items():
            if actor_id in skipped or actor_id in ambient_ids:
                continue
            actor.physiology.tick(
                seconds / 60.0,
                exertion=0.05,
                ambient_c=ambient_c,
            )

        if self.ambient is not None:
            self.ambient.advance(
                start_world_hour=start_world_hour,
                seconds=seconds,
                skip_actor_ids=frozenset(skipped),
                ambient_c=ambient_c,
                speed_multiplier=speed_multiplier,
            )

        self.elapsed_seconds += seconds
        self.environment.advance(seconds / 3600.0)
        if self.kernel is not None:
            target_hour = (
                self.kernel.world.time_hours + seconds / 3600.0
            )
            self.kernel.advance_to(target_hour)

    def _resolve_actor(self, query: str) -> str:
        lowered = query.lower()
        matches = [
            actor_id
            for actor_id, actor in self.actors.items()
            if actor_id.lower() == lowered
            or actor.spatial.name.lower() == lowered
        ]
        if len(matches) != 1:
            if not matches:
                raise ValueError(f"unknown actor: {query}")
            raise ValueError(f"ambiguous actor: {query}")
        return matches[0]

    def _resolve_entity(self, query: str) -> SpatialEntity:
        lowered = query.lower()
        matches = [
            entity
            for entity in self.entities
            if entity.entity_id.lower() == lowered
            or entity.name.lower() == lowered
        ]
        if len(matches) != 1:
            if not matches:
                raise ValueError(f"unknown target: {query}")
            raise ValueError(f"ambiguous target: {query}")
        return matches[0]

    @staticmethod
    def _expect_count(
        args: tuple[str, ...],
        count: int,
        usage: str,
    ) -> None:
        if len(args) != count:
            raise ValueError(f"usage: {usage}")

    @staticmethod
    def _positive_float(value: str, label: str) -> float:
        try:
            number = float(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be numeric") from exc
        return positive_number(number, label)

    @staticmethod
    def _position_text(position: Vec3) -> str:
        return (
            f"({position.x:.2f}, {position.y:.2f}, "
            f"{position.z:.2f})"
        )


def build_demo_session(seed: int = 42) -> TextWorldSession:
    from .textworld_scenario import build_demo_session as build

    return build(seed)


__all__ = [
    "CommandKind",
    "CommandResult",
    "ParsedCommand",
    "TextWorldSession",
    "build_demo_session",
    "parse_command",
]
