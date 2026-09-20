import random

from project_simulation import (
    BodyPart,
    Loadout,
    Mind,
    PhysicalItem,
    Physiology,
    SpatialCombatant,
    SpatialCombatResolver,
    SpatialEntity,
    StrikeType,
    Vec3,
    WeaponPhysics,
    WorldActor,
    create_character,
    create_enemy,
)
from project_simulation.models import Armor


def _world_actor(actor_id: str, name: str, position: Vec3, *, loaded: bool = False) -> WorldActor:
    items = (
        [PhysicalItem("load", "Load", 25.0, 30.0)]
        if loaded
        else []
    )
    return WorldActor(
        SpatialEntity(actor_id, name, position, facing=Vec3(0, 1, 0)),
        Mind(),
        Physiology(70.0),
        Loadout(70.0, carried_loose=items),
    )


def _combatants(
    distance: float,
    *,
    loaded: bool = False,
    strike_type: StrikeType = StrikeType.CUT,
) -> tuple[SpatialCombatant, SpatialCombatant]:
    hero = create_character("ranger", "Iris", 4)
    enemy = create_enemy("goblin", 1, 5)
    hero.stats.accuracy = 1.5
    enemy.stats.evasion = 0.0
    hero_world = _world_actor(hero.actor_id, hero.name, Vec3(0, 0, 0), loaded=loaded)
    enemy_world = _world_actor(enemy.actor_id, enemy.name, Vec3(0, distance, 0))
    weapon = WeaponPhysics(
        "test sword",
        mass_kg=1.4,
        reach_m=0.9,
        handling=1.0,
        strike_speed_mps=12.0,
        edge_factor=1.0,
        strike_type=strike_type,
    )
    return (
        SpatialCombatant(hero, hero_world, weapon),
        SpatialCombatant(enemy, enemy_world, weapon),
    )


def test_attack_outside_reach_cannot_damage_target() -> None:
    attacker, target = _combatants(3.0)
    before = target.actor.body_parts[BodyPart.TORSO].current_hp
    result = SpatialCombatResolver(random.Random(1)).resolve_attack(
        attacker,
        target,
        selected_part=BodyPart.TORSO,
    )
    assert not result.in_reach
    assert not result.hit
    assert result.damage == 0
    assert target.actor.body_parts[BodyPart.TORSO].current_hp == before
    assert not target.world_actor.physiology.injuries


def test_in_reach_attack_damages_body_and_creates_injury() -> None:
    attacker, target = _combatants(1.0)
    before = target.actor.body_parts[BodyPart.LEFT_LEG].current_hp
    result = SpatialCombatResolver(random.Random(1)).resolve_attack(
        attacker,
        target,
        selected_part=BodyPart.LEFT_LEG,
    )
    assert result.in_reach
    assert result.hit
    assert result.damage > 0
    assert target.actor.body_parts[BodyPart.LEFT_LEG].current_hp < before
    assert result.injury is not None
    assert result.injury.mobility_penalty > 0
    assert target.world_actor.physiology.injuries == [result.injury]


def test_thrust_creates_puncture_injury() -> None:
    attacker, target = _combatants(1.0, strike_type=StrikeType.THRUST)
    result = SpatialCombatResolver(random.Random(1)).resolve_attack(
        attacker,
        target,
        selected_part=BodyPart.RIGHT_ARM,
    )
    assert result.injury is not None
    assert result.injury.injury_type.value == "puncture"
    assert result.injury.manipulation_penalty > 0


def test_encumbrance_reduces_attack_quality_and_energy() -> None:
    light_attacker, light_target = _combatants(1.0, loaded=False)
    heavy_attacker, heavy_target = _combatants(1.0, loaded=True)
    light = SpatialCombatResolver(random.Random(1)).resolve_attack(
        light_attacker,
        light_target,
        selected_part=BodyPart.TORSO,
    )
    heavy = SpatialCombatResolver(random.Random(1)).resolve_attack(
        heavy_attacker,
        heavy_target,
        selected_part=BodyPart.TORSO,
    )
    assert heavy.hit_chance < light.hit_chance
    if light.hit and heavy.hit:
        assert heavy.impact_energy_j < light.impact_energy_j


def test_armor_reduces_spatial_damage() -> None:
    plain_attacker, plain_target = _combatants(1.0)
    armored_attacker, armored_target = _combatants(1.0)
    armored_target.actor.equipment["torso"] = Armor(
        "plate",
        "Plate",
        slot="torso",
        protection=10,
    )
    plain = SpatialCombatResolver(random.Random(1)).resolve_attack(
        plain_attacker,
        plain_target,
        selected_part=BodyPart.TORSO,
    )
    armored = SpatialCombatResolver(random.Random(1)).resolve_attack(
        armored_attacker,
        armored_target,
        selected_part=BodyPart.TORSO,
    )
    assert plain.hit and armored.hit
    assert armored.damage <= plain.damage


def test_many_spatial_attacks_preserve_health_bounds() -> None:
    attacker, target = _combatants(1.0)
    resolver = SpatialCombatResolver(random.Random(19))
    for _ in range(100):
        if not target.actor.alive:
            break
        resolver.resolve_attack(attacker, target)
    for part in target.actor.body_parts.values():
        assert 0 <= part.current_hp <= part.max_hp
