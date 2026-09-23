"""Persistent simulation kernel with event scheduling and level-of-detail updates."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import IntEnum
from heapq import heapify, heappop, heappush

from .validation import finite_number, nonnegative_number

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


def _strict_finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    try:
        return finite_number(value, name)
    except OverflowError as exc:
        raise ValueError(f"{name} must be finite") from exc


def _strict_nonnegative_number(value: object, name: str) -> float:
    number = _strict_finite_number(value, name)
    if number < 0:
        raise ValueError(f"{name} may not be negative")
    return number


def _strict_nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} may not be negative")
    return value


def _nonempty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{name} must be a non-empty string")
    return value


def _validate_macro_world(world: WorldState) -> None:
    _strict_nonnegative_number(world.time_hours, "world time")

    settlement_ids: set[str] = set()
    for key, settlement in world.settlements.items():
        _nonempty_string(key, "settlement key")
        if not isinstance(settlement, SettlementState):
            raise TypeError("settlements must contain settlement states")
        settlement_id = _nonempty_string(settlement.settlement_id, "settlement id")
        if settlement_id in settlement_ids:
            raise ValueError(f"duplicate settlement id: {settlement_id}")
        settlement_ids.add(settlement_id)
        _nonempty_string(settlement.name, "settlement name")
        _strict_nonnegative_int(settlement.population, "settlement population")
        _strict_nonnegative_number(settlement.food_units, "settlement food")
        _strict_nonnegative_number(settlement.wealth, "settlement wealth")
        security = _strict_finite_number(settlement.security, "settlement security")
        if not 0.0 <= security <= 10.0:
            raise ValueError("settlement security must be between 0 and 10")
        _strict_nonnegative_number(settlement.livestock, "settlement livestock")
        for occupation, workers in settlement.labor.items():
            _nonempty_string(occupation, "labor occupation")
            _strict_nonnegative_int(workers, "labor population")
        for commodity, price in settlement.prices.items():
            _nonempty_string(commodity, "price commodity")
            if _strict_finite_number(price, "commodity price") <= 0:
                raise ValueError("commodity price must be positive")

    faction_ids: set[str] = set()
    for key, faction in world.factions.items():
        _nonempty_string(key, "faction key")
        if not isinstance(faction, FactionState):
            raise TypeError("factions must contain faction states")
        faction_id = _nonempty_string(faction.faction_id, "faction id")
        if faction_id in faction_ids:
            raise ValueError(f"duplicate faction id: {faction_id}")
        faction_ids.add(faction_id)
        _nonempty_string(faction.name, "faction name")
        _strict_nonnegative_int(faction.members, "faction members")
        _strict_nonnegative_number(faction.wealth, "faction wealth")
        _strict_nonnegative_number(faction.military_power, "faction military power")
        _strict_nonnegative_number(faction.territory, "faction territory")
        for other_id, relation in faction.relations.items():
            _nonempty_string(other_id, "relation faction id")
            value = _strict_finite_number(relation, "faction relation")
            if not -1.0 <= value <= 1.0:
                raise ValueError("faction relation must be between -1 and 1")
        for memory_key, strength in faction.institutional_memory.items():
            _nonempty_string(memory_key, "institutional memory key")
            value = _strict_finite_number(strength, "institutional memory strength")
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    "institutional memory strength must be between 0 and 1"
                )

    if not isinstance(world.history, list) or not all(
        isinstance(item, str) for item in world.history
    ):
        raise TypeError("world history must be a list of strings")


def _validate_event(event: ScheduledEvent, *, world_time: float) -> None:
    event_time = _strict_finite_number(event.at, "event time")
    _strict_nonnegative_int(event.sequence, "event sequence")
    if event_time < world_time:
        raise ValueError("pending events may not occur before world time")
    _nonempty_string(event.kind, "event kind")
    if not isinstance(event.payload, dict):
        raise TypeError("event payload must be an object")
    for key, value in event.payload.items():
        _nonempty_string(key, "event payload key")
        if isinstance(value, bool) or isinstance(value, str):
            continue
        if isinstance(value, (int, float)):
            _strict_finite_number(value, "event payload number")
            continue
        raise TypeError("unsupported event payload value")


class SimulationKernel:
    """Deterministic event queue. Distant systems advance through coarse events, not frames."""

    def __init__(self, world: WorldState) -> None:
        self.world = world
        self._events: list[ScheduledEvent] = []
        self._next_sequence = 0
        self._handlers: dict[str, EventHandler] = {
            "wolf_attack": self._wolf_attack,
            "faction_conflict": self._faction_conflict,
        }

    def register_handler(self, kind: str, handler: EventHandler) -> None:
        self._handlers[kind] = handler

    def has_handler(self, kind: str) -> bool:
        return kind in self._handlers

    def schedule(self, at: float, kind: str, **payload: EventValue) -> ScheduledEvent:
        at = finite_number(at, "event time")
        if at < self.world.time_hours:
            raise ValueError("scheduled events may not occur before world time")
        event = ScheduledEvent(at, self._next_sequence, kind, dict(payload))
        self._next_sequence += 1
        heappush(self._events, event)
        return event

    def advance_to(self, target_hour: float) -> None:
        target_hour = finite_number(target_hour, "target hour")
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

    @property
    def next_event_sequence(self) -> int:
        """Sequence number that the next scheduled event will receive."""
        return self._next_sequence

    def pending_events(self) -> tuple[ScheduledEvent, ...]:
        """Return an immutable, sorted copy of future scheduled events."""
        return tuple(self._copy_event(event) for event in sorted(self._events))

    def replace_pending_events(
        self,
        events: Iterable[ScheduledEvent],
        *,
        next_sequence: int | None = None,
    ) -> None:
        """Replace the queue while preserving deterministic sequence ordering.

        When ``next_sequence`` is omitted, the next scheduled event continues
        after the highest restored sequence. An explicit value is required when
        the pending queue is empty but earlier events have already consumed
        sequence numbers.
        """
        restored = [self._copy_event(event) for event in events]
        chosen = self._validated_next_sequence(
            restored,
            world_time=self.world.time_hours,
            next_sequence=next_sequence,
        )
        self._events = restored
        heapify(self._events)
        self._next_sequence = chosen

    def restore_macro_continuation(
        self,
        world: WorldState,
        events: Iterable[ScheduledEvent],
        *,
        next_sequence: int,
    ) -> None:
        """Install world, pending events, and the next sequence together.

        Validation finishes before any live field changes. A rejected restore
        leaves this kernel unchanged. Event handlers are not replaced.
        """
        _validate_macro_world(world)
        restored = [self._copy_event(event) for event in events]
        chosen = self._validated_next_sequence(
            restored,
            world_time=world.time_hours,
            next_sequence=next_sequence,
        )
        self.world = world
        self._events = restored
        heapify(self._events)
        self._next_sequence = chosen

    @staticmethod
    def _copy_event(event: ScheduledEvent) -> ScheduledEvent:
        return ScheduledEvent(
            event.at,
            event.sequence,
            event.kind,
            dict(event.payload),
        )

    @staticmethod
    def _validated_next_sequence(
        events: list[ScheduledEvent],
        *,
        world_time: float,
        next_sequence: int | None,
    ) -> int:
        validated_world_time = _strict_nonnegative_number(
            world_time,
            "world time",
        )
        for event in events:
            _validate_event(event, world_time=validated_world_time)
        sequences = [event.sequence for event in events]
        if len(sequences) != len(set(sequences)):
            raise ValueError("pending event sequence numbers must be unique")
        derived = max(sequences, default=-1) + 1
        if next_sequence is None:
            return derived
        _strict_nonnegative_int(next_sequence, "next event sequence")
        if next_sequence < derived:
            raise ValueError(
                "next event sequence must be greater than every pending sequence"
            )
        return next_sequence

    def choose_lod(self, distance_m: float, important: bool = False) -> SimulationLOD:
        distance_m = nonnegative_number(distance_m, "LOD distance")
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
