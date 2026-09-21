import random

import pytest

from project_simulation import (
    BodyPart,
    Loadout,
    Mind,
    PhysicalItem,
    Physiology,
    SpatialAction,
    SpatialCombatant,
    SpatialEncounterEngine,
    SpatialEncounterState,
    SpatialEntity,
    SpatialIntent,
    Vec3,
    WeaponPhysics,
    WorldActor,
    create_character,
    create_enemy,
)


def _world_actor(
    actor_id: str,
    name: str,
    position: Vec3,
    *,
    loaded: bool = False,
) -> WorldActor:
    load = (
        [PhysicalItem("load", "Heavy load", 30.0, 35.0)]
        if loaded
        else []
    )
    return WorldActor(
        SpatialEntity(actor_id, name, position),
        Mind(),
        Physiology(70.0),
        Loadout(70.0, carried_loose=load),
        movement_speed_mps=1.5,
    )


def _state(
    *,
    distance: float = 5.0,
    loaded_hero: bool = False,
) -> SpatialEncounterState:
    hero = create_character("ranger", "Hero", 1)
    enemy = create_enemy("goblin", 1, 2)
    hero.stats.accuracy = 1.4
    enemy.stats.accuracy = 1.4
    hero.stats.evasion = 0.0
    enemy.stats.evasion = 0.0

    weapon = WeaponPhysics(
        "sword",
        mass_kg=1.4,
        reach_m=0.9,
        handling=1.0,
        strike_speed_mps=12.0,
    )
    combatants = {
        hero.actor_id: SpatialCombatant(
            hero,
            _world_actor(
                hero.actor_id,
                hero.name,
                Vec3(0.0, 0.0, 0.0),
                loaded=loaded_hero,
            ),
            weapon,
        ),
        enemy.actor_id: SpatialCombatant(
            enemy,
            _world_actor(
                enemy.actor_id,
                enemy.name,
                Vec3(0.0, distance, 0.0),
            ),
            weapon,
        ),
    }
    return SpatialEncounterState(combatants)


def test_attack_out_of_reach_cannot_damage() -> None:
    state = _state(distance=5.0)
    ids = list(state.combatants)
    hero, enemy = ids[0], ids[1]
    before = state.combatants[enemy].actor.body_parts[BodyPart.TORSO].current_hp

    result = SpatialEncounterEngine(random.Random(1)).resolve_turn(
        state,
        (
            SpatialIntent(hero, enemy, SpatialAction.ATTACK, BodyPart.TORSO),
        ),
    )

    attack = result.events[0].attack
    assert attack is not None
    assert not attack.in_reach
    assert state.combatants[enemy].actor.body_parts[BodyPart.TORSO].current_hp == before


def test_advance_reduces_distance() -> None:
    state = _state(distance=5.0)
    hero, enemy = list(state.combatants)
    engine = SpatialEncounterEngine(random.Random(2), seconds_per_turn=1.0)

    result = engine.resolve_turn(
        state,
        (SpatialIntent(hero, enemy, SpatialAction.ADVANCE),),
    )

    event = result.events[0]
    assert event.distance_after_m < event.distance_before_m
    assert event.distance_after_m > 0.0


def test_retreat_increases_distance() -> None:
    state = _state(distance=2.0)
    hero, enemy = list(state.combatants)
    result = SpatialEncounterEngine(random.Random(3)).resolve_turn(
        state,
        (SpatialIntent(hero, enemy, SpatialAction.RETREAT),),
    )
    event = result.events[0]
    assert event.distance_after_m > event.distance_before_m


def test_loaded_actor_advances_less_distance() -> None:
    light = _state(distance=10.0, loaded_hero=False)
    heavy = _state(distance=10.0, loaded_hero=True)
    light_hero, light_enemy = list(light.combatants)
    heavy_hero, heavy_enemy = list(heavy.combatants)

    light_result = SpatialEncounterEngine(random.Random(4)).resolve_turn(
        light,
        (SpatialIntent(light_hero, light_enemy, SpatialAction.ADVANCE),),
    )
    heavy_result = SpatialEncounterEngine(random.Random(4)).resolve_turn(
        heavy,
        (SpatialIntent(heavy_hero, heavy_enemy, SpatialAction.ADVANCE),),
    )

    light_move = (
        light_result.events[0].distance_before_m
        - light_result.events[0].distance_after_m
    )
    heavy_move = (
        heavy_result.events[0].distance_before_m
        - heavy_result.events[0].distance_after_m
    )
    assert heavy_move < light_move


