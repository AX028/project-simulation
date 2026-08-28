import json

import numpy as np
import pytest

from project_simulation import (
    GameState,
    WorldConfig,
    WorldStore,
    create_character,
    generate_world,
    load_game,
    save_game,
)
from project_simulation.models import IncompatibleSaveError


def test_world_is_deterministic_and_round_trips(tmp_path) -> None:
    config = WorldConfig(18, 13, 5)
    first = generate_world(config, 44)
    second = generate_world(config, 44)
    assert np.array_equal(first.terrain, second.terrain)
    path = tmp_path / "world.h5"
    WorldStore.write(first, path)
    restored = WorldStore.read(path)
    assert restored.config == config
    assert np.array_equal(restored.biome, first.biome)
    assert np.allclose(restored.temperature, first.temperature)


def test_campaign_round_trip(tmp_path) -> None:
    player = create_character("cleric", "Sol", 9)
    player.experience = 37
    player.body_parts["left_arm"].current_hp -= 3
    path = tmp_path / "campaign.json"
    save_game(GameState(9, 6, player, "world.h5", {"player": {"used:mend": 0.5}}), path)
    restored = load_game(path)
    assert restored.player.name == "Sol"
    assert restored.player.experience == 37
    assert (
        restored.player.body_parts["left_arm"].current_hp
        == player.body_parts["left_arm"].current_hp
    )
    assert restored.decision_memory == {"player": {"used:mend": 0.5}}


def test_bad_save_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    with pytest.raises(IncompatibleSaveError, match="unsupported"):
        load_game(path)
