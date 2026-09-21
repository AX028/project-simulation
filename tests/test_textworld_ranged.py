import pytest

from project_simulation import (
    BodyPart,
    Loadout,
    Mind,
    Physiology,
    SpatialCombatant,
    SpatialEntity,
    Vec3,
    WeaponPhysics,
    WorldActor,
    build_demo_session,
    create_enemy,
    session_digest,
)


def _wolf_id(session) -> str:
    return next(
        actor_id
        for actor_id, actor in session.actors.items()
        if actor.spatial.name == "Wolf"
    )


def test_shoot_wolf_consumes_ammo_and_damages_torso() -> None:
    session = build_demo_session(14)
    wolf = session.combatants[_wolf_id(session)]
    before_hp = wolf.actor.body_parts[BodyPart.TORSO].current_hp
    before_ammo = session.ranged_weapons[session.player_id].ammunition

    result = session.execute("shoot Wolf torso")

    assert "strikes Wolf" in result.output
    assert wolf.actor.body_parts[BodyPart.TORSO].current_hp < before_hp
    assert session.ranged_weapons[session.player_id].ammunition == before_ammo - 1


def test_shoot_specific_limb_creates_matching_injury() -> None:
    session = build_demo_session(15)
    session.execute("shoot Wolf left_leg")
    injuries = session.actors[_wolf_id(session)].physiology.injuries
    assert injuries
    assert injuries[-1].location == BodyPart.LEFT_LEG.value
    assert injuries[-1].mobility_penalty > 0


def test_solid_scenery_intercepts_shot_before_target() -> None:
    session = build_demo_session(16)
    blocker = SpatialEntity(
        "shield-wall",
        "Shield wall",
        Vec3(0.0, 4.0, 0.0),
        tags=frozenset({"solid", "occluder"}),
    )
    session.scenery = (*session.scenery, blocker)
    wolf = session.combatants[_wolf_id(session)]
    before = wolf.actor.body_parts[BodyPart.TORSO].current_hp

    result = session.execute("shoot Wolf torso")

    assert "Shield wall" in result.output
    assert wolf.actor.body_parts[BodyPart.TORSO].current_hp == before


def test_closed_gate_intercepts_and_takes_structural_damage() -> None:
    session = build_demo_session(17)
    wolf_world = session.actors[_wolf_id(session)]
    wolf_world.spatial.position = Vec3(6.0, 0.0, 0.0)
    before = session.doors["gate"].integrity

    result = session.execute("shoot Wolf torso")

    assert "Wooden gate" in result.output
    assert session.doors["gate"].integrity < before


def test_open_gate_allows_projectile_through() -> None:
    session = build_demo_session(18)
    session.doors["gate"].open_door()
    wolf_world = session.actors[_wolf_id(session)]
    wolf_world.spatial.position = Vec3(6.0, 0.0, 0.0)
    wolf = session.combatants[_wolf_id(session)]
    before = wolf.actor.body_parts[BodyPart.TORSO].current_hp

    result = session.execute("shoot Wolf torso")

    assert "strikes Wolf" in result.output
    assert wolf.actor.body_parts[BodyPart.TORSO].current_hp < before


def test_intervening_combatant_is_hit_before_intended_target() -> None:
    session = build_demo_session(19)
    goblin = create_enemy("goblin", 1, 20)
    goblin_world = WorldActor(
        SpatialEntity(
            goblin.actor_id,
            goblin.name,
            Vec3(0.0, 4.0, 0.0),
        ),
        Mind(),
        Physiology(50.0),
        Loadout(50.0),
    )
    session.actors[goblin.actor_id] = goblin_world
    session.combatants[goblin.actor_id] = SpatialCombatant(
        goblin,
        goblin_world,
        WeaponPhysics("club", 1.0, 0.5),
    )
    before = goblin.body_parts[BodyPart.TORSO].current_hp

    result = session.execute("shoot Wolf torso")

    assert "intercepted by" in result.output
    assert goblin.body_parts[BodyPart.TORSO].current_hp < before


def test_shooting_until_empty_rejects_next_shot() -> None:
    session = build_demo_session(21)
    weapon = session.ranged_weapons[session.player_id]
    weapon.ammunition = 2

    session.execute("shoot Wolf torso")
    session.execute("shoot Wolf torso")
    assert weapon.ammunition == 0
    with pytest.raises(ValueError, match="out of ammunition"):
        session.execute("shoot Wolf torso")


def test_failed_empty_shot_does_not_advance_time() -> None:
    session = build_demo_session(22)
    weapon = session.ranged_weapons[session.player_id]
    weapon.ammunition = 0
    before = session.elapsed_seconds
    with pytest.raises(ValueError, match="out of ammunition"):
        session.execute("shoot Wolf torso")
    assert session.elapsed_seconds == before


def test_shoot_command_advances_time() -> None:
    session = build_demo_session(23)
    before = session.elapsed_seconds
    session.execute("shoot Wolf torso")
    assert session.elapsed_seconds >= before + 1.0


def test_shoot_state_participates_in_replay_digest() -> None:
    untouched = build_demo_session(24)
    fired = build_demo_session(24)
    fired.execute("shoot Wolf torso")
    assert session_digest(fired) != session_digest(untouched)


def test_repeated_identical_shoot_sequences_are_deterministic() -> None:
    commands = (
        "shoot Wolf torso",
        "shoot Wolf left_leg",
        "shoot Wolf right_arm",
        "status",
    )
    first = build_demo_session(25)
    second = build_demo_session(25)
    assert first.replay(commands) == second.replay(commands)
    assert session_digest(first) == session_digest(second)


def test_invalid_shoot_body_part_is_rejected() -> None:
    session = build_demo_session(26)
    with pytest.raises(ValueError, match="body_part"):
        session.execute("shoot Wolf tail")


def test_noncombat_target_cannot_be_selected_for_detailed_shot() -> None:
    session = build_demo_session(27)
    with pytest.raises(ValueError, match="detailed combat"):
        session.execute("shoot Mira torso")


def test_one_hundred_shots_preserve_target_hp_bounds() -> None:
    session = build_demo_session(28)
    weapon = session.ranged_weapons[session.player_id]
    weapon.ammunition = 100
    for _ in range(100):
        session.execute("shoot Wolf torso")
    torso = session.combatants[_wolf_id(session)].actor.body_parts[BodyPart.TORSO]
    assert 0 <= torso.current_hp <= torso.max_hp
    assert weapon.ammunition == 0
