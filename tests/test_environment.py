"""Behavioral checks for shared environmental inputs and clock ownership."""

from math import inf, nan

import pytest

from project_simulation import (
    Projectile,
    ProjectileSimulator,
    ProjectileSpec,
    SoundEvent,
    Vec3,
    build_demo_session,
    hear_sound,
)
from project_simulation.environment import EnvironmentState, WeatherKind


def _illumination_line(hour: float, weather: WeatherKind) -> str:
    session = build_demo_session(11)
    session.environment.world_hour = hour
    session.environment.weather = weather
    return session.execute("status").output


def _inspect_clarity(hour: float, weather: WeatherKind, distance_m: float) -> str:
    session = build_demo_session(11)
    wolf_id = next(
        actor_id
        for actor_id, actor in session.actors.items()
        if actor.spatial.name == "Wolf"
    )
    session.actors[wolf_id].spatial.position = Vec3(0.0, distance_m, 0.0)
    session.environment.world_hour = hour
    session.environment.weather = weather
    return session.execute("inspect Wolf").output


def _illumination_value(text: str) -> float:
    return float(text.split("illumination ", 1)[1].split(";", 1)[0])


def test_night_and_fog_reduce_what_the_player_can_see() -> None:
    night = _illumination_value(_illumination_line(2.0, WeatherKind.CLEAR))
    noon = _illumination_value(_illumination_line(12.0, WeatherKind.CLEAR))
    fog = _illumination_value(_illumination_line(12.0, WeatherKind.FOG))
    assert night < fog < noon
    assert noon == pytest.approx(1.0)

    day_view = _inspect_clarity(12.0, WeatherKind.CLEAR, 8.0)
    night_view = _inspect_clarity(2.0, WeatherKind.CLEAR, 8.0)
    assert "clearly visible" in day_view
    assert "shaped figure" in night_view

    clear_far = _inspect_clarity(12.0, WeatherKind.CLEAR, 40.0)
    fog_far = _inspect_clarity(12.0, WeatherKind.FOG, 40.0)
    assert "shaped figure" in clear_far
    assert "distant figure" in fog_far
    clear_clarity = float(clear_far.rsplit("clarity ", 1)[1].rstrip("."))
    fog_clarity = float(fog_far.rsplit("clarity ", 1)[1].rstrip("."))
    assert fog_clarity < clear_clarity


def test_crosswind_moves_a_projectile_off_its_calm_path() -> None:
    spec = ProjectileSpec(
        "stone",
        mass_kg=0.05,
        radius_m=0.02,
        drag_coefficient=0.5,
        gravity_mps2=0.0,
        max_lifetime_s=0.4,
    )

    def landing(wind: Vec3) -> Vec3:
        simulator = ProjectileSimulator()
        simulator.launch(
            Projectile(
                "stone",
                spec,
                Vec3(0.0, 0.0, 1.0),
                Vec3(25.0, 0.0, 0.0),
            )
        )
        steps = simulator.simulate_until_inactive(
            "stone",
            (),
            dt_s=0.02,
            wind_velocity=wind,
        )
        return steps[-1].end_position

    calm = landing(Vec3(0.0, 0.0, 0.0))
    session = build_demo_session(3)
    session.environment.wind_velocity = Vec3(0.0, 12.0, 0.0)
    drifted = landing(session.environment.wind_velocity)
    assert drifted.y > calm.y + 0.05


def test_storm_noise_hides_a_sound_that_is_heard_in_clear_air() -> None:
    event = SoundEvent(
        "whisper",
        Vec3(2.0, 2.0, 1.0),
        30.0,
        "voice",
        "a whisper",
        0.0,
    )
    session = build_demo_session(4)
    listener = session.actors["mira"].spatial
    clear = EnvironmentState()
    storm = EnvironmentState(weather=WeatherKind.STORM)
    assert hear_sound(
        event,
        listener,
        ambient_noise_db=clear.ambient_noise_db,
    ) is not None
    assert hear_sound(
        event,
        listener,
        ambient_noise_db=storm.ambient_noise_db,
    ) is None

    def heard_count(weather: WeatherKind) -> int:
        probed = build_demo_session(4)
        probed.environment.weather = weather
        probed._emit_sound(
            category="voice",
            description="a whisper",
            position=Vec3(2.0, 2.0, 1.0),
            loudness_db_at_1m=30.0,
            source_id=probed.player_id,
        )
        return sum(
            1
            for actor in probed.actors.values()
            for memory in actor.mind.memories
            if memory.source == "hearing"
        )

    assert heard_count(WeatherKind.CLEAR) > heard_count(WeatherKind.STORM)


