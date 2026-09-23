"""Event-sourced save/load for deterministic text-world sessions.

Loading rebuilds ``build_demo_session(seed)`` and replays the stored commands.
It does not restore an arbitrary session. Schema 2 digests include
authoritative environment fields and each actor's skill configuration
(learning rate, baseline level, and transfer map). Derived environment
quantities are omitted. Out-of-band edits to those fields change the digest,
so a later load fails instead of dropping the edits.

Schema 1 digests omit environment and skill configuration. Those saves still
load, and their digests are checked with the schema 1 payload. A schema 1
digest is never accepted as a schema 2 identity.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import IncompatibleSaveError
from .skills import SkillSet
from .textworld import TextWorldSession, build_demo_session

TEXTWORLD_REPLAY_SCHEMA_VERSION = 2
_SUPPORTED_REPLAY_SCHEMAS = (1, TEXTWORLD_REPLAY_SCHEMA_VERSION)


def _skill_configuration(skills: SkillSet) -> dict[str, Any]:
    return {
        "learning_rate": round(skills.learning_rate, 9),
        "baseline_level": round(skills.baseline_level, 9),
        "transfers": {
            source: {
                target: round(weight, 9)
                for target, weight in sorted(mapping.items())
            }
            for source, mapping in sorted(skills.transfers.items())
        },
    }


def session_digest(
    session: TextWorldSession,
    *,
    schema_version: int | None = None,
) -> str:
    version = (
        TEXTWORLD_REPLAY_SCHEMA_VERSION
        if schema_version is None
        else schema_version
    )
    if version not in _SUPPORTED_REPLAY_SCHEMAS:
        raise ValueError(f"unsupported text-world replay schema: {version}")

    payload: dict[str, Any] = {
        "elapsed_seconds": round(session.elapsed_seconds, 9),
        "actors": {
            actor_id: {
                "position": [
                    round(actor.spatial.position.x, 9),
                    round(actor.spatial.position.y, 9),
                    round(actor.spatial.position.z, 9),
                ],
                "velocity": [
                    round(actor.spatial.velocity.x, 9),
                    round(actor.spatial.velocity.y, 9),
                    round(actor.spatial.velocity.z, 9),
                ],
                "fatigue": round(actor.physiology.fatigue, 9),
                "blood_lost_ml": round(actor.physiology.blood_lost_ml, 9),
                "hydration_l": round(actor.physiology.hydration_l, 9),
                "core_temperature_c": round(actor.physiology.core_temperature_c, 9),
                "skills": {
                    skill_id: {
                        "knowledge": round(skill.knowledge, 9),
                        "technique": round(skill.technique, 9),
                        "automaticity": round(skill.automaticity, 9),
                        "experience_hours": round(skill.experience_hours, 12),
                        "practice_counts": dict(
                            sorted(skill.practice_counts.items())
                        ),
                    }
                    for skill_id, skill in sorted(actor.skills.skills.items())
                },
                "injuries": [
                    {
                        "location": injury.location,
                        "type": injury.injury_type.value,
                        "severity": round(injury.severity, 9),
                        "bleeding": round(injury.bleeding_ml_per_min, 9),
                        "pain": round(injury.pain, 9),
                    }
                    for injury in actor.physiology.injuries
                ],
            }
            for actor_id, actor in sorted(session.actors.items())
        },
        "combat": {
            actor_id: {
                str(part): body.current_hp
                for part, body in sorted(
                    combatant.actor.body_parts.items(),
                    key=lambda item: str(item[0]),
                )
            }
            for actor_id, combatant in sorted(session.combatants.items())
        },
        "inventory": [
            {
                "id": item.item_id,
                "name": item.name,
                "mass_kg": round(item.mass_kg, 9),
                "volume_l": round(item.volume_l, 9),
                "length_m": round(item.length_m, 9),
            }
            for item in sorted(
                session.player.loadout.carried_loose,
                key=lambda value: value.item_id,
            )
        ],
        "doors": {
            door_id: {
                "open": door.is_open,
                "locked": door.locked,
                "integrity": round(door.integrity, 9),
                "destroyed": door.destroyed,
            }
            for door_id, door in sorted(session.doors.items())
        },
        "world_items": {
            item_id: {
                "name": item.name,
                "mass_kg": round(item.mass_kg, 9),
                "volume_l": round(item.volume_l, 9),
                "length_m": round(item.length_m, 9),
            }
            for item_id, item in sorted(session.world_items.items())
        },
        "scenery": {
            entity.entity_id: [
                round(entity.position.x, 9),
                round(entity.position.y, 9),
                round(entity.position.z, 9),
            ]
            for entity in sorted(session.scenery, key=lambda value: value.entity_id)
        },
        "ranged_weapons": {
            actor_id: {
                "name": weapon.name,
                "ammunition": weapon.ammunition,
                "shots_fired": weapon.shots_fired,
                "muzzle_speed_mps": round(weapon.muzzle_speed_mps, 9),
                "penetration_factor": round(weapon.penetration_factor, 9),
            }
            for actor_id, weapon in sorted(session.ranged_weapons.items())
        },
        "sound_events": [
            {
                "id": event.sound_id,
                "category": event.category,
                "description": event.description,
                "loudness_db_at_1m": round(event.loudness_db_at_1m, 9),
                "created_hour": round(event.created_hour, 12),
                "source_id": event.source_id,
                "position": [
                    round(event.position.x, 9),
                    round(event.position.y, 9),
                    round(event.position.z, 9),
                ],
            }
            for event in session.sound_events
        ],
        "heard_memories": {
            actor_id: [
                {
                    "subject": memory.subject,
                    "proposition": memory.proposition,
                    "confidence": round(memory.confidence, 9),
                    "accuracy": round(memory.accuracy, 9),
                    "created_at": round(memory.created_at, 12),
                }
                for memory in actor.mind.memories
                if memory.source == "hearing"
            ]
            for actor_id, actor in sorted(session.actors.items())
        },
        "kernel_time": (
            None
            if session.kernel is None
            else round(session.kernel.world.time_hours, 12)
        ),
        "transcript": list(session.transcript),
        "commands": list(session.command_history),
    }
    if version >= 2:
        environment = session.environment
        payload["environment"] = {
            "world_hour": round(environment.world_hour, 12),
            "weather": environment.weather.value,
            "base_temperature_c": round(environment.base_temperature_c, 9),
            "wind_velocity": [
                round(environment.wind_velocity.x, 9),
                round(environment.wind_velocity.y, 9),
                round(environment.wind_velocity.z, 9),
            ],
            "precipitation": round(environment.precipitation, 9),
            "cloud_cover": round(environment.cloud_cover, 9),
            "fog_density": round(environment.fog_density, 9),
            "ground_wetness": round(environment.ground_wetness, 9),
        }
        for actor_id, actor in session.actors.items():
            payload["actors"][actor_id]["skill_configuration"] = (
                _skill_configuration(actor.skills)
            )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class TextWorldReplayStore:
    @staticmethod
    def write(session: TextWorldSession, path: str | Path) -> None:
        if session.seed is None:
            raise ValueError("session seed is required for deterministic replay saves")

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": TEXTWORLD_REPLAY_SCHEMA_VERSION,
            "seed": session.seed,
            "commands": list(session.command_history),
            "digest": session_digest(session),
        }
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(destination)

    @staticmethod
    def read(path: str | Path) -> TextWorldSession:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IncompatibleSaveError(
                f"could not read text-world replay: {exc}"
            ) from exc

        if not isinstance(raw, dict):
            raise IncompatibleSaveError("text-world replay root must be an object")
        version = raw.get("schema_version")
        if version not in _SUPPORTED_REPLAY_SCHEMAS:
            raise IncompatibleSaveError(
                f"unsupported text-world replay schema: {version}"
            )

        try:
            seed = int(raw["seed"])
            commands_raw = raw["commands"]
            expected_digest = str(raw["digest"])
            if not isinstance(commands_raw, list):
                raise TypeError("commands must be a list")
            if not all(isinstance(command, str) for command in commands_raw):
                raise TypeError("every command must be a string")

            session = build_demo_session(seed)
            session.replay(tuple(commands_raw))
            actual_digest = session_digest(session, schema_version=int(version))
            if actual_digest != expected_digest:
                raise IncompatibleSaveError(
                    "replayed session does not match stored state digest"
                )
            return session
        except IncompatibleSaveError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise IncompatibleSaveError(
                f"malformed text-world replay payload: {exc}"
            ) from exc
