import random

import pytest

from project_simulation import (
    Loadout,
    Mind,
    Physiology,
    PracticeEvent,
    SimulationLOD,
    SkillSet,
    SkillState,
    SpatialCombatResolver,
    SpatialEntity,
    Vec3,
    WorldActor,
    abstract_actor,
    build_demo_session,
    restore_actor,
    session_digest,
)


def test_untracked_skill_uses_neutral_baseline_modifier() -> None:
    skills = SkillSet()
    assert skills.level("sword") == pytest.approx(50.0)
    assert skills.performance_modifier("sword") == pytest.approx(1.0)


def test_practice_increases_skill_components_and_experience() -> None:
    skills = SkillSet()
    result = skills.practice(
        "sword",
        PracticeEvent(
            difficulty=60.0,
            duration_hours=1.0,
            quality=0.9,
            context="sparring",
        ),
    )
    state = skills.skills["sword"]

    assert result.primary.total_component_gain > 0
    assert state.level > 50.0
    assert state.experience_hours == pytest.approx(1.0)
    assert state.practice_counts["sparring"] == 1


def test_repeated_context_loses_novelty() -> None:
    skills = SkillSet()
    event = PracticeEvent(
        difficulty=60.0,
        duration_hours=0.5,
        quality=0.8,
        context="same-drill",
    )

    first = skills.practice("sword", event)
    second = skills.practice("sword", event)
    for _ in range(20):
        last = skills.practice("sword", event)

    assert second.novelty_factor < first.novelty_factor
    assert last.novelty_factor < second.novelty_factor


def test_instruction_biases_gain_toward_knowledge() -> None:
    self_taught = SkillSet()
    instructed = SkillSet()
    base = dict(
        difficulty=60.0,
        duration_hours=1.0,
        quality=0.8,
        context="lesson",
    )

    self_gain = self_taught.practice(
        "medicine",
        PracticeEvent(**base, instruction=0.0),
    )
    taught_gain = instructed.practice(
        "medicine",
        PracticeEvent(**base, instruction=1.0),
    )

    assert taught_gain.primary.knowledge > self_gain.primary.knowledge
    assert taught_gain.primary.technique == pytest.approx(
        self_gain.primary.technique
    )


def test_matched_challenge_teaches_more_than_trivial_task() -> None:
    trivial = SkillSet()
    matched = SkillSet()

    trivial_result = trivial.practice(
        "tracking",
        PracticeEvent(
            difficulty=0.0,
            duration_hours=1.0,
            quality=1.0,
            context="trail",
        ),
    )
    matched_result = matched.practice(
        "tracking",
        PracticeEvent(
            difficulty=60.0,
            duration_hours=1.0,
            quality=1.0,
            context="trail",
        ),
    )

    assert matched_result.difficulty_factor > trivial_result.difficulty_factor
    assert (
        matched_result.primary.total_component_gain
        > trivial_result.primary.total_component_gain
    )


def test_related_skill_transfer_does_not_grant_automaticity() -> None:
    skills = SkillSet()
    result = skills.practice(
        "sword",
        PracticeEvent(
            difficulty=60.0,
            duration_hours=1.0,
            quality=1.0,
            context="duel",
        ),
    )

    transfers = {gain.skill_id: gain for gain in result.transfers}
    assert "greatsword" in transfers
    assert transfers["greatsword"].knowledge > 0
    assert transfers["greatsword"].technique > 0
    assert transfers["greatsword"].automaticity == 0
    assert skills.skills["greatsword"].automaticity == pytest.approx(50.0)


def test_skill_performance_modifier_tracks_level() -> None:
    skills = SkillSet(
        skills={
            "low": SkillState("low", 0.0, 0.0, 0.0),
            "high": SkillState("high", 100.0, 100.0, 100.0),
        }
    )
    assert skills.performance_modifier("low") == pytest.approx(0.5)
    assert skills.performance_modifier("high") == pytest.approx(1.5)


def test_performance_combines_skill_physiology_and_context() -> None:
    skills = SkillSet(
        skills={"sword": SkillState("sword", 75.0, 75.0, 75.0)}
    )
    full = skills.performance_modifier("sword")
    impaired = skills.performance_modifier(
        "sword",
        physiology_modifier=0.7,
        context_modifier=0.8,
    )
    assert impaired < full


