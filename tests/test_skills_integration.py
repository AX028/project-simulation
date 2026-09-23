"""Skill call-site audit and preservation regressions.

Call-site matrix:

- Spatial melee (``SpatialCombatResolver``): uses skill performance together
  with physiology and encumbrance. It does not award practice. Covered by
  ``test_melee_skill_changes_hit_chance``.
- Text-world ``attack``: uses that resolver, then awards one practice event
  when the attack was in reach. Hits use higher practice quality than misses.
  Out-of-reach and invalid commands award nothing.
- Text-world ``shoot``: awards one archery practice event after a shot is
  fired, including transfers. Aim, muzzle speed, and damage do not read
  archery performance. That split is current behavior, not a missing hook.
- Encounter combat (``combat.py``), spatial-encounter turns, NPC decisions,
  and planning do not read or train skills. That is unsupported, not a
  partial integration.
- ``SkillSet.practice`` is the training/instruction API. There is no separate
  lesson command. Instruction quality is covered by the existing skills tests.
- LOD abstraction and restoration deep-copy skill configuration, practice
  history, and spatial vectors so later edits cannot alias either side.
"""

import pytest

from project_simulation import (
    ActorLODManager,
    Loadout,
    Mind,
    Physiology,
    PracticeEvent,
    SimulationLOD,
    SkillSet,
    SkillState,
    SpatialEntity,
    Vec3,
    WorldActor,
    abstract_actor,
    build_demo_session,
    restore_actor,
)


def _close_enough_to_attack(session) -> None:
    session.execute("advance Wolf 5")


def test_out_of_reach_and_invalid_attacks_do_not_award_practice() -> None:
    missed_reach = build_demo_session(3)
    missed_reach.execute("attack Wolf")
    assert "sword" not in missed_reach.player.skills.skills

    invalid = build_demo_session(3)
    with pytest.raises(ValueError):
        invalid.execute("attack Aster")
    assert invalid.player.skills.skills == {}
    assert invalid.command_history == []


def test_each_in_reach_attack_awards_practice_once() -> None:
    session = build_demo_session(3)
    _close_enough_to_attack(session)
    session.execute("attack Wolf torso")
    session.execute("attack Wolf torso")

    counts = session.player.skills.skills["sword"].practice_counts
    assert sum(counts.values()) == 2


def test_misses_practice_and_grant_less_technique_than_hits() -> None:
    def technique(hit: bool) -> float:
        session = build_demo_session(3)
        _close_enough_to_attack(session)
        session.rng.random = lambda: 0.0 if hit else 0.999  # type: ignore[method-assign]
        session.execute("attack Wolf torso")
        sword = session.player.skills.skills["sword"]
        assert sum(sword.practice_counts.values()) == 1
        return sword.technique

    assert technique(True) > technique(False)


def test_failed_shots_do_not_award_practice() -> None:
    no_ammo = build_demo_session(4)
    no_ammo.ranged_weapons[no_ammo.player_id].ammunition = 0
    with pytest.raises(ValueError):
        no_ammo.execute("shoot Wolf")
    assert "archery" not in no_ammo.player.skills.skills

    bad_part = build_demo_session(4)
    with pytest.raises(ValueError):
        bad_part.execute("shoot Wolf tail")
    assert "archery" not in bad_part.player.skills.skills


def test_one_shot_awards_archery_practice_once_and_transfers_without_a_second_count() -> None:
    session = build_demo_session(4)
    session.execute("shoot Wolf torso")

    archery = session.player.skills.skills["archery"]
    throwing = session.player.skills.skills["throwing"]
    assert sum(archery.practice_counts.values()) == 1
    assert throwing.practice_counts == {}
    assert throwing.experience_hours > 0.0


def test_archery_performance_does_not_change_the_shot() -> None:
    def shot(level: float) -> str:
        session = build_demo_session(9)
        session.player.skills.skills["archery"] = SkillState(
            "archery",
            level,
            level,
            level,
        )
        return session.execute("shoot Wolf torso").output

    assert shot(0.0) == shot(100.0)


