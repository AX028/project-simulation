import pytest

from project_simulation import build_demo_session, session_digest


def test_take_moves_item_from_world_to_inventory() -> None:
    session = build_demo_session(5)
    assert "rope" in session.world_items
    assert not session.player.loadout.carried_loose

    result = session.execute("take rope")

    assert "take Rope" in result.output
    assert "rope" not in session.world_items
    assert [item.item_id for item in session.player.loadout.carried_loose] == ["rope"]
    assert all(entity.entity_id != "rope" for entity in session.scenery)


def test_take_requires_pickup_range() -> None:
    session = build_demo_session(5)
    rope = next(entity for entity in session.scenery if entity.entity_id == "rope")
    rope.position = rope.position + rope.facing.scale(10.0)
    with pytest.raises(ValueError, match="too far"):
        session.execute("take rope")


def test_nonportable_scenery_cannot_be_taken() -> None:
    session = build_demo_session(5)
    session.execute("move east 3")
    session.execute("move north 3")
    with pytest.raises(ValueError, match="cannot be taken"):
        session.execute("take barrel")


def test_inventory_reports_mass_after_pickup() -> None:
    session = build_demo_session(5)
    session.execute("take rope")
    output = session.execute("inventory").output
    assert "Rope" in output
    assert "1.80 kg" in output
    assert "load ratio" in output


def test_drop_returns_item_to_spatial_world() -> None:
    session = build_demo_session(5)
    session.execute("take rope")
    result = session.execute("drop rope")

    assert "drop Rope" in result.output
    assert not session.player.loadout.carried_loose
    assert "rope" in session.world_items
    rope = next(entity for entity in session.scenery if entity.entity_id == "rope")
    assert rope.position.distance_to(session.player.spatial.position) == pytest.approx(0.6)


def test_drop_unknown_item_is_rejected() -> None:
    session = build_demo_session(5)
    with pytest.raises(ValueError, match="not carrying"):
        session.execute("drop rope")


def test_take_and_drop_advance_time() -> None:
    session = build_demo_session(5)
    session.execute("take rope")
    assert session.elapsed_seconds == pytest.approx(0.5)
    session.execute("drop rope")
    assert session.elapsed_seconds == pytest.approx(1.0)


def test_carried_mass_reduces_effective_speed() -> None:
    session = build_demo_session(5)
    before = session.player.effective_speed()
    session.execute("take rope")
    after = session.player.effective_speed()
    assert after < before


def test_take_drop_replay_is_deterministic() -> None:
    commands = (
        "inventory",
        "take rope",
        "inventory",
        "move north 1",
        "drop rope",
        "look",
    )
    first = build_demo_session(99)
    second = build_demo_session(99)
    assert first.replay(commands) == second.replay(commands)
    assert session_digest(first) == session_digest(second)


def test_one_hundred_take_drop_cycles_preserve_item_mass() -> None:
    session = build_demo_session(44)
    initial_mass = session.world_items["rope"].mass_kg
    for _ in range(100):
        session.execute("take rope")
        assert session.player.loadout.carried_mass_kg == pytest.approx(initial_mass)
        session.execute("drop rope")
        assert session.player.loadout.carried_mass_kg == 0.0
        assert session.world_items["rope"].mass_kg == pytest.approx(initial_mass)


def test_inventory_command_does_not_advance_time() -> None:
    session = build_demo_session(5)
    before = session.elapsed_seconds
    session.execute("inventory")
    assert session.elapsed_seconds == before
