import pytest

from project_simulation import (
    Commodity,
    Market,
    ProductionRecipe,
    TradeRoute,
    run_production,
    transfer,
)

GRAIN = Commodity("grain", "Grain", base_price=2.0, mass_kg=1.0)
FLOUR = Commodity("flour", "Flour", base_price=4.0, mass_kg=1.0)


def test_production_consumes_inputs_and_conserves_recipe_ratios() -> None:
    market = Market(stock={"grain": 100.0})
    recipe = ProductionRecipe(
        "milling",
        inputs={"grain": 2.0},
        outputs={"flour": 1.5},
        labor_hours=1.0,
    )
    result = run_production(market, recipe, available_labor_hours=10.0)
    assert result.cycles == 10.0
    assert result.consumed == {"grain": 20.0}
    assert result.produced == {"flour": 15.0}
    assert market.quantity("grain") == 80.0
    assert market.quantity("flour") == 15.0


def test_production_is_limited_by_scarcest_input() -> None:
    market = Market(stock={"grain": 5.0})
    recipe = ProductionRecipe(
        "milling",
        inputs={"grain": 2.0},
        outputs={"flour": 1.0},
        labor_hours=1.0,
    )
    result = run_production(market, recipe, available_labor_hours=100.0)
    assert result.cycles == 2.5
    assert market.quantity("grain") == 0.0
    assert market.quantity("flour") == 2.5


def test_requested_production_cycles_cap_output() -> None:
    market = Market(stock={"grain": 100.0})
    recipe = ProductionRecipe(
        "milling",
        inputs={"grain": 1.0},
        outputs={"flour": 1.0},
        labor_hours=2.0,
    )
    result = run_production(
        market,
        recipe,
        available_labor_hours=100.0,
        requested_cycles=7.0,
    )
    assert result.cycles == 7.0
    assert result.labor_used == 14.0


def test_market_price_rises_with_demand_and_falls_with_supply() -> None:
    scarce = Market(stock={"grain": 10.0}, demand={"grain": 100.0})
    abundant = Market(stock={"grain": 100.0}, demand={"grain": 10.0})
    scarce_price = scarce.update_price(GRAIN)
    abundant_price = abundant.update_price(GRAIN)
    assert scarce_price > GRAIN.base_price
    assert abundant_price < GRAIN.base_price
    assert scarce_price > abundant_price


def test_trade_transfer_conserves_quantity() -> None:
    source = Market(stock={"grain": 100.0})
    destination = Market(stock={"grain": 12.0})
    route = TradeRoute(distance_km=20.0, risk=0.1, capacity_kg=50.0)
    before = source.quantity("grain") + destination.quantity("grain")
    result = transfer(source, destination, GRAIN, route, requested_quantity=80.0)
    after = source.quantity("grain") + destination.quantity("grain")
    assert result.quantity == 50.0
    assert result.cargo_mass_kg == 50.0
    assert before == after


def test_trade_cannot_move_more_than_source_stock() -> None:
    source = Market(stock={"grain": 3.0})
    destination = Market()
    route = TradeRoute(distance_km=1.0, risk=0.0, capacity_kg=100.0)
    result = transfer(source, destination, GRAIN, route, requested_quantity=20.0)
    assert result.quantity == 3.0
    assert source.quantity("grain") == 0.0
    assert destination.quantity("grain") == 3.0


def test_transport_and_risk_increase_landed_cost() -> None:
    near = TradeRoute(distance_km=1.0, risk=0.0, capacity_kg=100.0)
    far = TradeRoute(distance_km=100.0, risk=0.7, capacity_kg=100.0)
    assert far.landed_cost_multiplier(GRAIN) > near.landed_cost_multiplier(GRAIN)


@pytest.mark.parametrize(
    ("constructor", "message"),
    [
        (lambda: TradeRoute(-1.0, 0.0, 1.0), "distance"),
        (lambda: TradeRoute(1.0, -0.1, 1.0), "risk"),
        (
            lambda: ProductionRecipe(
                "bad",
                inputs={"grain": -1.0},
                outputs={"flour": 1.0},
                labor_hours=1.0,
            ),
            "inputs",
        ),
    ],
)
def test_invalid_economy_parameters_are_rejected(constructor, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        constructor()


def test_thousand_trade_operations_preserve_total_stock() -> None:
    source = Market(stock={"grain": 10_000.0})
    destination = Market(stock={"grain": 0.0})
    route = TradeRoute(distance_km=5.0, risk=0.2, capacity_kg=13.0)
    initial = source.quantity("grain") + destination.quantity("grain")
    for _ in range(1000):
        transfer(source, destination, GRAIN, route, requested_quantity=2.0)
    final = source.quantity("grain") + destination.quantity("grain")
    assert final == pytest.approx(initial)
    assert source.quantity("grain") >= 0.0
    assert destination.quantity("grain") >= 0.0
