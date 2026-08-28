import random

from project_simulation import (
    EncounterState,
    UtilityDecisionPolicy,
    create_character,
    create_enemy,
    run_encounter,
)
from project_simulation.combat import CombatEngine
from project_simulation.models import CombatMode, CombatSnapshot


def _fight(seed: int) -> tuple[str | None, list[str]]:
    hero = create_character("ranger", "Iris", seed)
    enemy = create_enemy("goblin", 1, seed + 1)
    state = EncounterState({hero.actor_id: hero, enemy.actor_id: enemy})
    result = run_encounter(state, UtilityDecisionPolicy(), seed)
    return result.winner_id, result.events


def test_seeded_encounter_is_reproducible() -> None:
    assert _fight(22) == _fight(22)


def test_encounter_finishes_and_records_memory() -> None:
    hero = create_character("paladin", "Aster", 4)
    enemy = create_enemy("wolf", 1, 5)
    state = EncounterState({hero.actor_id: hero, enemy.actor_id: enemy})
    result = run_encounter(state, UtilityDecisionPolicy(), 4)
    assert result.winner_id in state.actors
    assert result.rounds > 0
    assert state.event_memory
    assert any("hit" in event or "fled" in event for event in result.events)


def test_policy_exposes_each_explicit_mode() -> None:
    actor = create_character("rogue", "Shade", 1)
    target = create_enemy("ogre", 1, 2)
    policy = UtilityDecisionPolicy()
    snapshot = CombatSnapshot(actor, target, 1, {})
    assert policy.classify_mode(snapshot) in {CombatMode.ENGAGE, CombatMode.DEFEND}
    for part in actor.body_parts.values():
        part.current_hp = max(1, int(part.max_hp * 0.1))
    assert policy.classify_mode(snapshot) is CombatMode.DESPERATE
    for part in actor.body_parts.values():
        part.current_hp = max(1, int(part.max_hp * 0.22))
    assert policy.classify_mode(snapshot) is CombatMode.FLEE


def test_resource_cost_and_cooldown_are_applied() -> None:
    from project_simulation import Action

    hero = create_character("wizard", "Rune", 2)
    enemy = create_enemy("slime", 1, 3)
    engine = CombatEngine(random.Random(2))
    state = EncounterState({hero.actor_id: hero, enemy.actor_id: enemy})
    before = hero.resources["mana"].current
    engine.resolve_turn(state, [Action(hero.actor_id, "firebolt", enemy.actor_id)])
    assert hero.resources["mana"].current < before
    assert hero.cooldowns.get("firebolt", 0) > 0 or not enemy.alive