@pytest.mark.parametrize(
    "event",
    [
        lambda: PracticeEvent(-1.0, 1.0),
        lambda: PracticeEvent(101.0, 1.0),
        lambda: PracticeEvent(50.0, 0.0),
        lambda: PracticeEvent(50.0, 1.0, quality=1.1),
        lambda: PracticeEvent(50.0, 1.0, instruction=-0.1),
        lambda: PracticeEvent(50.0, 1.0, context=""),
    ],
)
def test_invalid_practice_events_are_rejected(event) -> None:
    with pytest.raises(ValueError):
        event()


def test_thousands_of_practices_remain_bounded() -> None:
    skills = SkillSet()
    for _ in range(3000):
        skills.practice(
            "sword",
            PracticeEvent(
                difficulty=55.0,
                duration_hours=1.0 / 60.0,
                quality=0.8,
                context="repeated-drill",
            ),
        )

    for state in skills.skills.values():
        assert 0.0 <= state.knowledge <= 100.0
        assert 0.0 <= state.technique <= 100.0
        assert 0.0 <= state.automaticity <= 100.0
        assert state.experience_hours >= 0.0


def test_lod_round_trip_preserves_skills() -> None:
    actor = WorldActor(
        SpatialEntity("actor", "Actor", Vec3(0.0, 0.0, 0.0)),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
    )
    actor.skills.practice(
        "tracking",
        PracticeEvent(
            difficulty=65.0,
            duration_hours=2.0,
            quality=0.9,
            context="forest",
        ),
    )

    state = abstract_actor(
        actor,
        tier=SimulationLOD.REGION,
        now=10.0,
    )
    restored = restore_actor(state)

    assert restored.skills == actor.skills


def test_melee_skill_changes_hit_chance() -> None:
    low = build_demo_session(70)
    high = build_demo_session(70)
    for session in (low, high):
        target_id = next(
            actor_id
            for actor_id, actor in session.actors.items()
            if actor.spatial.name == "Wolf"
        )
        session.player.spatial.position = Vec3(0.0, 7.0, 0.0)
        session.actors[target_id].spatial.position = Vec3(0.0, 8.0, 0.0)

    low.player.skills.skills["sword"] = SkillState(
        "sword",
        0.0,
        0.0,
        0.0,
    )
    high.player.skills.skills["sword"] = SkillState(
        "sword",
        100.0,
        100.0,
        100.0,
    )
    low_target = next(
        key for key, value in low.actors.items() if value.spatial.name == "Wolf"
    )
    high_target = next(
        key for key, value in high.actors.items() if value.spatial.name == "Wolf"
    )

    low_result = SpatialCombatResolver(random.Random(5)).resolve_attack(
        low.combatants[low.player_id],
        low.combatants[low_target],
    )
    high_result = SpatialCombatResolver(random.Random(5)).resolve_attack(
        high.combatants[high.player_id],
        high.combatants[high_target],
    )

    assert high_result.hit_chance > low_result.hit_chance


def test_textworld_melee_attack_trains_sword_skill() -> None:
    session = build_demo_session(71)
    session.execute("advance Wolf 5")
    assert "sword" not in session.player.skills.skills

    session.execute("attack Wolf torso")

    sword = session.player.skills.skills["sword"]
    assert sword.experience_hours > 0
    assert sword.practice_counts


def test_textworld_shoot_trains_archery_skill() -> None:
    session = build_demo_session(72)
    assert "archery" not in session.player.skills.skills

    session.execute("shoot Wolf torso")

    archery = session.player.skills.skills["archery"]
    assert archery.experience_hours > 0
    assert archery.practice_counts


def test_skill_progression_participates_in_replay_digest() -> None:
    untouched = build_demo_session(73)
    practiced = build_demo_session(73)
    practiced.player.skills.practice(
        "tracking",
        PracticeEvent(
            difficulty=60.0,
            duration_hours=1.0,
            context="forest",
        ),
    )
    assert session_digest(practiced) != session_digest(untouched)


def test_combat_skill_progression_is_replay_deterministic() -> None:
    commands = (
        "advance Wolf 5",
        "attack Wolf torso",
        "shoot Wolf torso",
    )
    first = build_demo_session(74)
    second = build_demo_session(74)

    assert first.replay(commands) == second.replay(commands)
    assert first.player.skills == second.player.skills
    assert session_digest(first) == session_digest(second)


