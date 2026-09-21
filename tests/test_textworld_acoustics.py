import pytest

from project_simulation import (
    Bounds,
    HearingProfile,
    SpatialEntity,
    Vec3,
    build_demo_session,
    observe,
    session_digest,
)


def test_shoot_creates_weapon_and_impact_sound_events() -> None:
    session = build_demo_session(40)
    session.execute("shoot Wolf torso")
    categories = [event.category for event in session.sound_events]
    assert categories == ["weapon", "impact"]


def test_nearby_npc_forms_hearing_memories_from_shot() -> None:
    session = build_demo_session(41)
    mira = session.actors["mira"]

    session.execute("shoot Wolf torso")

    heard = [memory for memory in mira.mind.memories if memory.source == "hearing"]
    assert heard
    assert {memory.subject for memory in heard} >= {"weapon", "impact"}


def test_hearing_memory_does_not_identify_source_actor() -> None:
    session = build_demo_session(42)
    mira = session.actors["mira"]

    session.execute("shoot Wolf torso")

    heard = [memory for memory in mira.mind.memories if memory.source == "hearing"]
    assert heard
    assert all(session.player_id not in memory.proposition for memory in heard)
    assert all(memory.source == "hearing" for memory in heard)


def test_npc_can_hear_shot_without_seeing_player() -> None:
    session = build_demo_session(43)
    mira = session.actors["mira"]
    mira.spatial.facing = Vec3(1.0, 1.0, 0.0)
    assert observe(mira.spatial, session.player.spatial) is None

    session.execute("shoot Wolf torso")

    heard = [memory for memory in mira.mind.memories if memory.source == "hearing"]
    assert heard


def test_occlusion_can_push_weapon_sound_below_threshold() -> None:
    session = build_demo_session(44)
    mira = session.actors["mira"]
    session.hearing_profiles["mira"] = HearingProfile(threshold_db=50.0)
    wall = SpatialEntity(
        "sound-wall",
        "Sound wall",
        Vec3(1.0, 1.0, 0.0),
        bounds=Bounds(0.7, 0.15, 3.0),
        tags=frozenset({"solid", "occluder"}),
    )
    session.scenery = (*session.scenery, wall)

    session.execute("shoot Wolf torso")

    weapon_memories = [
        memory
        for memory in mira.mind.memories
        if memory.source == "hearing" and memory.subject == "weapon"
    ]
    assert weapon_memories == []


def test_more_sensitive_listener_hears_weaker_sound() -> None:
    session = build_demo_session(45)
    mira = session.actors["mira"]
    mira.spatial.position = Vec3(0.0, 80.0, 0.0)
    session.hearing_profiles["mira"] = HearingProfile(
        threshold_db=20.0,
        sensitivity_db=20.0,
    )

    session.execute("shoot Wolf torso")

    assert any(
        memory.source == "hearing"
        for memory in mira.mind.memories
    )


def test_sound_memory_confidence_is_bounded() -> None:
    session = build_demo_session(46)
    session.execute("shoot Wolf torso")
    for actor in session.actors.values():
        for memory in actor.mind.memories:
            if memory.source == "hearing":
                assert 0.0 <= memory.confidence <= 1.0
                assert 0.0 <= memory.accuracy <= 1.0


def test_sound_events_participate_in_replay_digest() -> None:
    quiet = build_demo_session(47)
    noisy = build_demo_session(47)
    noisy.execute("shoot Wolf torso")
    assert session_digest(noisy) != session_digest(quiet)


def test_same_shoot_sequence_reproduces_same_heard_memories() -> None:
    first = build_demo_session(48)
    second = build_demo_session(48)
    commands = ("shoot Wolf torso", "shoot Wolf left_leg")
    first.replay(commands)
    second.replay(commands)

    first_memories = [
        (memory.subject, memory.proposition, memory.confidence, memory.accuracy)
        for memory in first.actors["mira"].mind.memories
        if memory.source == "hearing"
    ]
    second_memories = [
        (memory.subject, memory.proposition, memory.confidence, memory.accuracy)
        for memory in second.actors["mira"].mind.memories
        if memory.source == "hearing"
    ]
    assert first_memories == second_memories
    assert session_digest(first) == session_digest(second)


def test_one_hundred_shots_create_deterministic_sound_history() -> None:
    def simulate() -> tuple[int, int, str]:
        session = build_demo_session(49)
        weapon = session.ranged_weapons[session.player_id]
        weapon.ammunition = 100
        for _ in range(100):
            session.execute("shoot Wolf torso")
        heard_count = sum(
            1
            for memory in session.actors["mira"].mind.memories
            if memory.source == "hearing"
        )
        return len(session.sound_events), heard_count, session_digest(session)

    first = simulate()
    second = simulate()
    assert first == second
    assert first[0] == 200


def test_zero_volume_sound_requires_threshold_compatibility() -> None:
    session = build_demo_session(50)
    heard = session._emit_sound(
        category="quiet",
        description="almost nothing",
        position=session.player.spatial.position,
        loudness_db_at_1m=0.0,
        source_id=session.player_id,
    )
    assert heard == ()
