import json
from math import inf, nan

import h5py
import numpy as np
import pytest

from project_simulation import (
    Bounds,
    Physiology,
    PlanAction,
    SimulationKernel,
    SpatialEntity,
    Vec3,
    VisionProfile,
    WorldConfig,
    WorldState,
    WorldStore,
    build_demo_session,
    generate_world,
    load_game,
)
from project_simulation.models import (
    IllegalActionError,
    IncompatibleSaveError,
    ResourcePool,
    SimulationError,
)
from project_simulation.physiology import Injury, InjuryType
from project_simulation.planning import WorldFact
from project_simulation.world import _smooth


def test_schedule_rejects_event_before_world_time() -> None:
    world = WorldState(time_hours=100.0)
    kernel = SimulationKernel(world)

    with pytest.raises(ValueError, match="before world time"):
        kernel.schedule(90.0, "past")

    assert world.time_hours == 100.0
    assert kernel.pending_events() == ()


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_schedule_rejects_nonfinite_event_time(value: float) -> None:
    kernel = SimulationKernel(WorldState(time_hours=10.0))
    with pytest.raises(ValueError, match="finite"):
        kernel.schedule(value, "bad")


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_advance_rejects_nonfinite_target_time(value: float) -> None:
    kernel = SimulationKernel(WorldState(time_hours=10.0))
    with pytest.raises(ValueError, match="finite"):
        kernel.advance_to(value)


def test_campaign_loader_rejects_non_object_root(tmp_path) -> None:
    path = tmp_path / "campaign.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(IncompatibleSaveError, match="root must be an object"):
        load_game(path)


def test_campaign_loader_rejects_non_object_player(tmp_path) -> None:
    path = tmp_path / "campaign.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "seed": 1,
                "turn": 0,
                "player": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(IncompatibleSaveError, match="player must be an object"):
        load_game(path)


def _small_world_path(tmp_path):
    config = WorldConfig(4, 4, 2)
    world = generate_world(config, 7)
    path = tmp_path / "world.h5"
    WorldStore.write(world, path)
    return path


def test_world_reader_rejects_missing_chunk(tmp_path) -> None:
    path = _small_world_path(tmp_path)
    with h5py.File(path, "a") as handle:
        del handle["chunks"]["0_0"]

    with pytest.raises(SimulationError, match="chunk set"):
        WorldStore.read(path)


def test_world_reader_rejects_unexpected_chunk(tmp_path) -> None:
    path = _small_world_path(tmp_path)
    with h5py.File(path, "a") as handle:
        handle["chunks"].create_group("99_99")

    with pytest.raises(SimulationError, match="chunk set"):
        WorldStore.read(path)


def test_world_reader_rejects_missing_dataset(tmp_path) -> None:
    path = _small_world_path(tmp_path)
    with h5py.File(path, "a") as handle:
        del handle["chunks"]["0_0"]["temperature"]

    with pytest.raises(SimulationError, match="missing dataset"):
        WorldStore.read(path)


def test_world_reader_rejects_wrong_chunk_shape(tmp_path) -> None:
    path = _small_world_path(tmp_path)
    with h5py.File(path, "a") as handle:
        chunk = handle["chunks"]["0_0"]
        del chunk["terrain"]
        chunk.create_dataset("terrain", data=np.zeros((1, 1)))

    with pytest.raises(SimulationError, match="shape"):
        WorldStore.read(path)


def test_world_reader_rejects_nonfinite_chunk_data(tmp_path) -> None:
    path = _small_world_path(tmp_path)
    with h5py.File(path, "a") as handle:
        data = handle["chunks"]["0_0"]["terrain"]
        data[0, 0] = np.nan

    with pytest.raises(SimulationError, match="non-finite"):
        WorldStore.read(path)


def test_world_write_leaves_no_temporary_file(tmp_path) -> None:
    path = tmp_path / "world.h5"
    WorldStore.write(generate_world(WorldConfig(4, 4, 2), 3), path)
    assert path.exists()
    assert not path.with_suffix(".h5.tmp").exists()


