"""Atomic checkpoint of macro world state and the pending event queue.

The bundle is one generation: world time, settlements, factions, history,
pending events, and the next event sequence. Handler callables are not
stored. Register them on the live kernel before resuming; an event whose
kind has no handler keeps the kernel's existing unhandled-event behavior.

Actor, cognition, inventory, and RNG snapshots are outside this format, as
are text-world replay saves. Legacy ``WorldStateStore`` and
``EventQueueStore`` files remain valid for their own readers and are
rejected here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .event_persistence import (
    scheduled_event_from_payload,
    scheduled_event_payload,
)
from .models import IncompatibleSaveError
from .simulation import ScheduledEvent, SimulationKernel, WorldState
from .validation import finite_number
from .worldstate_persistence import (
    world_state_from_payload,
    world_state_payload,
)

MACRO_CHECKPOINT_SCHEMA_VERSION = 1
MACRO_CHECKPOINT_FORMAT = "macro-checkpoint"


class MacroCheckpointStore:
    @staticmethod
    def write(kernel: SimulationKernel, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "schema_version": MACRO_CHECKPOINT_SCHEMA_VERSION,
            "format": MACRO_CHECKPOINT_FORMAT,
            "world": world_state_payload(kernel.world),
            "events": [
                scheduled_event_payload(event)
                for event in kernel.pending_events()
            ],
            "next_sequence": kernel.next_event_sequence(),
        }
        encoded = json.dumps(data, indent=2, sort_keys=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(destination)

    @staticmethod
    def read_into(
        kernel: SimulationKernel,
        path: str | Path,
    ) -> tuple[ScheduledEvent, ...]:
        world, events, next_sequence = _load_checkpoint(path)
        previous_world = kernel.world
        previous_events = kernel.pending_events()
        previous_sequence = kernel.next_event_sequence()
        try:
            kernel.world = world
            kernel.replace_pending_events(
                events,
                next_sequence=next_sequence,
            )
        except Exception as exc:
            kernel.world = previous_world
            kernel.replace_pending_events(
                previous_events,
                next_sequence=previous_sequence,
            )
            raise IncompatibleSaveError(
                f"macro checkpoint could not be applied: {exc}"
            ) from exc
        return kernel.pending_events()


def _load_checkpoint(
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
    if raw.get("format") != MACRO_CHECKPOINT_FORMAT:
        raise IncompatibleSaveError("unsupported macro checkpoint format")
    version = raw.get("schema_version")
    if version != MACRO_CHECKPOINT_SCHEMA_VERSION:
        raise IncompatibleSaveError(
            f"unsupported macro checkpoint schema: {version}"
        )

    try:
        world_raw = raw["world"]
        if not isinstance(world_raw, dict):
            raise TypeError("world must be an object")
        world = world_state_from_payload(world_raw)
        finite_number(world.time_hours, "world time")

        raw_events = raw["events"]
        if not isinstance(raw_events, list):
            raise TypeError("events must be a list")
        events = tuple(
            _strict_event(item)
            for item in raw_events
        )
        next_sequence = _require_int(raw["next_sequence"], "next event sequence")
        if next_sequence < 0:
            raise ValueError("next event sequence may not be negative")

        sequences = [event.sequence for event in events]
        if len(sequences) != len(set(sequences)):
            raise ValueError("pending event sequence numbers must be unique")
        inferred = max(sequences, default=-1) + 1
        if next_sequence < inferred:
            raise ValueError(
                "next event sequence collides with a pending event"
            )
        for event in events:
            finite_number(event.at, "event time")
            if event.at < world.time_hours:
                raise ValueError(
                    "pending events may not occur before world time"
                )
    except IncompatibleSaveError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise IncompatibleSaveError(
            f"malformed macro checkpoint payload: {exc}"
        ) from exc
    return world, events, next_sequence


def _strict_event(raw: object) -> ScheduledEvent:
    if not isinstance(raw, dict):
        raise TypeError("event must be an object")
    if isinstance(raw.get("at"), bool) or not isinstance(
        raw.get("at"),
        (int, float),
    ):
        raise TypeError("event time must be a number")
    _require_int(raw.get("sequence"), "event sequence")
    return scheduled_event_from_payload(raw)


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value
