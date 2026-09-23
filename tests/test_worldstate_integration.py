from project_simulation import (
    Claim,
    Goal,
    Loadout,
    Mind,
    PhysicalItem,
    Physiology,
    PlanAction,
    Planner,
    SpatialEntity,
    Vec3,
    WorldActor,
    WorldFact,
    transmit_claim,
)


def test_planner_builds_low_cost_food_plan() -> None:
    planner = Planner()
    actions = [
        PlanAction(
            "work",
            preconditions=(WorldFact("has_job", True),),
            effects=(WorldFact("has_money", True),),
            cost=2.0,
        ),
        PlanAction(
            "buy_food",
            preconditions=(WorldFact("has_money", True),),
            effects=(WorldFact("has_food", True),),
            cost=1.0,
        ),
        PlanAction(
            "steal_food",
            effects=(WorldFact("has_food", True),),
            cost=0.5,
            risk=5.0,
        ),
    ]
    plan = planner.make_plan(
        {"has_job": True, "has_money": False, "has_food": False},
        [WorldFact("has_food", True)],
        actions,
    )
    assert plan is not None
    assert [action.name for action in plan.actions] == ["work", "buy_food"]


def test_claim_confidence_depends_on_relationship() -> None:
    receiver = Mind()
    receiver.relationship("mira").trust = 80
    receiver.relationship("mira").familiarity = 70

    transmission = transmit_claim(
        sender_id="mira",
        receiver_id="tomas",
        receiver=receiver,
        claim=Claim(
            "bridge",
            "east bridge",
            "the east bridge has collapsed",
            0.9,
            "mira",
        ),
        now=12.0,
    )

    assert transmission.receiver_confidence > 0.7
    assert receiver.beliefs["bridge"].proposition == "the east bridge has collapsed"


def test_world_actor_perception_memory_and_encumbered_movement() -> None:
    mind = Mind(goals={"survive": Goal("survive", 1.0)})
    physiology = Physiology(70.0)
    loadout = Loadout(
        70.0,
        carried_loose=[
            PhysicalItem("crate", "Heavy crate", 20.0, 30.0, 0.8, 1.0)
        ],
    )
    actor = WorldActor(
        SpatialEntity("player", "Player", Vec3(0, 0, 0), facing=Vec3(0, 1, 0)),
        mind,
        physiology,
        loadout,
    )
    guard = SpatialEntity("guard", "Guard", Vec3(0, 8, 0))

    observations = actor.perceive([actor.spatial, guard])
    assert observations
    actor.encode_observation_as_memory(observations[0], now=1.0)
    assert mind.memories

    moved = actor.move_toward(Vec3(0, 10, 0), seconds=2.0)
    assert 0 < moved < actor.movement_speed_mps * 2.0
    assert physiology.fatigue > 0
