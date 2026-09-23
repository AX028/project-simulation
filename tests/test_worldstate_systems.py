from project_simulation.cognition import CandidateAction, Goal, Memory, Mind
from project_simulation.physiology import Container, Loadout, PhysicalItem, Physiology
from project_simulation.simulation import SettlementState, SimulationKernel, WorldState
from project_simulation.spatial import Bounds, SpatialEntity, Vec3, observe
from project_simulation.textui import tactical_map


def test_observation_respects_distance_and_occlusion() -> None:
    observer = SpatialEntity("p", "Player", Vec3(0, 0, 0), facing=Vec3(0, 1, 0))
    target = SpatialEntity("g", "Guard", Vec3(0, 10, 0))
    wall = SpatialEntity(
        "w",
        "Wall",
        Vec3(0, 5, 0),
        bounds=Bounds(2, 0.2, 3),
        tags=frozenset({"occluder"}),
    )
    assert observe(observer, target) is not None
    assert observe(observer, target, obstacles=[wall]) is None


def test_memory_decay_and_goal_utility() -> None:
    mind = Mind(goals={"survive": Goal("survive", 2.0), "protect": Goal("protect", 3.0)})
    memory = Memory("wolf", "wolves circle prey", 0.9, 0.8, 0.95, 0.9, "direct", 0.0)
    assert memory.accessibility(1.0) > memory.accessibility(100.0)

    flee = CandidateAction("flee", {"survive": 1.0, "protect": -1.0})
    hold = CandidateAction("hold", {"survive": -0.2, "protect": 1.0}, risk=0.2)
    assert mind.choose_action([flee, hold]).name == "hold"


def test_loadout_is_continuous_and_spatially_constrained() -> None:
    pack = Container("pack", 20.0, 0.8, 2.0)
    knife = PhysicalItem("knife", "Knife", 0.3, 0.2, 0.25, 0.7)
    spear = PhysicalItem("spear", "Spear", 2.0, 1.5, 2.2, 0.5)
    pack.add(knife)
    assert not pack.can_fit(spear)
    loadout = Loadout(70.0, containers=[pack], carried_loose=[spear])
    assert loadout.load_ratio > 0
    assert loadout.retrieval_time("knife") > loadout.retrieval_time("spear")


def test_physiology_tracks_blood_loss_and_exertion() -> None:
    body = Physiology(70.0)
    before = body.performance_modifier
    body.tick(120, exertion=0.8, ambient_c=30)
    assert body.fatigue > 0
    assert body.hydration_l < 3.0
    assert body.performance_modifier < before


def test_wolf_attack_changes_settlement_prices() -> None:
    village = SettlementState(
        "v1",
        "Mera",
        population=100,
        food_units=120,
        wealth=1000,
        security=5,
        livestock=100,
        labor={"farmer": 40, "hunter": 2},
    )
    world = WorldState(settlements={"v1": village})
    kernel = SimulationKernel(world)
    village.recompute_prices()
    before_meat = village.prices["meat"]
    kernel.schedule(4.0, "wolf_attack", settlement_id="v1", severity=0.5)
    kernel.advance_to(4.0)
    assert village.livestock == 50
    assert village.prices["meat"] > before_meat
    assert world.history


def test_tactical_map_contains_player_and_hostile() -> None:
    player = SpatialEntity("p", "Player", Vec3(0, 0, 0))
    hostile = SpatialEntity("h", "Bandit", Vec3(2, 2, 0), tags=frozenset({"hostile"}))
    rendered = tactical_map(player, [player, hostile])
    assert "@" in rendered
    assert "H" in rendered
