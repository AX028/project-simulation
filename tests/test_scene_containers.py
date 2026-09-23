import pytest

from project_simulation import (
    Bounds,
    Container,
    PhysicalItem,
    SceneContainer,
    SpatialEntity,
    Vec3,
    build_demo_session,
    observe,
    session_digest,
    sweep_entity,
)


def _container(
    *,
    integrity: float = 100.0,
    hardness: float = 1.0,
    locked: bool = False,
    items: list[PhysicalItem] | None = None,
) -> SceneContainer:
    return SceneContainer(
        SpatialEntity(
            "crate",
            "Crate",
            Vec3(0.0, 2.0, 0.0),
            bounds=Bounds(0.5, 0.5, 2.0),
            tags=frozenset({"cover", "occluder", "solid", "wooden"}),
        ),
        Container(
            "Crate",
            max_volume_l=20.0,
            max_length_m=2.0,
            retrieval_penalty_s=0.5,
            items=[] if items is None else items,
        ),
        locked=locked,
        integrity=integrity,
        hardness=hardness,
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("integrity", -0.1, "integrity"),
        ("integrity", float("nan"), "finite"),
        ("hardness", 0.0, "hardness"),
        ("hardness", float("inf"), "finite"),
    ],
)
def test_scene_container_rejects_invalid_structure(
    field: str,
    value: float,
    message: str,
) -> None:
    kwargs = {field: value}
    with pytest.raises(ValueError, match=message):
        _container(**kwargs)


def test_scene_container_integrity_is_capped_like_a_door() -> None:
    container = _container(integrity=150.0)
    assert container.integrity == 100.0


def test_scene_container_damage_respects_hardness_and_transitions_tags() -> None:
    container = _container(
        integrity=10.0,
        hardness=2.0,
        locked=True,
    )

    assert container.apply_damage(6.0) == pytest.approx(3.0)
    assert container.integrity == pytest.approx(7.0)
    assert not container.destroyed
    assert {"cover", "occluder", "solid"} <= container.spatial.tags

    assert container.apply_damage(20.0) == pytest.approx(7.0)
    assert container.destroyed
    assert container.is_open
    assert not container.locked
    assert "container" in container.spatial.tags
    assert "wooden" in container.spatial.tags
    assert not {"cover", "occluder", "solid"} & container.spatial.tags
    with pytest.raises(ValueError, match="destroyed"):
        container.close_container()


def test_repeated_damage_and_spilling_are_idempotent_and_mass_conserving() -> None:
    apple = PhysicalItem("apple", "Apple", 0.2, 0.35, 0.1, 0.4)
    container = _container(integrity=1.0, items=[apple])
    initial_mass = sum(item.mass_kg for item in container.items)

    assert container.apply_damage(10.0) == pytest.approx(1.0)
    assert container.spill_contents() == (apple,)
    for _ in range(100):
        assert container.apply_damage(10.0) == 0.0
        assert container.spill_contents() == ()

    assert container.items == ()
    assert container.spilled
    assert initial_mass == pytest.approx(apple.mass_kg)


def test_destroyed_container_no_longer_blocks_navigation_or_line_of_sight() -> None:
    observer = SpatialEntity(
        "observer",
        "Observer",
        Vec3(0.0, 0.0, 0.0),
        facing=Vec3(0.0, 1.0, 0.0),
    )
    target = SpatialEntity(
        "target",
        "Target",
        Vec3(0.0, 4.0, 0.0),
    )
    container = _container(integrity=1.0)

    assert sweep_entity(
        observer,
        Vec3(0.0, 4.0, 0.0),
        [container.spatial],
    ) is not None
    assert observe(observer, target, obstacles=[container.spatial]) is None

    container.apply_damage(1.0)

    assert sweep_entity(
        observer,
        Vec3(0.0, 4.0, 0.0),
        [container.spatial],
    ) is None
    assert observe(observer, target, obstacles=[container.spatial]) is not None


def _place_fragile_barrel_in_shot_path(session) -> None:
    barrel = session.scene_containers["barrel"]
    barrel.spatial.position = Vec3(0.0, 4.0, 0.0)
    barrel.spatial.bounds = Bounds(0.5, 0.5, 2.0)
    barrel.integrity = 1.0


def _loose_item_mass(session) -> float:
    return sum(item.mass_kg for item in session.world_items.values()) + sum(
        item.mass_kg
        for container in session.scene_containers.values()
        for item in container.items
    )


def test_projectile_destroys_container_and_spills_contents_once() -> None:
    session = build_demo_session(91)
    _place_fragile_barrel_in_shot_path(session)
    barrel = session.scene_containers["barrel"]
    initial_mass = _loose_item_mass(session)

    result = session.execute("shoot Wolf torso")

    assert "strikes Barrel" in result.output
    assert "Spilled contents: Apple" in result.output
    assert barrel.destroyed
    assert barrel.spilled
    assert barrel.items == ()
    assert session.world_items["apple"].mass_kg == pytest.approx(0.2)
    spilled_entities = [
        entity
        for entity in session.scenery
        if entity.entity_id == "apple"
    ]
    assert len(spilled_entities) == 1
    assert spilled_entities[0].tags == frozenset({"item", "spilled"})
    assert _loose_item_mass(session) == pytest.approx(initial_mass)

    scenery_ids = tuple(entity.entity_id for entity in session.scenery)
    for _ in range(100):
        dealt, spilled = session.apply_scene_container_damage("barrel", 100.0)
        assert dealt == 0.0
        assert spilled == ()

    assert tuple(entity.entity_id for entity in session.scenery) == scenery_ids
    assert _loose_item_mass(session) == pytest.approx(initial_mass)


def test_container_destruction_and_spill_replay_deterministically() -> None:
    first = build_demo_session(92)
    second = build_demo_session(92)
    _place_fragile_barrel_in_shot_path(first)
    _place_fragile_barrel_in_shot_path(second)
    commands = (
        "shoot Wolf torso",
        "shoot Wolf torso",
        "status",
    )

    assert first.replay(commands) == second.replay(commands)
    assert session_digest(first) == session_digest(second)
    assert _loose_item_mass(first) == pytest.approx(_loose_item_mass(second))


def test_container_structure_tags_and_spill_participate_in_replay_identity() -> None:
    baseline = build_demo_session(93)

    integrity_changed = build_demo_session(93)
    integrity_changed.scene_containers["barrel"].integrity -= 1.0
    assert session_digest(integrity_changed) != session_digest(baseline)

    hardness_changed = build_demo_session(93)
    hardness_changed.scene_containers["barrel"].hardness = 2.0
    assert session_digest(hardness_changed) != session_digest(baseline)

    tags_changed = build_demo_session(93)
    tags_changed.scene_containers["barrel"].spatial.tags |= frozenset({"painted"})
    assert session_digest(tags_changed) != session_digest(baseline)

    destroyed = build_demo_session(93)
    destroyed.apply_scene_container_damage("barrel", 1_000.0)
    assert session_digest(destroyed) != session_digest(baseline)
    assert destroyed.scene_containers["barrel"].spilled
