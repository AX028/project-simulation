import pytest

from project_simulation import (
    Belief,
    Mind,
    Relationship,
    build_demo_session,
    converse,
    disposition_toward,
    find_belief,
)


def test_find_belief_matches_key_subject_and_proposition() -> None:
    mind = Mind(
        beliefs={
            "bridge": Belief(
                "east bridge",
                "the east bridge is damaged",
                0.8,
                "direct",
                0.0,
            )
        }
    )
    assert find_belief(mind, "bridge") is not None
    assert find_belief(mind, "east bridge") is not None
    assert find_belief(mind, "damaged") is not None
    assert find_belief(mind, "dragons") is None


def test_disposition_uses_relationship_dimensions() -> None:
    mind = Mind(
        relationships={
            "listener": Relationship(
                trust=60.0,
                affection=20.0,
                respect=30.0,
                fear=0.0,
                resentment=0.0,
            )
        }
    )
    assert disposition_toward(mind, "listener") > 30.0
    mind.relationships["listener"].resentment = 100.0
    assert disposition_toward(mind, "listener") < 0.0


def test_conversation_transfers_speaker_belief_to_listener() -> None:
    speaker = Mind(
        beliefs={
            "road": Belief(
                "north road",
                "the north road is flooded",
                0.9,
                "direct",
                0.0,
            )
        }
    )
    listener = Mind()
    listener.relationship("speaker").trust = 80.0
    listener.relationship("speaker").familiarity = 70.0

    result = converse(
        speaker_id="speaker",
        speaker_name="Mira",
        speaker=speaker,
        listener_id="listener",
        listener=listener,
        now=4.0,
        topic="road",
    )

    assert result.transmission is not None
    assert listener.beliefs["road"].proposition == "the north road is flooded"
    assert result.transmission.receiver_confidence > 0.7


def test_unknown_topic_does_not_create_false_belief() -> None:
    speaker = Mind()
    listener = Mind()
    result = converse(
        speaker_id="speaker",
        speaker_name="Mira",
        speaker=speaker,
        listener_id="listener",
        listener=listener,
        now=1.0,
        topic="dragons",
    )
    assert "do not know" in result.text
    assert listener.beliefs == {}


def test_hostile_relationship_can_refuse_conversation() -> None:
    speaker = Mind()
    speaker.relationship("listener").trust = -100.0
    speaker.relationship("listener").resentment = 100.0
    listener = Mind()

    result = converse(
        speaker_id="speaker",
        speaker_name="Mira",
        speaker=speaker,
        listener_id="listener",
        listener=listener,
        now=1.0,
        topic="bridge",
    )

    assert result.refused
    assert "refuses" in result.text


def test_greeting_changes_with_disposition() -> None:
    warm = Mind()
    warm.relationship("listener").trust = 100.0
    warm.relationship("listener").affection = 50.0
    neutral_listener = Mind()

    result = converse(
        speaker_id="speaker",
        speaker_name="Mira",
        speaker=warm,
        listener_id="listener",
        listener=neutral_listener,
        now=1.0,
    )
    assert "warmly" in result.text


def test_textworld_talk_transfers_demo_bridge_belief() -> None:
    session = build_demo_session(5)
    assert "bridge" not in session.player.mind.beliefs

    output = session.execute("talk Mira bridge").output

    assert "east bridge is damaged" in output
    assert "bridge" in session.player.mind.beliefs


def test_textworld_talk_increases_familiarity() -> None:
    session = build_demo_session(5)
    mira = session.actors["mira"]
    before = mira.mind.relationship(session.player_id).familiarity

    session.execute("talk Mira")

    after = mira.mind.relationship(session.player_id).familiarity
    assert after > before


def test_textworld_talk_unknown_topic_stays_bounded_to_npc_knowledge() -> None:
    session = build_demo_session(5)
    output = session.execute("talk Mira dragons").output
    assert "do not know" in output
    assert "dragons" not in session.player.mind.beliefs


def test_textworld_talk_requires_range() -> None:
    session = build_demo_session(5)
    session.execute("move south 10")
    with pytest.raises(ValueError, match="too far"):
        session.execute("talk Mira bridge")


def test_textworld_talk_requires_perception() -> None:
    session = build_demo_session(5)
    mira = session.actors["mira"]
    mira.spatial.position = session.player.spatial.position + mira.spatial.facing.scale(2.0)
    session.player.spatial.facing = mira.spatial.facing.scale(-1.0)
    with pytest.raises(ValueError, match="perceive"):
        session.execute("talk Mira bridge")


def test_talk_advances_time_once() -> None:
    session = build_demo_session(5)
    before = session.elapsed_seconds
    session.execute("talk Mira bridge")
    assert session.elapsed_seconds == pytest.approx(before + 1.0)


def test_two_hundred_dialogues_are_deterministic() -> None:
    def simulate() -> tuple[str, float, float]:
        session = build_demo_session(33)
        outputs = []
        for index in range(200):
            topic = "bridge" if index % 2 == 0 else "wolves"
            outputs.append(session.execute(f"talk Mira {topic}").output)
        familiarity = session.actors["mira"].mind.relationship(
            session.player_id
        ).familiarity
        confidence = session.player.mind.beliefs["bridge"].confidence
        return "\n".join(outputs), familiarity, confidence

    assert simulate() == simulate()
