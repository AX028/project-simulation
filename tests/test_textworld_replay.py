import json

import pytest

from project_simulation import (
    TextWorldReplayStore,
    Vec3,
    build_demo_session,
    session_digest,
)
from project_simulation.environment import WeatherKind
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


def test_current_saves_use_schema_two(tmp_path) -> None:
    session = build_demo_session(31)
    path = tmp_path / "save.json"
    TextWorldReplayStore.write(session, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2


def test_environment_and_skill_configuration_change_identity() -> None:
    baseline = build_demo_session(12)
    changed_weather = build_demo_session(12)
    changed_weather.environment.weather = WeatherKind.FOG
    changed_weather.environment.base_temperature_c = 4.0
    changed_weather.environment.wind_velocity = Vec3(1.0, 2.0, 0.0)
    changed_weather.environment.ground_wetness = 0.4

    changed_learning = build_demo_session(12)
    changed_learning.player.skills.learning_rate = 1.4
    changed_baseline = build_demo_session(12)
    changed_baseline.player.skills.baseline_level = 35.0
    changed_transfer = build_demo_session(12)
    changed_transfer.player.skills.transfers = {"sword": {"knife": 0.5}}

    identities = {
        session_digest(baseline),
        session_digest(changed_weather),
        session_digest(changed_learning),
        session_digest(changed_baseline),
        session_digest(changed_transfer),
    }
    assert len(identities) == 5
    assert session_digest(changed_weather, schema_version=1) == session_digest(
        baseline,
        schema_version=1,
    )


def test_transfer_insertion_order_does_not_change_digest() -> None:
    first = build_demo_session(13)
    second = build_demo_session(13)
    first.player.skills.transfers = {
        "sword": {"knife": 0.1, "spear": 0.08},
        "archery": {"throwing": 0.06},
    }
    second.player.skills.transfers = {
        "archery": {"throwing": 0.06},
        "sword": {"spear": 0.08, "knife": 0.1},
    }
    assert session_digest(first) == session_digest(second)


def test_out_of_band_state_is_rejected_on_load(tmp_path) -> None:
    session = build_demo_session(14)
    session.environment.weather = WeatherKind.RAIN
    session.player.skills.learning_rate = 0.5
    session.replay(("look", "status"))
    path = tmp_path / "custom.json"
    TextWorldReplayStore.write(session, path)

    with pytest.raises(IncompatibleSaveError, match="digest"):
        TextWorldReplayStore.read(path)


def test_schema_one_save_still_loads_and_is_not_read_as_schema_two(tmp_path) -> None:
    session = build_demo_session(15)
    session.replay(("look", "wait 2", "status"))
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "seed": session.seed,
                "commands": session.command_history,
                "digest": session_digest(session, schema_version=1),
            }
        ),
        encoding="utf-8",
    )

    restored = TextWorldReplayStore.read(path)
    assert session_digest(restored) == session_digest(session)

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["schema_version"] = 2
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(IncompatibleSaveError, match="digest"):
        TextWorldReplayStore.read(path)


def test_reloaded_session_continues_deterministically(tmp_path) -> None:
    session = build_demo_session(16)
    session.replay(("wait 2", "move north 1"))
    path = tmp_path / "save.json"
    TextWorldReplayStore.write(session, path)
    restored = TextWorldReplayStore.read(path)

    continued = ("wait 4", "status", "look")
    assert session.replay(continued) == restored.replay(continued)
    assert session_digest(session) == session_digest(restored)
