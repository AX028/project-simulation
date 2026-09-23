"""Versioned JSON persistence for persistent WORLDSTATE macro simulation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .models import IncompatibleSaveError
from .simulation import FactionState, SettlementState, WorldState

WORLDSTATE_SCHEMA_VERSION = 1


def world_state_to_mapping(world: WorldState) -> dict[str, Any]:
    """Return the world body shared by legacy saves and macro checkpoints."""
    return {
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
    }


def world_state_from_mapping(raw: Mapping[str, Any]) -> WorldState:
    """Rebuild a ``WorldState`` from the body written by ``world_state_to_mapping``."""
    if not isinstance(raw, Mapping):
        raise TypeError("world state must be an object")
    settlements = {
        key: SettlementState(
            settlement_id=value["settlement_id"],
            name=value["name"],
            population=int(value["population"]),
            food_units=float(value["food_units"]),
            wealth=float(value["wealth"]),
            security=float(value["security"]),
            livestock=float(value["livestock"]),
            labor={str(k): int(v) for k, v in value["labor"].items()},
            prices={str(k): float(v) for k, v in value["prices"].items()},
        )
        for key, value in raw["settlements"].items()
    }
    factions = {
        key: FactionState(
            faction_id=value["faction_id"],
            name=value["name"],
            members=int(value["members"]),
            wealth=float(value["wealth"]),
            military_power=float(value["military_power"]),
            territory=float(value["territory"]),
            relations={str(k): float(v) for k, v in value["relations"].items()},
            institutional_memory={
                str(k): float(v) for k, v in value["institutional_memory"].items()
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


class WorldStateStore:
    @staticmethod
    def write(world: WorldState, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "schema_version": WORLDSTATE_SCHEMA_VERSION,
            **world_state_to_mapping(world),
        }
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(destination)

    @staticmethod
    def read(path: str | Path) -> WorldState:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IncompatibleSaveError(f"could not read world state: {exc}") from exc

        if not isinstance(raw, dict):
            raise IncompatibleSaveError("world state root must be an object")
        version = raw.get("schema_version")
        if version != WORLDSTATE_SCHEMA_VERSION:
            raise IncompatibleSaveError(f"unsupported world state schema: {version}")

        try:
            return world_state_from_mapping(raw)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise IncompatibleSaveError(
                f"malformed world state payload: {exc}"
            ) from exc
