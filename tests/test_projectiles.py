import pytest

from project_simulation import (
    Bounds,
    Projectile,
    ProjectileSimulator,
    ProjectileSpec,
    SpatialEntity,
    Vec3,
    ballistic_drop_m,
    impact_speed_from_energy,
    launch_velocity,
    sweep_projectile,
)


def _arrow(
    *,
    position: Vec3 | None = None,
    velocity: Vec3 | None = None,
    owner_id: str | None = None,
    gravity: float = 0.0,
    lifetime: float = 30.0,
) -> Projectile:
    return Projectile(
        "arrow",
        ProjectileSpec(
            "Arrow",
            mass_kg=0.03,
            radius_m=0.01,
            gravity_mps2=gravity,
            max_lifetime_s=lifetime,
        ),
        Vec3(0.0, 0.0, 1.0) if position is None else position,
        Vec3(0.0, 50.0, 0.0) if velocity is None else velocity,
        owner_id=owner_id,
    )


def _target(
    entity_id: str,
    position: Vec3,
    *,
    width: float = 0.6,
    depth: float = 0.6,
    height: float = 1.8,
) -> SpatialEntity:
    return SpatialEntity(
        entity_id,
        entity_id.title(),
        position,
        bounds=Bounds(width / 2.0, depth / 2.0, height),
    )


def test_launch_velocity_normalizes_direction() -> None:
    velocity = launch_velocity(Vec3(0.0, 2.0, 0.0), 40.0)
    assert velocity == Vec3(0.0, 40.0, 0.0)


def test_ballistic_drop_matches_constant_gravity_formula() -> None:
    assert ballistic_drop_m(100.0, 50.0) == pytest.approx(19.62)


def test_energy_speed_conversion_round_trip() -> None:
    mass = 0.03
    speed = 60.0
    energy = 0.5 * mass * speed * speed
    assert impact_speed_from_energy(energy, mass) == pytest.approx(speed)


def test_projectile_kinetic_energy_uses_current_velocity() -> None:
    arrow = _arrow(velocity=Vec3(0.0, 60.0, 0.0))
    assert arrow.kinetic_energy_j == pytest.approx(54.0)


def test_swept_collision_hits_target_without_tunneling() -> None:
    arrow = _arrow(velocity=Vec3(0.0, 1000.0, 0.0))
    target = _target("wall", Vec3(0.0, 500.0, 0.0))
    collision = sweep_projectile(
        arrow,
        Vec3(0.0, 1000.0, 0.0),
        [target],
    )
    assert collision is not None
    assert collision[0].entity_id == "wall"
    assert 0.0 < collision[1] < 1.0


def test_owner_is_excluded_from_projectile_collision() -> None:
    arrow = _arrow(owner_id="archer")
    owner = _target("archer", Vec3(0.0, 1.0, 0.0))
    target = _target("target", Vec3(0.0, 5.0, 0.0))
    collision = sweep_projectile(
        arrow,
        Vec3(0.0, 10.0, 0.0),
        [owner, target],
    )
    assert collision is not None
    assert collision[0].entity_id == "target"


def test_nearest_projectile_target_wins() -> None:
    arrow = _arrow()
    collision = sweep_projectile(
        arrow,
        Vec3(0.0, 20.0, 0.0),
        [
            _target("far", Vec3(0.0, 15.0, 0.0)),
            _target("near", Vec3(0.0, 5.0, 0.0)),
        ],
    )
    assert collision is not None
    assert collision[0].entity_id == "near"


def test_equal_fraction_collision_breaks_tie_by_entity_id() -> None:
    arrow = _arrow()
    collision = sweep_projectile(
        arrow,
        Vec3(0.0, 10.0, 0.0),
        [
            _target("b", Vec3(0.0, 5.0, 0.0)),
            _target("a", Vec3(0.0, 5.0, 0.0)),
        ],
    )
    assert collision is not None
    assert collision[0].entity_id == "a"


def test_simulator_step_stops_projectile_on_impact() -> None:
    simulator = ProjectileSimulator()
    arrow = _arrow(velocity=Vec3(0.0, 50.0, 0.0))
    simulator.launch(arrow)
    target = _target("target", Vec3(0.0, 10.0, 0.0))

    step = simulator.step("arrow", 1.0, [target])

    assert step.hit is not None
    assert step.hit.target_id == "target"
    assert not step.active
    assert not arrow.active
    assert arrow.position.y < 10.0


