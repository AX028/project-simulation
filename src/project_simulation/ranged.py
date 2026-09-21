"""Resolve projectile impacts against anatomical combat actors."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from .models import Actor, Armor, BodyPart
from .physiology import Injury, InjuryType, Physiology
from .projectiles import (
    Projectile,
    ProjectileHit,
    ProjectileSpec,
    launch_velocity,
)
from .spatial import SpatialEntity, Vec3


@dataclass(slots=True)
class RangedWeapon:
    name: str
    projectile_spec: ProjectileSpec
    muzzle_speed_mps: float
    ammunition: int
    penetration_factor: float = 1.0
    shots_fired: int = 0

    def __post_init__(self) -> None:
        if self.muzzle_speed_mps <= 0:
            raise ValueError("muzzle speed must be positive")
        if self.ammunition < 0:
            raise ValueError("ammunition may not be negative")
        if self.penetration_factor <= 0:
            raise ValueError("penetration_factor must be positive")

    def fire(
        self,
        *,
        owner_id: str,
        origin: Vec3,
        direction: Vec3,
    ) -> Projectile:
        if self.ammunition <= 0:
            raise ValueError(f"{self.name} is out of ammunition")
        projectile_id = f"{owner_id}:{self.name}:{self.shots_fired}"
        projectile = Projectile(
            projectile_id=projectile_id,
            spec=self.projectile_spec,
            position=origin,
            velocity=launch_velocity(direction, self.muzzle_speed_mps),
            owner_id=owner_id,
        )
        self.ammunition -= 1
        self.shots_fired += 1
        return projectile


@dataclass(frozen=True, slots=True)
class RangedImpactResult:
    target_id: str
    body_part: BodyPart
    damage: int
    kinetic_energy_j: float
    injury: Injury
    text: str


def aim_point_for_body_part(
    entity: SpatialEntity,
    part: BodyPart,
) -> Vec3:
    """Return a deterministic approximate anatomical aim point."""
    height_fraction = {
        BodyPart.HEAD: 0.90,
        BodyPart.TORSO: 0.60,
        BodyPart.LEFT_ARM: 0.62,
        BodyPart.RIGHT_ARM: 0.62,
        BodyPart.LEFT_LEG: 0.25,
        BodyPart.RIGHT_LEG: 0.25,
    }[part]
    side_sign = {
        BodyPart.LEFT_ARM: -1.0,
        BodyPart.RIGHT_ARM: 1.0,
        BodyPart.LEFT_LEG: -0.45,
        BodyPart.RIGHT_LEG: 0.45,
    }.get(part, 0.0)
    forward = entity.facing.normalized()
    side = Vec3(-forward.y, forward.x, 0.0)
    lateral = side.scale(entity.bounds.half_width * side_sign)
    return (
        entity.position
        + lateral
        + Vec3(0.0, 0.0, entity.bounds.height * height_fraction)
    )


def resolve_projectile_impact(
    hit: ProjectileHit,
    target: Actor,
    physiology: Physiology,
    *,
    selected_part: BodyPart | None = None,
    penetration_factor: float = 1.0,
) -> RangedImpactResult:
    if penetration_factor <= 0:
        raise ValueError("penetration_factor must be positive")

    part = selected_part or BodyPart.TORSO
    body = target.body_parts[part]
    protection = target.stats.armor
    armor_item = target.equipment.get(body.armor_slot)
    if isinstance(armor_item, Armor) and armor_item.durability > 0:
        protection += armor_item.protection
        armor_item.durability = max(0, armor_item.durability - 1)

    raw = sqrt(max(0.0, hit.kinetic_energy_j)) * penetration_factor
    damage = max(
        1,
        round(raw * body.damage_multiplier - protection),
    )
    body.current_hp = max(0, body.current_hp - damage)

    severity = min(1.0, damage / max(1.0, body.max_hp))
    injury = Injury(
        location=part.value,
        injury_type=InjuryType.PUNCTURE,
        severity=severity,
        bleeding_ml_per_min=severity * 18.0,
        pain=severity * 75.0,
        mobility_penalty=(
            severity * 0.7
            if part in {BodyPart.LEFT_LEG, BodyPart.RIGHT_LEG}
            else severity * 0.08
        ),
        manipulation_penalty=(
            severity * 0.75
            if part in {BodyPart.LEFT_ARM, BodyPart.RIGHT_ARM}
            else severity * 0.04
        ),
        infection_risk=severity * 0.1,
    )
    physiology.add_injury(injury)

    return RangedImpactResult(
        target.actor_id,
        part,
        damage,
        hit.kinetic_energy_j,
        injury,
        (
            f"The projectile strikes {target.name}'s {part.value} "
            f"for {damage} damage."
        ),
    )
