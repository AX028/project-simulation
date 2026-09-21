import pytest

from project_simulation import (
    BodyPart,
    Physiology,
    ProjectileHit,
    ProjectileSpec,
    RangedWeapon,
    SpatialEntity,
    Vec3,
    aim_point_for_body_part,
    create_enemy,
    resolve_projectile_impact,
)
from project_simulation.models import Armor


def _hit(energy: float = 100.0) -> ProjectileHit:
    return ProjectileHit(
        "arrow",
        "target",
        Vec3(0.0, 1.0, 1.0),
        0.5,
        50.0,
        energy,
    )


def test_ranged_weapon_fire_consumes_ammunition() -> None:
    weapon = RangedWeapon(
        "bow",
        ProjectileSpec("arrow", 0.03, 0.01),
        muzzle_speed_mps=60.0,
        ammunition=2,
    )
    projectile = weapon.fire(
        owner_id="archer",
        origin=Vec3(0.0, 0.0, 1.5),
        direction=Vec3(0.0, 1.0, 0.0),
    )
    assert weapon.ammunition == 1
    assert weapon.shots_fired == 1
    assert projectile.owner_id == "archer"
    assert projectile.speed_mps == pytest.approx(60.0)


def test_projectile_ids_increment_deterministically() -> None:
    weapon = RangedWeapon(
        "bow",
        ProjectileSpec("arrow", 0.03, 0.01),
        60.0,
        ammunition=3,
    )
    ids = [
        weapon.fire(
            owner_id="archer",
            origin=Vec3(0.0, 0.0, 0.0),
            direction=Vec3(0.0, 1.0, 0.0),
        ).projectile_id
        for _ in range(3)
    ]
    assert ids == [
        "archer:bow:0",
        "archer:bow:1",
        "archer:bow:2",
    ]


def test_empty_ranged_weapon_cannot_fire() -> None:
    weapon = RangedWeapon(
        "bow",
        ProjectileSpec("arrow", 0.03, 0.01),
        60.0,
        ammunition=0,
    )
    with pytest.raises(ValueError, match="out of ammunition"):
        weapon.fire(
            owner_id="archer",
            origin=Vec3(0.0, 0.0, 0.0),
            direction=Vec3(0.0, 1.0, 0.0),
        )


def test_invalid_ranged_weapon_parameters_are_rejected() -> None:
    spec = ProjectileSpec("arrow", 0.03, 0.01)
    with pytest.raises(ValueError, match="muzzle"):
        RangedWeapon("bow", spec, 0.0, 1)
    with pytest.raises(ValueError, match="ammunition"):
        RangedWeapon("bow", spec, 60.0, -1)
    with pytest.raises(ValueError, match="penetration"):
        RangedWeapon("bow", spec, 60.0, 1, penetration_factor=0.0)


def test_aim_point_uses_requested_body_region_height() -> None:
    entity = SpatialEntity(
        "target",
        "Target",
        Vec3(0.0, 10.0, 0.0),
        facing=Vec3(0.0, -1.0, 0.0),
    )
    head = aim_point_for_body_part(entity, BodyPart.HEAD)
    leg = aim_point_for_body_part(entity, BodyPart.LEFT_LEG)
    assert head.z > leg.z


def test_left_and_right_limb_aim_points_are_separated() -> None:
    entity = SpatialEntity(
        "target",
        "Target",
        Vec3(0.0, 10.0, 0.0),
        facing=Vec3(0.0, -1.0, 0.0),
    )
    left = aim_point_for_body_part(entity, BodyPart.LEFT_ARM)
    right = aim_point_for_body_part(entity, BodyPart.RIGHT_ARM)
    assert left.x != right.x


def test_projectile_impact_reduces_body_part_hp_and_adds_injury() -> None:
    target = create_enemy("goblin", 1, 3)
    physiology = Physiology(50.0)
    before = target.body_parts[BodyPart.LEFT_LEG].current_hp
    result = resolve_projectile_impact(
        _hit(144.0),
        target,
        physiology,
        selected_part=BodyPart.LEFT_LEG,
    )
    assert result.damage > 0
    assert target.body_parts[BodyPart.LEFT_LEG].current_hp < before
    assert result.injury in physiology.injuries
    assert result.injury.mobility_penalty > 0


def test_arm_projectile_injury_penalizes_manipulation() -> None:
    target = create_enemy("goblin", 1, 4)
    physiology = Physiology(50.0)
    result = resolve_projectile_impact(
        _hit(144.0),
        target,
        physiology,
        selected_part=BodyPart.RIGHT_ARM,
    )
    assert result.injury.manipulation_penalty > 0


def test_armor_reduces_damage_and_loses_durability() -> None:
    plain = create_enemy("goblin", 1, 5)
    armored = create_enemy("goblin", 1, 5)
    armor = Armor(
        "plate",
        "Plate",
        slot="torso",
        protection=10,
        durability=20,
    )
    armored.equipment["torso"] = armor
    plain_body = Physiology(50.0)
    armored_body = Physiology(50.0)

    plain_result = resolve_projectile_impact(
        _hit(225.0),
        plain,
        plain_body,
        selected_part=BodyPart.TORSO,
    )
    armored_result = resolve_projectile_impact(
        _hit(225.0),
        armored,
        armored_body,
        selected_part=BodyPart.TORSO,
    )

    assert armored_result.damage <= plain_result.damage
    assert armor.durability == 19


def test_penetration_factor_increases_projectile_damage() -> None:
    low = create_enemy("goblin", 1, 8)
    high = create_enemy("goblin", 1, 8)
    low_result = resolve_projectile_impact(
        _hit(100.0),
        low,
        Physiology(50.0),
        penetration_factor=0.5,
    )
    high_result = resolve_projectile_impact(
        _hit(100.0),
        high,
        Physiology(50.0),
        penetration_factor=2.0,
    )
    assert high_result.damage > low_result.damage


def test_invalid_penetration_factor_is_rejected() -> None:
    target = create_enemy("goblin", 1, 9)
    with pytest.raises(ValueError, match="positive"):
        resolve_projectile_impact(
            _hit(),
            target,
            Physiology(50.0),
            penetration_factor=0.0,
        )


def test_hundred_impacts_preserve_body_hp_bounds() -> None:
    target = create_enemy("goblin", 1, 10)
    physiology = Physiology(50.0)
    for _ in range(100):
        resolve_projectile_impact(
            _hit(100.0),
            target,
            physiology,
            selected_part=BodyPart.TORSO,
        )
    torso = target.body_parts[BodyPart.TORSO]
    assert 0 <= torso.current_hp <= torso.max_hp
