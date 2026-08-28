"""Typed domain models for the simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class SimulationError(Exception):
    """Base exception for expected simulation errors."""


class ContentNotFoundError(SimulationError):
    """Raised when a requested class, enemy, or action is unknown."""


class IllegalActionError(SimulationError):
    """Raised when an actor attempts an action that is not currently legal."""


class IncompatibleSaveError(SimulationError):
    """Raised when loading an unsupported or malformed save."""


class DamageType(StrEnum):
    PHYSICAL = "physical"
    FIRE = "fire"
    FROST = "frost"
    HOLY = "holy"
    ARCANE = "arcane"
    POISON = "poison"


class BodyPart(StrEnum):
    HEAD = "head"
    TORSO = "torso"
    LEFT_ARM = "left_arm"
    RIGHT_ARM = "right_arm"
    LEFT_LEG = "left_leg"
    RIGHT_LEG = "right_leg"


class Rarity(StrEnum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


class CombatMode(StrEnum):
    ENGAGE = "engage"
    DEFEND = "defend"
    RECOVER = "recover"
    FLEE = "flee"
    DESPERATE = "desperate"


class TargetType(StrEnum):
    ENEMY = "enemy"
    SELF = "self"


@dataclass(slots=True)
class Stats:
    strength: int = 10
    agility: int = 10
    intellect: int = 10
    vitality: int = 10
    armor: int = 0
    accuracy: float = 0.8
    evasion: float = 0.05
    crit_chance: float = 0.05


@dataclass(slots=True)
class ResourcePool:
    current: int
    maximum: int

    @property
    def ratio(self) -> float:
        return self.current / self.maximum if self.maximum else 0.0

    def spend(self, amount: int) -> None:
        if amount > self.current:
            raise IllegalActionError("not enough resources")
        self.current -= amount

    def restore(self, amount: int) -> int:
        before = self.current
        self.current = min(self.maximum, self.current + amount)
        return self.current - before


@dataclass(slots=True)
class BodyPartState:
    part: BodyPart
    current_hp: int
    max_hp: int
    damage_multiplier: float
    armor_slot: str

    @property
    def ratio(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp else 0.0


@dataclass(slots=True)
class StatusEffect:
    effect_id: str
    duration: int
    potency: float = 1.0
    source_id: str | None = None


@dataclass(slots=True)
class Item:
    item_id: str
    name: str
    rarity: Rarity = Rarity.COMMON
    durability: int = 100
    modifiers: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class Weapon(Item):
    damage: int = 4
    damage_type: DamageType = DamageType.PHYSICAL
    accuracy_bonus: float = 0.0


@dataclass(slots=True)
class Armor(Item):
    slot: str = "torso"
    protection: int = 1
    material: str = "cloth"


@dataclass(slots=True, frozen=True)
class ActionSpec:
    action_id: str
    name: str
    damage: int = 0
    damage_type: DamageType = DamageType.PHYSICAL
    accuracy: float = 1.0
    resource: str | None = None
    cost: int = 0
    cooldown: int = 0
    target: TargetType = TargetType.ENEMY
    status_id: str | None = None
    status_duration: int = 0
    status_potency: float = 1.0
    heal: int = 0
    tags: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class Action:
    actor_id: str
    action_id: str
    target_id: str
    body_part: BodyPart | None = None


@dataclass(slots=True)
class Actor:
    actor_id: str
    name: str
    level: int
    stats: Stats
    body_parts: dict[str, BodyPartState]
    resources: dict[str, ResourcePool]
    abilities: tuple[ActionSpec, ...]
    statuses: list[StatusEffect] = field(default_factory=list)
    cooldowns: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, Item] = field(default_factory=dict)
    inventory: list[Item] = field(default_factory=list)
    archetype: str = "balanced"

    @property
    def alive(self) -> bool:
        return (
            self.body_parts[BodyPart.HEAD].current_hp > 0
            and self.body_parts[BodyPart.TORSO].current_hp > 0
        )

    @property
    def hp_ratio(self) -> float:
        current = sum(part.current_hp for part in self.body_parts.values())
        maximum = sum(part.max_hp for part in self.body_parts.values())
        return current / maximum if maximum else 0.0

    def get_action(self, action_id: str) -> ActionSpec:
        if action_id == "basic_attack":
            weapon = self.equipment.get("weapon")
            damage = weapon.damage if isinstance(weapon, Weapon) else 4
            damage_type = weapon.damage_type if isinstance(weapon, Weapon) else DamageType.PHYSICAL
            accuracy = 1.0 + (weapon.accuracy_bonus if isinstance(weapon, Weapon) else 0.0)
            return ActionSpec("basic_attack", "Basic attack", damage, damage_type, accuracy)
        if action_id == "defend":
            return ActionSpec("defend", "Defend", target=TargetType.SELF, tags=("defend",))
        if action_id == "recover":
            return ActionSpec("recover", "Recover", target=TargetType.SELF, tags=("recover",))
        if action_id == "flee":
            return ActionSpec("flee", "Flee", tags=("flee",))
        for ability in self.abilities:
            if ability.action_id == action_id:
                return ability
        raise ContentNotFoundError(f"unknown action: {action_id}")


@dataclass(slots=True)
class PlayerCharacter(Actor):
    class_id: str = "adventurer"
    experience: int = 0


@dataclass(slots=True)
class Enemy(Actor):
    enemy_id: str = "enemy"
    experience_reward: int = 10
    tier: str = "early"


@dataclass(slots=True)
class CombatSnapshot:
    actor: Actor
    target: Actor
    round_number: int
    event_memory: dict[str, float]


@dataclass(slots=True)
class TurnResult:
    round_number: int
    events: list[str]
    winner_id: str | None = None
    fled_id: str | None = None


@dataclass(slots=True)
class EncounterState:
    actors: dict[str, Actor]
    round_number: int = 0
    event_memory: dict[str, dict[str, float]] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    winner_id: str | None = None


@dataclass(slots=True)
class EncounterResult:
    winner_id: str | None
    rounds: int
    events: list[str]
    state: EncounterState


@dataclass(slots=True, frozen=True)
class WorldConfig:
    width: int = 64
    height: int = 64
    chunk_size: int = 16


@dataclass(slots=True)
class WorldMap:
    seed: int
    config: WorldConfig
    terrain: Any
    biome: Any
    temperature: Any
    precipitation: Any


@dataclass(slots=True)
class GameState:
    seed: int
    turn: int
    player: PlayerCharacter
    world_path: str | None = None
    decision_memory: dict[str, dict[str, float]] = field(default_factory=dict)
    rng_state: list[Any] | None = None
    schema_version: int = 1


class DecisionPolicy(Protocol):
    def choose_action(
        self, snapshot: CombatSnapshot, legal_actions: list[ActionSpec], rng: Any
    ) -> ActionSpec: ...
