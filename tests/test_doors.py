import pytest

from project_simulation import (
    Bounds,
    Door,
    Loadout,
    Mind,
    Physiology,
    SpatialEntity,
    Vec3,
    WorldActor,
    build_demo_session,
    move_actor_with_collisions,
    session_digest,
)


def _entity(
    *,
    width: float = 0.6,
    depth: float = 0.6,
    height: float = 1.8,
) -> SpatialEntity:
    return SpatialEntity(
        "entity",
        "Entity",
        Vec3(0.0, 0.0, 0.0),
        bounds=Bounds(width / 2.0, depth / 2.0, height),
    )


def _actor(
    *,
    width: float = 0.6,
    depth: float = 0.6,
    height: float = 1.8,
) -> WorldActor:
    return WorldActor(
        _entity(width=width, depth=depth, height=height),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
        movement_speed_mps=3.0,
    )


def test_closed_door_is_solid_and_occluding() -> None:
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 2.0, 0.0),
        1.0,
        2.0,
    )
    assert "solid" in door.spatial.tags
    assert "occluder" in door.spatial.tags
    assert not door.can_pass(_entity())


def test_open_door_allows_actor_that_fits() -> None:
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 2.0, 0.0),
        1.0,
        2.0,
    )
    door.open_door()
    assert "solid" not in door.spatial.tags
    assert door.can_pass(_entity(width=0.6, height=1.8))


def test_open_door_rejects_actor_too_wide() -> None:
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 2.0, 0.0),
        1.0,
        2.2,
    )
    door.open_door()
    assert not door.can_pass(_entity(width=1.2, height=1.8))


def test_open_door_rejects_actor_too_tall_without_crouch() -> None:
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 2.0, 0.0),
        1.2,
        1.6,
    )
    door.open_door()
    actor = _entity(width=0.6, height=1.9)
    assert not door.can_pass(actor)
    assert door.can_pass(actor, crouch_factor=0.75)


def test_locked_door_cannot_open() -> None:
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 2.0, 0.0),
        1.0,
        2.0,
        locked=True,
    )
    with pytest.raises(ValueError, match="locked"):
        door.open_door()


def test_destroying_door_opens_and_unlocks_it() -> None:
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 2.0, 0.0),
        1.0,
        2.0,
        locked=True,
        integrity=10.0,
    )
    dealt = door.apply_damage(20.0)
    assert dealt == 10.0
    assert door.destroyed
    assert door.is_open
    assert not door.locked
    assert "solid" not in door.spatial.tags


def test_hardness_reduces_door_damage() -> None:
    soft = Door(
        "soft",
        "Soft",
        Vec3(0.0, 2.0, 0.0),
        1.0,
        2.0,
        hardness=1.0,
    )
    hard = Door(
        "hard",
        "Hard",
        Vec3(0.0, 2.0, 0.0),
        1.0,
        2.0,
        hardness=4.0,
    )
    soft.apply_damage(20.0)
    hard.apply_damage(20.0)
    assert soft.integrity < hard.integrity


def test_open_narrow_door_blocks_oversized_actor_movement() -> None:
    actor = _actor(width=1.4, height=2.4)
    door = Door(
        "door",
        "Narrow door",
        Vec3(0.0, 2.0, 0.0),
        width_m=1.0,
        height_m=2.0,
    )
    door.open_door()

    result = move_actor_with_collisions(
        actor,
        Vec3(0.0, 5.0, 0.0),
        2.0,
        [door.spatial],
        doors=[door],
    )

    assert result.hit is not None
    assert result.hit.entity_id == "door"
    assert actor.spatial.position.y < 2.0


def test_open_door_allows_fitting_actor_movement() -> None:
    actor = _actor()
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 2.0, 0.0),
        width_m=1.2,
        height_m=2.1,
    )
    door.open_door()

    result = move_actor_with_collisions(
        actor,
        Vec3(0.0, 5.0, 0.0),
        2.0,
        [door.spatial],
        doors=[door],
    )

    assert result.hit is None
    assert actor.spatial.position.y > 2.0


def test_crossing_outside_door_opening_is_not_blocked_by_passage_rule() -> None:
    actor = _actor(width=1.4, height=2.4)
    actor.spatial.position = Vec3(4.0, 0.0, 0.0)
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 2.0, 0.0),
        width_m=1.0,
        height_m=2.0,
    )
    door.open_door()
    result = move_actor_with_collisions(
        actor,
        Vec3(4.0, 5.0, 0.0),
        2.0,
        [door.spatial],
        doors=[door],
    )
    assert result.hit is None


def test_textworld_closed_gate_blocks_eastward_movement() -> None:
    session = build_demo_session(12)
    result = session.execute("move east 4")
    assert "blocked by gate" in result.output.lower()
    assert session.player.spatial.position.x < 3.0


def test_textworld_open_gate_then_pass_through() -> None:
    session = build_demo_session(12)
    session.execute("move east 4")
    opened = session.execute("open gate")
    assert "open Wooden gate" in opened.output
    before = session.player.spatial.position.x
    moved = session.execute("move east 2")
    assert "blocked by gate" not in moved.output.lower()
    assert session.player.spatial.position.x > before
    assert session.player.spatial.position.x > 3.0


def test_textworld_close_gate_restores_collision() -> None:
    session = build_demo_session(12)
    session.execute("move east 4")
    session.execute("open gate")
    session.execute("close gate")
    result = session.execute("move east 2")
    assert "blocked by gate" in result.output.lower()


def test_textworld_locked_gate_reports_failure() -> None:
    session = build_demo_session(12)
    session.execute("move east 4")
    session.doors["gate"].locked = True
    with pytest.raises(ValueError, match="locked"):
        session.execute("open gate")


def test_door_state_participates_in_replay_digest() -> None:
    closed = build_demo_session(21)
    opened = build_demo_session(21)
    opened.execute("move east 4")
    opened.execute("open gate")
    assert session_digest(opened) != session_digest(closed)


def test_hundred_open_close_cycles_preserve_integrity() -> None:
    door = Door(
        "door",
        "Door",
        Vec3(0.0, 0.0, 0.0),
        1.0,
        2.0,
    )
    for _ in range(100):
        door.open_door()
        door.close_door()
    assert door.integrity == 100.0
    assert not door.is_open
