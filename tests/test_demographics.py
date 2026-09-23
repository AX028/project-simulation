from project_simulation import (
    SettlementState,
    employed_population,
    fill_occupation,
    migrate,
    migration_pressure,
    settlement_attractiveness,
    unemployment_ratio,
)


def _settlement(
    settlement_id: str,
    *,
    population: int,
    food_units: float,
    wealth: float,
    security: float,
    labor: dict[str, int],
) -> SettlementState:
    state = SettlementState(
        settlement_id,
        settlement_id.title(),
        population=population,
        food_units=food_units,
        wealth=wealth,
        security=security,
        livestock=100.0,
        labor=labor,
    )
    state.recompute_prices()
    return state


def test_unemployment_is_bounded_and_based_on_labor() -> None:
    town = _settlement(
        "town",
        population=100,
        food_units=100,
        wealth=1000,
        security=5,
        labor={"farmer": 40, "smith": 10},
    )
    assert employed_population(town) == 50
    assert unemployment_ratio(town) == 0.5


def test_better_settlement_has_positive_migration_pressure() -> None:
    poor = _settlement(
        "poor",
        population=100,
        food_units=40,
        wealth=100,
        security=2,
        labor={"farmer": 20},
    )
    rich = _settlement(
        "rich",
        population=100,
        food_units=200,
        wealth=5000,
        security=9,
        labor={"farmer": 80},
    )
    assert settlement_attractiveness(rich) > settlement_attractiveness(poor)
    assert migration_pressure(poor, rich) > 0.0
    assert migration_pressure(rich, poor) == 0.0


def test_migration_preserves_total_population() -> None:
    source = _settlement(
        "source",
        population=200,
        food_units=60,
        wealth=500,
        security=2,
        labor={"farmer": 80, "smith": 20},
    )
    destination = _settlement(
        "destination",
        population=100,
        food_units=300,
        wealth=4000,
        security=9,
        labor={"farmer": 50},
    )
    before = source.population + destination.population
    result = migrate(source, destination, max_people=50, pressure=1.0)
    after = source.population + destination.population
    assert result.people_moved == 10
    assert before == after
    assert source.population == 190
    assert destination.population == 110


def test_migration_never_creates_negative_occupations() -> None:
    source = _settlement(
        "source",
        population=20,
        food_units=10,
        wealth=100,
        security=1,
        labor={"farmer": 1, "smith": 1},
    )
    destination = _settlement(
        "destination",
        population=100,
        food_units=500,
        wealth=10_000,
        security=10,
        labor={},
    )
    migrate(source, destination, max_people=20, pressure=1.0)
    assert all(workers >= 0 for workers in source.labor.values())
    assert all(workers >= 0 for workers in destination.labor.values())


def test_fill_occupation_uses_only_unemployed_population() -> None:
    town = _settlement(
        "town",
        population=100,
        food_units=100,
        wealth=1000,
        security=5,
        labor={"farmer": 70, "smith": 20},
    )
    added = fill_occupation(town, "hunter", desired_workers=20)
    assert added == 10
    assert town.labor["hunter"] == 10
    assert employed_population(town) == 100


def test_migration_zero_pressure_moves_nobody() -> None:
    source = _settlement(
        "source",
        population=100,
        food_units=100,
        wealth=1000,
        security=5,
        labor={"farmer": 50},
    )
    destination = _settlement(
        "destination",
        population=100,
        food_units=100,
        wealth=1000,
        security=5,
        labor={"farmer": 50},
    )
    result = migrate(source, destination, max_people=50, pressure=0.0)
    assert result.people_moved == 0
    assert source.population == 100
    assert destination.population == 100


def test_repeated_migration_preserves_population_invariant() -> None:
    source = _settlement(
        "source",
        population=1000,
        food_units=100,
        wealth=1000,
        security=2,
        labor={"farmer": 300, "smith": 100},
    )
    destination = _settlement(
        "destination",
        population=100,
        food_units=1000,
        wealth=20_000,
        security=10,
        labor={"farmer": 80},
    )
    total = source.population + destination.population
    for _ in range(100):
        migrate(source, destination, max_people=25, pressure=0.8)
    assert source.population + destination.population == total
    assert source.population >= 0
    assert destination.population >= 0
