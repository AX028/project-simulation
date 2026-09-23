"""Integrated actor layer tying space, cognition, physiology, and movement together."""

from __future__ import annotations

from dataclasses import dataclass, field

from .cognition import Memory, Mind
from .physiology import Loadout, Physiology
from .skills import SkillSet
from .spatial import Observation, SpatialEntity, Vec3, VisionProfile, observe


@dataclass(slots=True)
class WorldActor:
    spatial: SpatialEntity
    mind: Mind
    physiology: Physiology
    loadout: Loadout
    vision: VisionProfile = field(default_factory=VisionProfile)
    movement_speed_mps: float = 1.4
    skills: SkillSet = field(default_factory=SkillSet)

    @property
    def actor_id(self) -> str:
        return self.spatial.entity_id

    def perceive(
        self,
        entities: list[SpatialEntity],
        *,
        illumination: float = 1.0,
        contrast: float = 1.0,
    ) -> list[Observation]:
        observations: list[Observation] = []
        for entity in entities:
            if entity.entity_id == self.actor_id:
                continue
            result = observe(
                self.spatial,
                entity,
                self.vision,
                illumination=illumination,
                contrast=contrast,
                obstacles=entities,
            )
            if result is not None:
                observations.append(result)
        observations.sort(key=lambda item: item.distance_m)
        return observations

    def encode_observation_as_memory(
        self,
        observation: Observation,
        *,
        now: float,
        importance: float = 0.4,
        emotional_intensity: float = 0.2,
    ) -> Memory:
        memory = Memory(
            subject=observation.target_id,
            proposition=observation.description,
            importance=importance,
            emotional_intensity=emotional_intensity,
            confidence=max(0.05, observation.clarity),
            accuracy=max(0.05, observation.clarity),
            source="direct_observation",
            created_at=now,
            tags=frozenset({"visual", observation.bearing.lower()}),
        )
        self.mind.remember(memory)
        return memory

    def effective_speed(self) -> float:
        encumbrance = self.loadout.fatigue_multiplier
        physical = self.physiology.performance_modifier
        return max(0.1, self.movement_speed_mps * physical / encumbrance)

    def move_toward(
        self,
        destination: Vec3,
        seconds: float,
        *,
        exertion: float = 0.35,
        ambient_c: float = 20.0,
        speed_multiplier: float = 1.0,
    ) -> float:
        seconds = max(0.0, seconds)
        speed_multiplier = max(0.0, speed_multiplier)
        distance_budget = self.effective_speed() * speed_multiplier * seconds
        delta = destination - self.spatial.position
        actual_distance = min(distance_budget, delta.magnitude)
        if actual_distance > 0:
            self.spatial.position = (
                self.spatial.position + delta.normalized().scale(actual_distance)
            )
        self.physiology.tick(
            seconds / 60.0,
            exertion=exertion,
            ambient_c=ambient_c,
        )
        return actual_distance
