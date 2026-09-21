"""Deterministic text-world command session built on the simulation systems."""

from __future__ import annotations

import random
import shlex
from dataclasses import dataclass, field
from enum import StrEnum

from .cognition import Mind
from .content import create_character, create_enemy
from .models import BodyPart
from .physiology import Loadout, Physiology
from .simulation import SimulationKernel, WorldState
from .spatial import Bounds, SpatialEntity, Vec3, observe
from .spatial_combat import (
    SpatialCombatant,
    SpatialCombatResolver,
    WeaponPhysics,
)
from .textui import narrative_view, tactical_map
from .worldstate import WorldActor


class CommandKind(StrEnum):
    LOOK = "look"
    MAP = "map"
    MOVE = "move"
    ADVANCE = "advance"
    ATTACK = "attack"
    INSPECT = "inspect"
    WAIT = "wait"
    STATUS = "status"
    HELP = "help"
    QUIT = "quit"


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    kind: CommandKind
    args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: ParsedCommand
    output: str
    elapsed_seconds: float
    quit: bool = False


def parse_command(text: str) -> ParsedCommand:
    try:
        parts = shlex.split(text)
    except ValueError as exc:
        raise ValueError(f"invalid command syntax: {exc}") from exc
    if not parts:
        raise ValueError("command may not be empty")
    try:
        kind = CommandKind(parts[0].lower())
    except ValueError as exc:
        raise ValueError(f"unknown command: {parts[0]}") from exc
    return ParsedCommand(kind, tuple(parts[1:]))


