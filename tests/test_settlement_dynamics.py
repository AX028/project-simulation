from project_simulation import (
    Commodity,
    Market,
    OccupationRecipe,
    ProductionRecipe,
    SettlementDynamics,
    SettlementEconomicProfile,
    SettlementState,
    SimulationKernel,
    WorldState,
)

FOOD = Commodity("food", "Food", base_price=1.0, mass_kg=1.0)
WOOD = Commodity("wood", "Wood", base_price=2.0, mass_kg=1.0)


def _settlement(
    settlement_id: str,
    *,
    population: int = 100,
    food_units: float = 0.0,
    wealth: float = 1000.0,
    security: float = 6.0,
    labor: dict[str, int] | None = None,
) -> SettlementState:
    return SettlementState(
        settlement_id,
        settlement_id.title(),
        population=population,
        food_units=food_units,
        wealth=wealth,
        security=security,
        livestock=50.0,
        labor={} if labor is None else dict(labor),
    )


def _profile(
    settlement_id: str,
    *,
    initial_food: float,
    farmer_output: float = 2.0,
    occupation_targets: dict[str, int] | None = None,
) -> SettlementEconomicProfile:
    farming = ProductionRecipe(
        "farm-food",
        inputs={},
        outputs={"food": farmer_output},
        labor_hours=8.0,
    )
    return SettlementEconomicProfile(
        settlement_id,
        Market(stock={"food": initial_food}),
        commodities={"food": FOOD, "wood": WOOD},
        occupation_recipes=(OccupationRecipe("farmer", farming, 8.0),),
        occupation_targets={} if occupation_targets is None else occupation_targets,
    )


def test_daily_labor_produces_then_population_consumes_food() -> None:
    village = _settlement("v", population=10, labor={"farmer": 5})
    world = WorldState(settlements={"v": village})
    profile = _profile("v", initial_food=0.0)
    dynamics = SettlementDynamics(world, {"v": profile})

    result = dynamics.process_day("v")

    assert result.production[0].cycles == 5.0
    assert result.production[0].produced["food"] == 10.0
    assert result.food_required == 10.0
    assert result.food_consumed == 10.0
    assert result.shortage_ratio == 0.0
    assert village.food_units == 0.0


def test_shortage_reduces_security_and_wealth() -> None:
    village = _settlement(
        "v",
        population=100,
        wealth=1000.0,
        security=6.0,
        labor={"farmer": 5},
    )
    world = WorldState(settlements={"v": village})
    profile = _profile("v", initial_food=0.0, farmer_output=1.0)
    dynamics = SettlementDynamics(world, {"v": profile})

    result = dynamics.process_day("v")

    assert result.shortage_ratio > 0.9
    assert village.security < 6.0
    assert village.wealth < 1000.0
    assert village.prices["food"] > 1.0


def test_unemployed_workers_are_assigned_before_production() -> None:
    village = _settlement(
        "v",
        population=20,
        labor={"farmer": 2},
    )
    world = WorldState(settlements={"v": village})
    profile = _profile(
        "v",
        initial_food=0.0,
        occupation_targets={"farmer": 10},
    )
    dynamics = SettlementDynamics(world, {"v": profile})

    result = dynamics.process_day("v")

    assert result.workers_assigned["farmer"] == 8
    assert village.labor["farmer"] == 10
    assert result.production[0].cycles == 10.0


def test_daily_food_price_tracks_market_price() -> None:
    village = _settlement("v", population=100, labor={"farmer": 0})
    world = WorldState(settlements={"v": village})
    profile = _profile("v", initial_food=1.0)
    dynamics = SettlementDynamics(world, {"v": profile})

    dynamics.process_day("v")

    assert village.prices["food"] == profile.market.prices["food"]


def test_kernel_binding_runs_and_reschedules_daily_updates() -> None:
    village = _settlement("v", population=10, labor={"farmer": 5})
    world = WorldState(settlements={"v": village})
    profile = _profile("v", initial_food=0.0)
    dynamics = SettlementDynamics(world, {"v": profile})
    kernel = SimulationKernel(world)
    dynamics.bind_to_kernel(kernel, first_hour=24.0, interval_hours=24.0)

    kernel.advance_to(72.0)

    assert world.time_hours == 72.0
    assert village.security == 6.0
    assert profile.market.quantity("food") == 0.0


