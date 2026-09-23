import json
from copy import deepcopy
from pathlib import Path
from typing import Any

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
                relations={"b": 0.25},
                institutional_memory={"treaty:b": 0.5},
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


def _checkpoint_payload(tmp_path) -> tuple[Path, dict[str, Any]]:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(kernel, path)
    return path, json.loads(path.read_text(encoding="utf-8"))


def _replace_path(
    payload: dict[str, Any],
    path: tuple[str | int, ...],
    value: object,
) -> None:
    target: Any = payload
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value


def test_checkpoint_resume_matches_uninterrupted_advance(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.schedule(12.0, "wolf_attack", settlement_id="v", severity=0.2)
    original.schedule(16.0, "faction_conflict", attacker="a", defender="b", scale=0.3)
    original.advance_to(11.0)
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(original, path)

    resumed = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(resumed, path)
    original.advance_to(20.0)
    resumed.advance_to(20.0)

    assert resumed.world == original.world
    assert resumed.pending_events() == original.pending_events()
    assert resumed.next_event_sequence == original.next_event_sequence


def test_equal_time_events_keep_order_after_resume(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.schedule(20.0, "record", value="first")
    original.schedule(20.0, "record", value="second")
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(original, path)

    resumed = SimulationKernel(_world())
    seen: list[str] = []

    def record(world: WorldState, event: ScheduledEvent) -> None:
        del world
        seen.append(str(event.payload["value"]))

    resumed.register_handler("record", record)
    MacroCheckpointStore.read_into(resumed, path)
    resumed.advance_to(20.0)

    assert seen == ["first", "second"]


def test_new_events_after_empty_queue_keep_the_saved_sequence(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.schedule(11.0, "wolf_attack", settlement_id="v", severity=0.1)
    original.advance_to(12.0)
    assert original.pending_events() == ()
    assert original.next_event_sequence == 1
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(original, path)

    resumed = SimulationKernel(WorldState(time_hours=0.0))
    MacroCheckpointStore.read_into(resumed, path)
    scheduled = resumed.schedule(13.0, "wolf_attack", settlement_id="v", severity=0.1)

    assert resumed.world.time_hours == pytest.approx(12.0)
    assert scheduled.sequence == 1


def test_custom_handler_must_be_registered_on_the_destination(tmp_path) -> None:
    original = SimulationKernel(_world())
    original.register_handler(
        "record",
        lambda world, event: world.history.append(str(event.payload["value"])),
    )
    original.schedule(12.0, "record", value="kept")
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(original, path)

    without_handler = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(without_handler, path)
    without_handler.advance_to(12.0)
    assert any("unhandled event record" in line for line in without_handler.world.history)

    with_handler = SimulationKernel(WorldState())
    with_handler.register_handler(
        "record",
        lambda world, event: world.history.append(str(event.payload["value"])),
    )
    MacroCheckpointStore.read_into(with_handler, path)
    with_handler.advance_to(12.0)
    assert with_handler.world.history[-1] == "kept"


def test_failed_write_preserves_the_previous_checkpoint(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    path = tmp_path / "macro.json"
    MacroCheckpointStore.write(kernel, path)
    previous = path.read_bytes()

    def fail_replace(self: Path, target: Path) -> Path:
        del self, target
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)
    kernel.schedule(30.0, "wolf_attack", settlement_id="v", severity=0.4)
    with pytest.raises(OSError, match="disk full"):
        MacroCheckpointStore.write(kernel, path)

    assert path.read_bytes() == previous
    restored = SimulationKernel(WorldState())
    MacroCheckpointStore.read_into(restored, path)
    assert len(restored.pending_events()) == 1


def test_corrupt_and_unsupported_checkpoints_are_rejected(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    before = kernel.pending_events()
    path = tmp_path / "macro.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(IncompatibleSaveError, match="could not read"):
        MacroCheckpointStore.read_into(kernel, path)
    assert kernel.pending_events() == before

    path.write_text(
        json.dumps({"schema_version": 999, "world": {}, "events": []}),
        encoding="utf-8",
    )
    with pytest.raises(IncompatibleSaveError, match="unsupported"):
        MacroCheckpointStore.read_into(kernel, path)
    assert kernel.pending_events() == before
    assert kernel.world.time_hours == pytest.approx(10.0)


def test_rejected_restore_leaves_the_live_kernel_unchanged(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", settlement_id="v", severity=0.2)
    kernel.world.history.append("already happened")
    before_events = kernel.pending_events()
    before_history = list(kernel.world.history)
    path = tmp_path / "macro.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "next_event_sequence": 0,
                "world": {
                    "time_hours": 10.0,
                    "history": [],
                    "settlements": {},
                    "factions": {},
                },
                "events": [
                    {
                        "at": 12.0,
                        "sequence": 0,
                        "kind": "record",
                        "payload": {},
                    },
                    {
                        "at": 13.0,
                        "sequence": 0,
                        "kind": "record",
                        "payload": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(IncompatibleSaveError, match="unique"):
        MacroCheckpointStore.read_into(kernel, path)

    assert kernel.pending_events() == before_events
    assert kernel.world.history == before_history
    assert kernel.world.time_hours == pytest.approx(10.0)
    assert "v" in kernel.world.settlements


@pytest.mark.parametrize(
    ("field_path", "invalid"),
    [
        pytest.param(("world", "time_hours"), float("nan"), id="world-time"),
        pytest.param(
            ("world", "settlements", "v", "food_units"),
            float("inf"),
            id="settlement-resource",
        ),
        pytest.param(
            ("world", "settlements", "v", "prices", "food"),
            float("-inf"),
            id="commodity-price",
        ),
        pytest.param(
            ("world", "factions", "a", "military_power"),
            float("nan"),
            id="faction-resource",
        ),
        pytest.param(
            ("world", "factions", "a", "relations", "b"),
            float("inf"),
            id="faction-relation",
        ),
        pytest.param(("events", 0, "at"), float("nan"), id="event-time"),
        pytest.param(
            ("events", 0, "payload", "severity"),
            float("inf"),
            id="event-payload",
        ),
    ],
)
def test_nonfinite_checkpoint_numbers_are_rejected(
    tmp_path,
    field_path: tuple[str | int, ...],
    invalid: float,
) -> None:
    path, payload = _checkpoint_payload(tmp_path)
    _replace_path(payload, field_path, invalid)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(IncompatibleSaveError, match="finite"):
        MacroCheckpointStore.read_into(SimulationKernel(_world()), path)


@pytest.mark.parametrize(
    ("field_path", "invalid"),
    [
        pytest.param(("world", "time_hours"), -1.0, id="negative-world-time"),
        pytest.param(
            ("world", "settlements", "v", "population"),
            -1,
            id="negative-population",
        ),
        pytest.param(
            ("world", "settlements", "v", "food_units"),
            -0.1,
            id="negative-food",
        ),
        pytest.param(
            ("world", "settlements", "v", "security"),
            10.1,
            id="security-above-range",
        ),
        pytest.param(
            ("world", "settlements", "v", "labor", "farmer"),
            -1,
            id="negative-labor",
        ),
        pytest.param(
            ("world", "settlements", "v", "prices", "food"),
            0.0,
            id="nonpositive-price",
        ),
        pytest.param(
            ("world", "factions", "a", "members"),
            -1,
            id="negative-members",
        ),
        pytest.param(
            ("world", "factions", "a", "territory"),
            -0.1,
            id="negative-territory",
        ),
        pytest.param(
            ("world", "factions", "a", "relations", "b"),
            1.1,
            id="relation-above-range",
        ),
        pytest.param(
            ("world", "factions", "a", "institutional_memory", "treaty:b"),
            -0.1,
            id="negative-memory",
        ),
        pytest.param(("events", 0, "at"), 9.0, id="event-before-world-time"),
        pytest.param(("events", 0, "sequence"), -1, id="negative-event-sequence"),
        pytest.param(("next_event_sequence",), -1, id="negative-next-sequence"),
    ],
)
def test_out_of_domain_checkpoint_numbers_are_rejected(
    tmp_path,
    field_path: tuple[str | int, ...],
    invalid: int | float,
) -> None:
    path, payload = _checkpoint_payload(tmp_path)
    _replace_path(payload, field_path, invalid)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(IncompatibleSaveError):
        MacroCheckpointStore.read_into(SimulationKernel(_world()), path)


@pytest.mark.parametrize("collection", ["settlements", "factions"])
def test_duplicate_world_entity_ids_are_rejected(tmp_path, collection: str) -> None:
    path, payload = _checkpoint_payload(tmp_path)
    entities = payload["world"][collection]
    entities["duplicate"] = deepcopy(next(iter(entities.values())))
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(IncompatibleSaveError, match="duplicate"):
        MacroCheckpointStore.read_into(SimulationKernel(_world()), path)


def test_domain_validation_failure_is_atomic_for_world_queue_and_sequence(
    tmp_path,
) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(30.0, "record", value="live")
    kernel.world.history.append("live history")
    original_world = kernel.world
    before_world = deepcopy(kernel.world)
    before_events = kernel.pending_events()
    before_sequence = kernel.next_event_sequence

    path, payload = _checkpoint_payload(tmp_path)
    payload["world"]["settlements"]["duplicate"] = deepcopy(
        payload["world"]["settlements"]["v"]
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(IncompatibleSaveError, match="duplicate settlement"):
        MacroCheckpointStore.read_into(kernel, path)

    assert kernel.world is original_world
    assert kernel.world == before_world
    assert kernel.pending_events() == before_events
    assert kernel.next_event_sequence == before_sequence


def test_legacy_world_store_is_not_a_macro_checkpoint(tmp_path) -> None:
    path = tmp_path / "world.json"
    WorldStateStore.write(_world(), path)
    kernel = SimulationKernel(_world())
    with pytest.raises(IncompatibleSaveError):
        MacroCheckpointStore.read_into(kernel, path)
    assert kernel.world.time_hours == pytest.approx(10.0)


def test_checkpoint_serialization_is_deterministic(tmp_path) -> None:
    kernel = SimulationKernel(_world())
    kernel.schedule(20.0, "wolf_attack", severity=0.5, settlement_id="v")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    MacroCheckpointStore.write(kernel, first)
    MacroCheckpointStore.write(kernel, second)
    assert first.read_bytes() == second.read_bytes()