def test_transfer_weight_is_bounded_and_independent_of_mapping_order() -> None:
    with pytest.raises(ValueError):
        SkillSet(transfers={"sword": {"knife": 1.1}})

    event = PracticeEvent(
        difficulty=60.0,
        duration_hours=1.0,
        quality=1.0,
        context="forms",
    )

    def practice(items: tuple[tuple[str, float], ...]):
        skills = SkillSet(transfers={"sword": dict(items)})
        return skills.practice("sword", event)

    forward = practice((("knife", 0.1), ("spear", 0.2)))
    reverse = practice((("spear", 0.2), ("knife", 0.1)))
    assert forward == reverse

    full = practice((("knife", 1.0),))
    assert full.transfers[0].knowledge <= full.primary.knowledge + 1e-9
    assert full.transfers[0].technique <= full.primary.technique + 1e-9


def _skilled_actor() -> WorldActor:
    actor = WorldActor(
        SpatialEntity("actor", "Actor", Vec3(0.0, 0.0, 0.0)),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
    )
    actor.skills.learning_rate = 1.4
    actor.skills.baseline_level = 20.0
    actor.skills.transfers = {"archery": {"throwing": 0.2}}
    actor.skills.practice(
        "archery",
        PracticeEvent(
            difficulty=55.0,
            duration_hours=0.5,
            quality=0.8,
            context="range",
        ),
    )
    return actor


def test_lod_round_trip_preserves_skill_configuration_without_aliasing() -> None:
    actor = _skilled_actor()
    state = abstract_actor(actor, tier=SimulationLOD.REGION, now=4.0)
    restored = restore_actor(state)

    assert restored.skills.learning_rate == pytest.approx(1.4)
    assert restored.skills.baseline_level == pytest.approx(20.0)
    assert restored.skills.transfers == {"archery": {"throwing": 0.2}}
    assert restored.skills.skills["archery"].practice_counts == {"range": 1}
    assert restored.skills is not actor.skills
    assert restored.skills.transfers is not actor.skills.transfers
    assert (
        restored.skills.skills["archery"].practice_counts
        is not actor.skills.skills["archery"].practice_counts
    )

    restored.skills.learning_rate = 3.0
    restored.skills.transfers["archery"]["throwing"] = 0.9
    restored.skills.skills["archery"].practice_counts["range"] = 9
    restored.spatial.position = Vec3(12.0, 0.0, 0.0)
    state.position = Vec3(0.0, 6.0, 0.0)

    assert actor.skills.learning_rate == pytest.approx(1.4)
    assert actor.skills.transfers["archery"]["throwing"] == pytest.approx(0.2)
    assert actor.skills.skills["archery"].practice_counts["range"] == 1
    assert actor.spatial.position == Vec3(0.0, 0.0, 0.0)
    assert state.position is not actor.spatial.position
    assert restored.spatial.position is not state.position
    assert state.skills is not actor.skills


def test_lod_manager_transition_keeps_an_independent_skill_copy() -> None:
    actor = _skilled_actor()
    manager = ActorLODManager()
    manager.register(actor, tier=SimulationLOD.LOCAL)
    abstract = manager.transition(
        actor.actor_id,
        SimulationLOD.REGION,
        now=1.0,
    )
    abstract.skills.learning_rate = 9.0
    abstract.position = Vec3(4.0, 0.0, 0.0)

    assert actor.skills.learning_rate == pytest.approx(1.4)
    assert actor.spatial.position == Vec3(0.0, 0.0, 0.0)
    assert abstract.position is not actor.spatial.position

    restored = manager.transition(
        actor.actor_id,
        SimulationLOD.LOCAL,
        now=2.0,
    )
    assert isinstance(restored, WorldActor)
    assert restored.skills.learning_rate == pytest.approx(9.0)
    assert restored.skills.skills["archery"].practice_counts == {"range": 1}
    restored.skills.skills["archery"].practice_counts["range"] = 3
    assert abstract.skills.skills["archery"].practice_counts["range"] == 1
