"""Faction diplomacy, treaties, and institutional memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .simulation import FactionState, WorldState


class TreatyStatus(StrEnum):
    ACTIVE = "active"
    BROKEN = "broken"
    EXPIRED = "expired"


@dataclass(slots=True)
class Treaty:
    treaty_id: str
    party_a: str
    party_b: str
    terms: frozenset[str]
    start_hour: float
    end_hour: float | None = None
    status: TreatyStatus = TreatyStatus.ACTIVE
    broken_by: str | None = None
    broken_at: float | None = None

    def involves(self, faction_id: str) -> bool:
        return faction_id in {self.party_a, self.party_b}

    def other_party(self, faction_id: str) -> str:
        if faction_id == self.party_a:
            return self.party_b
        if faction_id == self.party_b:
            return self.party_a
        raise ValueError(f"{faction_id} is not a treaty party")


@dataclass(slots=True)
class DiplomacyEngine:
    world: WorldState
    treaties: dict[str, Treaty] = field(default_factory=dict)

    def sign_treaty(
        self,
        treaty_id: str,
        party_a: str,
        party_b: str,
        *,
        terms: frozenset[str] = frozenset(),
        now: float,
        duration_hours: float | None = None,
    ) -> Treaty:
        if treaty_id in self.treaties:
            raise ValueError(f"duplicate treaty id: {treaty_id}")
        if party_a == party_b:
            raise ValueError("a faction cannot sign a treaty with itself")
        self._faction(party_a)
        self._faction(party_b)
        if duration_hours is not None and duration_hours <= 0:
            raise ValueError("duration_hours must be positive")

        treaty = Treaty(
            treaty_id=treaty_id,
            party_a=party_a,
            party_b=party_b,
            terms=terms,
            start_hour=now,
            end_hour=None if duration_hours is None else now + duration_hours,
        )
        self.treaties[treaty_id] = treaty
        self._change_relation(party_a, party_b, 0.08)
        self._remember(party_a, f"treaty:{party_b}", 0.15)
        self._remember(party_b, f"treaty:{party_a}", 0.15)
        self.world.history.append(
            f"{now:.1f}h: {self._faction(party_a).name} and "
            f"{self._faction(party_b).name} signed treaty {treaty_id}"
        )
        return treaty

    def break_treaty(
        self,
        treaty_id: str,
        *,
        breaker_id: str,
        now: float,
        severity: float = 0.7,
    ) -> Treaty:
        treaty = self.treaties[treaty_id]
        if treaty.status is not TreatyStatus.ACTIVE:
            raise ValueError("only active treaties can be broken")
        if not treaty.involves(breaker_id):
            raise ValueError("breaker must be a treaty party")
        if not 0.0 <= severity <= 1.0:
            raise ValueError("severity must be between zero and one")

        victim_id = treaty.other_party(breaker_id)
        treaty.status = TreatyStatus.BROKEN
        treaty.broken_by = breaker_id
        treaty.broken_at = now

        breaker = self._faction(breaker_id)
        victim = self._faction(victim_id)
        breaker.relations[victim_id] = max(
            -1.0,
            min(1.0, breaker.relations.get(victim_id, 0.0) - severity * 0.45),
        )
        victim.relations[breaker_id] = max(
            -1.0,
            min(1.0, victim.relations.get(breaker_id, 0.0) - severity * 0.85),
        )
        self._remember(victim_id, f"betrayal:{breaker_id}", severity)
        self._remember(breaker_id, f"broke_treaty:{victim_id}", severity * 0.5)
        self.world.history.append(
            f"{now:.1f}h: {breaker.name} broke treaty {treaty_id} "
            f"with {victim.name}"
        )
        return treaty

    def expire_treaties(self, now: float) -> list[Treaty]:
        expired: list[Treaty] = []
        for treaty in self.treaties.values():
            if (
                treaty.status is TreatyStatus.ACTIVE
                and treaty.end_hour is not None
                and treaty.end_hour <= now
            ):
                treaty.status = TreatyStatus.EXPIRED
                expired.append(treaty)
                self.world.history.append(
                    f"{now:.1f}h: treaty {treaty.treaty_id} expired"
                )
        return expired

    def cooperation_modifier(self, faction_id: str, other_id: str) -> float:
        faction = self._faction(faction_id)
        self._faction(other_id)
        relation = faction.relations.get(other_id, 0.0)
        active_bonus = 0.0
        for treaty in self.treaties.values():
            if (
                treaty.status is TreatyStatus.ACTIVE
                and treaty.involves(faction_id)
                and treaty.involves(other_id)
            ):
                active_bonus += 0.15

        betrayal = faction.institutional_memory.get(
            f"betrayal:{other_id}",
            0.0,
        )
        value = relation + min(0.3, active_bonus) - betrayal * 0.6
        return max(-1.0, min(1.0, value))

    def _change_relation(self, first_id: str, second_id: str, delta: float) -> None:
        first = self._faction(first_id)
        second = self._faction(second_id)
        first.relations[second_id] = max(
            -1.0,
            min(1.0, first.relations.get(second_id, 0.0) + delta),
        )
        second.relations[first_id] = max(
            -1.0,
            min(1.0, second.relations.get(first_id, 0.0) + delta),
        )

    def _remember(self, faction_id: str, key: str, strength: float) -> None:
        faction = self._faction(faction_id)
        faction.institutional_memory[key] = min(
            1.0,
            faction.institutional_memory.get(key, 0.0) + strength,
        )

    def _faction(self, faction_id: str) -> FactionState:
        try:
            return self.world.factions[faction_id]
        except KeyError as exc:
            raise KeyError(f"unknown faction: {faction_id}") from exc
