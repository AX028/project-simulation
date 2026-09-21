"""Deterministic sound propagation and hearing perception."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import log10

from .spatial import SpatialEntity, Vec3


@dataclass(frozen=True, slots=True)
class SoundEvent:
    sound_id: str
    position: Vec3
    loudness_db_at_1m: float
    category: str
    description: str
    created_hour: float
    source_id: str | None = None

    def __post_init__(self) -> None:
        if self.loudness_db_at_1m < 0:
            raise ValueError("sound loudness may not be negative")


@dataclass(frozen=True, slots=True)
class HearingProfile:
    threshold_db: float = 20.0
    sensitivity_db: float = 0.0
    occlusion_loss_db: float = 12.0

    def __post_init__(self) -> None:
        if self.occlusion_loss_db < 0:
            raise ValueError("occlusion loss may not be negative")


@dataclass(frozen=True, slots=True)
class HeardSound:
    listener_id: str
    sound_id: str
    distance_m: float
    perceived_db: float
    occluders: int
    direction: Vec3
    clarity: float


def distance_attenuation_db(distance_m: float) -> float:
    if distance_m < 0:
        raise ValueError("distance may not be negative")
    return 20.0 * log10(max(1.0, distance_m))


def _segment_intersects_entity(
    start: Vec3,
    end: Vec3,
    obstacle: SpatialEntity,
) -> bool:
    minimum = Vec3(
        obstacle.position.x - obstacle.bounds.half_width,
        obstacle.position.y - obstacle.bounds.half_depth,
        obstacle.position.z,
    )
    maximum = Vec3(
        obstacle.position.x + obstacle.bounds.half_width,
        obstacle.position.y + obstacle.bounds.half_depth,
        obstacle.position.z + obstacle.bounds.height,
    )
    direction = end - start
    enter = 0.0
    exit_ = 1.0
    for origin, delta, low, high in (
        (start.x, direction.x, minimum.x, maximum.x),
        (start.y, direction.y, minimum.y, maximum.y),
        (start.z, direction.z, minimum.z, maximum.z),
    ):
        if abs(delta) < 1e-12:
            if origin < low or origin > high:
                return False
            continue
        first = (low - origin) / delta
        second = (high - origin) / delta
        axis_enter = min(first, second)
        axis_exit = max(first, second)
        enter = max(enter, axis_enter)
        exit_ = min(exit_, axis_exit)
        if enter > exit_:
            return False
    return 0.0 < enter < 1.0


def count_sound_occluders(
    start: Vec3,
    end: Vec3,
    obstacles: Iterable[SpatialEntity],
    *,
    ignored_ids: frozenset[str] | None = None,
) -> int:
    ignored = frozenset() if ignored_ids is None else ignored_ids
    return sum(
        1
        for obstacle in obstacles
        if obstacle.entity_id not in ignored
        and ("solid" in obstacle.tags or "occluder" in obstacle.tags)
        and _segment_intersects_entity(start, end, obstacle)
    )


def hear_sound(
    event: SoundEvent,
    listener: SpatialEntity,
    profile: HearingProfile | None = None,
    *,
    obstacles: Iterable[SpatialEntity] = (),
) -> HeardSound | None:
    if profile is None:
        profile = HearingProfile()
    listener_point = listener.position + Vec3(
        0.0,
        0.0,
        listener.bounds.height * 0.85,
    )
    distance = listener_point.distance_to(event.position)
    occluders = count_sound_occluders(
        event.position,
        listener_point,
        obstacles,
        ignored_ids=frozenset(
            value
            for value in (event.source_id, listener.entity_id)
            if value is not None
        ),
    )
    perceived = (
        event.loudness_db_at_1m
        - distance_attenuation_db(distance)
        - occluders * profile.occlusion_loss_db
        + profile.sensitivity_db
    )
    if perceived < profile.threshold_db:
        return None

    margin = perceived - profile.threshold_db
    clarity = max(0.0, min(1.0, margin / 40.0))
    direction = (event.position - listener_point).normalized()
    return HeardSound(
        listener.entity_id,
        event.sound_id,
        distance,
        perceived,
        occluders,
        direction,
        clarity,
    )


def propagate_sound(
    event: SoundEvent,
    listeners: Iterable[tuple[SpatialEntity, HearingProfile]],
    *,
    obstacles: Iterable[SpatialEntity] = (),
) -> tuple[HeardSound, ...]:
    heard: list[HeardSound] = []
    obstacle_list = tuple(obstacles)
    for listener, profile in listeners:
        result = hear_sound(
            event,
            listener,
            profile,
            obstacles=obstacle_list,
        )
        if result is not None:
            heard.append(result)
    heard.sort(key=lambda item: (item.distance_m, item.listener_id))
    return tuple(heard)
