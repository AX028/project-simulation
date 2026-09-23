"""Atomic macro checkpoints of world state plus the pending event queue."""

import json
from pathlib import Path

import pytest

from project_simulation import (
    FactionState,
    MacroCheckpointStore,
    SettlementState,
    SimulationKernel,
    WorldState,
    WorldStateStore,
)
from project_simulation.models import IncompatibleSaveError
from project_simulation.simulation import ScheduledEvent


def _world() -> WorldState:
    return WorldState(
        time_hours=10.0,
        settlements={
            "v": SettlementState(
                "v",
                "Village",
                population=100,
                food_units=200.0,
                wealth=1000.0,
                security=5.0,
                livestock=100.0,
                labor={"farmer": 70},
            )
        },
        factions={
            "a": FactionState(
                "a",
                "A",
                members=100,
                wealth=1000.0,
                military_power=10.0,
                territory=2.0,
            ),
            "b": FactionState(
                "b",
                "B",
                members=100,
                wealth=1000.0,
                military_power=10.0,
                territory=2.0,
            ),
        },
    )


def test_checkpoint_resume_matches_uninterrupted_continuation(tmp_path) -> None:
    def run(split: bool) -> tuple[WorldState, tuple[ScheduledEvent, ...]]:
        kernel = SimulationKernel(_world())
        kernel.schedule(12.0, "wolf_attack", settlement_id="v", severity=0.25)
        kernel.advance_to(11.0)
        if split:
            path = tmp_path / "checkpoint.json"
            MacroCheckpointStore.write(kernel, path)
            kernel = SimulationKernel(WorldState())
            MacroCheckpointStore.read_into(kernel, path)
        kernel.schedule(
            16.0,
            "faction_conflict",
            attacker="a",
            defender="b",
            scale=0.2,
        )
        kernel.advance_to(20.0)
        return kernel.world, kernel.pending_events()

    assert run(False) == run(True)


def test_equal_time_events_keep_order_and_accept_a_later_sequence(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.schedule(12.0, "record", value="first")
    original.schedule(12.0, "record", value="second")
    path = tmp_path / "checkpoint.json"
    MacroCheckpointStore.write(original, path)

    seen: list[str] = []
    restored = SimulationKernel(WorldState(time_hours=1.0))
    restored.register_handler(
        "record",
        lambda world, event: seen.append(str(event.payload["value"])),
    )
    MacroCheckpointStore.read_into(restored, path)
    scheduled = restored.schedule(12.0, "record", value="third")

    assert scheduled.sequence == 2
    restored.advance_to(12.0)
    assert seen == ["first", "second", "third"]
    assert restored.has_handler("wolf_attack")


def test_empty_queue_keeps_the_next_sequence(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.schedule(11.0, "wolf_attack", settlement_id="v", severity=0.1)
    original.advance_to(11.0)
    assert original.pending_events() == ()
    assert original.next_event_sequence() == 1
    path = tmp_path / "checkpoint.json"
    MacroCheckpointStore.write(original, path)

    restored = SimulationKernel(_world())
    MacroCheckpointStore.read_into(restored, path)
    assert restored.world.time_hours == pytest.approx(11.0)
    assert restored.next_event_sequence() == 1
    scheduled = restored.schedule(14.0, "wolf_attack", settlement_id="v")
    assert scheduled.sequence == 1


def test_checkpoint_bytes_are_deterministic(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", severity=0.5, settlement_id="v")
    kernel.schedule(15.0, "record", value="note")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    MacroCheckpointStore.write(kernel, first)
    MacroCheckpointStore.write(kernel, second)
    assert first.read_bytes() == second.read_bytes()


def test_failed_write_preserves_the_previous_checkpoint(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(15.0, "wolf_attack", settlement_id="v")
    path = tmp_path / "checkpoint.json"
    MacroCheckpointStore.write(kernel, path)
    original = path.read_bytes()

    kernel.schedule(18.0, "wolf_attack", settlement_id="v", severity=0.4)

    def fail_write(self: Path, *args: object, **kwargs: object) -> int:
        del self, args, kwargs
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(OSError, match="disk full"):
        MacroCheckpointStore.write(kernel, path)
    assert path.read_bytes() == original


def test_rejected_load_leaves_the_live_kernel_unchanged(tmp_path) -> None:
    live = SimulationKernel(_world())
    live.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    live.register_handler("extra", lambda world, event: None)
    pending = live.pending_events()
    history = list(live.world.history)

    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "next_sequence": 0,
                "world": {
                    "time_hours": 10.0,
                    "history": [],
                    "settlements": {},
                    "factions": {},
                },
                "events": [
                    {
                        "at": 9.0,
                        "sequence": 0,
                        "kind": "record",
                        "payload": {"value": "too-early"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncompatibleSaveError, match="before world time"):
        MacroCheckpointStore.read_into(live, path)

    assert live.pending_events() == pending
    assert live.world.history == history
    assert live.world.time_hours == pytest.approx(10.0)
    assert live.has_handler("extra")
    assert live.next_event_sequence() == 1


def test_corrupt_and_unsupported_payloads_are_rejected(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(IncompatibleSaveError, match="could not read"):
        MacroCheckpointStore.read_into(kernel, broken)

    unsupported = tmp_path / "unsupported.json"
    unsupported.write_text(
        json.dumps({"schema_version": 4, "world": {}, "events": []}),
        encoding="utf-8",
    )
    with pytest.raises(IncompatibleSaveError, match="unsupported"):
        MacroCheckpointStore.read_into(kernel, unsupported)

    array_root = tmp_path / "array.json"
    array_root.write_text("[]", encoding="utf-8")
    with pytest.raises(IncompatibleSaveError, match="object"):
        MacroCheckpointStore.read_into(kernel, array_root)

    fractional = tmp_path / "fraction.json"
    fractional.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "next_sequence": 1.5,
                "world": {
                    "time_hours": 10.0,
                    "history": [],
                    "settlements": {},
                    "factions": {},
                },
                "events": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncompatibleSaveError, match="integer"):
        MacroCheckpointStore.read_into(kernel, fractional)


def test_legacy_world_file_is_not_loaded_as_a_checkpoint(tmp_path) -> None:
    world_path = tmp_path / "world.json"
    WorldStateStore.write(_world(), world_path)
    kernel = SimulationKernel(_world())
    kernel.schedule(30.0, "wolf_attack", settlement_id="v")
    pending = kernel.pending_events()

    with pytest.raises(IncompatibleSaveError, match="malformed"):
        MacroCheckpointStore.read_into(kernel, world_path)
    assert kernel.pending_events() == pending


def test_custom_handler_must_be_registered_again_before_resume(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.register_handler(
        "record",
        lambda world, event: world.history.append("recorded"),
    )
    original.schedule(12.0, "record", value="note")
    original.advance_to(11.0)
    path = tmp_path / "checkpoint.json"
    MacroCheckpointStore.write(original, path)

    bare = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(bare, path)
    bare.advance_to(12.0)
    assert any("unhandled event record" in line for line in bare.world.history)

    resumed = SimulationKernel(WorldState())
    resumed.register_handler(
        "record",
        lambda world, event: world.history.append("recorded"),
    )
    MacroCheckpointStore.read_into(resumed, path)
    resumed.advance_to(12.0)
    assert resumed.world.history[-1] == "recorded"
