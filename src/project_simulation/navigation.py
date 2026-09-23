"""Swept collision detection for deterministic 3D actor movement."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import inf

from .doors import Door
from .spatial import SpatialEntity, Vec3
from .worldstate import WorldActor

_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class SweepHit:
    entity_id: str
    fraction: float
    contact_position: Vec3


@dataclass(frozen=True, slots=True)
class MovementResult:
    requested_distance_m: float
    moved_distance_m: float
    end_position: Vec3
    hit: SweepHit | None


def _expanded_bounds(
    mover: SpatialEntity,
    obstacle: SpatialEntity,
) -> tuple[Vec3, Vec3]:
    return (
        Vec3(
            obstacle.position.x
            - obstacle.bounds.half_width
            - mover.bounds.half_width,
            obstacle.position.y
            - obstacle.bounds.half_depth
            - mover.bounds.half_depth,
            obstacle.position.z - mover.bounds.height,
        ),
        Vec3(
            obstacle.position.x
            + obstacle.bounds.half_width
            + mover.bounds.half_width,
            obstacle.position.y
            + obstacle.bounds.half_depth
            + mover.bounds.half_depth,
            obstacle.position.z + obstacle.bounds.height,
        ),
    )


def _point_inside_strict(point: Vec3, minimum: Vec3, maximum: Vec3) -> bool:
    return (
        minimum.x + _EPSILON < point.x < maximum.x - _EPSILON
        and minimum.y + _EPSILON < point.y < maximum.y - _EPSILON
        and minimum.z + _EPSILON < point.z < maximum.z - _EPSILON
    )


def _swept_point_fraction(
    start: Vec3,
    displacement: Vec3,
    minimum: Vec3,
    maximum: Vec3,
) -> float | None:
    if _point_inside_strict(start, minimum, maximum):
        return 0.0

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

    if exit_ <= _EPSILON or enter > 1.0 or exit_ < 0.0:
        return None
    return max(0.0, enter)


def sweep_entity(
    mover: SpatialEntity,
    displacement: Vec3,
    obstacles: Iterable[SpatialEntity],
) -> SweepHit | None:
    """Return the earliest collision against entities tagged solid."""
    if displacement.magnitude <= _EPSILON:
        return None

    best: SweepHit | None = None
    for obstacle in obstacles:
        if obstacle.entity_id == mover.entity_id or "solid" not in obstacle.tags:
            continue
        minimum, maximum = _expanded_bounds(mover, obstacle)
        fraction = _swept_point_fraction(
            mover.position,
            displacement,
            minimum,
            maximum,
        )
        if fraction is None or not 0.0 <= fraction <= 1.0:
            continue
        contact = mover.position + displacement.scale(fraction)
        candidate = SweepHit(obstacle.entity_id, fraction, contact)
        if best is None or (candidate.fraction, candidate.entity_id) < (
            best.fraction,
            best.entity_id,
        ):
            best = candidate
    return best



def sweep_doors(
    mover: SpatialEntity,
    displacement: Vec3,
    doors: Iterable[Door],
) -> SweepHit | None:
    """Return the earliest doorway crossing that the mover cannot pass."""
    if displacement.magnitude <= _EPSILON:
        return None

    best: SweepHit | None = None
    for door in doors:
        fraction = door.blocks_crossing(mover, displacement)
        if fraction is None:
            continue
        candidate = SweepHit(
            door.door_id,
            fraction,
            mover.position + displacement.scale(fraction),
        )
        if best is None or (candidate.fraction, candidate.entity_id) < (
            best.fraction,
            best.entity_id,
        ):
            best = candidate
    return best

def move_actor_with_collisions(
    actor: WorldActor,
    destination: Vec3,
    seconds: float,
    obstacles: Iterable[SpatialEntity],
    *,
    doors: Iterable[Door] = (),
    exertion: float = 0.35,
    clearance_m: float = 0.002,
    ambient_c: float = 20.0,
    speed_multiplier: float = 1.0,
) -> MovementResult:
    if seconds < 0:
        raise ValueError("seconds may not be negative")
    if clearance_m < 0:
        raise ValueError("clearance_m may not be negative")

    delta = destination - actor.spatial.position
    speed_multiplier = max(0.0, speed_multiplier)
    requested = min(
        delta.magnitude,
        actor.effective_speed() * speed_multiplier * seconds,
    )
    if requested <= _EPSILON:
        actor.physiology.tick(
            seconds / 60.0,
            exertion=exertion,
            ambient_c=ambient_c,
        )
        return MovementResult(
            requested,
            0.0,
            actor.spatial.position,
            None,
        )

    displacement = delta.normalized().scale(requested)
    solid_hit = sweep_entity(actor.spatial, displacement, obstacles)
    door_hit = sweep_doors(actor.spatial, displacement, doors)
    candidates = [hit for hit in (solid_hit, door_hit) if hit is not None]
    hit = min(
        candidates,
        key=lambda candidate: (candidate.fraction, candidate.entity_id),
        default=None,
    )
    allowed = requested
    if hit is not None:
        allowed = max(0.0, requested * hit.fraction - clearance_m)

    if allowed > 0:
        actor.spatial.position = (
            actor.spatial.position
            + displacement.normalized().scale(allowed)
        )
    actor.physiology.tick(
        seconds / 60.0,
        exertion=exertion,
        ambient_c=ambient_c,
    )
    return MovementResult(
        requested,
        allowed,
        actor.spatial.position,
        hit,
    )
