"""Deterministic social dialogue grounded in NPC beliefs and relationships."""

from __future__ import annotations

from dataclasses import dataclass

from .cognition import Belief, Mind
from .information import Claim, Transmission, transmit_claim


@dataclass(frozen=True, slots=True)
class DialogueResult:
    speaker_id: str
    listener_id: str
    text: str
    topic: str | None
    belief: Belief | None = None
    transmission: Transmission | None = None
    refused: bool = False


def disposition_toward(mind: Mind, other_id: str) -> float:
    relationship = mind.relationship(other_id)
    value = (
        relationship.trust * 0.45
        + relationship.affection * 0.25
        + relationship.respect * 0.15
        - relationship.fear * 0.35
        - relationship.resentment * 0.45
    )
    return max(-100.0, min(100.0, value))


def find_belief(mind: Mind, topic: str) -> tuple[str, Belief] | None:
    lowered = topic.strip().lower()
    if not lowered:
        return None

    direct = mind.beliefs.get(lowered)
    if direct is not None:
        return lowered, direct

    candidates = [
        (key, belief)
        for key, belief in mind.beliefs.items()
        if lowered in key.lower()
        or lowered in belief.subject.lower()
        or lowered in belief.proposition.lower()
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item[1].confidence, item[0]),
    )


def converse(
    *,
    speaker_id: str,
    speaker_name: str,
    speaker: Mind,
    listener_id: str,
    listener: Mind,
    now: float,
    topic: str | None = None,
) -> DialogueResult:
    relationship = speaker.relationship(listener_id)
    if disposition_toward(speaker, listener_id) <= -55.0:
        relationship.familiarity = min(100.0, relationship.familiarity + 0.2)
        return DialogueResult(
            speaker_id,
            listener_id,
            f"{speaker_name} refuses to speak with you.",
            topic,
            refused=True,
        )

    relationship.familiarity = min(100.0, relationship.familiarity + 1.0)
    listener.relationship(speaker_id).familiarity = min(
        100.0,
        listener.relationship(speaker_id).familiarity + 1.0,
    )

    if topic is None:
        disposition = disposition_toward(speaker, listener_id)
        if disposition >= 35.0:
            text = f"{speaker_name} greets you warmly."
        elif disposition <= -15.0:
            text = f"{speaker_name} acknowledges you cautiously."
        else:
            text = f"{speaker_name} acknowledges you."
        return DialogueResult(
            speaker_id,
            listener_id,
            text,
            None,
        )

    match = find_belief(speaker, topic)
    if match is None:
        return DialogueResult(
            speaker_id,
            listener_id,
            f"{speaker_name} says they do not know anything reliable about {topic}.",
            topic,
        )

    key, belief = match
    claim = Claim(
        key=key,
        subject=belief.subject,
        proposition=belief.proposition,
        confidence=belief.confidence,
        source_id=speaker_id,
    )
    transmission = transmit_claim(
        sender_id=speaker_id,
        receiver_id=listener_id,
        receiver=listener,
        claim=claim,
        now=now,
    )
    qualifier = (
        "is certain"
        if belief.confidence >= 0.9
        else "believes"
        if belief.confidence >= 0.6
        else "has heard"
    )
    return DialogueResult(
        speaker_id,
        listener_id,
        f"{speaker_name} {qualifier}: {belief.proposition}",
        topic,
        belief=belief,
        transmission=transmission,
    )
