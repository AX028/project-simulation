"""Behavioral coverage for shared environment inputs and clock rules.

Physiology and wetness use an explicit Euler step sampled at the start of each
advance. A long step is therefore not required to match the same interval split
into shorter steps. Kernel world time is the pre-step clock when a kernel is
attached; elapsed session time only accumulates command duration.
"""

from __future__ import annotations

import pytest

from project_simulation import (
    Projectile,
    ProjectileSimulator,
    ProjectileSpec,
    SoundEvent,
    SpatialEntity,
    Vec3,
    VisionProfile,
    build_demo_session,
    hear_sound,
)
from project_simulation.environment import EnvironmentState, WeatherKind


def _wolf(session):
    return next(
        actor for actor in session.actors.values() if actor.spatial.name == "Wolf"
    )


def _clarity(text: str) -> float:
    return float(text.split("clarity ")[1].rstrip("."))


def _fly(wind: Vec3 | None) -> Vec3:
    projectile = Projectile(
        "arrow",
        ProjectileSpec(
            "Arrow",
            mass_kg=0.03,
            radius_m=0.01,
            drag_coefficient=0.05,
            gravity_mps2=0.0,
            max_lifetime_s=2.0,
        ),
        Vec3(0.0, 0.0, 1.0),
        Vec3(0.0, 60.0, 0.0),
    )
    simulator = ProjectileSimulator()
    simulator.launch(projectile)
    steps = simulator.simulate_until_inactive(
        projectile.projectile_id,
        (),
        dt_s=0.05,
        wind_velocity=wind,
    )
    return steps[-1].end_position


def test_environment_rejects_non_finite_and_out_of_range_inputs() -> None:
    with pytest.raises(ValueError, match="world hour"):
        EnvironmentState(world_hour=float("nan"))
    with pytest.raises(ValueError, match="base temperature"):
        EnvironmentState(base_temperature_c=float("inf"))

    environment = EnvironmentState(world_hour=12.0, ground_wetness=0.2)
    with pytest.raises(ValueError, match="world hour"):
        environment.world_hour = float("nan")
    with pytest.raises(ValueError, match="precipitation"):
        environment.precipitation = 1.5
    with pytest.raises(ValueError, match="weather"):
        environment.weather = "storm"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="environment hours"):
        environment.advance(float("nan"))
    with pytest.raises(ValueError, match="backward"):
        environment.advance(-0.25)

    assert environment.world_hour == pytest.approx(12.0)
    assert environment.precipitation == pytest.approx(0.0)
    assert environment.ground_wetness == pytest.approx(0.2)
    assert environment.weather is WeatherKind.CLEAR


def test_dawn_and_fog_change_what_the_player_can_resolve() -> None:
    night = build_demo_session(3)
    day = build_demo_session(3)
    day.environment.world_hour = 12.0
    fog = build_demo_session(3)
    fog.environment.world_hour = 12.0
    fog.environment.weather = WeatherKind.FOG

    night_look = night.execute("look").output
    day_look = day.execute("look").output
    assert night_look != day_look

    night_clarity = _clarity(night.execute("inspect Wolf").output)
    day_clarity = _clarity(day.execute("inspect Wolf").output)
    fog_clarity = _clarity(fog.execute("inspect Wolf").output)
    assert day_clarity > night_clarity
    assert fog_clarity < day_clarity


def test_look_uses_the_player_vision_profile() -> None:
    blind = build_demo_session(3)
    keen = build_demo_session(3)
    blind.player.vision = VisionProfile(night_vision=0.0)
    keen.player.vision = VisionProfile(night_vision=1.0)

    blind_look = blind.execute("look").output
    keen_look = keen.execute("look").output
    assert blind_look != keen_look
    assert _clarity(blind.execute("inspect Wolf").output) < _clarity(
        keen.execute("inspect Wolf").output
    )


def test_crosswind_drifts_a_projectile_and_vertical_wind_does_not() -> None:
    calm = _fly(None)
    cross = _fly(EnvironmentState(wind_velocity=Vec3(15.0, 0.0, 0.0)).wind_velocity)
    upward = _fly(Vec3(0.0, 0.0, 15.0))

    assert cross.x > calm.x
    assert upward.z == pytest.approx(calm.z)
    assert upward.x == pytest.approx(calm.x)


def test_storm_noise_hides_a_sound_that_is_heard_in_clear_weather() -> None:
    event = SoundEvent(
        "shot",
        Vec3(0.0, 40.0, 1.5),
        65.0,
        "weapon",
        "a shot",
        0.0,
        "archer",
    )
    listener = SpatialEntity("listener", "Listener", Vec3(0.0, 0.0, 0.0))
    clear = EnvironmentState()
    storm = EnvironmentState(weather=WeatherKind.STORM)

    assert hear_sound(event, listener, ambient_noise_db=clear.ambient_noise_db) is not None
    assert hear_sound(event, listener, ambient_noise_db=storm.ambient_noise_db) is None


