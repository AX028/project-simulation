"""Versioned persistence for a SimulationKernel pending event queue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import IncompatibleSaveError
from .simulation import EventValue, ScheduledEvent, SimulationKernel

EVENT_QUEUE_SCHEMA_VERSION = 1


class EventQueueStore:
    @staticmethod
    def write(kernel: SimulationKernel, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "schema_version": EVENT_QUEUE_SCHEMA_VERSION,
            "world_time_hours": kernel.world.time_hours,
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
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(destination)

    @staticmethod
    def read_into(
        kernel: SimulationKernel,
        path: str | Path,
    ) -> tuple[ScheduledEvent, ...]:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IncompatibleSaveError(
                f"could not read event queue: {exc}"
            ) from exc

        if not isinstance(raw, dict):
            raise IncompatibleSaveError("event queue root must be an object")
        version = raw.get("schema_version")
        if version != EVENT_QUEUE_SCHEMA_VERSION:
            raise IncompatibleSaveError(
                f"unsupported event queue schema: {version}"
            )

        try:
            stored_time = float(raw["world_time_hours"])
            if abs(stored_time - kernel.world.time_hours) > 1e-9:
                raise IncompatibleSaveError(
                    "event queue world time does not match loaded world"
                )

            raw_events = raw["events"]
            if not isinstance(raw_events, list):
                raise TypeError("events must be a list")

            events = tuple(
                EventQueueStore._event_from_raw(item)
                for item in raw_events
            )
            kernel.replace_pending_events(events)
            return kernel.pending_events()
        except IncompatibleSaveError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise IncompatibleSaveError(
                f"malformed event queue payload: {exc}"
            ) from exc

    @staticmethod
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
            if not isinstance(value, (str, int, float, bool)):
                raise TypeError("unsupported event payload value")
            payload[key] = value

        kind = raw["kind"]
        if not isinstance(kind, str) or not kind:
            raise TypeError("event kind must be a non-empty string")

        return ScheduledEvent(
            at=float(raw["at"]),
            sequence=int(raw["sequence"]),
            kind=kind,
            payload=payload,
        )
