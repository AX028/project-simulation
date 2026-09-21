import json

import pytest

from project_simulation import (
    EventQueueStore,
    FactionState,
    SettlementState,
    SimulationKernel,
    WorldState,
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


def test_event_queue_round_trip_preserves_sorted_events(tmp_path) -> None:
    world = _world()
    kernel = SimulationKernel(world)
    kernel.schedule(50.0, "wolf_attack", settlement_id="v", severity=0.2)
    kernel.schedule(20.0, "daily_settlement", settlement_id="v")
    path = tmp_path / "events.json"

    EventQueueStore.write(kernel, path)

    restored = SimulationKernel(_world())
    events = EventQueueStore.read_into(restored, path)
    assert [event.at for event in events] == [20.0, 50.0]
    assert events == restored.pending_events()


def test_event_queue_serialization_is_deterministic(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", severity=0.5, settlement_id="v")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    EventQueueStore.write(kernel, first)
    EventQueueStore.write(kernel, second)
    assert first.read_bytes() == second.read_bytes()


def test_restored_builtin_events_produce_same_future_world(tmp_path) -> None:
    original_world = _world()
    original = SimulationKernel(original_world)
    original.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    original.schedule(30.0, "faction_conflict", attacker="a", defender="b", scale=0.3)

    path = tmp_path / "events.json"
    EventQueueStore.write(original, path)

    restored_world = _world()
    restored = SimulationKernel(restored_world)
    EventQueueStore.read_into(restored, path)

    original.advance_to(40.0)
    restored.advance_to(40.0)

    assert restored_world == original_world


def test_same_time_events_preserve_sequence_order_after_restore(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.schedule(20.0, "record", value="first")
    original.schedule(20.0, "record", value="second")
    path = tmp_path / "events.json"
    EventQueueStore.write(original, path)

    restored = SimulationKernel(_world())
    seen: list[str] = []

    def record(world, event) -> None:
        del world
        seen.append(str(event.payload["value"]))

    restored.register_handler("record", record)
    EventQueueStore.read_into(restored, path)
    restored.advance_to(20.0)
    assert seen == ["first", "second"]


def test_new_events_after_restore_use_fresh_sequence_number(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.schedule(20.0, "wolf_attack", settlement_id="v")
    original.schedule(30.0, "wolf_attack", settlement_id="v")
    path = tmp_path / "events.json"
    EventQueueStore.write(original, path)

    restored = SimulationKernel(_world())
    EventQueueStore.read_into(restored, path)
    new_event = restored.schedule(40.0, "wolf_attack", settlement_id="v")
    assert new_event.sequence == 2


def test_queue_rejects_event_before_world_time() -> None:
    kernel = SimulationKernel(_world())
    with pytest.raises(ValueError, match="before world time"):
        kernel.replace_pending_events(
            [ScheduledEvent(9.0, 0, "wolf_attack", {"settlement_id": "v"})]
        )


def test_queue_rejects_duplicate_sequences() -> None:
    kernel = SimulationKernel(_world())
    with pytest.raises(ValueError, match="unique"):
        kernel.replace_pending_events(
            [
                ScheduledEvent(20.0, 0, "wolf_attack", {"settlement_id": "v"}),
                ScheduledEvent(30.0, 0, "wolf_attack", {"settlement_id": "v"}),
            ]
        )


def test_load_rejects_mismatched_world_time(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    path = tmp_path / "events.json"
    EventQueueStore.write(kernel, path)

    other_world = _world()
    other_world.time_hours = 11.0
    other = SimulationKernel(other_world)
    with pytest.raises(IncompatibleSaveError, match="world time"):
        EventQueueStore.read_into(other, path)


def test_load_rejects_bad_schema(tmp_path) -> None:
    path = tmp_path / "events.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "world_time_hours": 10.0,
                "events": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncompatibleSaveError, match="unsupported"):
        EventQueueStore.read_into(SimulationKernel(_world()), path)


def test_thousand_event_round_trip_preserves_every_event(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    for index in range(1000):
        kernel.schedule(
            20.0 + index,
            "wolf_attack",
            settlement_id="v",
            severity=(index % 10) / 100.0,
        )
    path = tmp_path / "events.json"
    EventQueueStore.write(kernel, path)

    restored = SimulationKernel(_world())
    EventQueueStore.read_into(restored, path)

    assert restored.pending_events() == kernel.pending_events()
    assert len(restored.pending_events()) == 1000