@dataclass(slots=True)
class TextWorldSession:
    player_id: str
    actors: dict[str, WorldActor]
    combatants: dict[str, SpatialCombatant]
    rng: random.Random
    scenery: tuple[SpatialEntity, ...] = ()
    kernel: SimulationKernel | None = None
    elapsed_seconds: float = 0.0
    transcript: list[str] = field(default_factory=list)

    @property
    def player(self) -> WorldActor:
        return self.actors[self.player_id]

    @property
    def entities(self) -> list[SpatialEntity]:
        return [
            *(actor.spatial for actor in self.actors.values()),
            *self.scenery,
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
        return result

    def replay(self, commands: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(self.execute(command).output for command in commands)

    def _look(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 0, "look")
        return narrative_view(self.player.spatial, self.entities), False

    def _map(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 0, "map")
        return tactical_map(self.player.spatial, self.entities), False

    def _move(self, args: tuple[str, ...]) -> tuple[str, bool]:
        if not 1 <= len(args) <= 2:
            raise ValueError("usage: move <north|south|east|west> [meters]")
        directions = {
            "north": Vec3(0.0, 1.0, 0.0),
            "south": Vec3(0.0, -1.0, 0.0),
            "east": Vec3(1.0, 0.0, 0.0),
            "west": Vec3(-1.0, 0.0, 0.0),
        }
        try:
            direction = directions[args[0].lower()]
        except KeyError as exc:
            raise ValueError("direction must be north, south, east, or west") from exc
        distance = self._positive_float(args[1] if len(args) == 2 else "1", "distance")
        destination = self.player.spatial.position + direction.scale(distance)
        seconds = distance / self.player.effective_speed()
        moved = self.player.move_toward(destination, seconds, exertion=0.35)
        self._advance_clock(seconds, already_advanced={self.player_id})
        return (
            f"You move {args[0].lower()} {moved:.2f} m. "
            f"Position: {self._position_text(self.player.spatial.position)}",
            False,
        )

    def _advance(self, args: tuple[str, ...]) -> tuple[str, bool]:
        if not 1 <= len(args) <= 2:
            raise ValueError("usage: advance <target> [seconds]")
        target_id = self._resolve_actor(args[0])
        if target_id == self.player_id:
            raise ValueError("cannot advance toward yourself")
        seconds = self._positive_float(args[1] if len(args) == 2 else "1", "seconds")
        target = self.actors[target_id]
        before = self.player.spatial.position.distance_to(target.spatial.position)
        moved = self.player.move_toward(
            target.spatial.position,
            seconds,
            exertion=0.45,
        )
        self._advance_clock(seconds, already_advanced={self.player_id})
        after = self.player.spatial.position.distance_to(target.spatial.position)
        return (
            f"You advance {moved:.2f} m toward {target.spatial.name}; "
            f"distance {before:.2f} -> {after:.2f} m.",
            False,
        )

    def _attack(self, args: tuple[str, ...]) -> tuple[str, bool]:
        if not 1 <= len(args) <= 2:
            raise ValueError("usage: attack <target> [body_part]")
        target_id = self._resolve_actor(args[0])
        if target_id == self.player_id:
            raise ValueError("cannot attack yourself")
        if self.player_id not in self.combatants or target_id not in self.combatants:
            raise ValueError("target is not a combatant")

        part: BodyPart | None = None
        if len(args) == 2:
            try:
                part = BodyPart(args[1].lower())
            except ValueError as exc:
                valid = ", ".join(item.value for item in BodyPart)
                raise ValueError(f"body_part must be one of: {valid}") from exc

        result = SpatialCombatResolver(self.rng).resolve_attack(
            self.combatants[self.player_id],
            self.combatants[target_id],
            selected_part=part,
        )
        self._advance_clock(1.0)
        return result.text, False

    def _inspect(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 1, "inspect <target>")
        target = self._resolve_entity(args[0])
        observation = observe(
            self.player.spatial,
            target,
            self.player.vision,
            obstacles=self.entities,
        )
        if observation is None:
            return "You cannot currently perceive that target.", False
        return (
            f"{observation.description}; {observation.distance_m:.2f} m "
            f"{observation.bearing.lower()}, elevation "
            f"{observation.elevation_m:+.2f} m, clarity {observation.clarity:.2f}.",
            False,
        )

    def _wait(self, args: tuple[str, ...]) -> tuple[str, bool]:
        if len(args) > 1:
            raise ValueError("usage: wait [seconds]")
        seconds = self._positive_float(args[0] if args else "1", "seconds")
        self._advance_clock(seconds)
        return f"You wait {seconds:.2f} seconds.", False

    def _status(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 0, "status")
        body = self.player.physiology
        return (
            f"Position {self._position_text(self.player.spatial.position)}; "
            f"speed {self.player.effective_speed():.2f} m/s; "
            f"fatigue {body.fatigue:.2f}; blood lost {body.blood_lost_ml:.1f} ml; "
            f"injuries {len(body.injuries)}.",
            False,
        )

    def _help(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 0, "help")
        return (
            "Commands: look, map, move <direction> [m], advance <target> [s], "
            "attack <target> [body_part], inspect <target>, wait [s], "
            "status, help, quit.",
            False,
        )

    def _quit(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 0, "quit")
        return "Session ended.", True

    def _advance_clock(
        self,
        seconds: float,
        *,
        already_advanced: set[str] | None = None,
    ) -> None:
        skipped = already_advanced or set()
        for actor_id, actor in self.actors.items():
            if actor_id in skipped:
                continue
            actor.physiology.tick(seconds / 60.0, exertion=0.05)
        self.elapsed_seconds += seconds
        if self.kernel is not None:
            target_hour = self.kernel.world.time_hours + seconds / 3600.0
            self.kernel.advance_to(target_hour)

    def _resolve_actor(self, query: str) -> str:
        lowered = query.lower()
        matches = [
            actor_id
            for actor_id, actor in self.actors.items()
            if actor_id.lower() == lowered or actor.spatial.name.lower() == lowered
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
            if entity.entity_id.lower() == lowered or entity.name.lower() == lowered
        ]
        if len(matches) != 1:
            if not matches:
                raise ValueError(f"unknown target: {query}")
            raise ValueError(f"ambiguous target: {query}")
        return matches[0]

    @staticmethod
    def _expect_count(args: tuple[str, ...], count: int, usage: str) -> None:
        if len(args) != count:
            raise ValueError(f"usage: {usage}")

    @staticmethod
    def _positive_float(value: str, label: str) -> float:
        try:
            number = float(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be numeric") from exc
        if number <= 0:
            raise ValueError(f"{label} must be positive")
        return number

    @staticmethod
    def _position_text(position: Vec3) -> str:
        return f"({position.x:.2f}, {position.y:.2f}, {position.z:.2f})"


def build_demo_session(seed: int = 42) -> TextWorldSession:
    player_actor = create_character("ranger", "Aster", seed)
    wolf_actor = create_enemy("wolf", 1, seed + 1)

    player_world = WorldActor(
        SpatialEntity(
            player_actor.actor_id,
            player_actor.name,
            Vec3(0.0, 0.0, 0.0),
            facing=Vec3(0.0, 1.0, 0.0),
        ),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
    )
    wolf_world = WorldActor(
        SpatialEntity(
            wolf_actor.actor_id,
            wolf_actor.name,
            Vec3(0.0, 8.0, 0.0),
            facing=Vec3(0.0, -1.0, 0.0),
            tags=frozenset({"hostile", "creature"}),
        ),
        Mind(),
        Physiology(38.0),
        Loadout(38.0),
        movement_speed_mps=1.8,
    )

    sword = WeaponPhysics(
        "hunting sword",
        mass_kg=1.2,
        reach_m=0.85,
        handling=1.0,
        strike_speed_mps=11.0,
    )
    fangs = WeaponPhysics(
        "fangs",
        mass_kg=0.4,
        reach_m=0.25,
        handling=1.15,
        strike_speed_mps=9.0,
    )
    scenery = (
        SpatialEntity(
            "barrel",
            "Barrel",
            Vec3(3.0, 3.0, 0.0),
            bounds=Bounds(0.4, 0.4, 0.9),
            mass_kg=35.0,
            tags=frozenset({"cover"}),
        ),
    )
    kernel = SimulationKernel(WorldState())
    return TextWorldSession(
        player_id=player_actor.actor_id,
        actors={
            player_actor.actor_id: player_world,
            wolf_actor.actor_id: wolf_world,
        },
        combatants={
            player_actor.actor_id: SpatialCombatant(
                player_actor,
                player_world,
                sword,
            ),
            wolf_actor.actor_id: SpatialCombatant(
                wolf_actor,
                wolf_world,
                fangs,
            ),
        },
        rng=random.Random(seed),
        scenery=scenery,
        kernel=kernel,
    )
