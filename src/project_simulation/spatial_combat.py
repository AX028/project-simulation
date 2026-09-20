"""Spatial combat resolution linking 3D reach, actor stats, and persistent injuries."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum
from math import sqrt

from .models import Actor, Armor, BodyPart
from .physiology import Injury, InjuryType
from .worldstate import WorldActor


class StrikeType(StrEnum):
    CUT = "cut"
    THRUST = "thrust"
    BLUNT = "blunt"


@dataclass(frozen=True, slots=True)
class WeaponPhysics:
    name: str
    mass_kg: float
    reach_m: float
    handling: float = 1.0
    strike_speed_mps: float = 12.0
    edge_factor: float = 1.0
    strike_type: StrikeType = StrikeType.CUT


@dataclass(slots=True)
class SpatialCombatant:
    actor: Actor
    world_actor: WorldActor
    weapon: WeaponPhysics
    arm_reach_m: float = 0.65

    def __post_init__(self) -> None:
        if self.actor.actor_id != self.world_actor.actor_id:
            raise ValueError("combat actor IDs must match")

    @property
    def effective_reach_m(self) -> float:
        return self.arm_reach_m + self.weapon.reach_m


@dataclass(frozen=True, slots=True)
class SpatialAttackResult:
    hit: bool
    in_reach: bool
    distance_m: float
    hit_chance: float
    body_part: BodyPart | None
    damage: int
    impact_energy_j: float
    injury: Injury | None
    text: str


class SpatialCombatResolver:
    """Resolve one physical attack using geometry before combat statistics."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def resolve_attack(
        self,
        attacker: SpatialCombatant,
        target: SpatialCombatant,
        *,
        selected_part: BodyPart | None = None,
    ) -> SpatialAttackResult:
        distance = attacker.world_actor.spatial.position.distance_to(
            target.world_actor.spatial.position
        )
        reach = attacker.effective_reach_m
        if distance > reach:
            return SpatialAttackResult(
                hit=False,
                in_reach=False,
                distance_m=distance,
                hit_chance=0.0,
                body_part=None,
                damage=0,
                impact_energy_j=0.0,
                injury=None,
                text=(
                    f"{attacker.actor.name} cannot reach {target.actor.name}: "
                    f"{distance:.2f} m away, {reach:.2f} m effective reach."
                ),
            )

        attack_performance = attacker.world_actor.physiology.performance_modifier
        defense_performance = target.world_actor.physiology.performance_modifier
        handling = max(0.1, min(1.5, attacker.weapon.handling))
        encumbrance = max(1.0, attacker.world_actor.loadout.fatigue_multiplier)

        attack_quality = attacker.actor.stats.accuracy * attack_performance * handling
        attack_quality /= sqrt(encumbrance)
        defense = target.actor.stats.evasion * defense_performance
        distance_factor = max(0.55, 1.0 - 0.25 * (distance / max(0.1, reach)))
        hit_chance = max(0.05, min(0.97, attack_quality * distance_factor - defense))

        if self.rng.random() > hit_chance:
            return SpatialAttackResult(
                False,
                True,
                distance,
                hit_chance,
                None,
                0,
                0.0,
                None,
                f"{attacker.actor.name}'s {attacker.weapon.name} misses.",
            )

        part = selected_part or self._weighted_part(target.actor)
        body = target.actor.body_parts[part]
        speed = attacker.weapon.strike_speed_mps * attack_performance / sqrt(encumbrance)
        impact_energy = 0.5 * attacker.weapon.mass_kg * speed * speed
        strike_factor = {
            StrikeType.CUT: 1.0,
            StrikeType.THRUST: 1.12,
            StrikeType.BLUNT: 0.82,
        }[attacker.weapon.strike_type]

        raw_damage = (
            sqrt(max(0.0, impact_energy))
            * attacker.weapon.edge_factor
            * strike_factor
        )
        raw_damage += attacker.actor.stats.strength * 0.08
        protection = target.actor.stats.armor + self._armor_protection(target.actor, part)
        damage = max(1, round(raw_damage * body.damage_multiplier - protection))
        body.current_hp = max(0, body.current_hp - damage)

        severity = min(1.0, damage / max(1.0, body.max_hp))
        injury = self._injury_for(part, severity, attacker.weapon.strike_type)
        target.world_actor.physiology.add_injury(injury)

        return SpatialAttackResult(
            True,
            True,
            distance,
            hit_chance,
            part,
            damage,
            impact_energy,
            injury,
            (
                f"{attacker.actor.name}'s {attacker.weapon.name} strikes "
                f"{target.actor.name}'s {part.value} for {damage} damage."
            ),
        )

    def _weighted_part(self, actor: Actor) -> BodyPart:
        candidates = [part.part for part in actor.body_parts.values() if part.current_hp > 0]
        weights = [2.5 if part is BodyPart.TORSO else 1.0 for part in candidates]
        return self.rng.choices(candidates, weights=weights, k=1)[0]

    @staticmethod
    def _armor_protection(actor: Actor, part: BodyPart) -> int:
        body = actor.body_parts[part]
        armor = actor.equipment.get(body.armor_slot)
        if isinstance(armor, Armor) and armor.durability > 0:
            return armor.protection
        return 0

    @staticmethod
    def _injury_for(part: BodyPart, severity: float, strike_type: StrikeType) -> Injury:
        injury_type = {
            StrikeType.CUT: InjuryType.LACERATION,
            StrikeType.THRUST: InjuryType.PUNCTURE,
            StrikeType.BLUNT: InjuryType.BLUNT,
        }[strike_type]
        bleeding_factor = {
            InjuryType.LACERATION: 14.0,
            InjuryType.PUNCTURE: 18.0,
            InjuryType.BLUNT: 1.5,
        }[injury_type]
        mobility = severity * (0.7 if part in {BodyPart.LEFT_LEG, BodyPart.RIGHT_LEG} else 0.1)
        manipulation = severity * (
            0.75 if part in {BodyPart.LEFT_ARM, BodyPart.RIGHT_ARM} else 0.05
        )
        return Injury(
            location=part.value,
            injury_type=injury_type,
            severity=severity,
            bleeding_ml_per_min=severity * bleeding_factor,
            pain=severity * 80.0,
            mobility_penalty=mobility,
            manipulation_penalty=manipulation,
            infection_risk=severity * 0.08,
        )

    @property
    def _current_strike_type(self) -> StrikeType:
        # Set temporarily by resolve_attack through the active weapon.
        return self.__dict__.get("_strike_type", StrikeType.CUT)

    @_current_strike_type.setter
    def _current_strike_type(self, value: StrikeType) -> None:
        self.__dict__["_strike_type"] = value
