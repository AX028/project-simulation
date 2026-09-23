"""Behavioral coverage for shared environment inputs and the session clock."""

import re

import pytest

from project_simulation import (
    Projectile,
    ProjectileSimulator,
    ProjectileSpec,
    Vec3,
    build_demo_session,
    move_actor_with_collisions,
)
from project_simulation.environment import EnvironmentState, WeatherKind
from project_simulation.textworld_combat_commands import emit_sound


def _clarity(hour: float, weather: WeatherKind) -> float:
    session = build_demo_session(11)
    session.environment.world_hour = hour
    assert session.kernel is not None
    session.kernel.world.time_hours = hour
    session.environment.weather = weather
    output = session.execute("inspect Wolf").output
    match = re.search(r"clarity ([0-9]+(?:\.[0-9]+)?)", output)
    assert match is not None, output
    return float(match.group(1))


def test_day_dawn_and_night_change_visual_clarity() -> None:
    noon = _clarity(12.0, WeatherKind.CLEAR)
    dawn = _clarity(6.5, WeatherKind.CLEAR)
    night = _clarity(2.0, WeatherKind.CLEAR)

    assert noon > dawn > night


def test_fog_reduces_visual_clarity_at_the_same_hour() -> None:
    clear = _clarity(12.0, WeatherKind.CLEAR)
    fog = _clarity(12.0, WeatherKind.FOG)

    assert fog < clear


def test_crosswind_displaces_a_projectile() -> None:
    def landing(wind: Vec3) -> Vec3:
        spec = ProjectileSpec(
            "stone",
            mass_kg=0.2,
            radius_m=0.02,
            drag_coefficient=0.2,
            gravity_mps2=0.0,
            max_lifetime_s=1.5,
        )
        projectile = Projectile(
            "stone-1",
            spec,
            Vec3(0.0, 0.0, 1.0),
            Vec3(20.0, 0.0, 0.0),
        )
        simulator = ProjectileSimulator()
        simulator.launch(projectile)
        steps = simulator.simulate_until_inactive(
            projectile.projectile_id,
            (),
            dt_s=0.05,
            wind_velocity=wind,
        )
        assert steps
        return steps[-1].end_position

    calm = landing(Vec3(0.0, 0.0, 0.0))
    crosswind = landing(Vec3(0.0, 12.0, 0.0))

    assert calm.y == pytest.approx(0.0, abs=1e-9)
    assert crosswind.y > calm.y + 0.2


def test_storm_noise_hides_a_sound_that_is_heard_in_clear_air() -> None:
    def heard(weather: WeatherKind):
        session = build_demo_session(4)
        session.environment.weather = weather
        mira = session.actors["mira"].spatial.position
        return emit_sound(
            session,
            category="speech",
            description="a quiet call",
            position=mira + Vec3(0.4, 0.0, 0.0),
            loudness_db_at_1m=30.0,
            source_id=session.player_id,
        )

    clear = heard(WeatherKind.CLEAR)
    storm = heard(WeatherKind.STORM)

    assert any(item.listener_id == "mira" for item in clear)
    assert not any(item.listener_id == "mira" for item in storm)


def test_snow_and_wet_ground_slow_movement() -> None:
    def elapsed(weather: WeatherKind, wetness: float = 0.0) -> float:
        session = build_demo_session(2)
        session.environment.weather = weather
        session.environment.ground_wetness = wetness
        session.execute("move north 4")
        return session.elapsed_seconds

    clear = elapsed(WeatherKind.CLEAR)
    assert elapsed(WeatherKind.SNOW) > clear
    assert elapsed(WeatherKind.CLEAR, wetness=1.0) > clear


def test_fixed_duration_travel_is_shorter_in_snow() -> None:
    def traveled(weather: WeatherKind) -> float:
        session = build_demo_session(8)
        session.environment.weather = weather
        actor = session.player
        start = Vec3(
            actor.spatial.position.x,
            actor.spatial.position.y,
            actor.spatial.position.z,
        )
        move_actor_with_collisions(
            actor,
            Vec3(0.0, 20.0, 0.0),
            2.0,
            session.entities,
            doors=session.doors.values(),
            speed_multiplier=session.environment.movement_speed_multiplier,
            ambient_c=session.environment.ambient_temperature_c,
        )
        return actor.spatial.position.distance_to(start)

    assert traveled(WeatherKind.SNOW) < traveled(WeatherKind.CLEAR)


def test_snow_slows_ambient_npc_travel() -> None:
    def mira_x(weather: WeatherKind) -> float:
        session = build_demo_session(2)
        session.environment.world_hour = 8.0
        assert session.kernel is not None
        session.kernel.world.time_hours = 8.0
        session.environment.weather = weather
        session.actors["mira"].spatial.position = Vec3(2.0, 2.0, 0.0)
        session.execute("wait 1")
        return session.actors["mira"].spatial.position.x

    assert mira_x(WeatherKind.CLEAR) > mira_x(WeatherKind.SNOW)


