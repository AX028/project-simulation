"""Deterministic 3D projectile simulation with swept collision."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import inf, sqrt

from .spatial import SpatialEntity, Vec3

_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class ProjectileSpec:
    name: str
    mass_kg: float
    radius_m: float
    drag_coefficient: float = 0.0
    gravity_mps2: float = 9.81
    max_lifetime_s: float = 30.0

    def __post_init__(self) -> None:
        if self.mass_kg <= 0:
            raise ValueError("projectile mass must be positive")
        if self.radius_m < 0:
            raise ValueError("projectile radius may not be negative")
        if self.drag_coefficient < 0:
            raise ValueError("drag coefficient may not be negative")
        if self.gravity_mps2 < 0:
            raise ValueError("gravity may not be negative")
        if self.max_lifetime_s <= 0:
            raise ValueError("max lifetime must be positive")


@dataclass(slots=True)
class Projectile:
    projectile_id: str
    spec: ProjectileSpec
    position: Vec3
    velocity: Vec3
    owner_id: str | None = None
    age_s: float = 0.0
    distance_traveled_m: float = 0.0
    active: bool = True

    @property
    def speed_mps(self) -> float:
        return self.velocity.magnitude

    @property
    def kinetic_energy_j(self) -> float:
        return 0.5 * self.spec.mass_kg * self.speed_mps * self.speed_mps


@dataclass(frozen=True, slots=True)
class ProjectileHit:
    projectile_id: str
    target_id: str
    position: Vec3
    time_fraction: float
    speed_mps: float
    kinetic_energy_j: float


@dataclass(frozen=True, slots=True)
class ProjectileStep:
    projectile_id: str
    start_position: Vec3
    end_position: Vec3
    elapsed_s: float
    hit: ProjectileHit | None
    active: bool


def _expanded_bounds(
    target: SpatialEntity,
    radius: float,
) -> tuple[Vec3, Vec3]:
    return (
        Vec3(
            target.position.x - target.bounds.half_width - radius,
            target.position.y - target.bounds.half_depth - radius,
            target.position.z - radius,
        ),
        Vec3(
            target.position.x + target.bounds.half_width + radius,
            target.position.y + target.bounds.half_depth + radius,
            target.position.z + target.bounds.height + radius,
        ),
    )


def _segment_fraction(
    start: Vec3,
    displacement: Vec3,
    minimum: Vec3,
    maximum: Vec3,
) -> float | None:
    enter = -inf
    exit_ = inf
    for origin, delta, low, high in (
        (start.x, displacement.x, minimum.x, maximum.x),
        (start.y, displacement.y, minimum.y, maximum.y),
        (start.z, displacement.z, minimum.z, maximum.z),
    ):
        if abs(delta) <= _EPSILON:
            if origin < low or origin > high:
                return None
            continue
        first = (low - origin) / delta
        second = (high - origin) / delta
        axis_enter = min(first, second)
        axis_exit = max(first, second)
        enter = max(enter, axis_enter)
        exit_ = min(exit_, axis_exit)
        if enter > exit_:
            return None

    if exit_ < 0.0 or enter > 1.0:
        return None
    return max(0.0, enter)


def sweep_projectile(
    projectile: Projectile,
    displacement: Vec3,
    targets: Iterable[SpatialEntity],
) -> tuple[SpatialEntity, float] | None:
    best: tuple[SpatialEntity, float] | None = None
    for target in targets:
        if target.entity_id == projectile.owner_id:
            continue
        minimum, maximum = _expanded_bounds(
            target,
            projectile.spec.radius_m,
        )
        fraction = _segment_fraction(
            projectile.position,
            displacement,
            minimum,
            maximum,
        )
        if fraction is None:
            continue
        candidate = (target, fraction)
        if best is None or (fraction, target.entity_id) < (
            best[1],
            best[0].entity_id,
        ):
            best = candidate
    return best


@dataclass(slots=True)
class ProjectileSimulator:
    projectiles: dict[str, Projectile] = field(default_factory=dict)

    def launch(self, projectile: Projectile) -> None:
        if projectile.projectile_id in self.projectiles:
            raise ValueError(
                f"duplicate projectile id: {projectile.projectile_id}"
            )
        if not projectile.active:
            raise ValueError("cannot launch an inactive projectile")
        self.projectiles[projectile.projectile_id] = projectile

    def step(
        self,
        projectile_id: str,
        dt_s: float,
        targets: Iterable[SpatialEntity],
    ) -> ProjectileStep:
        if dt_s <= 0:
            raise ValueError("dt_s must be positive")
        try:
            projectile = self.projectiles[projectile_id]
        except KeyError as exc:
            raise KeyError(projectile_id) from exc
        if not projectile.active:
            raise ValueError("projectile is inactive")

        remaining_lifetime = (
            projectile.spec.max_lifetime_s - projectile.age_s
        )
        if remaining_lifetime <= _EPSILON:
            projectile.active = False
            return ProjectileStep(
                projectile.projectile_id,
                projectile.position,
                projectile.position,
                0.0,
                None,
                False,
            )
        effective_dt = min(dt_s, remaining_lifetime)

        start = projectile.position
        velocity_start = projectile.velocity
        drag = max(
            0.0,
            1.0 - projectile.spec.drag_coefficient * effective_dt,
        )
        velocity_horizontal = Vec3(
            velocity_start.x * drag,
            velocity_start.y * drag,
            velocity_start.z,
        )
        velocity_end = Vec3(
            velocity_horizontal.x,
            velocity_horizontal.y,
            velocity_horizontal.z
            - projectile.spec.gravity_mps2 * effective_dt,
        )
        average_velocity = Vec3(
            (velocity_start.x + velocity_end.x) / 2.0,
            (velocity_start.y + velocity_end.y) / 2.0,
            (velocity_start.z + velocity_end.z) / 2.0,
        )
        displacement = average_velocity.scale(effective_dt)

        collision = sweep_projectile(projectile, displacement, targets)
        hit: ProjectileHit | None = None
        actual_fraction = 1.0
        if collision is not None:
            target, actual_fraction = collision
            impact_velocity = Vec3(
                velocity_start.x
                + (velocity_end.x - velocity_start.x) * actual_fraction,
                velocity_start.y
                + (velocity_end.y - velocity_start.y) * actual_fraction,
                velocity_start.z
                + (velocity_end.z - velocity_start.z) * actual_fraction,
            )
            impact_speed = impact_velocity.magnitude
            impact_energy = (
                0.5
                * projectile.spec.mass_kg
                * impact_speed
                * impact_speed
            )
            projectile.position = start + displacement.scale(actual_fraction)
            projectile.velocity = impact_velocity
            projectile.active = False
            hit = ProjectileHit(
                projectile.projectile_id,
                target.entity_id,
                projectile.position,
                actual_fraction,
                impact_speed,
                impact_energy,
            )
        else:
            projectile.position = start + displacement
            projectile.velocity = velocity_end

        traveled = displacement.magnitude * actual_fraction
        projectile.distance_traveled_m += traveled
        elapsed = effective_dt * actual_fraction
        projectile.age_s += elapsed

        if (
            projectile.active
            and projectile.age_s >= projectile.spec.max_lifetime_s
        ):
            projectile.active = False

        return ProjectileStep(
            projectile.projectile_id,
            start,
            projectile.position,
            elapsed,
            hit,
            projectile.active,
        )

    def simulate_until_inactive(
        self,
        projectile_id: str,
        targets: Iterable[SpatialEntity],
        *,
        dt_s: float = 0.02,
        max_steps: int = 100_000,
    ) -> tuple[ProjectileStep, ...]:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        target_list = tuple(targets)
        steps: list[ProjectileStep] = []
        for _ in range(max_steps):
            projectile = self.projectiles[projectile_id]
            if not projectile.active:
                break
            steps.append(self.step(projectile_id, dt_s, target_list))
        return tuple(steps)


def launch_velocity(
    direction: Vec3,
    speed_mps: float,
) -> Vec3:
    if speed_mps < 0:
        raise ValueError("speed may not be negative")
    if direction.magnitude <= _EPSILON:
        raise ValueError("launch direction may not be zero")
    return direction.normalized().scale(speed_mps)


def ballistic_drop_m(
    horizontal_distance_m: float,
    horizontal_speed_mps: float,
    gravity_mps2: float = 9.81,
) -> float:
    if horizontal_distance_m < 0:
        raise ValueError("distance may not be negative")
    if horizontal_speed_mps <= 0:
        raise ValueError("horizontal speed must be positive")
    if gravity_mps2 < 0:
        raise ValueError("gravity may not be negative")
    time = horizontal_distance_m / horizontal_speed_mps
    return 0.5 * gravity_mps2 * time * time


def impact_speed_from_energy(energy_j: float, mass_kg: float) -> float:
    if energy_j < 0:
        raise ValueError("energy may not be negative")
    if mass_kg <= 0:
        raise ValueError("mass must be positive")
    return sqrt(2.0 * energy_j / mass_kg)
