import pytest

from project_simulation import (
    Bounds,
    Loadout,
    Mind,
    Physiology,
    SpatialEntity,
    Vec3,
    WorldActor,
    build_demo_session,
    move_actor_with_collisions,
    sweep_entity,
)


def _actor(position: Vec3 | None = None) -> WorldActor:
    if position is None:
        position = Vec3(0.0, 0.0, 0.0)
    return WorldActor(
        SpatialEntity(
            "actor",
            "Actor",
            position,
            bounds=Bounds(0.3, 0.3, 1.8),
        ),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
        movement_speed_mps=10.0,
    )


def _wall(
    entity_id: str = "wall",
    *,
    position: Vec3 | None = None,
    solid: bool = True,
) -> SpatialEntity:
    if position is None:
        position = Vec3(0.0, 2.0, 0.0)
    tags = frozenset({"solid"}) if solid else frozenset()
    return SpatialEntity(
        entity_id,
        "Wall",
        position,
        bounds=Bounds(2.0, 0.2, 3.0),
        tags=tags,
    )


def test_sweep_detects_expected_contact_fraction() -> None:
    actor = _actor()
    displacement = Vec3(0.0, 5.0, 0.0)
    hit = sweep_entity(actor.spatial, displacement, [_wall()])
    assert hit is not None
    assert hit.entity_id == "wall"
    assert hit.fraction == pytest.approx(0.3)
    assert hit.contact_position.y == pytest.approx(1.5)


def test_high_speed_sweep_does_not_tunnel_through_wall() -> None:
    actor = _actor()
    hit = sweep_entity(
        actor.spatial,
        Vec3(0.0, 1000.0, 0.0),
        [_wall(position=Vec3(0.0, 500.0, 0.0))],
    )
    assert hit is not None
    assert 0.0 < hit.fraction < 1.0


def test_vertical_separation_prevents_collision() -> None:
    actor = _actor()
    elevated = _wall(position=Vec3(0.0, 2.0, 5.0))
    assert sweep_entity(
        actor.spatial,
        Vec3(0.0, 5.0, 0.0),
        [elevated],
    ) is None


def test_non_solid_entity_is_ignored() -> None:
    actor = _actor()
    assert sweep_entity(
        actor.spatial,
        Vec3(0.0, 5.0, 0.0),
        [_wall(solid=False)],
    ) is None


def test_nearest_solid_obstacle_wins() -> None:
    actor = _actor()
    hit = sweep_entity(
        actor.spatial,
        Vec3(0.0, 10.0, 0.0),
        [
            _wall("far", position=Vec3(0.0, 6.0, 0.0)),
            _wall("near", position=Vec3(0.0, 2.0, 0.0)),
        ],
    )
    assert hit is not None
    assert hit.entity_id == "near"


def test_starting_inside_solid_returns_immediate_hit() -> None:
    actor = _actor(position=Vec3(0.0, 2.0, 0.0))
    hit = sweep_entity(
        actor.spatial,
        Vec3(0.0, 1.0, 0.0),
        [_wall()],
    )
    assert hit is not None
    assert hit.fraction == 0.0


def test_touching_wall_and_moving_away_is_allowed() -> None:
    actor = _actor(position=Vec3(0.0, 1.5, 0.0))
    hit = sweep_entity(
        actor.spatial,
        Vec3(0.0, -2.0, 0.0),
        [_wall()],
    )
    assert hit is None


def test_collision_aware_movement_stops_before_wall() -> None:
    actor = _actor()
    result = move_actor_with_collisions(
        actor,
        Vec3(0.0, 10.0, 0.0),
        1.0,
        [_wall()],
    )
    assert result.hit is not None
    assert result.moved_distance_m < 1.5
    assert actor.spatial.position.y < 1.5


def test_collision_movement_still_advances_physiology() -> None:
    actor = _actor()
    before = actor.physiology.fatigue
    move_actor_with_collisions(
        actor,
        Vec3(0.0, 10.0, 0.0),
        1.0,
        [_wall()],
    )
    assert actor.physiology.fatigue > before


def test_invalid_movement_parameters_are_rejected() -> None:
    actor = _actor()
    with pytest.raises(ValueError, match="seconds"):
        move_actor_with_collisions(
            actor,
            Vec3(1.0, 0.0, 0.0),
            -1.0,
            [],
        )
    with pytest.raises(ValueError, match="clearance"):
        move_actor_with_collisions(
            actor,
            Vec3(1.0, 0.0, 0.0),
            1.0,
            [],
            clearance_m=-1.0,
        )


def test_textworld_move_cannot_cross_added_wall() -> None:
    session = build_demo_session(7)
    wall = _wall(position=Vec3(0.0, 1.5, 0.0))
    session.scenery = (*session.scenery, wall)

    result = session.execute("move north 5")

    assert "blocked by wall" in result.output.lower()
    assert session.player.spatial.position.y < 1.0


def test_textworld_advance_respects_solid_cover() -> None:
    session = build_demo_session(7)
    wall = _wall(position=Vec3(0.0, 4.0, 0.0))
    session.scenery = (*session.scenery, wall)

    result = session.execute("advance Wolf 10")

    assert "blocked by wall" in result.output.lower()
    assert session.player.spatial.position.y < 3.5


def test_repeated_collision_attempts_never_penetrate_wall() -> None:
    actor = _actor()
    wall = _wall()
    for _ in range(100):
        move_actor_with_collisions(
            actor,
            Vec3(0.0, 10.0, 0.0),
            0.5,
            [wall],
        )
        assert actor.spatial.position.y < 1.5
