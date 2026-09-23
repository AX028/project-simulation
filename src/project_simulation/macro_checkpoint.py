"""Atomic checkpoint of macro world state and the pending event queue.

A checkpoint is one generation: world time, settlements, factions, history,
pending events, and the next event sequence. It is not a text-world replay
save and does not store actors, cognition, skills, inventories, environment,
or RNG state.

Custom event handlers are not stored. ``SimulationKernel`` restores its
builtin handlers. Re-register any other handler on the destination kernel
before advancing, or that event is recorded as unhandled. Validation finishes
before the live kernel is changed. A failed write leaves an existing file
in place.
"""

from __future__ import annotations

import json
from pathlib import Path

from .event_persistence import event_from_dict, event_to_dict
from .models import IncompatibleSaveError
from .simulation import ScheduledEvent, SimulationKernel, WorldState
from .worldstate_persistence import world_from_dict, world_to_dict

MACRO_CHECKPOINT_SCHEMA_VERSION = 1


def _whole_sequence(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("next event sequence must be an integer")
    number = float(value)
    if not number.is_integer():
        raise ValueError("next event sequence must be an integer")
    if number < 0:
        raise ValueError("next event sequence may not be negative")
    return int(number)


class MacroCheckpointStore:
    @staticmethod
    def write(kernel: SimulationKernel, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": MACRO_CHECKPOINT_SCHEMA_VERSION,
            "next_sequence": kernel.next_event_sequence(),
            "world": world_to_dict(kernel.world),
            "events": [event_to_dict(event) for event in kernel.pending_events()],
        }
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(destination)

    @staticmethod
    def read_into(kernel: SimulationKernel, path: str | Path) -> None:
        world, events, next_sequence = MacroCheckpointStore._parse(path)
        try:
            kernel.load_continuation(world, events, next_sequence)
        except (TypeError, ValueError) as exc:
            raise IncompatibleSaveError(
                f"malformed macro checkpoint payload: {exc}"
            ) from exc

    @staticmethod
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
        if version != MACRO_CHECKPOINT_SCHEMA_VERSION:
            raise IncompatibleSaveError(
                f"unsupported macro checkpoint schema: {version}"
            )

        try:
            world = world_from_dict(raw["world"])
            events_raw = raw["events"]
            if not isinstance(events_raw, list):
                raise TypeError("events must be a list")
            events = tuple(event_from_dict(item) for item in events_raw)
            next_sequence = _whole_sequence(raw["next_sequence"])
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise IncompatibleSaveError(
                f"malformed macro checkpoint payload: {exc}"
            ) from exc
        return world, events, next_sequence
