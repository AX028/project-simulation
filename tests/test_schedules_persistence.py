import json

import pytest

from project_simulation import (
    FactionState,
    RoutineBlock,
    RoutineSchedule,
    SettlementState,
    WorldState,
    WorldStateStore,
)
from project_simulation.models import IncompatibleSaveError


def test_routine_schedule_handles_day_and_overnight_blocks() -> None:
    schedule = RoutineSchedule(
        (
            RoutineBlock(6.0, 8.0, "breakfast", "home"),
            RoutineBlock(8.0, 17.0, "work", "forge"),
            RoutineBlock(22.0, 6.0, "sleep", "home"),
        )
    )
    assert schedule.activity_at(7.0).activity == "breakfast"
    assert schedule.activity_at(12.0).activity == "work"
    assert schedule.activity_at(23.0).activity == "sleep"
    assert schedule.activity_at(3.0).activity == "sleep"


def test_routine_schedule_returns_next_transition() -> None:
    schedule = RoutineSchedule(
        (
            RoutineBlock(8.0, 12.0, "work", "field"),
            RoutineBlock(13.0, 17.0, "work", "field"),
        )
    )
    assert schedule.next_transition_after(9.0) == 12.0
    assert schedule.next_transition_after(12.5) == 13.0
    assert schedule.next_transition_after(23.0) == 32.0


def test_equal_priority_overlap_is_rejected() -> None:
    with pytest.raises(ValueError, match="overlapping"):
        RoutineSchedule(
            (
                RoutineBlock(8.0, 12.0, "work", "field", priority=1.0),
                RoutineBlock(10.0, 14.0, "shop", "market", priority=1.0),
            )
        )


def _world_state() -> WorldState:
    return WorldState(
        time_hours=314.5,
        settlements={
            "mera": SettlementState(
                "mera",
                "Mera",
                population=220,
                food_units=450.5,
                wealth=1820.0,
                security=7.0,
                livestock=91.0,
                labor={"farmer": 90, "smith": 2},
                prices={"food": 1.2, "meat": 1.7, "leather": 1.4},
            )
        },
        factions={
            "guild": FactionState(
                "guild",
                "Iron Guild",
                members=43,
                wealth=9000.0,
                military_power=12.0,
                territory=3.5,
                relations={"crown": 0.25},
                institutional_memory={"betrayal:crown": 0.4},
            )
        },
        history=["12.0h: market opened", "300.0h: wolves attacked"],
    )


def test_worldstate_round_trip_preserves_macro_state(tmp_path) -> None:
    path = tmp_path / "worldstate.json"
    original = _world_state()
    WorldStateStore.write(original, path)
    restored = WorldStateStore.read(path)
    assert restored == original


def test_worldstate_serialization_is_deterministic(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    world = _world_state()
    WorldStateStore.write(world, first)
    WorldStateStore.write(world, second)
    assert first.read_bytes() == second.read_bytes()


def test_worldstate_bad_schema_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    with pytest.raises(IncompatibleSaveError, match="unsupported"):
        WorldStateStore.read(path)


def test_worldstate_malformed_payload_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "time_hours": 0,
                "settlements": {"x": {"name": "missing fields"}},
                "factions": {},
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncompatibleSaveError, match="malformed"):
        WorldStateStore.read(path)
