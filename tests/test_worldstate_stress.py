import random

from project_simulation import (
    CandidateAction,
    Goal,
    Loadout,
    Memory,
    Mind,
    PhysicalItem,
    Physiology,
    PlanAction,
    Planner,
    SettlementState,
    SimulationKernel,
    SimulationLOD,
    SpatialEntity,
    Vec3,
    WorldFact,
    WorldState,
    transmission_confidence,
)
from project_simulation.spatial import observe


def test_spatial_observation_is_repeatable_across_many_entities() -> None:
    rng = random.Random(4321)
    observer = SpatialEntity("observer", "Observer", Vec3(0, 0, 0), facing=Vec3(0, 1, 0))
    targets = [
        SpatialEntity(
            f"target-{index}",
            "Target",
            Vec3(rng.uniform(-30, 30), rng.uniform(1, 80), rng.uniform(0, 4)),
        )
        for index in range(100)
    ]
    first = [observe(observer, target) for target in targets]
    second = [observe(observer, target) for target in targets]
    assert first == second


def test_memory_accessibility_never_increases_with_age() -> None:
    memory = Memory(
        "wolf",
        "wolves circle prey",
        importance=0.9,
        emotional_intensity=0.8,
        confidence=0.9,
        accuracy=0.9,
        source="direct",
        created_at=0.0,
    )
    values = [memory.accessibility(float(hour)) for hour in range(101)]
    assert all(later <= earlier for earlier, later in zip(values, values[1:], strict=True))


def test_planner_is_deterministic_over_repeated_runs() -> None:
    planner = Planner()
    actions = (
        PlanAction(
            "work",
            preconditions=(WorldFact("job", True),),
            effects=(WorldFact("money", True),),
            cost=2.0,
        ),
        PlanAction(
            "buy",
            preconditions=(WorldFact("money", True),),
            effects=(WorldFact("food", True),),
            cost=1.0,
        ),
        PlanAction("steal", effects=(WorldFact("food", True),), cost=0.2, risk=8.0),
    )
    expected = ("work", "buy")
    for _ in range(100):
        plan = planner.make_plan(
            {"job": True, "money": False, "food": False},
            (WorldFact("food", True),),
            actions,
        )
        assert plan is not None
        assert tuple(action.name for action in plan.actions) == expected


def test_information_confidence_is_always_bounded() -> None:
    for trust in range(-100, 101, 10):
        for familiarity in range(0, 101, 10):
            confidence = transmission_confidence(
                claim_confidence=0.87,
                sender_trust=float(trust),
                sender_familiarity=float(familiarity),
                repetitions=3,
            )
            assert 0.0 <= confidence <= 1.0


def test_utility_choice_is_stable_for_equal_inputs() -> None:
    mind = Mind(goals={"survive": Goal("survive", 2.0), "protect": Goal("protect", 3.0)})
    actions = (
        CandidateAction("flee", {"survive": 1.0, "protect": -1.0}),
        CandidateAction("hold", {"survive": -0.2, "protect": 1.0}, risk=0.2),
    )
    assert {mind.choose_action(actions).name for _ in range(100)} == {"hold"}


def test_encumbrance_penalty_increases_monotonically() -> None:
    multipliers = []
    for count in range(11):
        items = [
            PhysicalItem(f"rock-{index}", "Rock", 2.0, 1.0)
            for index in range(count)
        ]
        multipliers.append(Loadout(70.0, carried_loose=items).fatigue_multiplier)
    assert all(later >= earlier for earlier, later in zip(multipliers, multipliers[1:], strict=True))


def test_physiology_remains_within_performance_bounds_under_stress() -> None:
    for exertion in (0.0, 0.25, 0.5, 0.75, 1.0):
        body = Physiology(70.0)
        for _ in range(24):
            body.tick(60.0, exertion=exertion, ambient_c=20.0)
            assert 0.05 <= body.performance_modifier <= 1.0


def _simulate_village() -> SettlementState:
    village = SettlementState(
        "v1",
        "Mera",
        population=180,
        food_units=260.0,
        wealth=1000.0,
        security=6.0,
        livestock=120.0,
        labor={"farmer": 120, "hunter": 5},
    )
    world = WorldState(settlements={"v1": village})
    kernel = SimulationKernel(world)
    kernel.schedule(24.0, "daily_settlement", settlement_id="v1")
    kernel.schedule(240.0, "wolf_attack", settlement_id="v1", severity=0.2)
    kernel.advance_to(24.0 * 30)
    return village


def test_long_running_settlement_simulation_is_deterministic() -> None:
    first = _simulate_village()
    second = _simulate_village()
    assert first.population == second.population
    assert first.food_units == second.food_units
    assert first.livestock == second.livestock
    assert first.prices == second.prices


def test_lod_boundaries_are_stable() -> None:
    kernel = SimulationKernel(WorldState())
    cases = (
        (0.0, SimulationLOD.IMMEDIATE),
        (80.0, SimulationLOD.IMMEDIATE),
        (80.1, SimulationLOD.LOCAL),
        (1500.0, SimulationLOD.LOCAL),
        (1500.1, SimulationLOD.SETTLEMENT),
        (25_000.0, SimulationLOD.SETTLEMENT),
        (25_000.1, SimulationLOD.REGION),
        (300_000.0, SimulationLOD.REGION),
        (300_000.1, SimulationLOD.WORLD),
    )
    for distance, expected in cases:
        assert kernel.choose_lod(distance) is expected
