import pytest

from project_simulation import (
    AmbientAgent,
    AmbientNPCSimulation,
    GoalRequest,
    Injury,
    InjuryType,
    Loadout,
    Mind,
    NPCController,
    Physiology,
    PlanAction,
    RoutineBlock,
    RoutineSchedule,
    SpatialEntity,
    Vec3,
    WorldActor,
    WorldFact,
    build_demo_session,
)


def _agent() -> AmbientAgent:
    actor = WorldActor(
        SpatialEntity("npc", "NPC", Vec3(0.0, 0.0, 0.0)),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
        movement_speed_mps=1.0,
    )
    schedule = RoutineSchedule(
        (
            RoutineBlock(0.0, 8.0, "home", "home"),
            RoutineBlock(8.0, 17.0, "work", "work"),
            RoutineBlock(17.0, 0.0, "home", "home"),
        )
    )
    return AmbientAgent(
        actor=actor,
        controller=NPCController(schedule),
        locations={
            "home": Vec3(0.0, 0.0, 0.0),
            "work": Vec3(10.0, 0.0, 0.0),
        },
    )


def test_ambient_agent_moves_to_scheduled_location() -> None:
    agent = _agent()
    simulation = AmbientNPCSimulation({"npc": agent})

    events = simulation.advance(start_world_hour=8.0, seconds=10.0)

    assert agent.actor.spatial.position == Vec3(10.0, 0.0, 0.0)
    assert sum(event.distance_moved for event in events) == pytest.approx(10.0)


def test_ambient_agent_stays_at_home_before_work() -> None:
    agent = _agent()
    simulation = AmbientNPCSimulation({"npc": agent})

    simulation.advance(start_world_hour=7.0, seconds=60.0)

    assert agent.actor.spatial.position == Vec3(0.0, 0.0, 0.0)


def test_schedule_transition_inside_long_advance_is_respected() -> None:
    agent = _agent()
    simulation = AmbientNPCSimulation({"npc": agent})

    simulation.advance(start_world_hour=7.999, seconds=120.0)

    assert agent.actor.spatial.position == Vec3(10.0, 0.0, 0.0)


def test_chunked_and_single_advance_have_same_position() -> None:
    single = _agent()
    chunked = _agent()
    one = AmbientNPCSimulation({"npc": single})
    two = AmbientNPCSimulation({"npc": chunked})

    one.advance(start_world_hour=7.99, seconds=120.0)
    two.advance(start_world_hour=7.99, seconds=60.0)
    two.advance(
        start_world_hour=7.99 + 60.0 / 3600.0,
        seconds=60.0,
    )

    assert single.actor.spatial.position == chunked.actor.spatial.position


def test_skip_actor_ids_prevents_ambient_double_advance() -> None:
    agent = _agent()
    agent.actor.physiology.add_injury(
        Injury(
            "torso",
            InjuryType.LACERATION,
            severity=0.2,
            bleeding_ml_per_min=60.0,
        )
    )
    simulation = AmbientNPCSimulation({"npc": agent})

    simulation.advance(
        start_world_hour=0.0,
        seconds=60.0,
        skip_actor_ids=frozenset({"npc"}),
    )

    assert agent.actor.physiology.blood_lost_ml == 0.0


def test_session_ticks_bound_npc_physiology_exactly_once() -> None:
    session = build_demo_session(5)
    mira = session.actors["mira"]
    mira.physiology.add_injury(
        Injury(
            "torso",
            InjuryType.LACERATION,
            severity=0.2,
            bleeding_ml_per_min=60.0,
        )
    )

    session.execute("wait 60")

    assert mira.physiology.blood_lost_ml == pytest.approx(60.0)


def test_zero_time_command_does_not_move_ambient_npc() -> None:
    session = build_demo_session(5)
    assert session.kernel is not None
    session.kernel.world.time_hours = 8.0
    before = session.actors["mira"].spatial.position

    session.execute("status")

    assert session.actors["mira"].spatial.position == before


def test_session_wait_at_work_time_moves_mira_toward_market() -> None:
    session = build_demo_session(5)
    assert session.kernel is not None
    session.kernel.world.time_hours = 8.0
    before = session.actors["mira"].spatial.position

    session.execute("wait 1")

    after = session.actors["mira"].spatial.position
    assert after.x > before.x
    assert after.y == pytest.approx(before.y)


def test_urgent_goal_moves_to_action_location_and_applies_effect() -> None:
    agent = _agent()
    action = PlanAction(
        "take_shelter",
        preconditions=(WorldFact("danger", True),),
        effects=(WorldFact("safe", True),),
        cost=1.0,
    )
    agent.controller.actions = (action,)
    agent.controller.facts = {"danger": True, "safe": False}
    agent.action_locations["take_shelter"] = "shelter"
    agent.locations["shelter"] = Vec3(2.0, 0.0, 0.0)

    simulation = AmbientNPCSimulation({"npc": agent})
    simulation.set_urgent_goal(
        "npc",
        GoalRequest(
            "survive",
            (WorldFact("safe", True),),
            priority=100.0,
        ),
    )
    simulation.advance(start_world_hour=2.0, seconds=3.0)

    assert agent.actor.spatial.position == Vec3(2.0, 0.0, 0.0)
    assert agent.controller.facts["safe"] is True
    assert "npc" not in simulation.urgent_goals


def test_unknown_ambient_location_is_rejected() -> None:
    agent = _agent()
    del agent.locations["work"]
    simulation = AmbientNPCSimulation({"npc": agent})

    with pytest.raises(KeyError, match="unknown ambient location"):
        simulation.advance(start_world_hour=8.0, seconds=1.0)


def test_duplicate_ambient_agent_is_rejected() -> None:
    agent = _agent()
    simulation = AmbientNPCSimulation()
    simulation.add_agent(agent)
    with pytest.raises(ValueError, match="already registered"):
        simulation.add_agent(agent)


def test_hundred_day_routine_simulation_is_deterministic() -> None:
    def simulate() -> tuple[Vec3, float]:
        agent = _agent()
        simulation = AmbientNPCSimulation({"npc": agent})
        for day in range(100):
            simulation.advance(
                start_world_hour=day * 24.0,
                seconds=24.0 * 3600.0,
            )
        return agent.actor.spatial.position, agent.actor.physiology.fatigue

    first = simulate()
    second = simulate()
    assert first[0] == second[0]
    assert first[1] == pytest.approx(second[1])
