"""Interactive physical objects placed in the spatial world."""

from __future__ import annotations

from dataclasses import dataclass

from .physiology import Container, PhysicalItem
from .spatial import SpatialEntity


@dataclass(slots=True)
class SceneContainer:
    """A spatial, openable container with physically constrained storage."""

    spatial: SpatialEntity
    storage: Container
    is_open: bool = False
    locked: bool = False

    def __post_init__(self) -> None:
        if not self.spatial.entity_id:
            raise ValueError("scene container id may not be empty")
        item_ids = [item.item_id for item in self.storage.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("scene container item ids must be unique")
        self.spatial.tags = self.spatial.tags | frozenset({"container"})

    @property
    def container_id(self) -> str:
        return self.spatial.entity_id

    @property
    def name(self) -> str:
        return self.spatial.name

    @property
    def items(self) -> tuple[PhysicalItem, ...]:
        return tuple(self.storage.items)

    def open_container(self) -> None:
        if self.locked:
            raise ValueError(f"{self.name} is locked")
        self.is_open = True

    def close_container(self) -> None:
        self.is_open = False

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
        if any(stored.item_id == item.item_id for stored in self.storage.items):
            raise ValueError(f"{self.name} already contains {item.name}")
        self.storage.add(item)

    def access_time(self, item: PhysicalItem) -> float:
        return item.accessibility_s + self.storage.retrieval_penalty_s

    def _require_open(self) -> None:
        if not self.is_open:
            raise ValueError(f"{self.name} is closed")


__all__ = ["SceneContainer"]
