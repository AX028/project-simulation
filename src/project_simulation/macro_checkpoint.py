"""Versioned macro checkpoint bundling world state and pending events.

The checkpoint is one generation: world time, settlements, factions, history,
the pending event queue, and the next event sequence number. Handlers are not
serialized. Register them on the destination kernel before advancing;
``SimulationKernel`` installs the built-in ``wolf_attack`` and
``faction_conflict`` handlers itself.

This format does not store text-world replay, actor or cognition snapshots, or
RNG state. Legacy ``WorldStateStore`` and ``EventQueueStore`` files stay
separate and are not rewritten here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import IncompatibleSaveError
from .simulation import (
    EventValue,
    FactionState,
    ScheduledEvent,
    SettlementState,
    SimulationKernel,
    WorldState,
)

MACRO_CHECKPOINT_SCHEMA_VERSION = 1


class MacroCheckpointStore:
    @staticmethod
    def write(kernel: SimulationKernel, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = _payload(kernel)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(destination)

    @staticmethod
    def read_into(kernel: SimulationKernel, path: str | Path) -> None:
        world, events, next_sequence = _parse(path)
        try:
            kernel.restore_macro_continuation(
                world,
                events,
                next_sequence=next_sequence,
            )
        except (TypeError, ValueError) as exc:
            raise IncompatibleSaveError(
                f"macro checkpoint failed validation: {exc}"
            ) from exc


def _payload(kernel: SimulationKernel) -> dict[str, Any]:
    world = kernel.world
    return {
        "schema_version": MACRO_CHECKPOINT_SCHEMA_VERSION,
        "next_event_sequence": kernel.next_event_sequence,
        "world": {
            "time_hours": world.time_hours,
            "history": list(world.history),
            "settlements": {
                key: {
                    "settlement_id": value.settlement_id,
                    "name": value.name,
                    "population": value.population,
                    "food_units": value.food_units,
                    "wealth": value.wealth,
                    "security": value.security,
                    "livestock": value.livestock,
                    "labor": value.labor,
                    "prices": value.prices,
                }
                for key, value in world.settlements.items()
            },
            "factions": {
                key: {
                    "faction_id": value.faction_id,
                    "name": value.name,
                    "members": value.members,
                    "wealth": value.wealth,
                    "military_power": value.military_power,
                    "territory": value.territory,
                    "relations": value.relations,
                    "institutional_memory": value.institutional_memory,
                }
                for key, value in world.factions.items()
            },
        },
        "events": [
            {
                "at": event.at,
                "sequence": event.sequence,
                "kind": event.kind,
                "payload": dict(sorted(event.payload.items())),
            }
            for event in kernel.pending_events()
        ],
    }


def _parse(
    path: str | Path,
) -> tuple[WorldState, tuple[ScheduledEvent, ...], int]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IncompatibleSaveError(
            f"could not read macro checkpoint: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise IncompatibleSaveError("macro checkpoint root must be an object")
    version = raw.get("schema_version")
    if (
        isinstance(version, bool)
        or version != MACRO_CHECKPOINT_SCHEMA_VERSION
    ):
        raise IncompatibleSaveError(
            f"unsupported macro checkpoint schema: {version}"
        )

    try:
        next_sequence = _require_int(
            raw["next_event_sequence"],
            "next event sequence",
        )
        if next_sequence < 0:
            raise ValueError("next event sequence may not be negative")
        world = _world_from_raw(raw["world"])
        events_raw = raw["events"]
        if not isinstance(events_raw, list):
            raise TypeError("events must be a list")
        events = tuple(_event_from_raw(item) for item in events_raw)
        return world, events, next_sequence
    except IncompatibleSaveError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise IncompatibleSaveError(
            f"malformed macro checkpoint payload: {exc}"
        ) from exc


def _world_from_raw(raw: object) -> WorldState:
    if not isinstance(raw, dict):
        raise TypeError("world must be an object")
    settlements = {
        key: SettlementState(
            settlement_id=value["settlement_id"],
            name=value["name"],
            population=_require_int(value["population"], "population"),
            food_units=float(value["food_units"]),
            wealth=float(value["wealth"]),
            security=float(value["security"]),
            livestock=float(value["livestock"]),
            labor={
                str(labor_key): _require_int(labor_value, "labor")
                for labor_key, labor_value in value["labor"].items()
            },
            prices={
                str(price_key): float(price_value)
                for price_key, price_value in value["prices"].items()
            },
        )
        for key, value in raw["settlements"].items()
    }
    factions = {
        key: FactionState(
            faction_id=value["faction_id"],
            name=value["name"],
            members=_require_int(value["members"], "members"),
            wealth=float(value["wealth"]),
            military_power=float(value["military_power"]),
            territory=float(value["territory"]),
            relations={
                str(relation_key): float(relation_value)
                for relation_key, relation_value in value["relations"].items()
            },
            institutional_memory={
                str(memory_key): float(memory_value)
                for memory_key, memory_value in value[
                    "institutional_memory"
                ].items()
            },
        )
        for key, value in raw["factions"].items()
    }
    return WorldState(
        time_hours=float(raw["time_hours"]),
        settlements=settlements,
        factions=factions,
        history=[str(item) for item in raw["history"]],
    )


def _event_from_raw(raw: object) -> ScheduledEvent:
    if not isinstance(raw, dict):
        raise TypeError("event must be an object")
    payload_raw = raw["payload"]
    if not isinstance(payload_raw, dict):
        raise TypeError("event payload must be an object")
    payload: dict[str, EventValue] = {}
    for key, value in payload_raw.items():
        if not isinstance(key, str):
            raise TypeError("event payload keys must be strings")
        if isinstance(value, bool):
            payload[key] = value
        elif isinstance(value, (str, int, float)):
            payload[key] = value
        else:
            raise TypeError("unsupported event payload value")
    kind = raw["kind"]
    if not isinstance(kind, str) or not kind:
        raise TypeError("event kind must be a non-empty string")
    return ScheduledEvent(
        at=float(raw["at"]),
        sequence=_require_int(raw["sequence"], "event sequence"),
        kind=kind,
        payload=payload,
    )


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value
