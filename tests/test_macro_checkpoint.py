"""Atomic macro-world checkpoints and continuation behavior."""

import json

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
        history=["10.0h: founded"],
    )


def _kernel() -> SimulationKernel:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    kernel.schedule(40.0, "wolf_attack", settlement_id="v", severity=0.1)
    kernel.schedule(
        60.0,
        "faction_conflict",
        attacker="a",
        defender="b",
        scale=0.2,
    )
    return kernel


def _snapshot(kernel: SimulationKernel):
    world = kernel.world
    return (
        world.time_hours,
        list(world.history),
        world.settlements["v"].livestock,
        kernel.pending_events(),
        kernel.next_event_sequence(),
    )


def test_checkpoint_resume_matches_uninterrupted_advancement(tmp_path) -> None:
    straight = _kernel()
    straight.advance_to(70.0)

    paused = _kernel()
    paused.advance_to(30.0)
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(paused, path)

    resumed = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(resumed, path)
    resumed.advance_to(70.0)

    assert resumed.world.time_hours == pytest.approx(straight.world.time_hours)
    assert resumed.world.history == straight.world.history
    assert resumed.world.settlements["v"].livestock == pytest.approx(
        straight.world.settlements["v"].livestock
    )
    assert resumed.world.factions["a"].members == straight.world.factions["a"].members
    assert resumed.pending_events() == straight.pending_events()
    assert resumed.next_event_sequence() == straight.next_event_sequence()


def test_equal_time_events_keep_sequence_order_across_reload(tmp_path) -> None:
    seen: list[str] = []

    def mark(world: WorldState, event: ScheduledEvent) -> None:
        del world
        seen.append(str(event.payload["label"]))

    original = SimulationKernel(_world())
    original.register_handler("mark", mark)
    original.schedule(15.0, "mark", label="first")
    original.schedule(15.0, "mark", label="second")
    path = tmp_path / "marks.json"
    MacroCheckpointStore.write(original, path)

    restored = SimulationKernel(_world())
    restored.register_handler("mark", mark)
    MacroCheckpointStore.read_into(restored, path)
    restored.advance_to(15.0)

    assert seen == ["first", "second"]


def test_new_events_after_reload_continue_the_saved_sequence(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(30.0, "wolf_attack", settlement_id="v", severity=0.1)
    kernel.schedule(12.0, "wolf_attack", settlement_id="v", severity=0.2)
    assert kernel.next_event_sequence() == 2
    kernel.advance_to(12.0)
    assert [event.sequence for event in kernel.pending_events()] == [0]
    assert kernel.next_event_sequence() == 2

    path = tmp_path / "gap.json"
    MacroCheckpointStore.write(kernel, path)
    restored = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(restored, path)
    restored.schedule(
        30.0,
        "faction_conflict",
        attacker="a",
        defender="b",
        scale=0.1,
    )

    assert [event.sequence for event in restored.pending_events()] == [0, 2]
    assert restored.next_event_sequence() == 3


def test_registered_handlers_survive_a_load(tmp_path) -> None:
    seen: list[str] = []
    kernel = SimulationKernel(_world())
    kernel.register_handler(
        "mark",
        lambda world, event: seen.append(str(event.payload["label"])),
    )
    kernel.schedule(13.0, "mark", label="kept")
    path = tmp_path / "handler.json"
    MacroCheckpointStore.write(kernel, path)
    kernel.advance_to(11.0)

    MacroCheckpointStore.read_into(kernel, path)
    assert kernel.has_handler("mark")
    kernel.advance_to(13.0)

    assert seen == ["kept"]


def test_checkpoint_bytes_are_deterministic(tmp_path) -> None:
    kernel = _kernel()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    MacroCheckpointStore.write(kernel, first)
    MacroCheckpointStore.write(kernel, second)
    assert first.read_bytes() == second.read_bytes()


def test_corrupt_and_unsupported_payloads_leave_the_kernel_unchanged(
    tmp_path,
) -> None:
    kernel = _kernel()
    before = _snapshot(kernel)

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{", encoding="utf-8")
    with pytest.raises(IncompatibleSaveError):
        MacroCheckpointStore.read_into(kernel, corrupt)
    assert _snapshot(kernel) == before

    unsupported = tmp_path / "new.json"
    MacroCheckpointStore.write(kernel, unsupported)
    raw = json.loads(unsupported.read_text(encoding="utf-8"))
    raw["schema_version"] = 2
    unsupported.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(IncompatibleSaveError, match="unsupported"):
        MacroCheckpointStore.read_into(kernel, unsupported)
    assert _snapshot(kernel) == before

    legacy = tmp_path / "legacy.json"
    WorldStateStore.write(kernel.world, legacy)
    with pytest.raises(IncompatibleSaveError, match="format"):
        MacroCheckpointStore.read_into(kernel, legacy)
    assert _snapshot(kernel) == before

    early = tmp_path / "early.json"
    MacroCheckpointStore.write(kernel, early)
    payload = json.loads(early.read_text(encoding="utf-8"))
    payload["events"][0]["at"] = 0.0
    early.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IncompatibleSaveError, match="world time"):
        MacroCheckpointStore.read_into(kernel, early)
    assert _snapshot(kernel) == before


def test_failed_write_preserves_the_previous_checkpoint(tmp_path) -> None:
    kernel = _kernel()
    path = tmp_path / "save.json"
    MacroCheckpointStore.write(kernel, path)
    original = path.read_bytes()
    path.with_suffix(path.suffix + ".tmp").mkdir()

    with pytest.raises(OSError):
        MacroCheckpointStore.write(kernel, path)

    assert path.read_bytes() == original
    restored = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(restored, path)
    assert restored.world.history == kernel.world.history
    assert restored.pending_events() == kernel.pending_events()


def test_legacy_event_store_remains_independent_of_checkpoints(tmp_path) -> None:
    kernel = _kernel()
    path = tmp_path / "events.json"
    EventQueueStore.write(kernel, path)
    restored = SimulationKernel(_world())
    EventQueueStore.read_into(restored, path)
    assert restored.pending_events() == kernel.pending_events()
