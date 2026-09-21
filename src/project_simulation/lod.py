"""Actor level-of-detail compression and deterministic restoration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from .cognition import Belief, EmotionState, Goal, Memory, Mind, Relationship
from .physiology import Loadout, PhysicalItem, Physiology
from .simulation import SimulationLOD
from .spatial import Bounds, SpatialEntity, Vec3, VisionProfile
from .worldstate import WorldActor


@dataclass(slots=True)
class AbstractActorState:
    actor_id: str
    name: str
    tier: SimulationLOD
    position: Vec3
    facing: Vec3
    velocity: Vec3
    bounds: Bounds
    spatial_mass_kg: float
    visible: bool
    tags: frozenset[str]
    physiology: Physiology
    body_mass_kg: float
    comfortable_load_ratio: float
    carried_mass_kg: float
    carried_volume_l: float
    movement_speed_mps: float
    vision: VisionProfile
    memories: tuple[Memory, ...]
    beliefs: tuple[tuple[str, Belief], ...]
    relationships: tuple[tuple[str, Relationship], ...]
    emotions: EmotionState
    goals: tuple[tuple[str, Goal], ...]
    knowledge: frozenset[str]
    original_memory_count: int
    original_belief_count: int
    original_relationship_count: int

    @property
    def compression_counts(self) -> tuple[int, int, int]:
        return (
            len(self.memories),
            len(self.beliefs),
            len(self.relationships),
        )


def _memory_score(memory: Memory, now: float) -> float:
    return memory.accessibility(now) * (0.5 + 0.5 * memory.confidence)


def _relationship_score(relationship: Relationship) -> float:
    return (
        abs(relationship.affection)
        + abs(relationship.trust)
        + abs(relationship.respect)
        + relationship.fear
        + abs(relationship.resentment)
        + relationship.dependency
        + relationship.familiarity * 0.25
    )


def abstract_actor(
    actor: WorldActor,
    *,
    tier: SimulationLOD,
    now: float,
    memory_limit: int = 12,
    belief_limit: int = 20,
    relationship_limit: int = 12,
) -> AbstractActorState:
    if tier < SimulationLOD.SETTLEMENT:
        raise ValueError("abstract actors must use settlement-or-coarser LOD")
    if min(memory_limit, belief_limit, relationship_limit) < 0:
        raise ValueError("compression limits may not be negative")

    memories = sorted(
        actor.mind.memories,
        key=lambda item: (-_memory_score(item, now), item.subject, item.proposition),
    )[:memory_limit]
    beliefs = sorted(
        actor.mind.beliefs.items(),
        key=lambda item: (-item[1].confidence, item[0]),
    )[:belief_limit]
    relationships = sorted(
        actor.mind.relationships.items(),
        key=lambda item: (-_relationship_score(item[1]), item[0]),
    )[:relationship_limit]

    carried_items = [
        item
        for container in actor.loadout.containers
        for item in container.items
    ]
    carried_items.extend(actor.loadout.carried_loose)

    return AbstractActorState(
        actor_id=actor.actor_id,
        name=actor.spatial.name,
        tier=tier,
        position=actor.spatial.position,
        facing=actor.spatial.facing,
        velocity=actor.spatial.velocity,
        bounds=deepcopy(actor.spatial.bounds),
        spatial_mass_kg=actor.spatial.mass_kg,
        visible=actor.spatial.visible,
        tags=actor.spatial.tags,
        physiology=deepcopy(actor.physiology),
        body_mass_kg=actor.loadout.body_mass_kg,
        comfortable_load_ratio=actor.loadout.comfortable_load_ratio,
        carried_mass_kg=sum(item.mass_kg for item in carried_items),
        carried_volume_l=sum(item.volume_l for item in carried_items),
        movement_speed_mps=actor.movement_speed_mps,
        vision=deepcopy(actor.vision),
        memories=tuple(deepcopy(memories)),
        beliefs=tuple((key, deepcopy(value)) for key, value in beliefs),
        relationships=tuple(
            (key, deepcopy(value))
            for key, value in relationships
        ),
        emotions=deepcopy(actor.mind.emotions),
        goals=tuple(
            (key, deepcopy(value))
            for key, value in sorted(actor.mind.goals.items())
        ),
        knowledge=frozenset(actor.mind.knowledge),
        original_memory_count=len(actor.mind.memories),
        original_belief_count=len(actor.mind.beliefs),
        original_relationship_count=len(actor.mind.relationships),
    )


def restore_actor(state: AbstractActorState) -> WorldActor:
    mind = Mind(
        memories=list(deepcopy(state.memories)),
        beliefs={
            key: deepcopy(value)
            for key, value in state.beliefs
        },
        emotions=deepcopy(state.emotions),
        relationships={
            key: deepcopy(value)
            for key, value in state.relationships
        },
        goals={
            key: deepcopy(value)
            for key, value in state.goals
        },
        knowledge=set(state.knowledge),
    )

    abstract_load: list[PhysicalItem] = []
    if state.carried_mass_kg > 0 or state.carried_volume_l > 0:
        abstract_load.append(
            PhysicalItem(
                item_id=f"abstract-load:{state.actor_id}",
                name="Abstracted carried load",
                mass_kg=state.carried_mass_kg,
                volume_l=state.carried_volume_l,
                accessibility_s=3.0,
            )
        )
    loadout = Loadout(
        body_mass_kg=state.body_mass_kg,
        comfortable_load_ratio=state.comfortable_load_ratio,
        carried_loose=abstract_load,
    )
    spatial = SpatialEntity(
        entity_id=state.actor_id,
        name=state.name,
        position=state.position,
        facing=state.facing,
        velocity=state.velocity,
        bounds=deepcopy(state.bounds),
        mass_kg=state.spatial_mass_kg,
        visible=state.visible,
        tags=state.tags,
    )
    return WorldActor(
        spatial=spatial,
        mind=mind,
        physiology=deepcopy(state.physiology),
        loadout=loadout,
        vision=deepcopy(state.vision),
        movement_speed_mps=state.movement_speed_mps,
    )


@dataclass(slots=True)
class ActorLODManager:
    detailed: dict[str, WorldActor] = field(default_factory=dict)
    abstract: dict[str, AbstractActorState] = field(default_factory=dict)
    tiers: dict[str, SimulationLOD] = field(default_factory=dict)

    def register(
        self,
        actor: WorldActor,
        *,
        tier: SimulationLOD = SimulationLOD.LOCAL,
        now: float = 0.0,
    ) -> None:
        if actor.actor_id in self.tiers:
            raise ValueError(f"actor already registered: {actor.actor_id}")
        self.tiers[actor.actor_id] = tier
        if tier <= SimulationLOD.LOCAL:
            self.detailed[actor.actor_id] = actor
        else:
            self.abstract[actor.actor_id] = abstract_actor(
                actor,
                tier=tier,
                now=now,
            )

    def transition(
        self,
        actor_id: str,
        target_tier: SimulationLOD,
        *,
        now: float,
    ) -> WorldActor | AbstractActorState:
        if actor_id not in self.tiers:
            raise KeyError(actor_id)
        current = self.tiers[actor_id]

        if current <= SimulationLOD.LOCAL and target_tier >= SimulationLOD.SETTLEMENT:
            actor = self.detailed.pop(actor_id)
            state = abstract_actor(actor, tier=target_tier, now=now)
            self.abstract[actor_id] = state
            self.tiers[actor_id] = target_tier
            return state

        if current >= SimulationLOD.SETTLEMENT and target_tier <= SimulationLOD.LOCAL:
            state = self.abstract.pop(actor_id)
            actor = restore_actor(state)
            self.detailed[actor_id] = actor
            self.tiers[actor_id] = target_tier
            return actor

        self.tiers[actor_id] = target_tier
        if actor_id in self.abstract:
            self.abstract[actor_id].tier = target_tier
            return self.abstract[actor_id]
        return self.detailed[actor_id]

    def tier_of(self, actor_id: str) -> SimulationLOD:
        try:
            return self.tiers[actor_id]
        except KeyError as exc:
            raise KeyError(actor_id) from exc

    def is_detailed(self, actor_id: str) -> bool:
        return actor_id in self.detailed