def test_world_smoothing_does_not_wrap_opposite_edges() -> None:
    layer = np.zeros((5, 5), dtype=np.float64)
    layer[0, 0] = 1.0
    smoothed = _smooth(layer, passes=1)
    assert smoothed[-1, -1] == 0.0


def test_negative_resource_spend_is_rejected_without_mutation() -> None:
    pool = ResourcePool(50, 100)
    with pytest.raises(ValueError, match="may not be negative"):
        pool.spend(-10)
    assert pool.current == 50


def test_negative_resource_restore_is_rejected_without_mutation() -> None:
    pool = ResourcePool(50, 100)
    with pytest.raises(ValueError, match="may not be negative"):
        pool.restore(-10)
    assert pool.current == 50


def test_resource_pool_rejects_impossible_initial_state() -> None:
    with pytest.raises(ValueError, match="positive"):
        ResourcePool(0, 0)
    with pytest.raises(ValueError, match="exceed"):
        ResourcePool(11, 10)


def test_resource_pool_still_rejects_overspend() -> None:
    pool = ResourcePool(5, 10)
    with pytest.raises(IllegalActionError, match="not enough"):
        pool.spend(6)


@pytest.mark.parametrize("mass", [0.0, -1.0, nan, inf])
def test_physiology_rejects_invalid_mass(mass: float) -> None:
    with pytest.raises(ValueError):
        Physiology(mass)


def test_injury_rejects_negative_bleeding() -> None:
    with pytest.raises(ValueError, match="bleeding"):
        Injury(
            "arm",
            InjuryType.LACERATION,
            severity=0.4,
            bleeding_ml_per_min=-1.0,
        )


def test_injury_rejects_negative_mobility_penalty() -> None:
    with pytest.raises(ValueError, match="mobility"):
        Injury(
            "leg",
            InjuryType.FRACTURE,
            severity=0.6,
            mobility_penalty=-0.2,
        )


def test_negative_bleeding_cannot_be_injected_after_construction() -> None:
    body = Physiology(70.0)
    injury = Injury(
        "arm",
        InjuryType.LACERATION,
        severity=0.4,
        bleeding_ml_per_min=2.0,
    )
    injury.bleeding_ml_per_min = -2.0
    with pytest.raises(ValueError, match="bleeding"):
        body.add_injury(injury)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_text_commands_reject_nonfinite_numbers(value: str) -> None:
    session = build_demo_session(5)
    with pytest.raises(ValueError, match="finite"):
        session.execute(f"wait {value}")


def test_plan_action_rejects_negative_or_nonfinite_costs() -> None:
    with pytest.raises(ValueError, match="cost"):
        PlanAction("bad", cost=-1.0)
    with pytest.raises(ValueError, match="risk"):
        PlanAction("bad", risk=-1.0)
    with pytest.raises(ValueError, match="finite"):
        PlanAction("bad", cost=nan)


def test_world_fact_rejects_nondeterministic_mutable_values() -> None:
    with pytest.raises(ValueError, match="deterministic"):
        WorldFact("inventory", ["apple"])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bounds",
    [
        (-1.0, 0.3, 1.8),
        (0.3, 0.0, 1.8),
        (0.3, 0.3, nan),
    ],
)
def test_bounds_reject_invalid_geometry(bounds: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError):
        Bounds(*bounds)


def test_spatial_entity_rejects_nonpositive_mass() -> None:
    with pytest.raises(ValueError, match="mass"):
        SpatialEntity("x", "X", Vec3(0.0, 0.0, 0.0), mass_kg=0.0)


@pytest.mark.parametrize(
    "profile",
    [
        lambda: VisionProfile(field_of_view_degrees=0.0),
        lambda: VisionProfile(field_of_view_degrees=361.0),
        lambda: VisionProfile(max_distance_m=0.0),
        lambda: VisionProfile(night_vision=1.1),
        lambda: VisionProfile(acuity=nan),
    ],
)
def test_vision_profile_rejects_invalid_ranges(profile) -> None:
    with pytest.raises(ValueError):
        profile()