def test_gravity_changes_vertical_velocity_and_position() -> None:
    simulator = ProjectileSimulator()
    arrow = _arrow(
        velocity=Vec3(50.0, 0.0, 0.0),
        gravity=10.0,
    )
    simulator.launch(arrow)

    step = simulator.step("arrow", 1.0, [])

    assert step.end_position.x == pytest.approx(50.0)
    assert step.end_position.z == pytest.approx(-4.0)
    assert arrow.velocity.z == pytest.approx(-10.0)


def test_drag_reduces_horizontal_speed() -> None:
    simulator = ProjectileSimulator()
    arrow = Projectile(
        "arrow",
        ProjectileSpec(
            "Arrow",
            mass_kg=0.03,
            radius_m=0.01,
            drag_coefficient=0.1,
            gravity_mps2=0.0,
        ),
        Vec3(0.0, 0.0, 1.0),
        Vec3(100.0, 0.0, 0.0),
    )
    simulator.launch(arrow)
    simulator.step("arrow", 1.0, [])
    assert arrow.velocity.x == pytest.approx(90.0)


def test_lifetime_caps_large_timestep() -> None:
    simulator = ProjectileSimulator()
    arrow = _arrow(
        velocity=Vec3(10.0, 0.0, 0.0),
        lifetime=0.5,
    )
    simulator.launch(arrow)

    step = simulator.step("arrow", 10.0, [])

    assert step.elapsed_s == pytest.approx(0.5)
    assert arrow.age_s == pytest.approx(0.5)
    assert arrow.position.x == pytest.approx(5.0)
    assert not arrow.active


def test_duplicate_projectile_id_is_rejected() -> None:
    simulator = ProjectileSimulator()
    simulator.launch(_arrow())
    with pytest.raises(ValueError, match="duplicate"):
        simulator.launch(_arrow())


def test_inactive_projectile_cannot_launch() -> None:
    simulator = ProjectileSimulator()
    arrow = _arrow()
    arrow.active = False
    with pytest.raises(ValueError, match="inactive"):
        simulator.launch(arrow)


def test_invalid_step_duration_is_rejected() -> None:
    simulator = ProjectileSimulator()
    simulator.launch(_arrow())
    with pytest.raises(ValueError, match="positive"):
        simulator.step("arrow", 0.0, [])


def test_simulate_until_inactive_reaches_lifetime() -> None:
    simulator = ProjectileSimulator()
    arrow = _arrow(
        velocity=Vec3(1.0, 0.0, 0.0),
        lifetime=0.1,
    )
    simulator.launch(arrow)

    steps = simulator.simulate_until_inactive(
        "arrow",
        [],
        dt_s=0.02,
    )

    assert len(steps) == 5
    assert not arrow.active
    assert arrow.age_s == pytest.approx(0.1)


def test_thousand_small_steps_are_deterministic() -> None:
    def simulate() -> tuple[Vec3, Vec3, float]:
        simulator = ProjectileSimulator()
        projectile = Projectile(
            "p",
            ProjectileSpec(
                "Test",
                mass_kg=0.02,
                radius_m=0.005,
                drag_coefficient=0.001,
                gravity_mps2=9.81,
                max_lifetime_s=10.0,
            ),
            Vec3(0.0, 0.0, 10.0),
            Vec3(40.0, 20.0, 10.0),
        )
        simulator.launch(projectile)
        for _ in range(1000):
            if not projectile.active:
                break
            simulator.step("p", 0.01, [])
        return (
            projectile.position,
            projectile.velocity,
            projectile.distance_traveled_m,
        )

    assert simulate() == simulate()


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (
            lambda: ProjectileSpec("bad", 0.0, 0.01),
            "mass",
        ),
        (
            lambda: ProjectileSpec("bad", 1.0, -0.01),
            "radius",
        ),
        (
            lambda: ProjectileSpec(
                "bad",
                1.0,
                0.01,
                drag_coefficient=-1.0,
            ),
            "drag",
        ),
        (
            lambda: ProjectileSpec(
                "bad",
                1.0,
                0.01,
                max_lifetime_s=0.0,
            ),
            "lifetime",
        ),
    ],
)
def test_invalid_projectile_specs_are_rejected(spec, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        spec()