def test_unreachable_and_invalid_attacks_do_not_grant_practice() -> None:
    session = build_demo_session(75)
    session.execute("attack Wolf torso")
    assert session.player.skills.skills == {}

    with pytest.raises(ValueError, match="unknown actor"):
        session.execute("attack Nobody")
    with pytest.raises(ValueError, match="body_part"):
        session.execute("attack Wolf not_a_limb")
    assert session.player.skills.skills == {}


def test_in_reach_attack_awards_practice_once_per_action() -> None:
    session = build_demo_session(76)
    session.execute("advance Wolf 5")
    session.execute("attack Wolf torso")
    sword = session.player.skills.skills["sword"]
    assert sum(sword.practice_counts.values()) == 1

    session.execute("attack Wolf torso")
    assert sum(session.player.skills.skills["sword"].practice_counts.values()) == 2


def test_invalid_shot_does_not_train_archery() -> None:
    session = build_demo_session(77)
    with pytest.raises(ValueError, match="unknown actor"):
        session.execute("shoot Nobody")
    assert "archery" not in session.player.skills.skills


def test_archery_practice_does_not_change_the_geometric_shot() -> None:
    low = build_demo_session(14)
    high = build_demo_session(14)
    low.player.skills.skills["archery"] = SkillState("archery", 0.0, 0.0, 0.0)
    high.player.skills.skills["archery"] = SkillState(
        "archery",
        100.0,
        100.0,
        100.0,
    )

    assert low.execute("shoot Wolf torso").output == high.execute(
        "shoot Wolf torso"
    ).output
    assert sum(low.player.skills.skills["archery"].practice_counts.values()) == 1
    assert sum(high.player.skills.skills["archery"].practice_counts.values()) == 1


def test_transfer_mapping_order_does_not_change_gains() -> None:
    event = PracticeEvent(
        difficulty=60.0,
        duration_hours=1.0,
        quality=0.8,
        context="forms",
    )
    forward = SkillSet(transfers={"sword": {"knife": 0.2, "spear": 0.1}})
    reverse_targets: dict[str, float] = {}
    reverse_targets["spear"] = 0.1
    reverse_targets["knife"] = 0.2
    reverse = SkillSet(transfers={"sword": reverse_targets})

    forward.practice("sword", event)
    reverse.practice("sword", event)

    assert forward.skills["knife"] == reverse.skills["knife"]
    assert forward.skills["spear"] == reverse.skills["spear"]


def test_invalid_transfer_weight_does_not_grant_practice() -> None:
    skills = SkillSet()
    skills.transfers["sword"] = {"knife": 1.5}
    with pytest.raises(ValueError, match="transfer weight"):
        skills.practice(
            "sword",
            PracticeEvent(
                difficulty=60.0,
                duration_hours=1.0,
                context="forms",
            ),
        )
    assert skills.skills == {}


def test_lod_round_trip_preserves_skill_configuration_without_aliasing() -> None:
    actor = WorldActor(
        SpatialEntity("actor", "Actor", Vec3(0.0, 0.0, 0.0)),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
    )
    actor.skills.learning_rate = 1.4
    actor.skills.baseline_level = 20.0
    actor.skills.transfers = {"sword": {"knife": 0.2}}
    actor.skills.practice(
        "tracking",
        PracticeEvent(
            difficulty=65.0,
            duration_hours=2.0,
            quality=0.9,
            context="forest",
        ),
    )
    original_knowledge = actor.skills.skills["tracking"].knowledge

    state = abstract_actor(actor, tier=SimulationLOD.REGION, now=10.0)
    state.skills.learning_rate = 9.0
    state.skills.skills["tracking"].knowledge = 0.0
    state.skills.transfers["sword"]["knife"] = 1.0

    assert actor.skills.learning_rate == pytest.approx(1.4)
    assert actor.skills.skills["tracking"].knowledge == pytest.approx(
        original_knowledge
    )
    assert actor.skills.transfers["sword"]["knife"] == pytest.approx(0.2)

    restored = restore_actor(state)
    assert restored.skills.learning_rate == pytest.approx(9.0)
    assert restored.skills.baseline_level == pytest.approx(20.0)
    assert restored.skills.transfers == {"sword": {"knife": 1.0}}
    assert restored.skills.skills["tracking"].practice_counts == {"forest": 1}
    restored.skills.practice(
        "tracking",
        PracticeEvent(
            difficulty=65.0,
            duration_hours=1.0,
            context="forest",
        ),
    )
    assert actor.skills.skills["tracking"].practice_counts == {"forest": 1}
