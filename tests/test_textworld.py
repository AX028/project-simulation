import pytest

from project_simulation import (
    CommandKind,
    SpatialEntity,
    Vec3,
    build_demo_session,
    parse_command,
)


def test_parse_command_is_case_insensitive_and_preserves_args() -> None:
    parsed = parse_command("MoVe north 2")
    assert parsed.kind is CommandKind.MOVE
    assert parsed.args == ("north", "2")


def test_parse_command_rejects_empty_and_unknown_commands() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_command("   ")
    with pytest.raises(ValueError, match="unknown"):
        parse_command("teleport north")


def test_look_uses_perception_and_describes_visible_wolf() -> None:
    session = build_demo_session(10)
    result = session.execute("look")
    assert "wolf" in result.output.lower()
    assert result.elapsed_seconds == 0.0


def test_map_renders_player_and_scenery() -> None:
    session = build_demo_session(10)
    output = session.execute("map").output
    assert "@" in output
    assert "#" in output


def test_move_changes_position_and_advances_time() -> None:
    session = build_demo_session(10)
    before = session.player.spatial.position
    result = session.execute("move north 2")
    after = session.player.spatial.position
    assert after.y == pytest.approx(before.y + 2.0)
    assert after.x == pytest.approx(before.x)
    assert result.elapsed_seconds > 0.0
    assert session.kernel is not None
    assert session.kernel.world.time_hours > 0.0


def test_wait_advances_physiology_and_macro_clock() -> None:
    session = build_demo_session(10)
    assert session.kernel is not None
    before_hour = session.kernel.world.time_hours
    before_fatigue = session.player.physiology.fatigue

    result = session.execute("wait 60")

    assert result.elapsed_seconds == 60.0
    assert session.kernel.world.time_hours == pytest.approx(before_hour + 1 / 60)
    assert session.player.physiology.fatigue > before_fatigue


def test_inspect_reveals_visible_target_but_not_target_behind_player() -> None:
    session = build_demo_session(10)
    visible = session.execute("inspect Wolf").output
    assert "clarity" in visible

    hidden = SpatialEntity(
        "hidden",
        "Hidden marker",
        Vec3(0.0, -5.0, 0.0),
    )
    session.scenery = (*session.scenery, hidden)
    not_visible = session.execute("inspect hidden").output
    assert "cannot currently perceive" in not_visible.lower()


def test_attack_out_of_reach_reports_physical_limit() -> None:
    session = build_demo_session(10)
    result = session.execute("attack Wolf torso")
    assert "cannot reach" in result.output.lower()
    assert result.elapsed_seconds == 1.0


def test_advance_then_attack_can_create_injury() -> None:
    session = build_demo_session(3)
    session.execute("advance Wolf 5")
    target_id = next(
        actor_id
        for actor_id, actor in session.actors.items()
        if actor.spatial.name == "Wolf"
    )
    before = len(session.actors[target_id].physiology.injuries)

    result = session.execute("attack Wolf left_leg")

    assert "strikes" in result.output.lower() or "misses" in result.output.lower()
    after = len(session.actors[target_id].physiology.injuries)
    assert after >= before


def test_status_reports_physical_state() -> None:
    session = build_demo_session(10)
    output = session.execute("status").output
    assert "speed" in output
    assert "fatigue" in output
    assert "blood lost" in output
    assert "injuries" in output


def test_bad_command_arguments_are_rejected() -> None:
    session = build_demo_session(10)
    with pytest.raises(ValueError, match="usage"):
        session.execute("move")
    with pytest.raises(ValueError, match="positive"):
        session.execute("wait 0")
    with pytest.raises(ValueError, match="direction"):
        session.execute("move upward 2")
    with pytest.raises(ValueError, match="unknown actor"):
        session.execute("advance Nobody")


def test_replay_is_deterministic_for_same_seed_and_commands() -> None:
    commands = (
        "look",
        "move north 2",
        "advance Wolf 2",
        "inspect Wolf",
        "attack Wolf torso",
        "status",
        "wait 3",
        "map",
    )
    first = build_demo_session(22)
    second = build_demo_session(22)

    assert first.replay(commands) == second.replay(commands)
    assert first.player.spatial.position == second.player.spatial.position
    assert first.elapsed_seconds == second.elapsed_seconds
    assert first.kernel is not None
    assert second.kernel is not None
    assert first.kernel.world.time_hours == second.kernel.world.time_hours


def test_quit_marks_result_without_advancing_time() -> None:
    session = build_demo_session(10)
    result = session.execute("quit")
    assert result.quit
    assert result.elapsed_seconds == 0.0
