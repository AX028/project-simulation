"""Turn-based combat resolution."""

from __future__ import annotations

import random
from collections.abc import Iterable

from .models import (
    Action,
    ActionSpec,
    Actor,
    Armor,
    BodyPart,
    CombatSnapshot,
    EncounterResult,
    EncounterState,
    IllegalActionError,
    StatusEffect,
    TurnResult,
)


class CombatEngine:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def legal_actions(self, actor: Actor) -> list[ActionSpec]:
        if not actor.alive or self._has_status(actor, "stunned"):
            return []
        actions = [
            actor.get_action("basic_attack"),
            actor.get_action("defend"),
            actor.get_action("recover"),
        ]
        if actor.hp_ratio < 0.3 and not self._has_status(actor, "rooted"):
            actions.append(actor.get_action("flee"))
        for ability in actor.abilities:
            pool = actor.resources.get(ability.resource) if ability.resource else None
            if actor.cooldowns.get(ability.action_id, 0) == 0 and (
                pool is None or pool.current >= ability.cost
            ):
                actions.append(ability)
        return actions

    def resolve_turn(self, state: EncounterState, intents: Iterable[Action]) -> TurnResult:
        if state.winner_id:
            raise IllegalActionError("encounter has already ended")
        state.round_number += 1
        events: list[str] = []
        self._tick_start(state.actors.values(), events)
        ordered = sorted(
            intents,
            key=lambda action: state.actors[action.actor_id].stats.agility + self.rng.random(),
            reverse=True,
        )
        fled_id: str | None = None
        for intent in ordered:
            actor = state.actors.get(intent.actor_id)
            target = state.actors.get(intent.target_id)
            if actor is None or target is None:
                raise IllegalActionError("action references an unknown actor")
            if not actor.alive or not target.alive or self._has_status(actor, "stunned"):
                continue
            spec = actor.get_action(intent.action_id)
            legal_ids = {candidate.action_id for candidate in self.legal_actions(actor)}
            if spec.action_id not in legal_ids:
                raise IllegalActionError(
                    f"{spec.action_id} is not currently legal for {actor.name}"
                )
            if spec.resource:
                actor.resources[spec.resource].spend(spec.cost)
            if spec.cooldown:
                actor.cooldowns[spec.action_id] = spec.cooldown + 1
            if spec.action_id == "flee":
                chance = min(0.9, 0.35 + actor.stats.agility / 50 - target.stats.agility / 100)
                if self.rng.random() < chance:
                    fled_id = actor.actor_id
                    events.append(f"{actor.name} fled the encounter.")
                    break
                events.append(f"{actor.name} failed to flee.")
                continue
            actual_target = (
                actor if spec.target.value == "self" or "self_status" in spec.tags else target
            )
            if spec.action_id == "defend":
                self._apply_status(
                    actor,
                    ActionSpec(
                        "guarded",
                        "Guarded",
                        status_id="guarded",
                        status_duration=1,
                        status_potency=3,
                    ),
                    actor.actor_id,
                )
            if spec.action_id == "recover":
                stamina = actor.resources["stamina"].restore(20)
                mana = actor.resources["mana"].restore(12)
                events.append(f"{actor.name} recovered {stamina} stamina and {mana} mana.")
                continue
            if "cleanse" in spec.tags:
                negative = {"bleed", "burn", "poison", "rooted", "weakened", "blinded", "stunned"}
                actor.statuses = [
                    effect for effect in actor.statuses if effect.effect_id not in negative
                ]
            if spec.heal:
                healed = self._heal(actor, spec.heal + actor.stats.intellect // 4)
                events.append(f"{actor.name} used {spec.name} and restored {healed} health.")
            if spec.damage:
                hits = 2 if "multi_hit" in spec.tags else 1
                for _ in range(hits):
                    if target.alive:
                        events.append(self._attack(actor, target, spec, intent.body_part))
            elif not spec.heal:
                events.append(f"{actor.name} used {spec.name}.")
            if spec.status_id and actual_target.alive:
                self._apply_status(actual_target, spec, actor.actor_id)
                events.append(f"{actual_target.name} gained {spec.status_id}.")
            if not target.alive:
                state.winner_id = actor.actor_id
                events.append(f"{target.name} was defeated.")
                break
        self._tick_end(state.actors.values(), events)
        state.log.extend(events)
        return TurnResult(state.round_number, events, state.winner_id, fled_id)

    def _attack(
        self, attacker: Actor, target: Actor, spec: ActionSpec, selected: BodyPart | None
    ) -> str:
        hit_chance = max(
            0.1, min(0.98, attacker.stats.accuracy * spec.accuracy - target.stats.evasion)
        )
        if self._has_status(attacker, "blinded"):
            hit_chance -= 0.2
        if self._has_status(attacker, "stealth"):
            hit_chance += 0.15
        if self.rng.random() > hit_chance:
            return f"{attacker.name}'s {spec.name} missed {target.name}."
        part = selected or self._weighted_part(target)
        base = spec.damage + attacker.stats.strength // 4
        if self._has_status(attacker, "rage"):
            base = int(base * 1.25)
        if self._has_status(attacker, "weakened"):
            base = int(base * 0.8)
        if spec.damage_type.value in {"arcane", "fire", "frost", "holy"}:
            base += attacker.stats.intellect // 5
        critical = self.rng.random() < attacker.stats.crit_chance + (
            0.2 if self._has_status(attacker, "stealth") else 0
        )
        if critical:
            base = int(base * 1.6)
        body = target.body_parts[part]
        protection = target.stats.armor
        armor_item = target.equipment.get(body.armor_slot)
        if isinstance(armor_item, Armor) and armor_item.durability > 0:
            protection += armor_item.protection
            armor_item.durability = max(0, armor_item.durability - 1)
        protection += int(
            self._status_potency(target, "shield") + self._status_potency(target, "guarded")
        )
        if self._has_status(target, "marked"):
            base = int(base * (1 + self._status_potency(target, "marked")))
        damage = max(1, int(base * body.damage_multiplier) - protection)
        body.current_hp = max(0, body.current_hp - damage)
        suffix = " (critical)" if critical else ""
        return (
            f"{attacker.name}'s {spec.name} hit {target.name}'s {part.value} for {damage}{suffix}."
        )

    def _weighted_part(self, actor: Actor) -> BodyPart:
        candidates = [part.part for part in actor.body_parts.values() if part.current_hp > 0]
        return self.rng.choices(
            candidates, weights=[2 if p is BodyPart.TORSO else 1 for p in candidates], k=1
        )[0]

    def _heal(self, actor: Actor, amount: int) -> int:
        wounded = sorted(actor.body_parts.values(), key=lambda part: part.ratio)
        remaining = amount
        healed = 0
        for part in wounded:
            gain = min(remaining, part.max_hp - part.current_hp)
            part.current_hp += gain
            healed += gain
            remaining -= gain
            if remaining <= 0:
                break
        return healed

    def _apply_status(self, actor: Actor, spec: ActionSpec, source_id: str) -> None:
        existing = next(
            (effect for effect in actor.statuses if effect.effect_id == spec.status_id), None
        )
        if existing:
            existing.duration = max(existing.duration, spec.status_duration)
            existing.potency = max(existing.potency, spec.status_potency)
        else:
            actor.statuses.append(
                StatusEffect(
                    spec.status_id or "", spec.status_duration, spec.status_potency, source_id
                )
            )

    def _tick_start(self, actors: Iterable[Actor], events: list[str]) -> None:
        for actor in actors:
            if not actor.alive:
                continue
            for effect in actor.statuses:
                if effect.effect_id in {"bleed", "burn", "poison"}:
                    damage = max(1, int(effect.potency * 2))
                    torso = actor.body_parts[BodyPart.TORSO]
                    torso.current_hp = max(0, torso.current_hp - damage)
                    events.append(f"{actor.name} took {damage} {effect.effect_id} damage.")

    def _tick_end(self, actors: Iterable[Actor], events: list[str]) -> None:
        for actor in actors:
            remaining: list[StatusEffect] = []
            for effect in actor.statuses:
                effect.duration -= 1
                if effect.duration > 0:
                    remaining.append(effect)
            actor.statuses = remaining
            actor.cooldowns = {key: max(0, value - 1) for key, value in actor.cooldowns.items()}
            actor.resources["stamina"].restore(8)
            actor.resources["mana"].restore(5)
        del events

    @staticmethod
    def _has_status(actor: Actor, effect_id: str) -> bool:
        return any(effect.effect_id == effect_id for effect in actor.statuses)

    @staticmethod
    def _status_potency(actor: Actor, effect_id: str) -> float:
        return max(
            (effect.potency for effect in actor.statuses if effect.effect_id == effect_id),
            default=0.0,
        )


def run_encounter(
    state: EncounterState, policy: object, seed: int | None = None, max_rounds: int = 100
) -> EncounterResult:
    rng = random.Random(seed)
    engine = CombatEngine(rng)
    while state.winner_id is None and state.round_number < max_rounds:
        living = [actor for actor in state.actors.values() if actor.alive]
        if len(living) < 2:
            state.winner_id = living[0].actor_id if living else None
            break
        intents: list[Action] = []
        for actor in living:
            target = next(other for other in living if other.actor_id != actor.actor_id)
            legal = engine.legal_actions(actor)
            if not legal:
                continue
            memory = state.event_memory.setdefault(actor.actor_id, {})
            snapshot = CombatSnapshot(actor, target, state.round_number, memory)
            chosen = policy.choose_action(snapshot, legal, rng)  # type: ignore[attr-defined]
            intents.append(Action(actor.actor_id, chosen.action_id, target.actor_id))
            for key in list(memory):
                memory[key] *= 0.72
                if memory[key] < 0.01:
                    del memory[key]
            memory[f"used:{chosen.action_id}"] = memory.get(f"used:{chosen.action_id}", 0.0) + 1
        result = engine.resolve_turn(state, intents)
        if result.fled_id:
            opponents = [actor.actor_id for actor in living if actor.actor_id != result.fled_id]
            state.winner_id = opponents[0] if opponents else None
    if state.winner_id is None:
        living = sorted(
            (actor for actor in state.actors.values() if actor.alive),
            key=lambda actor: actor.hp_ratio,
            reverse=True,
        )
        state.winner_id = living[0].actor_id if living else None
        state.log.append(
            "The encounter reached its round limit and was decided by remaining health."
        )
    return EncounterResult(state.winner_id, state.round_number, list(state.log), state)
