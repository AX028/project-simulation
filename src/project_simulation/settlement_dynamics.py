"""Couple settlement labor, production, consumption, prices, and migration."""

from __future__ import annotations

from dataclasses import dataclass, field

from .demographics import MigrationResult, fill_occupation, migrate, migration_pressure
from .economy import Commodity, Market, ProductionRecipe, ProductionResult, run_production
from .simulation import ScheduledEvent, SimulationKernel, WorldState


@dataclass(frozen=True, slots=True)
class OccupationRecipe:
    occupation: str
    recipe: ProductionRecipe
    labor_hours_per_worker: float = 8.0

    def __post_init__(self) -> None:
        if self.labor_hours_per_worker < 0:
            raise ValueError("labor_hours_per_worker may not be negative")


@dataclass(slots=True)
class SettlementEconomicProfile:
    settlement_id: str
    market: Market
    commodities: dict[str, Commodity]
    occupation_recipes: tuple[OccupationRecipe, ...] = ()
    food_commodity_id: str = "food"
    food_units_per_person_day: float = 1.0
    occupation_targets: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.food_units_per_person_day < 0:
            raise ValueError("food consumption may not be negative")
        if self.food_commodity_id not in self.commodities:
            raise ValueError("food commodity must exist in commodities")


@dataclass(frozen=True, slots=True)
class SettlementDayResult:
    settlement_id: str
    production: tuple[ProductionResult, ...]
    food_required: float
    food_consumed: float
    shortage_ratio: float
    workers_assigned: dict[str, int]


class SettlementDynamics:
    """High-level daily settlement update using the lower-level systemic modules."""

    def __init__(
        self,
        world: WorldState,
        profiles: dict[str, SettlementEconomicProfile],
    ) -> None:
        self.world = world
        self.profiles = profiles
        missing = set(profiles) - set(world.settlements)
        if missing:
            raise KeyError(f"profiles reference unknown settlements: {sorted(missing)}")
        for settlement_id, profile in profiles.items():
            if profile.settlement_id != settlement_id:
                raise ValueError("profile key must match profile settlement_id")

    def process_day(self, settlement_id: str) -> SettlementDayResult:
        settlement = self.world.settlements[settlement_id]
        profile = self.profiles[settlement_id]

        workers_assigned: dict[str, int] = {}
        for occupation, target in sorted(profile.occupation_targets.items()):
            workers_assigned[occupation] = fill_occupation(
                settlement,
                occupation,
                desired_workers=target,
            )

        production: list[ProductionResult] = []
        for occupation_recipe in profile.occupation_recipes:
            workers = max(0, settlement.labor.get(occupation_recipe.occupation, 0))
            labor_hours = workers * occupation_recipe.labor_hours_per_worker
            production.append(
                run_production(
                    profile.market,
                    occupation_recipe.recipe,
                    available_labor_hours=labor_hours,
                )
            )

        food_required = settlement.population * profile.food_units_per_person_day
        food_consumed = profile.market.remove(profile.food_commodity_id, food_required)
        shortage = max(0.0, food_required - food_consumed)
        shortage_ratio = 0.0 if food_required == 0 else shortage / food_required

        if shortage_ratio > 0:
            settlement.security = max(
                0.0,
                settlement.security - shortage_ratio * 0.35,
            )
            settlement.wealth = max(
                0.0,
                settlement.wealth * (1.0 - shortage_ratio * 0.01),
            )

        profile.market.demand[profile.food_commodity_id] = max(0.1, food_required)
        for commodity_id, commodity in profile.commodities.items():
            profile.market.update_price(commodity)
            if commodity_id == profile.food_commodity_id:
                settlement.prices["food"] = profile.market.prices[commodity_id]

        settlement.food_units = profile.market.quantity(profile.food_commodity_id)
        return SettlementDayResult(
            settlement_id=settlement_id,
            production=tuple(production),
            food_required=food_required,
            food_consumed=food_consumed,
            shortage_ratio=shortage_ratio,
            workers_assigned=workers_assigned,
        )

    def migrate_best_destination(
        self,
        source_id: str,
        *,
        max_people: int,
        minimum_pressure: float = 0.05,
    ) -> MigrationResult | None:
        source = self.world.settlements[source_id]
        candidates = [
            settlement
            for settlement_id, settlement in sorted(self.world.settlements.items())
            if settlement_id != source_id
        ]
        if not candidates:
            return None

        ranked = sorted(
            (
                (migration_pressure(source, destination), destination.settlement_id)
                for destination in candidates
            ),
            key=lambda item: (-item[0], item[1]),
        )
        pressure, destination_id = ranked[0]
        if pressure < minimum_pressure:
            return None
        return migrate(
            source,
            self.world.settlements[destination_id],
            max_people=max_people,
            pressure=pressure,
        )

    def bind_to_kernel(
        self,
        kernel: SimulationKernel,
        *,
        first_hour: float = 24.0,
        interval_hours: float = 24.0,
    ) -> None:
        if interval_hours <= 0:
            raise ValueError("interval_hours must be positive")

        event_kind = "settlement_dynamics_day"

        def handler(world: WorldState, event: ScheduledEvent) -> None:
            del world
            settlement_id = str(event.payload["settlement_id"])
            self.process_day(settlement_id)
            kernel.schedule(
                event.at + interval_hours,
                event_kind,
                settlement_id=settlement_id,
            )

        kernel.register_handler(event_kind, handler)
        for settlement_id in sorted(self.profiles):
            kernel.schedule(
                first_hour,
                event_kind,
                settlement_id=settlement_id,
            )
