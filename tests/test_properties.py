import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from project_simulation import (
    Bounds,
    Loadout,
    Mind,
    Physiology,
    SettlementState,
    SimulationKernel,
    SpatialEntity,
    Vec3,
    WorldActor,
    WorldConfig,
    WorldState,
    WorldStore,
    generate_world,
    move_actor_with_collisions,
)
from project_simulation.demographics import migrate
from project_simulation.models import IllegalActionError, ResourcePool


@given(
    maximum=st.integers(min_value=1, max_value=10_000),
    current=st.integers(min_value=0, max_value=10_000),
    amount=st.integers(min_value=0, max_value=10_000),
)
def test_resource_pool_never_escapes_bounds(
    maximum: int,
    current: int,
    amount: int,
) -> None:
    if current > maximum:
        with pytest.raises(ValueError):
            ResourcePool(current, maximum)
        return

    pool = ResourcePool(current, maximum)
    if amount <= current:
        pool.spend(amount)
        assert pool.current == current - amount
    else:
        with pytest.raises(IllegalActionError):
            pool.spend(amount)
        assert pool.current == current

    pool.restore(amount)
    assert 0 <= pool.current <= pool.maximum


@given(
    start=st.integers(min_value=0, max_value=100_000),
    offsets=st.lists(
        st.integers(min_value=0, max_value=1000),
        min_size=1,
        max_size=25,
    ),
)
def test_event_execution_time_is_monotonic(
    start: int,
    offsets: list[int],
) -> None:
    world = WorldState(time_hours=float(start))
    kernel = SimulationKernel(world)
    observed: list[float] = []

    def record(current_world: WorldState, event) -> None:
        assert current_world.time_hours == event.at
        observed.append(event.at)

    kernel.register_handler("record", record)
    for offset in offsets:
        kernel.schedule(float(start + offset), "record")

    target = float(start + max(offsets))
    kernel.advance_to(target)

    assert observed == sorted(observed)
    assert world.time_hours == target
    assert all(time >= start for time in observed)


@given(
    source_population=st.integers(min_value=0, max_value=10_000),
    destination_population=st.integers(min_value=0, max_value=10_000),
    max_people=st.integers(min_value=0, max_value=2000),
    pressure=st.floats(
        min_value=0.0,
        max_value=1.0,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_migration_conserves_total_population(
    source_population: int,
    destination_population: int,
    max_people: int,
    pressure: float,
) -> None:
    source = SettlementState(
        "source",
        "Source",
        population=source_population,
        food_units=100.0,
        wealth=100.0,
        security=5.0,
        livestock=10.0,
    )
    destination = SettlementState(
        "destination",
        "Destination",
        population=destination_population,
        food_units=100.0,
        wealth=100.0,
        security=5.0,
        livestock=10.0,
    )
    total = source.population + destination.population

    result = migrate(
        source,
        destination,
        max_people=max_people,
        pressure=pressure,
    )

    assert source.population + destination.population == total
    assert 0 <= result.people_moved <= min(source_population, max_people)


@given(
    wall_y=st.floats(
        min_value=1.0,
        max_value=50.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    speed=st.floats(
        min_value=0.1,
        max_value=100.0,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_collision_movement_never_penetrates_solid_wall(
    wall_y: float,
    speed: float,
) -> None:
    actor = WorldActor(
        SpatialEntity(
            "actor",
            "Actor",
            Vec3(0.0, 0.0, 0.0),
            bounds=Bounds(0.3, 0.3, 1.8),
        ),
        Mind(),
        Physiology(70.0),
        Loadout(70.0),
        movement_speed_mps=speed,
    )
    wall = SpatialEntity(
        "wall",
        "Wall",
        Vec3(0.0, wall_y, 0.0),
        bounds=Bounds(2.0, 0.2, 3.0),
        mass_kg=100.0,
        tags=frozenset({"solid"}),
    )

    move_actor_with_collisions(
        actor,
        Vec3(0.0, wall_y + 100.0, 0.0),
        1000.0,
        [wall],
    )

    contact_y = wall_y - wall.bounds.half_depth - actor.spatial.bounds.half_depth
    assert actor.spatial.position.y <= contact_y


@settings(max_examples=20)
@given(
    width=st.integers(min_value=1, max_value=10),
    height=st.integers(min_value=1, max_value=10),
    chunk_size=st.integers(min_value=1, max_value=6),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_generated_world_round_trip_is_exact(
    tmp_path,
    width: int,
    height: int,
    chunk_size: int,
    seed: int,
) -> None:
    config = WorldConfig(width, height, chunk_size)
    world = generate_world(config, seed)
    path = tmp_path / "property-world.h5"

    WorldStore.write(world, path)
    restored = WorldStore.read(path)

    assert restored.seed == seed
    assert restored.config == config
    assert np.array_equal(restored.terrain, world.terrain)
    assert np.array_equal(restored.biome, world.biome)
    assert np.array_equal(restored.temperature, world.temperature)
    assert np.array_equal(restored.precipitation, world.precipitation)