def test_multi_turn_advance_then_attack_creates_injury() -> None:
    state = _state(distance=4.0)
    hero, enemy = list(state.combatants)
    engine = SpatialEncounterEngine(random.Random(5))

    for _ in range(3):
        engine.resolve_turn(
            state,
            (SpatialIntent(hero, enemy, SpatialAction.ADVANCE),),
        )

    result = engine.resolve_turn(
        state,
        (
            SpatialIntent(
                hero,
                enemy,
                SpatialAction.ATTACK,
                BodyPart.LEFT_LEG,
            ),
        ),
    )
    attack = result.events[0].attack
    assert attack is not None
    assert attack.in_reach
    assert attack.hit
    assert state.combatants[enemy].world_actor.physiology.injuries


def test_initiative_is_seeded_and_reproducible() -> None:
    def run() -> tuple[str, ...]:
        state = _state(distance=1.0)
        hero, enemy = list(state.combatants)
        engine = SpatialEncounterEngine(random.Random(42))
        result = engine.resolve_turn(
            state,
            (
                SpatialIntent(hero, enemy, SpatialAction.ATTACK),
                SpatialIntent(enemy, hero, SpatialAction.ATTACK),
            ),
        )
        return tuple(event.actor_id for event in result.events)

    assert run() == run()


def test_dead_actor_is_not_allowed_to_continue_affecting_turn() -> None:
    state = _state(distance=1.0)
    hero, enemy = list(state.combatants)
    target = state.combatants[enemy].actor
    target.body_parts[BodyPart.TORSO].current_hp = 1
    state.combatants[hero].actor.stats.strength = 100
    engine = SpatialEncounterEngine(random.Random(1))

    result = engine.resolve_turn(
        state,
        (
            SpatialIntent(hero, enemy, SpatialAction.ATTACK, BodyPart.TORSO),
            SpatialIntent(enemy, hero, SpatialAction.ATTACK, BodyPart.TORSO),
        ),
    )

    assert result.winner_id == hero
    assert not target.alive


def test_duplicate_actor_intents_are_rejected() -> None:
    state = _state()
    hero, enemy = list(state.combatants)
    engine = SpatialEncounterEngine(random.Random(1))
    with pytest.raises(ValueError, match="one intent"):
        engine.resolve_turn(
            state,
            (
                SpatialIntent(hero, enemy, SpatialAction.ADVANCE),
                SpatialIntent(hero, enemy, SpatialAction.ATTACK),
            ),
        )


def test_self_target_is_rejected() -> None:
    state = _state()
    hero = list(state.combatants)[0]
    engine = SpatialEncounterEngine(random.Random(1))
    with pytest.raises(ValueError, match="differ"):
        engine.resolve_turn(
            state,
            (SpatialIntent(hero, hero, SpatialAction.ADVANCE),),
        )


def test_fifty_turn_replay_is_deterministic() -> None:
    def simulate() -> tuple[
        tuple[str, ...],
        tuple[tuple[str, float, float, float], ...],
    ]:
        state = _state(distance=12.0)
        hero, enemy = list(state.combatants)
        engine = SpatialEncounterEngine(random.Random(99))
        log: list[str] = []

        for _ in range(50):
            if state.winner_id is not None:
                break
            distance = (
                state.combatants[hero]
                .world_actor.spatial.position.distance_to(
                    state.combatants[enemy].world_actor.spatial.position
                )
            )
            if distance > state.combatants[hero].effective_reach_m:
                hero_action = SpatialAction.ADVANCE
            else:
                hero_action = SpatialAction.ATTACK

            if distance > state.combatants[enemy].effective_reach_m:
                enemy_action = SpatialAction.ADVANCE
            else:
                enemy_action = SpatialAction.ATTACK

            result = engine.resolve_turn(
                state,
                (
                    SpatialIntent(hero, enemy, hero_action),
                    SpatialIntent(enemy, hero, enemy_action),
                ),
            )
            log.extend(event.text for event in result.events)

        summary = tuple(
            (
                actor_id,
                combatant.world_actor.spatial.position.x,
                combatant.world_actor.spatial.position.y,
                combatant.world_actor.physiology.blood_lost_ml,
            )
            for actor_id, combatant in sorted(state.combatants.items())
        )
        return tuple(log), summary

    assert simulate() == simulate()
