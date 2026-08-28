"""Deterministic utility-based decisions with explicit combat modes."""

from __future__ import annotations

import random

from .models import ActionSpec, CombatMode, CombatSnapshot


class UtilityDecisionPolicy:
    """Score legal actions using transparent, inspectable combat signals."""

    ARCHETYPE_BONUSES = {
        "aggressive": {"attack": 0.25, "desperate": 0.25},
        "cunning": {"execute": 0.25, "flee": 0.15},
        "caster": {"status": 0.25, "recover": 0.1},
        "guardian": {"defend": 0.3},
        "support": {"recover": 0.35, "defend": 0.15},
        "ranged": {"ranged": 0.25},
        "brute": {"attack": 0.35},
        "controller": {"status": 0.3},
        "swarm": {"multi_hit": 0.3},
        "boss": {"attack": 0.2, "defend": 0.15, "desperate": 0.2},
    }

    def classify_mode(self, snapshot: CombatSnapshot) -> CombatMode:
        actor = snapshot.actor
        if actor.hp_ratio <= 0.16:
            return CombatMode.DESPERATE
        if actor.hp_ratio <= 0.28 and actor.archetype in {"cunning", "support"}:
            return CombatMode.FLEE
        if actor.hp_ratio <= 0.42:
            return CombatMode.RECOVER
        if snapshot.target.hp_ratio > actor.hp_ratio + 0.3:
            return CombatMode.DEFEND
        return CombatMode.ENGAGE

    def choose_action(
        self, snapshot: CombatSnapshot, legal_actions: list[ActionSpec], rng: random.Random
    ) -> ActionSpec:
        if not legal_actions:
            raise ValueError("legal_actions may not be empty")
        mode = self.classify_mode(snapshot)
        scored = [
            (self.score(action, snapshot, mode), rng.random(), action) for action in legal_actions
        ]
        return max(scored, key=lambda item: (item[0], item[1]))[2]

    def score(self, action: ActionSpec, snapshot: CombatSnapshot, mode: CombatMode) -> float:
        actor = snapshot.actor
        target = snapshot.target
        tags = set(action.tags)
        if action.damage > 0:
            tags.add("attack")
        if action.status_id:
            tags.add("status")
        score = action.damage / 20 + action.heal / 18 + action.accuracy * 0.15
        score += sum(self.ARCHETYPE_BONUSES.get(actor.archetype, {}).get(tag, 0.0) for tag in tags)
        if mode is CombatMode.ENGAGE:
            score += 0.35 if "attack" in tags else 0.0
        elif mode is CombatMode.DEFEND:
            score += 0.7 if "defend" in tags else 0.0
        elif mode is CombatMode.RECOVER:
            score += 0.9 if action.heal or "recover" in tags else 0.0
        elif mode is CombatMode.FLEE:
            score += 1.1 if "flee" in tags else 0.0
        elif mode is CombatMode.DESPERATE:
            score += 0.6 if "desperate" in tags or "execute" in tags else 0.0
        score += (1.0 - target.hp_ratio) * (0.35 if "execute" in tags else 0.12)
        score += (1.0 - actor.hp_ratio) * (0.4 if action.heal else 0.0)
        score -= action.cost / 150
        score -= snapshot.event_memory.get(f"used:{action.action_id}", 0.0) * 0.15
        if action.status_id and any(
            effect.effect_id == action.status_id for effect in target.statuses
        ):
            score -= 0.35
        return score
