"""Event-sourced save/load for deterministic text-world sessions.

Reconstruction contract: a save is ``build_demo_session(seed)`` followed by
the recorded command history. The digest authenticates that result. It does
not make an arbitrarily mutated session reloadable. ``write`` rejects a
session whose digest cannot be reproduced from that pair, including custom
initial environment or skill configuration.

Schema 2 is the current digest. It adds authoritative environment fields and
per-actor skill configuration (learning rate, baseline level, and transfer
mappings). Derived environment properties and skill levels are omitted.
Schema 1 saves still load, checked with the original digest. A version 1
digest does not authenticate environment or skill configuration, and it is
never compared as if it were a version 2 digest.
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
SUPPORTED_TEXTWORLD_REPLAY_SCHEMAS = (1, 2)


def session_digest(
    session: TextWorldSession,
    *,
    schema_version: int = TEXTWORLD_REPLAY_SCHEMA_VERSION,
) -> str:
    if schema_version not in SUPPORTED_TEXTWORLD_REPLAY_SCHEMAS:
        raise ValueError(
            f"unsupported text-world replay schema: {schema_version}"
        )
    encoded = json.dumps(
        _digest_payload(session, schema_version),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _digest_payload(
    session: TextWorldSession,
    schema_version: int,
) -> dict[str, Any]:
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
                **(
                    {}
                    if schema_version < 2
                    else {
                        "skill_configuration": _skill_configuration(actor.skills),
                    }
                ),
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
    if schema_version >= 2:
        payload["environment"] = _environment_identity(session)
    return payload


def _skill_configuration(skills: SkillSet) -> dict[str, Any]:
    return {
        "learning_rate": round(skills.learning_rate, 9),
        "baseline_level": round(skills.baseline_level, 9),
        "transfers": {
            source: {
                target: round(weight, 9)
                for target, weight in sorted(targets.items())
            }
            for source, targets in sorted(skills.transfers.items())
        },
    }


def _environment_identity(session: TextWorldSession) -> dict[str, Any]:
    environment = session.environment
    wind = environment.wind_velocity
    return {
        "world_hour": round(environment.world_hour, 12),
        "weather": environment.weather.value,
        "base_temperature_c": round(environment.base_temperature_c, 9),
        "wind_velocity": [
            round(wind.x, 9),
            round(wind.y, 9),
            round(wind.z, 9),
        ],
        "precipitation": round(environment.precipitation, 9),
        "cloud_cover": round(environment.cloud_cover, 9),
        "fog_density": round(environment.fog_density, 9),
        "ground_wetness": round(environment.ground_wetness, 9),
    }


class TextWorldReplayStore:
    @staticmethod
    def write(session: TextWorldSession, path: str | Path) -> None:
        if session.seed is None:
            raise ValueError("session seed is required for deterministic replay saves")
        _require_demo_reconstruction(session)

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
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version not in SUPPORTED_TEXTWORLD_REPLAY_SCHEMAS
        ):
            raise IncompatibleSaveError(
                f"unsupported text-world replay schema: {version}"
            )
        if "custom_initial_state" in raw:
            raise IncompatibleSaveError(
                "custom initial state is not supported by text-world replay"
            )
        origin = raw.get("session_origin", "demo")
        if origin != "demo":
            raise IncompatibleSaveError(
                f"unsupported text-world session origin: {origin}"
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
            actual_digest = session_digest(session, schema_version=version)
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


def _require_demo_reconstruction(session: TextWorldSession) -> None:
    """Reject state that seed plus command history cannot reproduce."""
    if session.seed is None:
        raise ValueError("session seed is required for deterministic replay saves")
    reconstructed = build_demo_session(session.seed)
    reconstructed.replay(tuple(session.command_history))
    if session_digest(reconstructed) != session_digest(session):
        raise IncompatibleSaveError(
            "text-world replay cannot save custom initial state; "
            "only build_demo_session(seed) followed by its command history "
            "is supported"
        )
