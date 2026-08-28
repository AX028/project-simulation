"""Versioned JSON campaign persistence."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .content import create_character
from .models import (
    Armor,
    GameState,
    IncompatibleSaveError,
    Item,
    Rarity,
    StatusEffect,
    Weapon,
)

SAVE_SCHEMA_VERSION = 1


def save_game(state: GameState, path: str | Path) -> None:
    payload = {
        "schema_version": SAVE_SCHEMA_VERSION,
        "seed": state.seed,
        "turn": state.turn,
        "world_path": state.world_path,
        "decision_memory": state.decision_memory,
        "rng_state": state.rng_state,
        "player": _player_to_dict(state.player),
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(destination)


def load_game(path: str | Path) -> GameState:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != SAVE_SCHEMA_VERSION:
            raise IncompatibleSaveError(
                "save schema "
                f"{payload.get('schema_version')!r} is unsupported; expected {SAVE_SCHEMA_VERSION}"
            )
        player_data = payload["player"]
        player = create_character(player_data["class_id"], player_data["name"], payload["seed"])
        player.level = int(player_data["level"])
        player.experience = int(player_data["experience"])
        player.stats = type(player.stats)(**player_data["stats"])
        for key, part in player_data["body_parts"].items():
            player.body_parts[key].current_hp = int(part["current_hp"])
            player.body_parts[key].max_hp = int(part["max_hp"])
        for key, pool in player_data["resources"].items():
            player.resources[key].current = int(pool["current"])
            player.resources[key].maximum = int(pool["maximum"])
        player.statuses = [StatusEffect(**effect) for effect in player_data["statuses"]]
        player.cooldowns = {key: int(value) for key, value in player_data["cooldowns"].items()}
        player.equipment = {
            key: _item_from_dict(value) for key, value in player_data["equipment"].items()
        }
        player.inventory = [_item_from_dict(value) for value in player_data["inventory"]]
        return GameState(
            seed=int(payload["seed"]),
            turn=int(payload["turn"]),
            player=player,
            world_path=payload.get("world_path"),
            decision_memory=payload.get("decision_memory", {}),
            rng_state=payload.get("rng_state"),
        )
    except IncompatibleSaveError:
        raise
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IncompatibleSaveError(f"could not load save: {exc}") from exc


def _player_to_dict(player: Any) -> dict[str, Any]:
    return {
        "class_id": player.class_id,
        "name": player.name,
        "level": player.level,
        "experience": player.experience,
        "stats": asdict(player.stats),
        "body_parts": {key: asdict(value) for key, value in player.body_parts.items()},
        "resources": {key: asdict(value) for key, value in player.resources.items()},
        "statuses": [asdict(effect) for effect in player.statuses],
        "cooldowns": player.cooldowns,
        "equipment": {key: _item_to_dict(value) for key, value in player.equipment.items()},
        "inventory": [_item_to_dict(value) for value in player.inventory],
    }


def _item_to_dict(item: Item) -> dict[str, Any]:
    data = asdict(item)
    data["kind"] = (
        "weapon" if isinstance(item, Weapon) else "armor" if isinstance(item, Armor) else "item"
    )
    return data


def _item_from_dict(data: dict[str, Any]) -> Item:
    values = dict(data)
    kind = values.pop("kind", "item")
    values["rarity"] = Rarity(values["rarity"])
    if kind == "weapon":
        from .models import DamageType

        values["damage_type"] = DamageType(values["damage_type"])
        return Weapon(**values)
    if kind == "armor":
        return Armor(**values)
    return Item(**values)
