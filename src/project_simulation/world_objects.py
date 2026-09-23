"""Interactive physical objects placed in the spatial world."""

from __future__ import annotations

from dataclasses import dataclass

from .physiology import Container, PhysicalItem
from .spatial import SpatialEntity
from .validation import nonnegative_number, positive_number

_DESTROYED_PHYSICAL_TAGS = frozenset({"cover", "occluder", "solid"})


@dataclass(slots=True)
class SceneContainer:
    """A spatial, openable container with physically constrained storage."""

    spatial: SpatialEntity
    storage: Container
    is_open: bool = False
    locked: bool = False
    integrity: float = 100.0
    hardness: float = 1.0
    spilled: bool = False

    def __post_init__(self) -> None:
        if not self.spatial.entity_id:
            raise ValueError("scene container id may not be empty")
        item_ids = [item.item_id for item in self.storage.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("scene container item ids must be unique")
        self.integrity = min(
            100.0,
            nonnegative_number(
                self.integrity,
                "scene container integrity",
            ),
        )
        self.hardness = positive_number(
            self.hardness,
            "scene container hardness",
        )
        if self.spilled and not self.destroyed:
            raise ValueError("an intact scene container may not be spilled")
        if self.spilled and self.storage.items:
            raise ValueError("a spilled scene container may not contain items")
        if self.destroyed:
            self.locked = False
            self.is_open = True
        self._sync_spatial_tags()

    @property
    def container_id(self) -> str:
        return self.spatial.entity_id

    @property
    def name(self) -> str:
        return self.spatial.name

    @property
    def items(self) -> tuple[PhysicalItem, ...]:
        return tuple(self.storage.items)

    @property
    def destroyed(self) -> bool:
        return self.integrity <= 0.0

    def open_container(self) -> None:
        if self.destroyed:
            self.is_open = True
            self._sync_spatial_tags()
            return
        if self.locked:
            raise ValueError(f"{self.name} is locked")
        self.is_open = True

    def close_container(self) -> None:
        if self.destroyed:
            raise ValueError(f"{self.name} is destroyed and cannot close")
        self.is_open = False

    def apply_damage(self, damage: float) -> float:
        damage = nonnegative_number(
            damage,
            "scene container damage",
        )
        effective = damage / self.hardness
        before = self.integrity
        self.integrity = max(0.0, self.integrity - effective)
        dealt = before - self.integrity
        if self.destroyed:
            self.locked = False
            self.is_open = True
        self._sync_spatial_tags()
        return dealt

    def spill_contents(self) -> tuple[PhysicalItem, ...]:
        if not self.destroyed:
            raise ValueError(f"{self.name} is intact and cannot spill")
        if self.spilled:
            return ()
        items = tuple(
            sorted(
                self.storage.items,
                key=lambda item: item.item_id,
            )
        )
        self.storage.items.clear()
        self.spilled = True
        return items

    def resolve_item(self, query: str) -> PhysicalItem:
        lowered = query.lower()
        matches = [
            item
            for item in self.storage.items
            if item.item_id.lower() == lowered or item.name.lower() == lowered
        ]
        if len(matches) != 1:
            if not matches:
                raise ValueError(f"{self.name} does not contain: {query}")
            raise ValueError(f"ambiguous item in {self.name}: {query}")
        return matches[0]

    def take(self, query: str) -> PhysicalItem:
        self._require_open()
        item = self.resolve_item(query)
        self.storage.items.remove(item)
        return item

    def put(self, item: PhysicalItem) -> None:
        self._require_open()
        if self.destroyed:
            raise ValueError(f"{self.name} is destroyed and cannot hold items")
        if any(stored.item_id == item.item_id for stored in self.storage.items):
            raise ValueError(f"{self.name} already contains {item.name}")
        self.storage.add(item)

    def access_time(self, item: PhysicalItem) -> float:
        return item.accessibility_s + self.storage.retrieval_penalty_s

    def _require_open(self) -> None:
        if not self.is_open:
            raise ValueError(f"{self.name} is closed")

    def _sync_spatial_tags(self) -> None:
        tags = set(self.spatial.tags)
        tags.add("container")
        if self.destroyed:
            tags.difference_update(_DESTROYED_PHYSICAL_TAGS)
        self.spatial.tags = frozenset(tags)


__all__ = ["SceneContainer"]
