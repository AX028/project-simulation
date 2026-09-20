import pytest

from project_simulation import (
    GoalRequest,
    NPCController,
    PlanAction,
    RoutineBlock,
    RoutineSchedule,
    WorldFact,
)


def _controller() -> NPCController:
    schedule = RoutineSchedule(
        (
            RoutineBlock(8.0, 17.0, "work", "forge", priority=1.0),
            RoutineBlock(22.0, 6.0, "sleep", "home", priority=1.0),
        ),
        fallback_activity="free_time",
        fallback_location_id="town",
    )
    actions = (
        PlanAction(
            "take_shelter",
            preconditions=(WorldFact("danger_nearby", True),),
            effects=(WorldFact("safe", True),),
            cost=1.0,
        ),
        PlanAction(
            "go_home",
            preconditions=(WorldFact("safe", True),),
            effects=(WorldFact("with_family", True),),
            cost=1.0,
        ),
    )
    return NPCController(
        schedule=schedule,
        actions=actions,
        facts={"danger_nearby": True, "safe": False, "with_family": False},
    )


def test_routine_used_without_urgent_goal() -> None:
    directive = _controller().choose_directive(10.0)
    assert directive.source == "routine"
    assert directive.activity == "work"
    assert directive.location_id == "forge"


def test_low_priority_goal_does_not_break_routine() -> None:
    goal = GoalRequest(
        "minor curiosity",
        facts=(WorldFact("safe", True),),
        priority=0.5,
    )
    directive = _controller().choose_directive(10.0, urgent_goal=goal)
    assert directive.source == "routine"
    assert directive.activity == "work"


def test_high_priority_goal_overrides_routine_with_first_plan_step() -> None:
    goal = GoalRequest(
        "protect family",
        facts=(WorldFact("with_family", True),),
        priority=10.0,
    )
    directive = _controller().choose_directive(10.0, urgent_goal=goal)
    assert directive.source == "goal:protect family"
    assert directive.activity == "take_shelter"
    assert directive.plan is not None
    assert [action.name for action in directive.plan.actions] == [
        "take_shelter",
        "go_home",
    ]


def test_apply_action_advances_controller_facts() -> None:
    controller = _controller()
    action = controller.actions[0]
    controller.apply_action(action)
    assert controller.facts["safe"] is True


def test_apply_action_rejects_unsatisfied_preconditions() -> None:
    controller = _controller()
    controller.facts["danger_nearby"] = False
    with pytest.raises(ValueError, match="preconditions"):
        controller.apply_action(controller.actions[0])


def test_unreachable_goal_falls_back_to_routine() -> None:
    controller = _controller()
    goal = GoalRequest(
        "become king",
        facts=(WorldFact("king", True),),
        priority=100.0,
    )
    directive = controller.choose_directive(10.0, urgent_goal=goal)
    assert directive.source == "routine"
    assert directive.activity == "work"


def test_exact_schedule_overlap_catches_sub_minute_conflict() -> None:
    with pytest.raises(ValueError, match="overlapping"):
        RoutineSchedule(
            (
                RoutineBlock(8.0, 8.01, "a", "one", priority=1.0),
                RoutineBlock(8.005, 8.02, "b", "two", priority=1.0),
            )
        )


def test_different_priority_blocks_may_overlap() -> None:
    schedule = RoutineSchedule(
        (
            RoutineBlock(8.0, 12.0, "work", "forge", priority=1.0),
            RoutineBlock(9.0, 10.0, "meeting", "hall", priority=5.0),
        )
    )
    directive = schedule.activity_at(9.5)
    assert directive.activity == "meeting"
    assert directive.location_id == "hall"


def test_controller_decisions_are_repeatable() -> None:
    goal = GoalRequest(
        "protect family",
        facts=(WorldFact("with_family", True),),
        priority=10.0,
    )
    results = {
        _controller().choose_directive(10.0, urgent_goal=goal).activity
        for _ in range(100)
    }
    assert results == {"take_shelter"}
