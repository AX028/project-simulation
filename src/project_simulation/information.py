"""Information propagation between NPC minds without global omniscience."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .cognition import Mind


@dataclass(frozen=True, slots=True)
class Claim:
    key: str
    subject: str
    proposition: str
    confidence: float
    source_id: str


@dataclass(frozen=True, slots=True)
class Transmission:
    sender_id: str
    receiver_id: str
    claim: Claim
    receiver_confidence: float


def transmission_confidence(
    *,
    claim_confidence: float,
    sender_trust: float,
    sender_familiarity: float,
    repetitions: int = 0,
) -> float:
    trust = max(0.0, min(1.0, (sender_trust + 100.0) / 200.0))
    familiarity = max(0.0, min(1.0, sender_familiarity / 100.0))
    repetition_bonus = min(0.18, max(0, repetitions) * 0.03)
    value = claim_confidence * (0.45 + 0.4 * trust + 0.15 * familiarity) + repetition_bonus
    return max(0.0, min(1.0, value))


def transmit_claim(
    *,
    sender_id: str,
    receiver_id: str,
    receiver: Mind,
    claim: Claim,
    now: float,
    repetitions: int = 0,
) -> Transmission:
    relationship = receiver.relationship(sender_id)
    confidence = transmission_confidence(
        claim_confidence=claim.confidence,
        sender_trust=relationship.trust,
        sender_familiarity=relationship.familiarity,
        repetitions=repetitions,
    )
    receiver.learn_claim(
        key=claim.key,
        subject=claim.subject,
        proposition=claim.proposition,
        confidence=confidence,
        source=sender_id,
        now=now,
        source_trust=1.0,
    )
    return Transmission(sender_id, receiver_id, claim, confidence)


def broadcast_claim(
    *,
    sender_id: str,
    receivers: Iterable[tuple[str, Mind]],
    claim: Claim,
    now: float,
) -> list[Transmission]:
    return [
        transmit_claim(
            sender_id=sender_id,
            receiver_id=receiver_id,
            receiver=mind,
            claim=claim,
            now=now,
        )
        for receiver_id, mind in receivers
    ]
