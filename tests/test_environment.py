"""Behavioral coverage for shared environmental inputs and clock semantics."""

import math

import pytest

from project_simulation import (
    Projectile,
    ProjectileSimulator,
    ProjectileSpec,
    SoundEvent,
    SpatialEntity,
    Vec3,
    build_demo_session,
    hear_sound,
    observe,
)
from project_simulation.environment import EnvironmentState, WeatherKind


def _observer_and_target(distance_m: float) -> tuple[SpatialEntity, SpatialEntity]:
    observer = SpatialEntity(
        "observer",
        "Observer",
        Vec3(0.0, 0.0, 0.0),
        facing=Vec3(0.0, 1.0, 0.0),
    )
    target = SpatialEntity(
        "marker",
        "Marker",
        Vec3(0.0, distance_m, 0.0),
    )
    return observer, target


def test_dawn_and_night_change_visual_clarity() -> None:
    observer, target = _observer_and_target(40.0)
    day = EnvironmentState(world_hour=12.0)
    night = EnvironmentState(world_hour=0.0)

    day_view = observe(
        observer,
        target,
        illumination=day.illumination,
        contrast=day.contrast_multiplier,
    )
    night_view = observe(
        observer,
        target,
        illumination=night.illumination,
        contrast=night.contrast_multiplier,
    )

    assert day_view is not None
    assert night_view is not None
    assert day.illumination > night.illumination
    assert day_view.clarity > night_view.clarity


def test_fog_reduces_contrast_and_inspected_clarity() -> None:
    clear = build_demo_session(4)
    foggy = build_demo_session(4)
    clear.environment.world_hour = 12.0
    foggy.environment.world_hour = 12.0
    foggy.environment.weather = WeatherKind.FOG

    clear_text = clear.execute("inspect Wolf").output
    fog_text = foggy.execute("inspect Wolf").output

    assert (
        foggy.environment.contrast_multiplier
        < clear.environment.contrast_multiplier
    )
    assert "clarity" in clear_text
    assert clear_text != fog_text


def test_wind_drifts_a_projectile_off_the_calm_path() -> None:
    spec = ProjectileSpec(
        "stone",
        mass_kg=0.05,
        radius_m=0.02,
        drag_coefficient=0.8,
        gravity_mps2=0.0,
        max_lifetime_s=0.4,
    )

    def fly(wind: Vec3) -> Vec3:
        simulator = ProjectileSimulator()
        simulator.launch(
            Projectile(
                "stone-1",
                spec,
                Vec3(0.0, 0.0, 1.0),
                Vec3(0.0, 30.0, 0.0),
            )
        )
        simulator.simulate_until_inactive(
            "stone-1",
            (),
            dt_s=0.05,
            wind_velocity=wind,
        )
        return simulator.projectiles["stone-1"].position

    calm = fly(Vec3(0.0, 0.0, 0.0))
    crosswind = fly(Vec3(12.0, 0.0, 0.0))

    assert calm.x == pytest.approx(0.0, abs=1e-9)
    assert crosswind.x > calm.x + 0.2


def test_storm_noise_hides_a_sound_that_is_heard_in_clear_weather() -> None:
    listener = SpatialEntity("listener", "Listener", Vec3(0.0, 0.0, 0.0))
    event = SoundEvent(
        "rustle",
        Vec3(0.0, 0.0, listener.bounds.height * 0.85),
        loudness_db_at_1m=25.0,
        category="movement",
        description="a soft rustle",
        created_hour=0.0,
    )
    clear = EnvironmentState()
    storm = EnvironmentState(weather=WeatherKind.STORM)

    assert storm.ambient_noise_db > clear.ambient_noise_db
    assert hear_sound(event, listener, ambient_noise_db=clear.ambient_noise_db)
    assert (
        hear_sound(event, listener, ambient_noise_db=storm.ambient_noise_db)
        is None
    )


def test_wet_and_snow_slow_movement_and_advance() -> None:
    dry = build_demo_session(6)
    wet = build_demo_session(6)
    snow = build_demo_session(6)
    wet.environment.ground_wetness = 1.0
    snow.environment.weather = WeatherKind.SNOW

    dry.execute("move north 4")
    wet.execute("move north 4")
    snow.execute("move north 4")

    assert wet.elapsed_seconds > dry.elapsed_seconds
    assert snow.elapsed_seconds > dry.elapsed_seconds

    dry_advance = build_demo_session(6)
    wet_advance = build_demo_session(6)
    snow_advance = build_demo_session(6)
    wet_advance.environment.ground_wetness = 1.0
    snow_advance.environment.weather = WeatherKind.SNOW
    dry_result = dry_advance.execute("advance Wolf 1")
    wet_result = wet_advance.execute("advance Wolf 1")
    snow_result = snow_advance.execute("advance Wolf 1")

    dry_moved = _moved_distance(dry_result.output)
    assert _moved_distance(wet_result.output) < dry_moved
    assert _moved_distance(snow_result.output) < dry_moved


def test_ambient_temperature_changes_core_temperature() -> None:
    afternoon = build_demo_session(8)
    night = build_demo_session(8)
    afternoon.environment.world_hour = 15.0
    afternoon.environment.base_temperature_c = 0.0
    night.environment.world_hour = 3.0
    night.environment.base_temperature_c = 0.0

    afternoon.execute("wait 3600")
    night.execute("wait 3600")

    assert (
        afternoon.player.physiology.core_temperature_c
        > night.player.physiology.core_temperature_c + 0.5
    )


def test_wetness_evolves_and_long_steps_are_not_equivalent() -> None:
    single = EnvironmentState(world_hour=6.0, ground_wetness=0.5)
    split = EnvironmentState(world_hour=6.0, ground_wetness=0.5)
    single.advance(6.0)
    for _ in range(6):
        split.advance(1.0)

    assert single.world_hour == pytest.approx(split.world_hour)
    assert single.ground_wetness != pytest.approx(split.ground_wetness)


def test_environment_rejects_non_finite_and_backward_time_without_mutation() -> None:
    with pytest.raises(ValueError, match="world hour"):
        EnvironmentState(world_hour=math.nan)
    with pytest.raises(ValueError, match="base temperature"):
        EnvironmentState(base_temperature_c=math.inf)
    with pytest.raises(ValueError, match="precipitation"):
        EnvironmentState(precipitation=1.1)
    with pytest.raises(ValueError, match="finite"):
        Vec3(math.nan, 0.0, 0.0)

    state = EnvironmentState(world_hour=8.0, ground_wetness=0.4)
    with pytest.raises(ValueError, match="backward"):
        state.advance(-0.1)
    with pytest.raises(ValueError, match="finite"):
        state.advance(math.nan)
    assert state.world_hour == pytest.approx(8.0)
    assert state.ground_wetness == pytest.approx(0.4)


def test_clocks_share_a_delta_and_keep_their_initial_offset() -> None:
    session = build_demo_session(9)
    assert session.kernel is not None
    session.environment.world_hour = 8.0

    session.execute("wait 1800")
    session.execute("move north 1")

    assert session.kernel.world.time_hours == pytest.approx(
        session.elapsed_seconds / 3600.0
    )
    assert session.environment.world_hour == pytest.approx(
        session.kernel.world.time_hours + 8.0
    )


def _moved_distance(output: str) -> float:
    return float(output.split()[2])
