"""Multi-turn encounters resolved in physical 3D space."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum

from .models import BodyPart
from .spatial import Vec3
from .spatial_combat import (
    SpatialAttackResult,
    SpatialCombatant,
    SpatialCombatResolver,
)


class SpatialAction(StrEnum):
    ADVANCE = "advance"
    RETREAT = "retreat"
    ATTACK = "attack"


@dataclass(frozen=True, slots=True)
class SpatialIntent:
    actor_id: str
    target_id: str
    action: SpatialAction
    body_part: BodyPart | None = None


@dataclass(frozen=True, slots=True)
class SpatialTurnEvent:
    actor_id: str
    target_id: str
    action: SpatialAction
    text: str
    distance_before_m: float
    distance_after_m: float
    attack: SpatialAttackResult | None = None


@dataclass(slots=True)
class SpatialEncounterState:
    combatants: dict[str, SpatialCombatant]
    round_number: int = 0
    winner_id: str | None = None
    log: list[str] = field(default_factory=list)

    @property
    def living_ids(self) -> tuple[str, ...]:
        return tuple(
            actor_id
            for actor_id, combatant in sorted(self.combatants.items())
            if combatant.actor.alive
            and combatant.world_actor.physiology.conscious
        )


@dataclass(frozen=True, slots=True)
class SpatialTurnResult:
    round_number: int
    events: tuple[SpatialTurnEvent, ...]
    winner_id: str | None


class SpatialEncounterEngine:
    """Resolve movement and attacks while preserving spatial consequences."""

    def __init__(
        self,
        rng: random.Random,
        *,
        seconds_per_turn: float = 1.0,
        retreat_distance_m: float = 2.0,
    ) -> None:
        if seconds_per_turn <= 0:
            raise ValueError("seconds_per_turn must be positive")
        if retreat_distance_m <= 0:
            raise ValueError("retreat_distance_m must be positive")
        self.rng = rng
        self.seconds_per_turn = seconds_per_turn
        self.retreat_distance_m = retreat_distance_m
        self.attack_resolver = SpatialCombatResolver(rng)

    def resolve_turn(
        self,
        state: SpatialEncounterState,
        intents: tuple[SpatialIntent, ...],
    ) -> SpatialTurnResult:
        if state.winner_id is not None:
            raise ValueError("encounter has already ended")

        self._validate_intents(state, intents)
        state.round_number += 1
        events: list[SpatialTurnEvent] = []
        physiology_advanced: set[str] = set()

        ordered = sorted(
            intents,
            key=lambda intent: (
                state.combatants[intent.actor_id].actor.stats.agility
                + self.rng.random()
            ),
            reverse=True,
        )

        for intent in ordered:
            actor = state.combatants[intent.actor_id]
            target = state.combatants[intent.target_id]
            if not actor.actor.alive or not actor.world_actor.physiology.conscious:
                continue
            if not target.actor.alive or not target.world_actor.physiology.conscious:
                continue

            before = self._distance(actor, target)
            if intent.action is SpatialAction.ADVANCE:
                actor.world_actor.move_toward(
                    target.world_actor.spatial.position,
                    self.seconds_per_turn,
                    exertion=0.45,
                )
                physiology_advanced.add(actor.actor.actor_id)
                after = self._distance(actor, target)
                event = SpatialTurnEvent(
                    actor.actor.actor_id,
                    target.actor.actor_id,
                    intent.action,
                    (
                        f"{actor.actor.name} advances toward {target.actor.name} "
                        f"to {after:.2f} m."
                    ),
                    before,
                    after,
                )
            elif intent.action is SpatialAction.RETREAT:
                self._retreat(actor, target)
                physiology_advanced.add(actor.actor.actor_id)
                after = self._distance(actor, target)
                event = SpatialTurnEvent(
                    actor.actor.actor_id,
                    target.actor.actor_id,
                    intent.action,
                    (
                        f"{actor.actor.name} retreats from {target.actor.name} "
                        f"to {after:.2f} m."
                    ),
                    before,
                    after,
                )
            else:
                attack = self.attack_resolver.resolve_attack(
                    actor,
                    target,
                    selected_part=intent.body_part,
                )
                after = self._distance(actor, target)
                event = SpatialTurnEvent(
                    actor.actor.actor_id,
                    target.actor.actor_id,
                    intent.action,
                    attack.text,
                    before,
                    after,
                    attack,
                )

            events.append(event)
            state.log.append(event.text)
            winner = self._winner_if_resolved(state)
            if winner is not None:
                state.winner_id = winner
                break

        for actor_id, combatant in state.combatants.items():
            if actor_id not in physiology_advanced:
                combatant.world_actor.physiology.tick(
                    self.seconds_per_turn / 60.0,
                    exertion=0.18,
                )

        winner = self._winner_if_resolved(state)
        if winner is not None:
            state.winner_id = winner
        return SpatialTurnResult(
            state.round_number,
            tuple(events),
            state.winner_id,
        )

    def _retreat(
        self,
        actor: SpatialCombatant,
        target: SpatialCombatant,
    ) -> None:
        position = actor.world_actor.spatial.position
        direction = position - target.world_actor.spatial.position
        if direction.magnitude == 0:
            direction = Vec3(1.0, 0.0, 0.0)
        destination = (
            position
            + direction.normalized().scale(self.retreat_distance_m)
        )
        actor.world_actor.move_toward(
            destination,
            self.seconds_per_turn,
            exertion=0.55,
        )

    @staticmethod
    def _distance(
        actor: SpatialCombatant,
        target: SpatialCombatant,
    ) -> float:
        return actor.world_actor.spatial.position.distance_to(
            target.world_actor.spatial.position
        )

    @staticmethod
    def _validate_intents(
        state: SpatialEncounterState,
        intents: tuple[SpatialIntent, ...],
    ) -> None:
        seen: set[str] = set()
        for intent in intents:
            if intent.actor_id not in state.combatants:
                raise ValueError(f"unknown acting combatant: {intent.actor_id}")
            if intent.target_id not in state.combatants:
                raise ValueError(f"unknown target combatant: {intent.target_id}")
            if intent.actor_id == intent.target_id:
                raise ValueError("spatial intent target must differ from actor")
            if intent.actor_id in seen:
                raise ValueError("each combatant may submit only one intent per turn")
            seen.add(intent.actor_id)

    @staticmethod
    def _winner_if_resolved(state: SpatialEncounterState) -> str | None:
        living = state.living_ids
        if len(living) == 1:
            return living[0]
        return None
