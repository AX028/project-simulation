"""Physical doors and doorway clearance constraints."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .spatial import Bounds, SpatialEntity, Vec3


class PassageAxis(StrEnum):
    X = "x"
    Y = "y"


@dataclass(slots=True)
class Door:
    door_id: str
    name: str
    position: Vec3
    width_m: float
    height_m: float
    axis: PassageAxis = PassageAxis.Y
    thickness_m: float = 0.12
    is_open: bool = False
    locked: bool = False
    integrity: float = 100.0
    hardness: float = 1.0
    spatial: SpatialEntity = field(init=False)

    def __post_init__(self) -> None:
        if self.width_m <= 0 or self.height_m <= 0 or self.thickness_m <= 0:
            raise ValueError("door dimensions must be positive")
        if self.integrity < 0:
            raise ValueError("door integrity may not be negative")
        if self.hardness <= 0:
            raise ValueError("door hardness must be positive")
        self.integrity = min(100.0, self.integrity)
        self.spatial = SpatialEntity(
            self.door_id,
            self.name,
            self.position,
            bounds=self._closed_bounds(),
            mass_kg=max(1.0, self.width_m * self.height_m * self.thickness_m * 450.0),
            tags=frozenset(),
        )
        self._sync_spatial_tags()

    @property
    def destroyed(self) -> bool:
        return self.integrity <= 0.0

    def can_pass(
        self,
        entity: SpatialEntity,
        *,
        clearance_m: float = 0.02,
        crouch_factor: float = 1.0,
    ) -> bool:
        if not self.is_open and not self.destroyed:
            return False
        if clearance_m < 0:
            raise ValueError("clearance_m may not be negative")
        if not 0 < crouch_factor <= 1.0:
            raise ValueError("crouch_factor must be within (0, 1]")

        lateral_size = (
            entity.bounds.half_depth * 2.0
            if self.axis is PassageAxis.X
            else entity.bounds.half_width * 2.0
        )
        required_height = entity.bounds.height * crouch_factor
        available_width = max(0.0, self.width_m - clearance_m * 2.0)
        available_height = max(0.0, self.height_m - clearance_m)
        return (
            lateral_size <= available_width
            and required_height <= available_height
        )

    def crossing_fraction(
        self,
        entity: SpatialEntity,
        displacement: Vec3,
    ) -> float | None:
        if self.axis is PassageAxis.X:
            delta = displacement.x
            origin = entity.position.x
            plane = self.position.x
            lateral = entity.position.y
            lateral_delta = displacement.y
            half_size = entity.bounds.half_depth
            center = self.position.y
        else:
            delta = displacement.y
            origin = entity.position.y
            plane = self.position.y
            lateral = entity.position.x
            lateral_delta = displacement.x
            half_size = entity.bounds.half_width
            center = self.position.x

        if abs(delta) <= 1e-12:
            return None
        fraction = (plane - origin) / delta
        if not 0.0 <= fraction <= 1.0:
            return None

        crossing_lateral = lateral + lateral_delta * fraction
        opening_half = self.width_m / 2.0
        overlaps_opening = (
            crossing_lateral + half_size >= center - opening_half
            and crossing_lateral - half_size <= center + opening_half
        )
        if not overlaps_opening:
            return None

        crossing_z = entity.position.z + displacement.z * fraction
        overlaps_vertical = (
            crossing_z + entity.bounds.height >= self.position.z
            and crossing_z <= self.position.z + self.height_m
        )
        return fraction if overlaps_vertical else None

    def blocks_crossing(
        self,
        entity: SpatialEntity,
        displacement: Vec3,
    ) -> float | None:
        fraction = self.crossing_fraction(entity, displacement)
        if fraction is None:
            return None
        if self.can_pass(entity):
            return None
        return fraction

    def open_door(self) -> None:
        if self.destroyed:
            self.is_open = True
            self._sync_spatial_tags()
            return
        if self.locked:
            raise ValueError(f"{self.name} is locked")
        self.is_open = True
        self._sync_spatial_tags()

    def close_door(self) -> None:
        if self.destroyed:
            raise ValueError(f"{self.name} is destroyed and cannot close")
        self.is_open = False
        self._sync_spatial_tags()

    def apply_damage(self, damage: float) -> float:
        if damage < 0:
            raise ValueError("door damage may not be negative")
        effective = damage / self.hardness
        before = self.integrity
        self.integrity = max(0.0, self.integrity - effective)
        dealt = before - self.integrity
        if self.destroyed:
            self.locked = False
            self.is_open = True
        self._sync_spatial_tags()
        return dealt

    def _closed_bounds(self) -> Bounds:
        if self.axis is PassageAxis.X:
            return Bounds(
                self.thickness_m / 2.0,
                self.width_m / 2.0,
                self.height_m,
            )
        return Bounds(
            self.width_m / 2.0,
            self.thickness_m / 2.0,
            self.height_m,
        )

    def _sync_spatial_tags(self) -> None:
        tags = {"door"}
        if not self.is_open and not self.destroyed:
            tags.update({"solid", "occluder"})
        self.spatial.tags = frozenset(tags)