def test_snow_slows_movement_time_and_advance_distance() -> None:
    clear = build_demo_session(5)
    snow = build_demo_session(5)
    snow.environment.weather = WeatherKind.SNOW

    clear.execute("move north 2")
    snow.execute("move north 2")
    assert clear.player.spatial.position.y == pytest.approx(2.0)
    assert snow.player.spatial.position.y == pytest.approx(2.0)
    assert snow.elapsed_seconds > clear.elapsed_seconds

    clear_advance = build_demo_session(5)
    snow_advance = build_demo_session(5)
    snow_advance.environment.weather = WeatherKind.SNOW
    clear_before = clear_advance.player.spatial.position.distance_to(
        _wolf(clear_advance).spatial.position
    )
    snow_before = snow_advance.player.spatial.position.distance_to(
        _wolf(snow_advance).spatial.position
    )
    clear_advance.execute("advance Wolf 2")
    snow_advance.execute("advance Wolf 2")
    clear_closed = clear_before - clear_advance.player.spatial.position.distance_to(
        _wolf(clear_advance).spatial.position
    )
    snow_closed = snow_before - snow_advance.player.spatial.position.distance_to(
        _wolf(snow_advance).spatial.position
    )
    assert snow_closed < clear_closed


def test_weather_changes_body_temperature_and_ground_wetness() -> None:
    clear = build_demo_session(5)
    snow = build_demo_session(5)
    rain = build_demo_session(5)
    snow.environment.weather = WeatherKind.SNOW
    rain.environment.weather = WeatherKind.RAIN

    clear.execute("wait 3600")
    snow.execute("wait 3600")
    rain.execute("wait 3600")

    assert snow.player.physiology.core_temperature_c < clear.player.physiology.core_temperature_c
    assert rain.environment.ground_wetness > clear.environment.ground_wetness
    assert clear.environment.ground_wetness == pytest.approx(0.0)
    assert snow.environment.ground_wetness > 0.0


def test_wet_ground_slows_a_move_at_the_same_ambient_temperature() -> None:
    dry = build_demo_session(5)
    wet = build_demo_session(5)
    wet.environment.ground_wetness = 1.0
    assert wet.environment.ambient_temperature_c == pytest.approx(
        dry.environment.ambient_temperature_c
    )

    dry.execute("move north 2")
    wet.execute("move north 2")

    assert wet.elapsed_seconds > dry.elapsed_seconds
    assert dry.player.spatial.position.y == pytest.approx(wet.player.spatial.position.y)


def test_ambient_npc_covers_less_ground_in_snow() -> None:
    def position_after(weather: WeatherKind) -> float:
        session = build_demo_session(5)
        assert session.kernel is not None
        session.kernel.world.time_hours = 8.0
        session.environment.world_hour = 8.0
        session.environment.weather = weather
        session.execute("wait 1")
        return session.actors["mira"].spatial.position.x

    assert position_after(WeatherKind.SNOW) < position_after(WeatherKind.CLEAR)


def test_failed_time_step_does_not_rewrite_clocks() -> None:
    session = build_demo_session(5)
    session.environment.world_hour = 12.0
    before_fatigue = session.player.physiology.fatigue

    for bad in (-5.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            session._advance_clock(bad)

    assert session.environment.world_hour == pytest.approx(12.0)
    assert session.elapsed_seconds == pytest.approx(0.0)
    assert session.kernel is not None
    assert session.kernel.world.time_hours == pytest.approx(0.0)
    assert session.player.physiology.fatigue == pytest.approx(before_fatigue)


def test_advancing_command_samples_one_clock_when_hours_were_split() -> None:
    diverged = build_demo_session(5)
    aligned = build_demo_session(5)
    diverged.environment.weather = WeatherKind.SNOW
    diverged.environment.world_hour = 12.0
    aligned.environment.weather = WeatherKind.SNOW

    diverged.execute("move north 2")
    aligned.execute("move north 2")

    assert diverged.player.physiology.core_temperature_c == pytest.approx(
        aligned.player.physiology.core_temperature_c
    )
    assert _wolf(diverged).physiology.core_temperature_c == pytest.approx(
        _wolf(aligned).physiology.core_temperature_c
    )


def test_normal_wait_keeps_the_three_clocks_aligned() -> None:
    session = build_demo_session(5)
    session.execute("wait 60")
    assert session.kernel is not None
    assert session.environment.world_hour == pytest.approx(session.elapsed_seconds / 3600.0)
    assert session.kernel.world.time_hours == pytest.approx(session.environment.world_hour)


def test_split_waits_move_temperature_more_than_one_long_wait() -> None:
    def temperature_after(pieces: int) -> tuple[float, float]:
        session = build_demo_session(5)
        session.environment.weather = WeatherKind.RAIN
        step = 3600.0 / pieces
        for _ in range(pieces):
            session.execute(f"wait {step}")
        assert session.kernel is not None
        return (
            session.player.physiology.core_temperature_c,
            session.environment.world_hour,
        )

    one_step = temperature_after(1)
    sixty_steps = temperature_after(60)
    assert sixty_steps[0] != pytest.approx(one_step[0], abs=1e-4)
    assert sixty_steps[1] == pytest.approx(one_step[1])