def test_snow_and_wet_ground_slow_travel() -> None:
    def move_elapsed(weather: WeatherKind, wetness: float) -> float:
        session = build_demo_session(5)
        session.environment.weather = weather
        session.environment.ground_wetness = wetness
        session.execute("move north 2")
        return session.elapsed_seconds

    assert move_elapsed(WeatherKind.SNOW, 0.0) > move_elapsed(WeatherKind.CLEAR, 0.0)
    assert move_elapsed(WeatherKind.CLEAR, 1.0) > move_elapsed(WeatherKind.CLEAR, 0.0)


def test_snow_slows_ambient_travel_to_work() -> None:
    def mira_progress(weather: WeatherKind) -> float:
        session = build_demo_session(6)
        assert session.kernel is not None
        session.kernel.world.time_hours = 8.0
        session.environment.weather = weather
        session.execute("wait 2")
        return session.actors["mira"].spatial.position.x

    assert mira_progress(WeatherKind.CLEAR) > mira_progress(WeatherKind.SNOW)


def test_cold_weather_pulls_core_temperature_down_faster() -> None:
    def core_temperature(weather: WeatherKind) -> float:
        session = build_demo_session(7)
        session.environment.weather = weather
        session.execute("wait 600")
        return session.player.physiology.core_temperature_c

    assert core_temperature(WeatherKind.SNOW) < core_temperature(WeatherKind.CLEAR)


def test_rain_wets_ground_and_clear_air_dries_it() -> None:
    rain = EnvironmentState(weather=WeatherKind.RAIN, world_hour=1.0)
    rain.advance(2.0)
    assert rain.ground_wetness > 0.0

    drying = EnvironmentState(world_hour=1.0, ground_wetness=0.6)
    before = drying.ground_wetness
    drying.advance(3.0)
    assert drying.ground_wetness < before


def test_constant_daylight_steps_match_and_changing_daylight_does_not() -> None:
    def wetness(start: float, steps: tuple[float, ...]) -> float:
        environment = EnvironmentState(
            world_hour=start,
            ground_wetness=0.8,
            wind_velocity=Vec3(2.0, 0.0, 0.0),
        )
        for step in steps:
            environment.advance(step)
        return environment.ground_wetness

    assert wetness(1.0, (2.0,)) == pytest.approx(wetness(1.0, (1.0, 1.0)))
    assert wetness(9.0, (6.0,)) != pytest.approx(wetness(9.0, (1.0,) * 6))


def test_environment_rejects_nonfinite_and_backward_time_without_mutation() -> None:
    with pytest.raises(ValueError, match="finite"):
        EnvironmentState(world_hour=nan)
    with pytest.raises(ValueError, match="finite"):
        EnvironmentState(base_temperature_c=inf)
    with pytest.raises(ValueError, match="finite"):
        EnvironmentState(wind_velocity=Vec3(nan, 0.0, 0.0))
    with pytest.raises(ValueError, match="precipitation"):
        EnvironmentState(precipitation=-0.01)
    with pytest.raises(ValueError, match="fog_density"):
        EnvironmentState(fog_density=1.1)

    environment = EnvironmentState(world_hour=4.0, ground_wetness=0.3)
    for bad in (nan, inf, -inf, -0.25):
        with pytest.raises(ValueError):
            environment.advance(bad)
    assert environment.world_hour == pytest.approx(4.0)
    assert environment.ground_wetness == pytest.approx(0.3)


def test_kernel_clock_owns_environment_time_from_the_first_action() -> None:
    session = build_demo_session(8)
    assert session.kernel is not None
    session.environment.world_hour = 15.0
    session.execute("wait 1")

    expected = 1.0 / 3600.0
    assert session.kernel.world.time_hours == pytest.approx(expected)
    assert session.environment.world_hour == pytest.approx(expected)
    assert session.elapsed_seconds / 3600.0 == pytest.approx(expected)

    session.replay(("move north 1", "wait 3", "status"))
    assert session.environment.world_hour == pytest.approx(
        session.kernel.world.time_hours
    )
    assert session.elapsed_seconds / 3600.0 == pytest.approx(
        session.kernel.world.time_hours
    )


def test_negative_session_advance_does_not_corrupt_clocks() -> None:
    session = build_demo_session(9)
    assert session.kernel is not None
    fatigue = session.player.physiology.fatigue
    with pytest.raises(ValueError):
        session._advance_clock(-5.0)
    with pytest.raises(ValueError):
        session._advance_clock(nan)

    assert session.elapsed_seconds == pytest.approx(0.0)
    assert session.environment.world_hour == pytest.approx(0.0)
    assert session.kernel.world.time_hours == pytest.approx(0.0)
    assert session.player.physiology.fatigue == pytest.approx(fatigue)
