"""Versioned checkpoint bundling macro world state and pending events.

One file is one generation: the ``WorldState`` body and the pending event
queue are written and replaced together. The kernel's built-in ``wolf_attack``
and ``faction_conflict`` handlers are recreated by ``SimulationKernel``. Every
other kind must be registered again with ``register_handler`` before
``advance_to``. The next sequence number is one past the highest stored
sequence, or zero when the queue is empty. Handlers themselves are not stored.

This checkpoint does not store replay documents, actor or cognition snapshots,
settlement markets, rumor state, schedules, or any RNG. Legacy
``WorldStateStore`` and ``EventQueueStore`` files stay separate and are not
rewritten. Calling ``bind_to_kernel`` after a restore schedules another
``daily_settlement`` series on top of events already in the queue.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .event_persistence import event_from_mapping
from .models import IncompatibleSaveError
from .simulation import ScheduledEvent, SimulationKernel, WorldState
from .worldstate_persistence import world_state_from_mapping, world_state_to_mapping

MACRO_CHECKPOINT_SCHEMA_VERSION = 1


class MacroCheckpointStore:
    @staticmethod
    def write(kernel: SimulationKernel, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "schema_version": MACRO_CHECKPOINT_SCHEMA_VERSION,
            "world": world_state_to_mapping(kernel.world),
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
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(data, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def read_into(kernel: SimulationKernel, path: str | Path) -> tuple[ScheduledEvent, ...]:
        """Replace ``kernel`` world and queue, or leave both unchanged on failure."""
        world, events = _load(path)
        previous_world = kernel.world
        previous_events = kernel.pending_events()
        try:
            kernel.world = world
            kernel.replace_pending_events(events)
        except Exception:
            kernel.world = previous_world
            kernel.replace_pending_events(previous_events)
            raise
        return kernel.pending_events()


def _load(path: str | Path) -> tuple[WorldState, tuple[ScheduledEvent, ...]]:
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
        world = world_state_from_mapping(raw["world"])
        raw_events = raw["events"]
        if not isinstance(raw_events, list):
            raise TypeError("events must be a list")
        events = tuple(event_from_mapping(item) for item in raw_events)
        SimulationKernel(world).replace_pending_events(events)
    except IncompatibleSaveError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise IncompatibleSaveError(
            f"malformed macro checkpoint payload: {exc}"
        ) from exc
    return world, events
