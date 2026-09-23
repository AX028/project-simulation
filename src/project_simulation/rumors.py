"""Delayed information propagation through explicit social and travel links."""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count

from .cognition import Mind
from .information import Claim, Transmission, transmit_claim


@dataclass(frozen=True, slots=True)
class SocialLink:
    source_id: str
    target_id: str
    delay_hours: float
    reliability: float = 1.0
    propagation_factor: float = 0.92

    def __post_init__(self) -> None:
        if self.delay_hours < 0:
            raise ValueError("delay_hours may not be negative")
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError("reliability must be between zero and one")
        if not 0.0 <= self.propagation_factor <= 1.0:
            raise ValueError("propagation_factor must be between zero and one")


@dataclass(order=True, slots=True)
class RumorEvent:
    arrival_hour: float
    sequence: int
    rumor_id: str = field(compare=False)
    sender_id: str = field(compare=False)
    receiver_id: str = field(compare=False)
    claim: Claim = field(compare=False)
    hop: int = field(compare=False)
    max_hops: int = field(compare=False)
    visited: frozenset[str] = field(compare=False)


@dataclass(frozen=True, slots=True)
class RumorDelivery:
    arrival_hour: float
    rumor_id: str
    hop: int
    transmission: Transmission


class RumorNetwork:
    """Finite deterministic rumor propagation across directed social links."""

    def __init__(self, minds: dict[str, Mind]) -> None:
        self.minds = minds
        self._links: dict[str, list[SocialLink]] = {}
        self._queue: list[RumorEvent] = []
        self._counter = count()
        self._used_edges: set[tuple[str, str, str]] = set()
        self.time_hours = 0.0

    @property
    def pending_events(self) -> int:
        return len(self._queue)

    def add_link(self, link: SocialLink, *, bidirectional: bool = False) -> None:
        if link.source_id not in self.minds or link.target_id not in self.minds:
            raise KeyError("both endpoints must exist in minds")
        self._links.setdefault(link.source_id, []).append(link)
        self._links[link.source_id].sort(
            key=lambda item: (item.delay_hours, item.target_id)
        )
        if bidirectional:
            reverse = SocialLink(
                link.target_id,
                link.source_id,
                link.delay_hours,
                link.reliability,
                link.propagation_factor,
            )
            self._links.setdefault(reverse.source_id, []).append(reverse)
            self._links[reverse.source_id].sort(
                key=lambda item: (item.delay_hours, item.target_id)
            )

    def seed(
        self,
        *,
        rumor_id: str,
        origin_id: str,
        claim: Claim,
        now: float,
        max_hops: int = 4,
    ) -> None:
        if origin_id not in self.minds:
            raise KeyError(origin_id)
        if max_hops < 1:
            raise ValueError("max_hops must be at least one")
        if now < self.time_hours:
            raise ValueError("cannot seed a rumor in the past")
        self._schedule_from(
            rumor_id=rumor_id,
            sender_id=origin_id,
            claim=claim,
            now=now,
            hop=1,
            max_hops=max_hops,
            visited=frozenset({origin_id}),
        )

    def advance_to(self, target_hour: float) -> list[RumorDelivery]:
        if target_hour < self.time_hours:
            raise ValueError("network time cannot move backward")
        deliveries: list[RumorDelivery] = []
        while self._queue and self._queue[0].arrival_hour <= target_hour:
            event = heappop(self._queue)
            self.time_hours = event.arrival_hour
            edge_key = (event.rumor_id, event.sender_id, event.receiver_id)
            if edge_key in self._used_edges:
                continue
            self._used_edges.add(edge_key)

            receiver = self.minds[event.receiver_id]
            transmission = transmit_claim(
                sender_id=event.sender_id,
                receiver_id=event.receiver_id,
                receiver=receiver,
                claim=event.claim,
                now=event.arrival_hour,
            )
            deliveries.append(
                RumorDelivery(
                    event.arrival_hour,
                    event.rumor_id,
                    event.hop,
                    transmission,
                )
            )

            if event.hop >= event.max_hops:
                continue
            forwarded = Claim(
                key=event.claim.key,
                subject=event.claim.subject,
                proposition=event.claim.proposition,
                confidence=transmission.receiver_confidence,
                source_id=event.receiver_id,
            )
            self._schedule_from(
                rumor_id=event.rumor_id,
                sender_id=event.receiver_id,
                claim=forwarded,
                now=event.arrival_hour,
                hop=event.hop + 1,
                max_hops=event.max_hops,
                visited=event.visited | {event.receiver_id},
            )

        self.time_hours = target_hour
        return deliveries

    def _schedule_from(
        self,
        *,
        rumor_id: str,
        sender_id: str,
        claim: Claim,
        now: float,
        hop: int,
        max_hops: int,
        visited: frozenset[str],
    ) -> None:
        for link in self._links.get(sender_id, ()):
            if link.target_id in visited:
                continue
            edge_key = (rumor_id, sender_id, link.target_id)
            if edge_key in self._used_edges:
                continue
            forwarded_claim = Claim(
                key=claim.key,
                subject=claim.subject,
                proposition=claim.proposition,
                confidence=max(
                    0.0,
                    min(
                        1.0,
                        claim.confidence
                        * link.reliability
                        * link.propagation_factor,
                    ),
                ),
                source_id=sender_id,
            )
            event = RumorEvent(
                arrival_hour=now + link.delay_hours,
                sequence=next(self._counter),
                rumor_id=rumor_id,
                sender_id=sender_id,
                receiver_id=link.target_id,
                claim=forwarded_claim,
                hop=hop,
                max_hops=max_hops,
                visited=visited,
            )
            heappush(self._queue, event)
