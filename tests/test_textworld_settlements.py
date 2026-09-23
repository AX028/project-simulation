import pytest

from project_simulation import (
    TextWorldReplayStore,
    TextWorldSession,
    build_demo_session,
    session_digest,
)
from project_simulation.simulation import ScheduledEvent


def _macro_snapshot(session: TextWorldSession) -> tuple[object, ...]:
    assert session.kernel is not None
    world = session.kernel.world
    settlements = tuple(
        (
            settlement_id,
            settlement.population,
            settlement.food_units,
            settlement.wealth,
            settlement.security,
            settlement.livestock,
            tuple(sorted(settlement.labor.items())),
            tuple(sorted(settlement.prices.items())),
        )
        for settlement_id, settlement in sorted(world.settlements.items())
    )
    events = tuple(
        (
            event.at,
            event.sequence,
            event.kind,
            tuple(sorted(event.payload.items())),
        )
        for event in session.kernel.pending_events()
    )
    return world.time_hours, settlements, events


def test_demo_seeds_playable_settlements_and_economic_profiles() -> None:
    session = build_demo_session(101)

    assert session.kernel is not None
    assert session.settlement_dynamics is not None
    assert tuple(sorted(session.kernel.world.settlements)) == (
        "greenhollow",
        "stoneford",
    )
    assert tuple(sorted(session.settlement_dynamics.profiles)) == (
        "greenhollow",
        "stoneford",
    )
    assert [
        event.payload["settlement_id"]
        for event in session.kernel.pending_events()
    ] == ["greenhollow", "stoneford"]

    output = session.execute("status").output
    assert "Greenhollow pop 120, food 70.0, price" in output
    assert "Stoneford pop 80, food 180.0, price" in output


def test_text_world_daily_boundary_fires_once() -> None:
    session = build_demo_session(102)
    assert session.kernel is not None
    greenhollow = session.kernel.world.settlements["greenhollow"]
    initial = (greenhollow.population, greenhollow.food_units)

    session.execute("wait 86399")
    assert (greenhollow.population, greenhollow.food_units) == initial

    session.execute("wait 1")
    at_boundary = (greenhollow.population, greenhollow.food_units)
    assert at_boundary != initial
    assert {event.at for event in session.kernel.pending_events()} == {48.0}

    session.execute("wait 1")
    assert (greenhollow.population, greenhollow.food_units) == at_boundary


def test_chunked_and_uninterrupted_daily_advances_are_equivalent() -> None:
    uninterrupted = build_demo_session(103)
    chunked = build_demo_session(103)
    assert uninterrupted.kernel is not None
    initial_population = sum(
        settlement.population
        for settlement in uninterrupted.kernel.world.settlements.values()
    )

    uninterrupted.execute("wait 259200")
    for seconds in (43200, 43200, 86400, 86400):
        chunked.execute(f"wait {seconds}")

    assert _macro_snapshot(chunked) == _macro_snapshot(uninterrupted)
    final_population = sum(
        settlement.population
        for settlement in uninterrupted.kernel.world.settlements.values()
    )
    assert final_population == initial_population
    assert [
        (event.at, event.sequence, event.payload["settlement_id"])
        for event in uninterrupted.kernel.pending_events()
    ] == [
        (96.0, 6, "greenhollow"),
        (96.0, 7, "stoneford"),
    ]


def test_settlement_progress_replays_deterministically(tmp_path) -> None:
    commands = ("status", "wait 86400", "status", "wait 172800", "status")
    first = build_demo_session(104)
    second = build_demo_session(104)

    assert first.replay(commands) == second.replay(commands)
    assert session_digest(first) == session_digest(second)

    save_path = tmp_path / "settlement-replay.json"
    TextWorldReplayStore.write(first, save_path)
    restored = TextWorldReplayStore.read(save_path)
    assert session_digest(restored) == session_digest(first)


def test_replay_identity_includes_settlements_and_pending_event_order() -> None:
    baseline = build_demo_session(105)
    changed_settlement = build_demo_session(105)
    assert changed_settlement.kernel is not None
    changed_settlement.kernel.world.settlements["greenhollow"].food_units += 1.0
    assert session_digest(changed_settlement) != session_digest(baseline)

    reordered = build_demo_session(105)
    assert reordered.kernel is not None
    events = reordered.kernel.pending_events()
    reordered.kernel.replace_pending_events(
        (
            ScheduledEvent(
                events[1].at,
                events[0].sequence,
                events[1].kind,
                dict(events[1].payload),
            ),
            ScheduledEvent(
                events[0].at,
                events[1].sequence,
                events[0].kind,
                dict(events[0].payload),
            ),
        )
    )
    assert [
        event.payload["settlement_id"]
        for event in reordered.kernel.pending_events()
    ] == ["stoneford", "greenhollow"]
    assert session_digest(reordered) != session_digest(baseline)


@pytest.mark.parametrize("max_migrants", [-1, -10])
def test_daily_binding_rejects_negative_migration_bounds(max_migrants: int) -> None:
    session = build_demo_session(106)
    assert session.settlement_dynamics is not None
    assert session.kernel is not None

    with pytest.raises(ValueError, match="may not be negative"):
        session.settlement_dynamics.bind_to_kernel(
            session.kernel,
            max_migrants_per_day=max_migrants,
        )
