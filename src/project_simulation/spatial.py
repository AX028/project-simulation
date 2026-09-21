"""3D spatial primitives and perception for the text-first world simulation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import acos, degrees, sqrt

from .validation import bounded_number, finite_number, nonnegative_number, positive_number


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float = 0.0

    def __post_init__(self) -> None:
        finite_number(self.x, "x coordinate")
        finite_number(self.y, "y coordinate")
        finite_number(self.z, "z coordinate")

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def scale(self, value: float) -> Vec3:
        return Vec3(self.x * value, self.y * value, self.z * value)

    @property
    def magnitude(self) -> float:
        return sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self) -> Vec3:
        length = self.magnitude
        return self if length == 0 else self.scale(1.0 / length)

    def distance_to(self, other: Vec3) -> float:
        return (other - self).magnitude

    def dot(self, other: Vec3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z


@dataclass(slots=True)
class Bounds:
    half_width: float
    half_depth: float
    height: float

    def __post_init__(self) -> None:
        positive_number(self.half_width, "half width")
        positive_number(self.half_depth, "half depth")
        positive_number(self.height, "height")


@dataclass(slots=True)
class SpatialEntity:
    entity_id: str
    name: str
    position: Vec3
    facing: Vec3 = field(default_factory=lambda: Vec3(0.0, 1.0, 0.0))
    velocity: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    bounds: Bounds = field(default_factory=lambda: Bounds(0.3, 0.3, 1.8))
    mass_kg: float = 70.0
    visible: bool = True
    tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        positive_number(self.mass_kg, "entity mass")


@dataclass(frozen=True, slots=True)
class VisionProfile:
    acuity: float = 1.0
    field_of_view_degrees: float = 160.0
    max_distance_m: float = 120.0
    night_vision: float = 0.2

    def __post_init__(self) -> None:
        nonnegative_number(self.acuity, "visual acuity")
        bounded_number(
            self.field_of_view_degrees,
            "field of view",
            0.000001,
            360.0,
        )
        positive_number(self.max_distance_m, "vision distance")
        bounded_number(self.night_vision, "night vision", 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class Observation:
    observer_id: str
    target_id: str
    distance_m: float
    bearing: str
    elevation_m: float
    clarity: float
    description: str


def bearing_label(observer: SpatialEntity, target: SpatialEntity) -> str:
    direction = (target.position - observer.position).normalized()
    forward = observer.facing.normalized()
    dot = max(-1.0, min(1.0, forward.dot(direction)))
    angle = degrees(acos(dot))
    cross_z = forward.x * direction.y - forward.y * direction.x
    if angle <= 22.5:
        return "FRONT"
    if angle >= 157.5:
        return "BEHIND"
    side = "LEFT" if cross_z > 0 else "RIGHT"
    if angle <= 67.5:
        return f"FRONT-{side}"
    if angle >= 112.5:
        return f"BEHIND-{side}"
    return side


def _segment_aabb_occluded(start: Vec3, end: Vec3, obstacle: SpatialEntity) -> bool:
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
    t_min, t_max = 0.0, 1.0
    for origin, delta, low, high in (
        (start.x, direction.x, minimum.x, maximum.x),
        (start.y, direction.y, minimum.y, maximum.y),
        (start.z, direction.z, minimum.z, maximum.z),
    ):
        if abs(delta) < 1e-9:
            if origin < low or origin > high:
                return False
            continue
        t1, t2 = (low - origin) / delta, (high - origin) / delta
        t1, t2 = min(t1, t2), max(t1, t2)
        t_min, t_max = max(t_min, t1), min(t_max, t2)
        if t_min > t_max:
            return False
    return 0.0 < t_min < 1.0


def observe(
    observer: SpatialEntity,
    target: SpatialEntity,
    profile: VisionProfile | None = None,
    *,
    illumination: float = 1.0,
    contrast: float = 1.0,
    obstacles: Iterable[SpatialEntity] = (),
) -> Observation | None:
    if not target.visible:
        return None
    if profile is None:
        profile = VisionProfile()
    illumination = bounded_number(
        illumination,
        "illumination",
        0.0,
        1.0,
    )
    contrast = nonnegative_number(contrast, "contrast")

    distance = observer.position.distance_to(target.position)
    if distance > profile.max_distance_m:
        return None

    direction = (target.position - observer.position).normalized()
    dot = max(-1.0, min(1.0, observer.facing.normalized().dot(direction)))
    angle = degrees(acos(dot))
    if angle > profile.field_of_view_degrees / 2.0:
        return None

    eye = observer.position + Vec3(0.0, 0.0, observer.bounds.height * 0.9)
    target_center = target.position + Vec3(0.0, 0.0, target.bounds.height * 0.55)
    blocked = any(
        item.entity_id not in {observer.entity_id, target.entity_id}
        and "occluder" in item.tags
        and _segment_aabb_occluded(eye, target_center, item)
        for item in obstacles
    )
    if blocked:
        return None

    light = max(0.05, min(1.0, illumination + profile.night_vision * (1.0 - illumination)))
    apparent_size = max(0.1, target.bounds.height)
    clarity = profile.acuity * contrast * light * apparent_size / max(1.0, distance * 0.08)
    clarity = max(0.0, min(1.0, clarity))

    if clarity >= 0.75:
        description = f"{target.name}, clearly visible"
    elif clarity >= 0.4:
        description = f"a {target.name.lower()}-shaped figure"
    elif clarity >= 0.15:
        description = "a distant figure"
    else:
        description = "faint movement"

    return Observation(
        observer.entity_id,
        target.entity_id,
        distance,
        bearing_label(observer, target),
        target.position.z - observer.position.z,
        clarity,
        description,
    )