def test_migration_chooses_most_attractive_destination() -> None:
    source = _settlement(
        "source",
        population=200,
        wealth=100.0,
        security=1.0,
        labor={"farmer": 20},
    )
    medium = _settlement(
        "medium",
        population=100,
        wealth=1500.0,
        security=6.0,
        labor={"farmer": 60},
    )
    best = _settlement(
        "best",
        population=100,
        wealth=5000.0,
        security=10.0,
        labor={"farmer": 90},
    )
    for settlement in (source, medium, best):
        settlement.recompute_prices()

    world = WorldState(
        settlements={"source": source, "medium": medium, "best": best}
    )
    profiles = {
        settlement_id: _profile(settlement_id, initial_food=100.0)
        for settlement_id in world.settlements
    }
    dynamics = SettlementDynamics(world, profiles)

    result = dynamics.migrate_best_destination("source", max_people=50)

    assert result is not None
    assert result.destination_id == "best"
    assert result.people_moved > 0


def test_migration_preserves_total_population_through_dynamics() -> None:
    source = _settlement(
        "source",
        population=500,
        wealth=100.0,
        security=1.0,
        labor={"farmer": 100},
    )
    destination = _settlement(
        "destination",
        population=100,
        wealth=10_000.0,
        security=10.0,
        labor={"farmer": 90},
    )
    source.recompute_prices()
    destination.recompute_prices()
    world = WorldState(
        settlements={"source": source, "destination": destination}
    )
    dynamics = SettlementDynamics(
        world,
        {
            "source": _profile("source", initial_food=10.0),
            "destination": _profile("destination", initial_food=500.0),
        },
    )
    total = source.population + destination.population

    for _ in range(50):
        dynamics.migrate_best_destination("source", max_people=20)

    assert source.population + destination.population == total


def test_year_of_daily_updates_is_deterministic() -> None:
    def simulate() -> tuple[int, float, float, float]:
        village = _settlement(
            "v",
            population=50,
            wealth=1000.0,
            security=6.0,
            labor={"farmer": 30},
        )
        world = WorldState(settlements={"v": village})
        profile = _profile("v", initial_food=40.0, farmer_output=2.0)
        dynamics = SettlementDynamics(world, {"v": profile})
        for _ in range(365):
            dynamics.process_day("v")
        return (
            village.population,
            village.wealth,
            village.security,
            profile.market.quantity("food"),
        )

    assert simulate() == simulate()


def test_bad_profile_reference_is_rejected() -> None:
    world = WorldState(settlements={"v": _settlement("v")})
    profile = _profile("missing", initial_food=1.0)
    try:
        SettlementDynamics(world, {"missing": profile})
    except KeyError as exc:
        assert "unknown settlements" in str(exc)
    else:
        raise AssertionError("expected unknown profile to fail")


def test_nonpositive_kernel_interval_is_rejected() -> None:
    village = _settlement("v")
    world = WorldState(settlements={"v": village})
    dynamics = SettlementDynamics(
        world,
        {"v": _profile("v", initial_food=1.0)},
    )
    kernel = SimulationKernel(world)
    try:
        dynamics.bind_to_kernel(kernel, interval_hours=0.0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected invalid interval to fail")


def test_daily_settlement_event_is_not_a_kernel_builtin() -> None:
    village = _settlement("v", population=10, labor={"farmer": 5})
    world = WorldState(settlements={"v": village})
    kernel = SimulationKernel(world)
    before = (
        village.population,
        village.food_units,
        village.wealth,
        village.security,
    )

    kernel.schedule(24.0, "daily_settlement", settlement_id="v")
    kernel.advance_to(24.0)

    after = (
        village.population,
        village.food_units,
        village.wealth,
        village.security,
    )
    assert after == before
    assert world.history[-1].endswith("unhandled event daily_settlement")


def test_binding_uses_canonical_daily_settlement_event_kind() -> None:
    village = _settlement("v", population=10, labor={"farmer": 5})
    world = WorldState(settlements={"v": village})
    dynamics = SettlementDynamics(
        world,
        {"v": _profile("v", initial_food=0.0)},
    )
    kernel = SimulationKernel(world)

    dynamics.bind_to_kernel(kernel, first_hour=24.0)

    events = kernel.pending_events()
    assert len(events) == 1
    assert events[0].kind == "daily_settlement"


def test_binding_settlement_dynamics_twice_is_rejected() -> None:
    village = _settlement("v")
    world = WorldState(settlements={"v": village})
    dynamics = SettlementDynamics(
        world,
        {"v": _profile("v", initial_food=1.0)},
    )
    kernel = SimulationKernel(world)
    dynamics.bind_to_kernel(kernel)

    try:
        dynamics.bind_to_kernel(kernel)
    except ValueError as exc:
        assert "already bound" in str(exc)
    else:
        raise AssertionError("expected duplicate settlement binding to fail")
