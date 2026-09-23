"""Macro checkpoint: one generation of world state and pending events."""

import json
from pathlib import Path

import pytest

from project_simulation import (
    EventQueueStore,
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
        history=["founded"],
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


def _kernel() -> SimulationKernel:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    kernel.schedule(30.0, "faction_conflict", attacker="a", defender="b", scale=0.2)
    return kernel


def test_checkpoint_resume_matches_uninterrupted_advance(tmp_path) -> None:
    original = _kernel()
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(original, path)

    resumed = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(resumed, path)
    original.advance_to(40.0)
    resumed.advance_to(40.0)

    assert resumed.world == original.world
    assert resumed.pending_events() == ()


def test_equal_time_events_keep_sequence_order_after_restore(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    seen: list[str] = []

    def record(world: WorldState, event: ScheduledEvent) -> None:
        del world
        seen.append(str(event.payload["name"]))

    kernel.register_handler("record", record)
    kernel.schedule(20.0, "record", name="first")
    kernel.schedule(20.0, "record", name="second")
    path = tmp_path / "order.json"
    MacroCheckpointStore.write(kernel, path)

    restored = SimulationKernel(WorldState(time_hours=1.0))
    restored.world.history.append("untouched")
    MacroCheckpointStore.read_into(restored, path)
    assert restored.has_handler("record") is False
    restored.register_handler("record", record)
    restored.advance_to(20.0)

    assert seen == ["first", "second"]
    assert "untouched" not in restored.world.history


def test_new_schedule_after_reload_uses_the_next_sequence(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.1)
    kernel.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    path = tmp_path / "sequence.json"
    MacroCheckpointStore.write(kernel, path)

    restored = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(restored, path)
    scheduled = restored.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.3)

    assert scheduled.sequence == 2
    assert [event.sequence for event in restored.pending_events()] == [0, 1, 2]


def test_checkpoint_bytes_are_deterministic(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    MacroCheckpointStore.write(_kernel(), first)
    MacroCheckpointStore.write(_kernel(), second)
    assert first.read_bytes() == second.read_bytes()


def test_failed_write_preserves_the_previous_checkpoint(tmp_path, monkeypatch) -> None:
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(_kernel(), path)
    original = path.read_bytes()
    changed = _kernel()
    changed.world.history.append("later")

    def fail(self: Path, text: str, encoding: str = "utf-8") -> int:
        del self, text, encoding
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail)
    with pytest.raises(OSError, match="disk full"):
        MacroCheckpointStore.write(changed, path)

    assert path.read_bytes() == original
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_rejected_load_leaves_the_live_kernel_unchanged(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    live = _kernel()
    live.world.history.append("keep")
    pending = live.pending_events()
    history = list(live.world.history)

    with pytest.raises(IncompatibleSaveError, match="could not read"):
        MacroCheckpointStore.read_into(live, path)

    assert live.world.history == history
    assert live.pending_events() == pending
    assert live.world.time_hours == pytest.approx(10.0)


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 2, "world": {}, "events": []},
        {"schema_version": 1, "events": []},
        {
            "schema_version": 1,
            "world": {
                "time_hours": 10.0,
                "history": [],
                "settlements": {},
                "factions": {},
            },
            "events": [
                {"at": 9.0, "sequence": 0, "kind": "wolf_attack", "payload": {}},
            ],
        },
        {
            "schema_version": 1,
            "world": {
                "time_hours": 10.0,
                "history": [],
                "settlements": {},
                "factions": {},
            },
            "events": [
                {"at": 12.0, "sequence": 1, "kind": "note", "payload": {}},
                {"at": 13.0, "sequence": 1, "kind": "note", "payload": {}},
            ],
        },
    ],
)
def test_unsupported_or_corrupt_checkpoint_does_not_mutate_kernel(tmp_path, payload) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    live = _kernel()
    pending = live.pending_events()

    with pytest.raises(IncompatibleSaveError):
        MacroCheckpointStore.read_into(live, path)

    assert live.pending_events() == pending
    assert live.world.time_hours == pytest.approx(10.0)
    assert live.world.history == ["founded"]


def test_legacy_world_file_is_not_a_macro_checkpoint(tmp_path) -> None:
    path = tmp_path / "world.json"
    WorldStateStore.write(_world(), path)
    live = SimulationKernel(WorldState(time_hours=3.0))

    with pytest.raises(IncompatibleSaveError):
        MacroCheckpointStore.read_into(live, path)

    assert live.world.time_hours == pytest.approx(3.0)
    assert live.pending_events() == ()


def test_legacy_event_queue_still_round_trips_separately(tmp_path) -> None:
    kernel = _kernel()
    path = tmp_path / "events.json"
    EventQueueStore.write(kernel, path)
    other = SimulationKernel(_world())
    EventQueueStore.read_into(other, path)
    assert other.pending_events() == kernel.pending_events()
