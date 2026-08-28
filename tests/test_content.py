import pytest

from project_simulation import CLASS_DEFINITIONS, ENEMY_DEFINITIONS, create_character, create_enemy
from project_simulation.models import ContentNotFoundError


def test_complete_rosters_are_constructible() -> None:
    assert len(CLASS_DEFINITIONS) == 6
    assert len(ENEMY_DEFINITIONS) == 12
    for class_id in CLASS_DEFINITIONS:
        actor = create_character(class_id, "Tester", seed=1)
        assert actor.class_id == class_id
        assert actor.abilities
        assert actor.alive
    for enemy_id in ENEMY_DEFINITIONS:
        enemy = create_enemy(enemy_id, 3, seed=1)
        assert enemy.enemy_id == enemy_id
        assert enemy.abilities
        assert enemy.alive


def test_invalid_content_has_helpful_error() -> None:
    with pytest.raises(ContentNotFoundError, match="unknown class"):
        create_character("accountant", "Nope")
    with pytest.raises(ContentNotFoundError, match="unknown enemy"):
        create_enemy("paperwork", 1)
