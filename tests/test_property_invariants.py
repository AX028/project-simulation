from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from project_simulation import (
    Loadout,
    Mind,
    Physiology,
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
from project_simulation.models import ResourcePool
from project_simulation.spatial import Bounds


DETERMINISTIC = settings(
    max_examples=100,
    deadline=None,
    derandomize=True,
)


@st.composite
def resource_pools(draw):
    maximum = draw(st.integers(min_value=1, max_value=10_000))
    current = draw(st.integers(min_value=0, max_value=maximum))
    return ResourcePool(current, maximum)


@DETERMINISTIC
@given(pool=resource_pools(), amount=st.integers(min_value=0, max_value=10_000))
def test_resource_pool_operations_preserve_bounds(
    pool: ResourcePool,
    amount: int,
) -> None:
    before = pool.current
    if amount <= pool.current:
        pool.spend(amount)
        assert pool.current == before - amount
        restored = pool.restore(amount)
        assert restored == amount
        assert pool.current == before
    else:
        restored = pool.restore(amount)
        assert 0 <= restored <= amount
        assert 0 <= pool.current <= pool.maximum


@DETERMINISTIC
@given(
    world_hour=st.floats(
        min_value=0.0,
        max_value=100_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    offsets=st.lists(
        st.floats(
            min_value=0.0,
            max_value=1_000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=30,
    ),
)
def test_event_execution_never_moves_time_backward(
    world_hour: float,
    offsets: list[float],
) -> None:
    world = WorldState(time_hours=world_hour)
    kernel = SimulationKernel(world)
    observed: list[float] = []

    def record(state: WorldState, event) -> None:
        observed.append(state.time_hours)
        assert state.time_hours == event.at

    kernel.register_handler("record", record)
    for offset in offsets:
        kernel.schedule(world_hour + offset, "record")

    target = world_hour + max(offsets)
    kernel.advance_to(target)

    assert observed == sorted(observed)
    assert all(time >= world_hour for time in observed)
    assert world.time_hours == target


@settings(max_examples=20, deadline=None, derandomize=True)
@given(
    width=st.integers(min_value=1, max_value=20),
    height=st.integers(min_value=1, max_value=20),
    chunk_size=st.integers(min_value=1, max_value=8),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_generated_world_round_trip_preserves_every_layer(
    width: int,
    height: int,
    chunk_size: int,
    seed: int,
) -> None:
    config = WorldConfig(width, height, chunk_size)
    world = generate_world(config, seed)

    with TemporaryDirectory() as directory:
        path = Path(directory) / "property-world.h5"
        WorldStore.write(world, path)
        restored = WorldStore.read(path)

    assert restored.seed == world.seed
    assert restored.config == world.config
    assert np.array_equal(restored.terrain, world.terrain)
    assert np.array_equal(restored.biome, world.biome)
    assert np.array_equal(restored.temperature, world.temperature)
    assert np.array_equal(restored.precipitation, world.precipitation)


@st.composite
def wall_cases(draw):
    wall_y = draw(
        st.floats(
            min_value=1.0,
            max_value=50.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    speed = draw(
        st.floats(
            min_value=0.1,
            max_value=200.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    seconds = draw(
        st.floats(
            min_value=0.01,
            max_value=20.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    return wall_y, speed, seconds


@DETERMINISTIC
@given(case=wall_cases())
def test_swept_collision_never_places_actor_inside_wall(
    case: tuple[float, float, float],
) -> None:
    wall_y, speed, seconds = case
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
        tags=frozenset({"solid"}),
    )
    destination = Vec3(0.0, wall_y + 100.0, 0.0)

    move_actor_with_collisions(
        actor,
        destination,
        seconds,
        [wall],
    )

    wall_near_face = wall_y - wall.bounds.half_depth - actor.spatial.bounds.half_depth
    assert actor.spatial.position.y <= wall_near_face + 1e-9


@DETERMINISTIC
@given(
    x=st.floats(
        min_value=-1_000.0,
        max_value=1_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    y=st.floats(
        min_value=-1_000.0,
        max_value=1_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    z=st.floats(
        min_value=-1_000.0,
        max_value=1_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_vec3_normalization_is_bounded_and_direction_preserving(
    x: float,
    y: float,
    z: float,
) -> None:
    vector = Vec3(x, y, z)
    normalized = vector.normalized()

    if vector.magnitude == 0.0:
        assert normalized == vector
    else:
        assert abs(normalized.magnitude - 1.0) < 1e-9
        assert vector.dot(normalized) >= 0.0
