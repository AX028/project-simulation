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

_SCHEMA_V1_COMMAND_DIGEST = (
    "a8158672078da2ea3ece3c3b5675f8b0bbeab0f83a9602c718d62c4f57861119"
)


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


def test_schema_v1_digest_algorithm_is_unchanged() -> None:
    session = build_demo_session(31)
    session.replay(_commands())
    assert session_digest(session, schema_version=1) == _SCHEMA_V1_COMMAND_DIGEST


def test_schema_v1_save_still_loads(tmp_path) -> None:
    session = build_demo_session(31)
    session.replay(_commands())
    path = tmp_path / "v1.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "seed": 31,
                "commands": list(session.command_history),
                "digest": session_digest(session, schema_version=1),
            }
        ),
        encoding="utf-8",
    )

    restored = TextWorldReplayStore.read(path)

    assert restored.command_history == session.command_history
    assert session_digest(restored, schema_version=1) == session_digest(
        session,
        schema_version=1,
    )


def test_schema_v1_does_not_use_schema_v2_digest_rules() -> None:
    original = build_demo_session(1)
    changed = build_demo_session(1)
    changed.environment.weather = WeatherKind.FOG
    changed.player.skills.learning_rate = 2.0

    assert session_digest(original, schema_version=1) == session_digest(
        changed,
        schema_version=1,
    )
    assert session_digest(original) != session_digest(changed)


def test_schema_version_is_not_checked_with_the_other_digest(tmp_path) -> None:
    session = build_demo_session(31)
    session.replay(_commands())
    path = tmp_path / "crossed.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "seed": 31,
                "commands": list(session.command_history),
                "digest": session_digest(session, schema_version=1),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(IncompatibleSaveError, match="digest"):
        TextWorldReplayStore.read(path)


def test_new_saves_use_schema_version_two(tmp_path) -> None:
    session = build_demo_session(1)
    path = tmp_path / "save.json"
    TextWorldReplayStore.write(session, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2


def test_authoritative_fields_change_replay_identity() -> None:
    baseline = session_digest(build_demo_session(6))
    variants = []

    weather = build_demo_session(6)
    weather.environment.weather = WeatherKind.FOG
    variants.append(weather)

    wind = build_demo_session(6)
    wind.environment.wind_velocity = Vec3(3.0, 0.0, 0.0)
    variants.append(wind)

    hour = build_demo_session(6)
    hour.environment.world_hour = 9.0
    variants.append(hour)

    rate = build_demo_session(6)
    rate.player.skills.learning_rate = 1.2
    variants.append(rate)

    level = build_demo_session(6)
    level.player.skills.baseline_level = 40.0
    variants.append(level)

    transfers = build_demo_session(6)
    transfers.player.skills.transfers = {"sword": {"knife": 0.5}}
    variants.append(transfers)

    for variant in variants:
        assert session_digest(variant) != baseline


def test_transfer_insertion_order_does_not_change_replay_identity() -> None:
    first = build_demo_session(6)
    second = build_demo_session(6)
    first.player.skills.transfers = {
        "sword": {"knife": 0.1, "spear": 0.2},
    }
    second.player.skills.transfers = {
        "sword": {"spear": 0.2, "knife": 0.1},
    }

    assert session_digest(first) == session_digest(second)


def test_out_of_band_state_cannot_be_saved(tmp_path) -> None:
    session = build_demo_session(4)
    session.execute("look")
    session.environment.base_temperature_c = 4.0
    path = tmp_path / "custom.json"

    with pytest.raises(ValueError, match="out-of-band"):
        TextWorldReplayStore.write(session, path)

    assert not path.exists()


def test_reloaded_session_continues_in_the_same_way_as_an_uninterrupted_replay(
    tmp_path,
) -> None:
    commands = ("look", "wait 2")
    session = build_demo_session(5)
    session.replay(commands)
    path = tmp_path / "save.json"
    TextWorldReplayStore.write(session, path)

    restored = TextWorldReplayStore.read(path)
    restored.execute("wait 3")
    fresh = build_demo_session(5)
    fresh.replay((*commands, "wait 3"))

    assert restored.command_history == fresh.command_history
    assert session_digest(restored) == session_digest(fresh)
