"""Settlement migration and occupation responses driven by simulated conditions."""

from __future__ import annotations

from dataclasses import dataclass

from .simulation import SettlementState


@dataclass(frozen=True, slots=True)
class MigrationResult:
    people_moved: int
    source_id: str
    destination_id: str
    transferred_labor: dict[str, int]


def employed_population(settlement: SettlementState) -> int:
    return sum(max(0, workers) for workers in settlement.labor.values())


def unemployment_ratio(settlement: SettlementState) -> float:
    if settlement.population <= 0:
        return 0.0
    employed = min(settlement.population, employed_population(settlement))
    return max(0.0, (settlement.population - employed) / settlement.population)


def settlement_attractiveness(settlement: SettlementState) -> float:
    """Return a bounded quality-of-life signal used for migration decisions."""
    if settlement.population <= 0:
        return 0.0
    wealth_per_capita = settlement.wealth / max(1, settlement.population)
    wealth_score = min(1.0, wealth_per_capita / 20.0)
    security_score = max(0.0, min(1.0, settlement.security / 10.0))
    food_price = max(0.1, settlement.prices.get("food", 1.0))
    food_score = max(0.0, min(1.0, 1.0 / food_price))
    employment_score = 1.0 - unemployment_ratio(settlement)
    return (
        wealth_score * 0.25
        + security_score * 0.30
        + food_score * 0.25
        + employment_score * 0.20
    )


def migration_pressure(source: SettlementState, destination: SettlementState) -> float:
    """Positive values indicate incentive to leave source for destination."""
    difference = settlement_attractiveness(destination) - settlement_attractiveness(source)
    return max(0.0, min(1.0, difference))


def migrate(
    source: SettlementState,
    destination: SettlementState,
    *,
    max_people: int,
    pressure: float | None = None,
) -> MigrationResult:
    if max_people < 0:
        raise ValueError("max_people may not be negative")
    if source.settlement_id == destination.settlement_id:
        raise ValueError("source and destination must differ")

    effective_pressure = (
        migration_pressure(source, destination) if pressure is None else pressure
    )
    if not 0.0 <= effective_pressure <= 1.0:
        raise ValueError("pressure must be between zero and one")

    movable = min(source.population, max_people)
    people = min(movable, round(source.population * effective_pressure * 0.05))
    if people <= 0:
        return MigrationResult(
            0,
            source.settlement_id,
            destination.settlement_id,
            {},
        )

    source_population_before = source.population
    transferred: dict[str, int] = {}
    remaining_people = people

    occupations = sorted(
        source.labor,
        key=lambda occupation: (-source.labor[occupation], occupation),
    )
    for occupation in occupations:
        workers = max(0, source.labor.get(occupation, 0))
        if workers == 0 or remaining_people <= 0:
            continue
        share = workers / max(1, source_population_before)
        moving_workers = min(workers, remaining_people, round(people * share))
        if moving_workers <= 0:
            continue
        source.labor[occupation] = workers - moving_workers
        destination.labor[occupation] = (
            destination.labor.get(occupation, 0) + moving_workers
        )
        transferred[occupation] = moving_workers
        remaining_people -= moving_workers

    source.population -= people
    destination.population += people
    source.recompute_prices()
    destination.recompute_prices()

    return MigrationResult(
        people,
        source.settlement_id,
        destination.settlement_id,
        transferred,
    )


def fill_occupation(
    settlement: SettlementState,
    occupation: str,
    desired_workers: int,
) -> int:
    """Move available unemployed residents into an occupation."""
    if desired_workers < 0:
        raise ValueError("desired_workers may not be negative")
    current = max(0, settlement.labor.get(occupation, 0))
    if current >= desired_workers:
        return 0
    unemployed = max(0, settlement.population - employed_population(settlement))
    added = min(unemployed, desired_workers - current)
    settlement.labor[occupation] = current + added
    return added
