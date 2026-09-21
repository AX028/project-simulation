"""Deterministic text-world command session built on the simulation systems."""

from __future__ import annotations

import random
import shlex
from dataclasses import dataclass, field
from enum import StrEnum

from .acoustics import HearingProfile, HeardSound, SoundEvent, propagate_sound
from .ambient import AmbientAgent, AmbientNPCSimulation
from .cognition import Belief, Memory, Mind
from .content import create_character, create_enemy
from .dialogue import converse
from .doors import Door, PassageAxis
from .models import BodyPart
from .navigation import move_actor_with_collisions
from .npc_controller import NPCController
from .physiology import Loadout, PhysicalItem, Physiology
from .projectiles import ProjectileSimulator, ProjectileSpec
from .ranged import RangedWeapon, aim_point_for_body_part, resolve_projectile_impact
from .schedules import RoutineBlock, RoutineSchedule
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
    TAKE = "take"
    DROP = "drop"
    INVENTORY = "inventory"
    TALK = "talk"
    OPEN = "open"
    CLOSE = "close"
    SHOOT = "shoot"
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
    world_items: dict[str, PhysicalItem] = field(default_factory=dict)
    doors: dict[str, Door] = field(default_factory=dict)
    ranged_weapons: dict[str, RangedWeapon] = field(default_factory=dict)
    hearing_profiles: dict[str, HearingProfile] = field(default_factory=dict)
    sound_events: list[SoundEvent] = field(default_factory=list)
    kernel: SimulationKernel | None = None
    ambient: AmbientNPCSimulation | None = None
    elapsed_seconds: float = 0.0
    transcript: list[str] = field(default_factory=list)
    seed: int | None = None
    command_history: list[str] = field(default_factory=list)

    @property
    def player(self) -> WorldActor:
        return self.actors[self.player_id]

    @property
    def entities(self) -> list[SpatialEntity]:
        return [
            *(actor.spatial for actor in self.actors.values()),
            *self.scenery,
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
        self.player.spatial.facing = direction
        destination = self.player.spatial.position + direction.scale(distance)
        seconds = distance / self.player.effective_speed()
        movement = move_actor_with_collisions(
            self.player,
            destination,
            seconds,
            self.entities,
            doors=self.doors.values(),
            exertion=0.35,
        )
        self._advance_clock(seconds, already_advanced={self.player_id})
        blocked = (
            ""
            if movement.hit is None
            else f" Movement blocked by {movement.hit.entity_id}."
        )
        return (
            f"You move {args[0].lower()} {movement.moved_distance_m:.2f} m. "
            f"Position: {self._position_text(self.player.spatial.position)}."
            f"{blocked}",
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
        direction = target.spatial.position - self.player.spatial.position
        if direction.magnitude > 0:
            self.player.spatial.facing = direction.normalized()
        before = self.player.spatial.position.distance_to(target.spatial.position)
        movement = move_actor_with_collisions(
            self.player,
            target.spatial.position,
            seconds,
            self.entities,
            doors=self.doors.values(),
            exertion=0.45,
        )
        self._advance_clock(seconds, already_advanced={self.player_id})
        after = self.player.spatial.position.distance_to(target.spatial.position)
        blocked = (
            ""
            if movement.hit is None
            else f" Blocked by {movement.hit.entity_id}."
        )
        return (
            f"You advance {movement.moved_distance_m:.2f} m "
            f"toward {target.spatial.name}; "
            f"distance {before:.2f} -> {after:.2f} m.{blocked}",
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

    def _take(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 1, "take <item>")
        entity = self._resolve_entity(args[0])
        try:
            item = self.world_items[entity.entity_id]
        except KeyError as exc:
            raise ValueError(f"{entity.name} cannot be taken") from exc

        distance = self.player.spatial.position.distance_to(entity.position)
        if distance > 1.5:
            raise ValueError(
                f"{entity.name} is too far away to take ({distance:.2f} m)"
            )
        observation = observe(
            self.player.spatial,
            entity,
            self.player.vision,
            obstacles=self.entities,
        )
        if observation is None:
            raise ValueError(f"you cannot currently perceive {entity.name}")

        self.player.loadout.carried_loose.append(item)
        self.scenery = tuple(
            candidate
            for candidate in self.scenery
            if candidate.entity_id != entity.entity_id
        )
        del self.world_items[entity.entity_id]
        self._advance_clock(0.5)
        return (
            f"You take {item.name}. Carried mass: "
            f"{self.player.loadout.carried_mass_kg:.2f} kg.",
            False,
        )

    def _drop(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 1, "drop <item>")
        lowered = args[0].lower()
        matches = [
            item
            for item in self.player.loadout.carried_loose
            if item.item_id.lower() == lowered or item.name.lower() == lowered
        ]
        if len(matches) != 1:
            if not matches:
                raise ValueError(f"you are not carrying: {args[0]}")
            raise ValueError(f"ambiguous carried item: {args[0]}")

        item = matches[0]
        self.player.loadout.carried_loose.remove(item)
        position = (
            self.player.spatial.position
            + self.player.spatial.facing.normalized().scale(0.6)
        )
        volume_m3 = max(0.000125, item.volume_l / 1000.0)
        side = volume_m3 ** (1.0 / 3.0)
        entity = SpatialEntity(
            item.item_id,
            item.name,
            position,
            bounds=Bounds(side / 2.0, side / 2.0, side),
            mass_kg=item.mass_kg,
            tags=frozenset({"item"}),
        )
        self.scenery = (*self.scenery, entity)
        self.world_items[item.item_id] = item
        self._advance_clock(0.5)
        return (
            f"You drop {item.name}. Carried mass: "
            f"{self.player.loadout.carried_mass_kg:.2f} kg.",
            False,
        )

    def _inventory(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 0, "inventory")
        items = self.player.loadout.carried_loose
        if not items:
            return (
                f"You are carrying nothing. Load ratio "
                f"{self.player.loadout.load_ratio:.2f}.",
                False,
            )
        lines = ", ".join(
            f"{item.name} ({item.mass_kg:.2f} kg)"
            for item in sorted(items, key=lambda value: value.item_id)
        )
        return (
            f"Carrying: {lines}. Total "
            f"{self.player.loadout.carried_mass_kg:.2f} kg; "
            f"load ratio {self.player.loadout.load_ratio:.2f}.",
            False,
        )

    def _talk(self, args: tuple[str, ...]) -> tuple[str, bool]:
        if not 1 <= len(args) <= 2:
            raise ValueError("usage: talk <target> [topic]")
        target_id = self._resolve_actor(args[0])
        if target_id == self.player_id:
            raise ValueError("cannot talk to yourself")
        target = self.actors[target_id]

        distance = self.player.spatial.position.distance_to(target.spatial.position)
        if distance > 3.0:
            raise ValueError(
                f"{target.spatial.name} is too far away to talk ({distance:.2f} m)"
            )
        observation = observe(
            self.player.spatial,
            target.spatial,
            self.player.vision,
            obstacles=self.entities,
        )
        if observation is None:
            raise ValueError(f"you cannot currently perceive {target.spatial.name}")

        topic = args[1] if len(args) == 2 else None
        now = self.elapsed_seconds / 3600.0
        result = converse(
            speaker_id=target_id,
            speaker_name=target.spatial.name,
            speaker=target.mind,
            listener_id=self.player_id,
            listener=self.player.mind,
            now=now,
            topic=topic,
        )
        self._advance_clock(1.0)
        return result.text, False

    def _open(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 1, "open <door>")
        door = self._resolve_door(args[0])
        self._require_door_reach(door)
        door.open_door()
        self._advance_clock(0.5)
        return f"You open {door.name}.", False

    def _close(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 1, "close <door>")
        door = self._resolve_door(args[0])
        self._require_door_reach(door)
        door.close_door()
        self._advance_clock(0.5)
        return f"You close {door.name}.", False

    def _require_door_reach(self, door: Door) -> None:
        distance = self.player.spatial.position.distance_to(door.position)
        if distance > 1.5:
            raise ValueError(
                f"{door.name} is too far away to manipulate ({distance:.2f} m)"
            )
        observation = observe(
            self.player.spatial,
            door.spatial,
            self.player.vision,
            obstacles=self.entities,
        )
        if observation is None:
            raise ValueError(f"you cannot currently perceive {door.name}")

    def _resolve_door(self, query: str) -> Door:
        lowered = query.lower()
        matches = [
            door
            for door in self.doors.values()
            if door.door_id.lower() == lowered or door.name.lower() == lowered
        ]
        if len(matches) != 1:
            if not matches:
                raise ValueError(f"unknown door: {query}")
            raise ValueError(f"ambiguous door: {query}")
        return matches[0]

    def _shoot(self, args: tuple[str, ...]) -> tuple[str, bool]:
        if not 1 <= len(args) <= 2:
            raise ValueError("usage: shoot <target> [body_part]")
        target_id = self._resolve_actor(args[0])
        if target_id == self.player_id:
            raise ValueError("cannot shoot yourself")
        if self.player_id not in self.ranged_weapons:
            raise ValueError("you do not have a ranged weapon")
        if target_id not in self.combatants:
            raise ValueError("target does not have a detailed combat profile")

        part = BodyPart.TORSO
        if len(args) == 2:
            try:
                part = BodyPart(args[1].lower())
            except ValueError as exc:
                valid = ", ".join(item.value for item in BodyPart)
                raise ValueError(f"body_part must be one of: {valid}") from exc

        target = self.actors[target_id]
        origin = self.player.spatial.position + Vec3(
            0.0,
            0.0,
            self.player.spatial.bounds.height * 0.85,
        )
        aim_point = aim_point_for_body_part(target.spatial, part)
        direction = aim_point - origin
        if direction.magnitude <= 0:
            raise ValueError("target is too close for a valid shot")
        self.player.spatial.facing = Vec3(
            direction.x,
            direction.y,
            0.0,
        ).normalized()

        weapon = self.ranged_weapons[self.player_id]
        projectile = weapon.fire(
            owner_id=self.player_id,
            origin=origin,
            direction=direction,
        )
        self._emit_sound(
            category="weapon",
            description=f"{weapon.name} firing",
            position=origin,
            loudness_db_at_1m=65.0,
            source_id=self.player_id,
        )
        simulator = ProjectileSimulator()
        simulator.launch(projectile)

        projectile_targets = [
            actor.spatial
            for actor_id, actor in self.actors.items()
            if actor_id != self.player_id
        ]
        projectile_targets.extend(self.scenery)
        projectile_targets.extend(
            door.spatial
            for door in self.doors.values()
            if not door.is_open and not door.destroyed
        )
        steps = simulator.simulate_until_inactive(
            projectile.projectile_id,
            projectile_targets,
            dt_s=0.01,
        )
        hit = next(
            (step.hit for step in steps if step.hit is not None),
            None,
        )
        flight_time = sum(step.elapsed_s for step in steps)
        self._advance_clock(max(1.0, flight_time))

        if hit is None:
            return (
                f"You fire {weapon.name}, but the projectile hits nothing. "
                f"Ammunition remaining: {weapon.ammunition}.",
                False,
            )

        self._emit_sound(
            category="impact",
            description="projectile impact",
            position=hit.position,
            loudness_db_at_1m=58.0,
            source_id=self.player_id,
        )

        if hit.target_id in self.combatants:
            combatant = self.combatants[hit.target_id]
            impact_part = part if hit.target_id == target_id else BodyPart.TORSO
            impact = resolve_projectile_impact(
                hit,
                combatant.actor,
                combatant.world_actor.physiology,
                selected_part=impact_part,
                penetration_factor=weapon.penetration_factor,
            )
            prefix = (
                ""
                if hit.target_id == target_id
                else f"The shot is intercepted by {combatant.actor.name}. "
            )
            return (
                f"{prefix}{impact.text} Ammunition remaining: "
                f"{weapon.ammunition}.",
                False,
            )

        if hit.target_id in self.doors:
            door = self.doors[hit.target_id]
            door_damage = max(0.0, hit.kinetic_energy_j ** 0.5)
            dealt = door.apply_damage(door_damage)
            return (
                f"The projectile strikes {door.name} for {dealt:.1f} structural "
                f"damage. Ammunition remaining: {weapon.ammunition}.",
                False,
            )

        struck = self._resolve_entity(hit.target_id)
        return (
            f"The projectile strikes {struck.name} at "
            f"{hit.kinetic_energy_j:.1f} J. Ammunition remaining: "
            f"{weapon.ammunition}.",
            False,
        )

    def _emit_sound(
        self,
        *,
        category: str,
        description: str,
        position: Vec3,
        loudness_db_at_1m: float,
        source_id: str | None = None,
    ) -> tuple[HeardSound, ...]:
        created_hour = (
            self.kernel.world.time_hours
            if self.kernel is not None
            else self.elapsed_seconds / 3600.0
        )
        event = SoundEvent(
            sound_id=f"sound-{len(self.sound_events)}",
            position=position,
            loudness_db_at_1m=loudness_db_at_1m,
            category=category,
            description=description,
            created_hour=created_hour,
            source_id=source_id,
        )
        self.sound_events.append(event)

        listeners = [
            (
                actor.spatial,
                self.hearing_profiles.get(actor_id, HearingProfile()),
            )
            for actor_id, actor in self.actors.items()
            if actor_id != source_id
        ]
        heard = propagate_sound(
            event,
            listeners,
            obstacles=self.entities,
        )
        for perception in heard:
            actor = self.actors.get(perception.listener_id)
            if actor is None:
                continue
            confidence = max(0.05, min(1.0, 0.2 + 0.8 * perception.clarity))
            actor.mind.remember(
                Memory(
                    subject=category,
                    proposition=f"heard {description}",
                    importance=0.45,
                    emotional_intensity=0.25,
                    confidence=confidence,
                    accuracy=perception.clarity,
                    source="hearing",
                    created_at=created_hour,
                    tags=frozenset({"sound", category}),
                )
            )
        return heard

    def _help(self, args: tuple[str, ...]) -> tuple[str, bool]:
        self._expect_count(args, 0, "help")
        return (
            "Commands: look, map, move <direction> [m], advance <target> [s], "
            "attack <target> [body_part], inspect <target>, wait [s], "
            "status, take <item>, drop <item>, inventory, "
            "talk <target> [topic], open <door>, close <door>, "
            "shoot <target> [body_part], help, quit.",
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

        for actor_id, actor in self.actors.items():
            if actor_id in skipped or actor_id in ambient_ids:
                continue
            actor.physiology.tick(seconds / 60.0, exertion=0.05)

        if self.ambient is not None:
            self.ambient.advance(
                start_world_hour=start_world_hour,
                seconds=seconds,
                skip_actor_ids=frozenset(skipped),
            )

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

    villager_mind = Mind(
        beliefs={
            "bridge": Belief(
                "east bridge",
                "the east bridge is damaged and unsafe for carts",
                0.85,
                "direct_observation",
                0.0,
            ),
            "wolves": Belief(
                "wolves",
                "wolves have been coming closer to the village at dusk",
                0.75,
                "neighbors",
                0.0,
            ),
        }
    )
    villager_mind.relationship(player_actor.actor_id).trust = 20.0
    villager_mind.relationship(player_actor.actor_id).respect = 10.0
    villager_world = WorldActor(
        SpatialEntity(
            "mira",
            "Mira",
            Vec3(2.0, 2.0, 0.0),
            facing=Vec3(-1.0, -1.0, 0.0),
            tags=frozenset({"npc"}),
        ),
        villager_mind,
        Physiology(62.0),
        Loadout(62.0),
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
    rope = PhysicalItem(
        "rope",
        "Rope",
        mass_kg=1.8,
        volume_l=3.0,
        length_m=8.0,
        accessibility_s=1.0,
    )
    scenery = (
        SpatialEntity(
            "barrel",
            "Barrel",
            Vec3(3.0, 3.0, 0.0),
            bounds=Bounds(0.4, 0.4, 0.9),
            mass_kg=35.0,
            tags=frozenset({"cover", "occluder", "solid"}),
        ),
        SpatialEntity(
            "rope",
            "Rope",
            Vec3(0.5, 0.8, 0.0),
            bounds=Bounds(0.15, 0.15, 0.1),
            mass_kg=rope.mass_kg,
            tags=frozenset({"item"}),
        ),
    )
    mira_schedule = RoutineSchedule(
        (
            RoutineBlock(22.0, 6.0, "sleep", "home"),
            RoutineBlock(6.0, 8.0, "breakfast", "home"),
            RoutineBlock(8.0, 17.0, "work", "market"),
            RoutineBlock(17.0, 22.0, "home", "home"),
        )
    )
    mira_ambient = AmbientNPCSimulation(
        agents={
            "mira": AmbientAgent(
                actor=villager_world,
                controller=NPCController(mira_schedule),
                locations={
                    "home": Vec3(2.0, 2.0, 0.0),
                    "market": Vec3(5.0, 2.0, 0.0),
                },
            )
        }
    )

    hunting_bow = RangedWeapon(
        name="hunting bow",
        projectile_spec=ProjectileSpec(
            "arrow",
            mass_kg=0.03,
            radius_m=0.01,
            drag_coefficient=0.002,
            gravity_mps2=9.81,
            max_lifetime_s=5.0,
        ),
        muzzle_speed_mps=60.0,
        ammunition=12,
        penetration_factor=1.0,
    )

    gate = Door(
        "gate",
        "Wooden gate",
        Vec3(3.0, 0.0, 0.0),
        width_m=1.1,
        height_m=2.1,
        axis=PassageAxis.X,
    )

    kernel = SimulationKernel(WorldState())
    return TextWorldSession(
        player_id=player_actor.actor_id,
        actors={
            player_actor.actor_id: player_world,
            wolf_actor.actor_id: wolf_world,
            "mira": villager_world,
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
        world_items={"rope": rope},
        doors={"gate": gate},
        ranged_weapons={player_actor.actor_id: hunting_bow},
        kernel=kernel,
        ambient=mira_ambient,
        seed=seed,
    )
