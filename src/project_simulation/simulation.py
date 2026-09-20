"""Persistent simulation kernel with event scheduling and level-of-detail updates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from heapq import heappop, heappush
from itertools import count

EventValue = str | int | float | bool


class SimulationLOD(IntEnum):
    IMMEDIATE = 0
    LOCAL = 1
    SETTLEMENT = 2
    REGION = 3
    WORLD = 4


@dataclass(order=True, slots=True)
class ScheduledEvent:
    at: float
    sequence: int
    kind: str = field(compare=False)
    payload: dict[str, EventValue] = field(compare=False, default_factory=dict)


@dataclass(slots=True)
class SettlementState:
    settlement_id: str
    name: str
    population: int
    food_units: float
    wealth: float
    security: float
    livestock: float
    labor: dict[str, int] = field(default_factory=dict)
    prices: dict[str, float] = field(
        default_factory=lambda: {"food": 1.0, "meat": 1.0, "leather": 1.0}
    )

    def recompute_prices(self) -> None:
        mouths = max(1.0, self.population)
        food_supply = max(1.0, self.food_units)
        livestock_supply = max(1.0, self.livestock)
        self.prices["food"] = max(0.2, min(8.0, (mouths / food_supply) ** 0.55))
        self.prices["meat"] = max(0.2, min(10.0, (mouths / livestock_supply) ** 0.45))
        self.prices["leather"] = max(0.2, min(10.0, (mouths / livestock_supply) ** 0.30))


@dataclass(slots=True)
class FactionState:
    faction_id: str
    name: str
    members: int
    wealth: float
    military_power: float
    territory: float
    relations: dict[str, float] = field(default_factory=dict)
    institutional_memory: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class WorldState:
    time_hours: float = 0.0
    settlements: dict[str, SettlementState] = field(default_factory=dict)
    factions: dict[str, FactionState] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)


EventHandler = Callable[[WorldState, ScheduledEvent], None]


class SimulationKernel:
    """Deterministic event queue. Distant systems advance through coarse events, not frames."""

    def __init__(self, world: WorldState) -> None:
        self.world = world
        self._events: list[ScheduledEvent] = []
        self._counter = count()
        self._handlers: dict[str, EventHandler] = {
            "wolf_attack": self._wolf_attack,
            "daily_settlement": self._daily_settlement,
            "faction_conflict": self._faction_conflict,
        }

    def register_handler(self, kind: str, handler: EventHandler) -> None:
        self._handlers[kind] = handler

    def schedule(self, at: float, kind: str, **payload: EventValue) -> ScheduledEvent:
        event = ScheduledEvent(at, next(self._counter), kind, dict(payload))
        heappush(self._events, event)
        return event

    def advance_to(self, target_hour: float) -> None:
        if target_hour < self.world.time_hours:
            raise ValueError("simulation time cannot move backward")
        while self._events and self._events[0].at <= target_hour:
            event = heappop(self._events)
            self.world.time_hours = event.at
            handler = self._handlers.get(event.kind)
            if handler is None:
                self.world.history.append(f"{event.at:.1f}h: unhandled event {event.kind}")
                continue
            handler(self.world, event)
        self.world.time_hours = target_hour

    def choose_lod(self, distance_m: float, important: bool = False) -> SimulationLOD:
        if distance_m <= 80:
            return SimulationLOD.IMMEDIATE
        if distance_m <= 1500 or important:
            return SimulationLOD.LOCAL
        if distance_m <= 25_000:
            return SimulationLOD.SETTLEMENT
        if distance_m <= 300_000:
            return SimulationLOD.REGION
        return SimulationLOD.WORLD

    def _wolf_attack(self, world: WorldState, event: ScheduledEvent) -> None:
        settlement_id = str(event.payload["settlement_id"])
        severity = float(event.payload.get("severity", 0.1))
        settlement = world.settlements[settlement_id]
        lost = min(settlement.livestock, max(1.0, settlement.livestock * severity))
        settlement.livestock -= lost
        settlement.security = max(0.0, settlement.security - severity * 4.0)
        settlement.recompute_prices()
        world.history.append(
            f"{event.at:.1f}h: wolves killed {lost:.1f} livestock near {settlement.name}"
        )

    def _daily_settlement(self, world: WorldState, event: ScheduledEvent) -> None:
        settlement_id = str(event.payload["settlement_id"])
        settlement = world.settlements[settlement_id]
        farmers = settlement.labor.get("farmer", 0)
        hunters = settlement.labor.get("hunter", 0)
        produced = farmers * 1.35 + hunters * 0.35
        consumed = settlement.population * 0.95
        settlement.food_units += produced - consumed
        if settlement.food_units < 0:
            shortage = min(1.0, abs(settlement.food_units) / max(1.0, consumed))
            population_loss = round(shortage * 0.003 * settlement.population)
            settlement.population = max(0, settlement.population - population_loss)
            settlement.wealth = max(0.0, settlement.wealth * (1.0 - shortage * 0.015))
            settlement.food_units = 0.0
        settlement.recompute_prices()
        self.schedule(event.at + 24.0, "daily_settlement", settlement_id=settlement_id)

    def _faction_conflict(self, world: WorldState, event: ScheduledEvent) -> None:
        attacker = world.factions[str(event.payload["attacker"])]
        defender = world.factions[str(event.payload["defender"])]
        scale = max(0.01, min(1.0, float(event.payload.get("scale", 0.1))))
        wealth_factor = attacker.wealth / max(1.0, attacker.members) * 0.01
        attack_strength = attacker.military_power * (0.75 + wealth_factor)
        defense_strength = defender.military_power * 1.05
        total = max(1.0, attack_strength + defense_strength)
        attacker_loss = scale * defender.members * defense_strength / total * 0.08
        defender_loss = scale * attacker.members * attack_strength / total * 0.08
        attacker.members = max(0, attacker.members - round(attacker_loss))
        defender.members = max(0, defender.members - round(defender_loss))
        swing = scale * (attack_strength - defense_strength) / total
        attacker.territory = max(0.0, attacker.territory + swing)
        defender.territory = max(0.0, defender.territory - swing)
        key = f"conflict:{defender.faction_id}"
        attacker.institutional_memory[key] = min(
            1.0, attacker.institutional_memory.get(key, 0.0) + scale
        )
        world.history.append(
            f"{event.at:.1f}h: {attacker.name} fought {defender.name}; "
            f"losses {round(attacker_loss)}/{round(defender_loss)}"
        )