def test_ambient_temperature_changes_core_temperature() -> None:
    def core(base_temperature_c: float) -> float:
        session = build_demo_session(2)
        session.environment.base_temperature_c = base_temperature_c
        session.execute("wait 600")
        return session.player.physiology.core_temperature_c

    assert core(35.0) > core(-10.0)


def test_rain_increases_ground_wetness_through_session_time() -> None:
    session = build_demo_session(2)
    session.environment.weather = WeatherKind.RAIN
    assert session.environment.ground_wetness == 0.0

    session.execute("wait 3600")

    assert session.environment.ground_wetness > 0.0
    assert session.environment.world_hour == pytest.approx(1.0)


def test_first_action_keeps_environment_kernel_and_elapsed_clocks_aligned() -> None:
    session = build_demo_session(1)
    assert session.kernel is not None
    assert session.environment.world_hour == 0.0
    assert session.kernel.world.time_hours == 0.0
    assert session.elapsed_seconds == 0.0

    session.execute("wait 3600")
    session.execute("move north 2")

    assert session.environment.world_hour == pytest.approx(
        session.kernel.world.time_hours
    )
    assert session.elapsed_seconds / 3600.0 == pytest.approx(
        session.kernel.world.time_hours
    )
    assert session.environment.world_hour > 1.0


def test_kernel_clock_replaces_a_divergent_environment_hour() -> None:
    session = build_demo_session(1)
    assert session.kernel is not None
    session.environment.world_hour = 12.0

    session.execute("wait 10")

    assert session.kernel.world.time_hours == pytest.approx(10.0 / 3600.0)
    assert session.environment.world_hour == pytest.approx(
        session.kernel.world.time_hours
    )
    assert session.elapsed_seconds == pytest.approx(10.0)


def test_clock_rejects_backward_and_non_finite_steps_before_mutation() -> None:
    session = build_demo_session(1)
    fatigue = session.player.physiology.fatigue

    with pytest.raises(ValueError, match="backward"):
        session._advance_clock(-5)
    with pytest.raises(ValueError, match="finite"):
        session._advance_clock(float("nan"))

    assert session.elapsed_seconds == 0.0
    assert session.environment.world_hour == 0.0
    assert session.player.physiology.fatigue == fatigue


def test_extreme_ambient_temperature_does_not_partially_advance() -> None:
    session = build_demo_session(1)
    assert session.kernel is not None
    session.environment.base_temperature_c = 400.0
    core = session.player.physiology.core_temperature_c

    with pytest.raises(ValueError, match="ambient temperature"):
        session.execute("wait 10")

    assert session.player.physiology.core_temperature_c == core
    assert session.elapsed_seconds == 0.0
    assert session.kernel.world.time_hours == 0.0
    assert session.environment.world_hour == 0.0
    assert session.command_history == []


def test_invalid_environment_inputs_leave_previous_state_intact() -> None:
    with pytest.raises(ValueError):
        EnvironmentState(world_hour=float("nan"))
    with pytest.raises(ValueError):
        EnvironmentState(base_temperature_c=float("inf"))
    with pytest.raises(ValueError):
        EnvironmentState(precipitation=1.1)
    with pytest.raises(ValueError):
        EnvironmentState(wind_velocity=Vec3(float("nan"), 0.0, 0.0))

    env = EnvironmentState(world_hour=3.0, ground_wetness=0.4, precipitation=0.2)
    with pytest.raises(ValueError):
        env.world_hour = float("inf")
    with pytest.raises(ValueError):
        env.precipitation = -0.01
    with pytest.raises(ValueError):
        env.weather = "rain"  # type: ignore[assignment]
    with pytest.raises(ValueError):
        env.advance(-0.25)
    with pytest.raises(ValueError):
        env.advance(float("nan"))

    assert env.world_hour == 3.0
    assert env.ground_wetness == 0.4
    assert env.precipitation == 0.2
    assert env.weather is WeatherKind.CLEAR


def test_night_time_advancement_matches_when_subdivided() -> None:
    def wetness(steps: int) -> float:
        env = EnvironmentState(world_hour=0.0, ground_wetness=0.8)
        span = 5.0
        for _ in range(steps):
            env.advance(span / steps)
        return env.ground_wetness

    assert wetness(1) == pytest.approx(wetness(5))


def test_daylight_sampling_makes_long_steps_differ_from_subdivisions() -> None:
    def wetness(steps: int) -> float:
        env = EnvironmentState(world_hour=8.0, ground_wetness=0.8)
        span = 6.0
        for _ in range(steps):
            env.advance(span / steps)
        return env.ground_wetness

    assert abs(wetness(1) - wetness(6)) > 1e-4


def test_long_weather_evolution_keeps_wetness_bounded() -> None:
    storm = EnvironmentState(weather=WeatherKind.STORM, world_hour=0.0)
    clear = EnvironmentState(ground_wetness=1.0, world_hour=0.0)
    for _ in range(400):
        storm.advance(1.0)
        clear.advance(1.0)

    assert 0.0 <= storm.ground_wetness <= 1.0
    assert storm.ground_wetness > 0.5
    assert clear.ground_wetness == 0.0
    assert storm.world_hour == pytest.approx(400.0)
