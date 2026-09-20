"""Deterministic commodity production, pricing, and trade-route simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import pow


@dataclass(frozen=True, slots=True)
class Commodity:
    commodity_id: str
    name: str
    base_price: float
    mass_kg: float = 1.0


@dataclass(frozen=True, slots=True)
class ProductionRecipe:
    recipe_id: str
    inputs: dict[str, float]
    outputs: dict[str, float]
    labor_hours: float

    def __post_init__(self) -> None:
        if self.labor_hours <= 0:
            raise ValueError("labor_hours must be positive")
        if any(amount < 0 for amount in self.inputs.values()):
            raise ValueError("recipe inputs may not be negative")
        if any(amount <= 0 for amount in self.outputs.values()):
            raise ValueError("recipe outputs must be positive")


@dataclass(slots=True)
class Market:
    stock: dict[str, float] = field(default_factory=dict)
    demand: dict[str, float] = field(default_factory=dict)
    prices: dict[str, float] = field(default_factory=dict)

    def quantity(self, commodity_id: str) -> float:
        return max(0.0, self.stock.get(commodity_id, 0.0))

    def add(self, commodity_id: str, amount: float) -> None:
        if amount < 0:
            raise ValueError("cannot add a negative quantity")
        self.stock[commodity_id] = self.quantity(commodity_id) + amount

    def remove(self, commodity_id: str, amount: float) -> float:
        if amount < 0:
            raise ValueError("cannot remove a negative quantity")
        removed = min(self.quantity(commodity_id), amount)
        self.stock[commodity_id] = self.quantity(commodity_id) - removed
        return removed

    def update_price(
        self,
        commodity: Commodity,
        *,
        elasticity: float = 0.55,
        transport_factor: float = 1.0,
        risk_factor: float = 1.0,
    ) -> float:
        supply = max(0.1, self.quantity(commodity.commodity_id))
        demand = max(0.1, self.demand.get(commodity.commodity_id, 0.1))
        pressure = pow(demand / supply, elasticity)
        price = commodity.base_price * pressure * transport_factor * risk_factor
        price = max(commodity.base_price * 0.1, min(commodity.base_price * 20.0, price))
        self.prices[commodity.commodity_id] = price
        return price


@dataclass(frozen=True, slots=True)
class ProductionResult:
    cycles: float
    labor_used: float
    consumed: dict[str, float]
    produced: dict[str, float]


def run_production(
    market: Market,
    recipe: ProductionRecipe,
    *,
    available_labor_hours: float,
    requested_cycles: float | None = None,
) -> ProductionResult:
    if available_labor_hours < 0:
        raise ValueError("available labor may not be negative")

    cycle_limit = available_labor_hours / recipe.labor_hours
    for commodity_id, amount in recipe.inputs.items():
        if amount > 0:
            cycle_limit = min(cycle_limit, market.quantity(commodity_id) / amount)
    if requested_cycles is not None:
        if requested_cycles < 0:
            raise ValueError("requested cycles may not be negative")
        cycle_limit = min(cycle_limit, requested_cycles)

    cycles = max(0.0, cycle_limit)
    consumed = {
        commodity_id: amount * cycles
        for commodity_id, amount in recipe.inputs.items()
    }
    produced = {
        commodity_id: amount * cycles
        for commodity_id, amount in recipe.outputs.items()
    }
    for commodity_id, amount in consumed.items():
        market.remove(commodity_id, amount)
    for commodity_id, amount in produced.items():
        market.add(commodity_id, amount)
    return ProductionResult(
        cycles=cycles,
        labor_used=cycles * recipe.labor_hours,
        consumed=consumed,
        produced=produced,
    )


@dataclass(frozen=True, slots=True)
class TradeRoute:
    distance_km: float
    risk: float
    capacity_kg: float
    cost_per_kg_km: float = 0.002

    def __post_init__(self) -> None:
        if self.distance_km < 0 or self.capacity_kg < 0:
            raise ValueError("distance and capacity may not be negative")
        if not 0.0 <= self.risk <= 1.0:
            raise ValueError("risk must be between zero and one")

    def landed_cost_multiplier(self, commodity: Commodity) -> float:
        transport = self.distance_km * self.cost_per_kg_km * commodity.mass_kg
        return 1.0 + transport / max(0.01, commodity.base_price) + self.risk * 0.5


@dataclass(frozen=True, slots=True)
class TradeResult:
    quantity: float
    cargo_mass_kg: float


def transfer(
    source: Market,
    destination: Market,
    commodity: Commodity,
    route: TradeRoute,
    requested_quantity: float,
) -> TradeResult:
    if requested_quantity < 0:
        raise ValueError("requested quantity may not be negative")
    capacity_units = route.capacity_kg / max(0.001, commodity.mass_kg)
    quantity = min(
        requested_quantity,
        source.quantity(commodity.commodity_id),
        capacity_units,
    )
    moved = source.remove(commodity.commodity_id, quantity)
    destination.add(commodity.commodity_id, moved)
    return TradeResult(moved, moved * commodity.mass_kg)
