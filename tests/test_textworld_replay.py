import json

import pytest

from project_simulation import (
    TextWorldReplayStore,
    Vec3,
    build_demo_session,
    session_digest,
)
from project_simulation.models import IncompatibleSaveError


def _commands() -> tuple[str, ...]:
    return (
        "look",
        "move north 2",
        "advance Wolf 2",
        "inspect Wolf",
        "attack Wolf torso",
        "status",
        "wait 3",
        "map",
    )


def test_successful_commands_are_recorded_in_order() -> None:
    session = build_demo_session(31)
    session.replay(_commands())
    assert tuple(session.command_history) == _commands()


def test_failed_command_is_not_recorded() -> None:
    session = build_demo_session(31)
    with pytest.raises(ValueError):
        session.execute("move upward 2")
    assert session.command_history == []


def test_replay_store_round_trip_preserves_digest(tmp_path) -> None:
    session = build_demo_session(31)
    session.replay(_commands())
    path = tmp_path / "save.json"

    TextWorldReplayStore.write(session, path)
    restored = TextWorldReplayStore.read(path)

    assert session_digest(restored) == session_digest(session)
    assert restored.command_history == session.command_history
    assert restored.transcript == session.transcript


def test_replay_store_serialization_is_deterministic(tmp_path) -> None:
    session = build_demo_session(31)
    session.replay(_commands())
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    TextWorldReplayStore.write(session, first)
    TextWorldReplayStore.write(session, second)

    assert first.read_bytes() == second.read_bytes()


def test_tampered_command_history_is_detected(tmp_path) -> None:
    session = build_demo_session(31)
    session.replay(_commands())
    path = tmp_path / "save.json"
    TextWorldReplayStore.write(session, path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["commands"].append("wait 1")
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(IncompatibleSaveError, match="digest"):
        TextWorldReplayStore.read(path)


def test_tampered_digest_is_detected(tmp_path) -> None:
    session = build_demo_session(31)
    session.replay(_commands())
    path = tmp_path / "save.json"
    TextWorldReplayStore.write(session, path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["digest"] = "0" * 64
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(IncompatibleSaveError, match="digest"):
        TextWorldReplayStore.read(path)


def test_bad_schema_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "seed": 1,
                "commands": [],
                "digest": "x",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncompatibleSaveError, match="unsupported"):
        TextWorldReplayStore.read(path)


def test_non_string_commands_are_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "seed": 1,
                "commands": ["look", 3],
                "digest": "x",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncompatibleSaveError, match="command"):
        TextWorldReplayStore.read(path)


def test_seed_is_required_for_replay_save(tmp_path) -> None:
    session = build_demo_session(1)
    session.seed = None
    with pytest.raises(ValueError, match="seed"):
        TextWorldReplayStore.write(session, tmp_path / "save.json")


def test_five_hundred_command_round_trip_is_exact(tmp_path) -> None:
    session = build_demo_session(77)
    commands = tuple(
        "wait 1" if index % 3 else "status"
        for index in range(500)
    )
    session.replay(commands)
    path = tmp_path / "long.json"

    TextWorldReplayStore.write(session, path)
    restored = TextWorldReplayStore.read(path)

    assert restored.command_history == session.command_history
    assert restored.elapsed_seconds == pytest.approx(session.elapsed_seconds)
    assert session_digest(restored) == session_digest(session)


def test_environment_and_skill_configuration_change_replay_identity() -> None:
    original = build_demo_session(31)
    wind = build_demo_session(31)
    learning = build_demo_session(31)
    wind.environment.wind_velocity = Vec3(4.0, 0.0, 0.0)
    learning.player.skills.learning_rate = 1.5
    learning.player.skills.baseline_level = 30.0

    assert session_digest(wind) != session_digest(original)
    assert session_digest(learning) != session_digest(original)


def test_transfer_insertion_order_does_not_change_replay_identity() -> None:
    first = build_demo_session(31)
    second = build_demo_session(31)
    forward: dict[str, float] = {}
    forward["knife"] = 0.1
    forward["spear"] = 0.2
    reverse: dict[str, float] = {}
    reverse["spear"] = 0.2
    reverse["knife"] = 0.1
    first.player.skills.transfers = {"sword": forward}
    second.player.skills.transfers = {"sword": reverse}

    assert session_digest(first) == session_digest(second)


def test_custom_initial_state_cannot_be_saved(tmp_path) -> None:
    session = build_demo_session(31)
    session.environment.base_temperature_c = 4.0
    with pytest.raises(IncompatibleSaveError, match="custom initial state"):
        TextWorldReplayStore.write(session, tmp_path / "custom.json")
    assert not (tmp_path / "custom.json").exists()


def test_schema_v1_save_still_loads_with_its_own_digest(tmp_path) -> None:
    commands = ("look", "wait 1")
    session = build_demo_session(31)
    session.replay(commands)
    path = tmp_path / "v1.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "seed": 31,
                "commands": list(commands),
                "digest": session_digest(session, schema_version=1),
            }
        ),
        encoding="utf-8",
    )

    restored = TextWorldReplayStore.read(path)

    assert session_digest(restored) == session_digest(session)
    assert restored.command_history == list(commands)


def test_v1_digest_is_not_accepted_as_v2(tmp_path) -> None:
    commands = ("look", "wait 1")
    session = build_demo_session(31)
    session.replay(commands)
    path = tmp_path / "mislabelled.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "seed": 31,
                "commands": list(commands),
                "digest": session_digest(session, schema_version=1),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(IncompatibleSaveError, match="digest"):
        TextWorldReplayStore.read(path)


def test_custom_state_marker_is_rejected(tmp_path) -> None:
    session = build_demo_session(31)
    path = tmp_path / "marked.json"
    TextWorldReplayStore.write(session, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["custom_initial_state"] = {"environment": "noon"}
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(IncompatibleSaveError, match="custom initial state"):
        TextWorldReplayStore.read(path)


def test_loaded_replay_continues_deterministically(tmp_path) -> None:
    commands = _commands()
    session = build_demo_session(31)
    session.replay(commands)
    path = tmp_path / "save.json"
    TextWorldReplayStore.write(session, path)

    restored = TextWorldReplayStore.read(path)
    restored.execute("wait 2")
    continued = build_demo_session(31)
    continued.replay((*commands, "wait 2"))

    assert session_digest(restored) == session_digest(continued)
    assert restored.elapsed_seconds == pytest.approx(continued.elapsed_seconds)


def test_three_independent_reloads_have_identical_state(tmp_path) -> None:
    session = build_demo_session(88)
    session.replay(_commands())
    path = tmp_path / "save.json"
    TextWorldReplayStore.write(session, path)

    digests = {
        session_digest(TextWorldReplayStore.read(path))
        for _ in range(3)
    }
    assert digests == {session_digest(session)}
