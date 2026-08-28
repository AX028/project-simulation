"""Built-in playable classes, enemies, and starter equipment."""

from __future__ import annotations

import random
from dataclasses import replace

from .models import (
    ActionSpec,
    Armor,
    BodyPart,
    BodyPartState,
    ContentNotFoundError,
    DamageType,
    Enemy,
    PlayerCharacter,
    Rarity,
    ResourcePool,
    Stats,
    TargetType,
    Weapon,
)


def _body(vitality: int) -> dict[str, BodyPartState]:
    base = max(8, vitality * 2)
    definitions = {
        BodyPart.HEAD: (0.55, 1.5, "head"),
        BodyPart.TORSO: (1.5, 1.0, "torso"),
        BodyPart.LEFT_ARM: (0.75, 0.9, "arms"),
        BodyPart.RIGHT_ARM: (0.75, 0.9, "arms"),
        BodyPart.LEFT_LEG: (0.9, 0.8, "legs"),
        BodyPart.RIGHT_LEG: (0.9, 0.8, "legs"),
    }
    return {
        part: BodyPartState(part, max(1, int(base * hp)), max(1, int(base * hp)), mult, slot)
        for part, (hp, mult, slot) in definitions.items()
    }


CLASS_DEFINITIONS: dict[str, tuple[Stats, tuple[ActionSpec, ...], str]] = {
    "barbarian": (
        Stats(16, 9, 6, 16, 2, 0.78, 0.03, 0.08),
        (
            ActionSpec(
                "rage",
                "Rage strike",
                9,
                cost=20,
                resource="stamina",
                cooldown=2,
                status_id="rage",
                status_duration=2,
                tags=("desperate", "self_status"),
            ),
            ActionSpec(
                "frenzy",
                "Frenzy",
                6,
                accuracy=0.82,
                cost=28,
                resource="stamina",
                cooldown=3,
                tags=("multi_hit",),
            ),
        ),
        "aggressive",
    ),
    "rogue": (
        Stats(10, 17, 9, 10, 1, 0.9, 0.14, 0.2),
        (
            ActionSpec(
                "vanish",
                "Vanish",
                target=TargetType.SELF,
                cost=18,
                resource="stamina",
                cooldown=3,
                status_id="stealth",
                status_duration=2,
                tags=("defend",),
            ),
            ActionSpec(
                "backstab",
                "Backstab",
                11,
                accuracy=0.88,
                cost=22,
                resource="stamina",
                cooldown=2,
                tags=("execute",),
            ),
        ),
        "cunning",
    ),
    "wizard": (
        Stats(6, 9, 18, 9, 0, 0.82, 0.05, 0.08),
        (
            ActionSpec(
                "firebolt",
                "Firebolt",
                10,
                DamageType.FIRE,
                cost=18,
                resource="mana",
                cooldown=1,
                status_id="burn",
                status_duration=2,
            ),
            ActionSpec(
                "arcane_shield",
                "Arcane shield",
                target=TargetType.SELF,
                cost=22,
                resource="mana",
                cooldown=3,
                status_id="shield",
                status_duration=2,
                status_potency=5,
                tags=("defend",),
            ),
        ),
        "caster",
    ),
    "ranger": (
        Stats(10, 16, 10, 11, 1, 0.91, 0.1, 0.14),
        (
            ActionSpec(
                "mark",
                "Hunter's mark",
                2,
                cost=12,
                resource="stamina",
                cooldown=2,
                status_id="marked",
                status_duration=3,
                status_potency=0.25,
            ),
            ActionSpec(
                "volley",
                "Volley",
                8,
                accuracy=0.86,
                cost=24,
                resource="stamina",
                cooldown=2,
                tags=("ranged",),
            ),
        ),
        "ranged",
    ),
    "cleric": (
        Stats(9, 8, 15, 13, 3, 0.82, 0.04, 0.06),
        (
            ActionSpec(
                "mend",
                "Mend",
                target=TargetType.SELF,
                cost=18,
                resource="mana",
                cooldown=2,
                heal=13,
                tags=("recover",),
            ),
            ActionSpec(
                "purify",
                "Purify",
                7,
                DamageType.HOLY,
                cost=17,
                resource="mana",
                cooldown=1,
                tags=("cleanse",),
            ),
        ),
        "support",
    ),
    "paladin": (
        Stats(14, 7, 11, 15, 5, 0.8, 0.02, 0.08),
        (
            ActionSpec(
                "guard",
                "Sacred guard",
                target=TargetType.SELF,
                cost=16,
                resource="mana",
                cooldown=2,
                status_id="guarded",
                status_duration=2,
                status_potency=4,
                tags=("defend",),
            ),
            ActionSpec(
                "smite",
                "Smite",
                10,
                DamageType.HOLY,
                cost=20,
                resource="mana",
                cooldown=2,
                tags=("execute",),
            ),
        ),
        "guardian",
    ),
}


ENEMY_DEFINITIONS: dict[str, tuple[str, int, Stats, tuple[ActionSpec, ...], str]] = {
    "slime": (
        "early",
        10,
        Stats(8, 5, 3, 13, 0, 0.72),
        (
            ActionSpec(
                "split",
                "Split assault",
                5,
                cooldown=2,
                status_id="slowed",
                status_duration=1,
                tags=("multi_hit",),
            ),
        ),
        "swarm",
    ),
    "goblin": (
        "early",
        12,
        Stats(8, 14, 7, 8, 1, 0.86, 0.12, 0.12),
        (
            ActionSpec(
                "dirty_trick", "Dirty trick", 5, cooldown=2, status_id="blinded", status_duration=1
            ),
        ),
        "cunning",
    ),
    "skeleton": (
        "early",
        13,
        Stats(11, 8, 4, 11, 3, 0.77),
        (
            ActionSpec(
                "bone_reform",
                "Bone reform",
                target=TargetType.SELF,
                cooldown=4,
                heal=9,
                tags=("recover",),
            ),
        ),
        "guardian",
    ),
    "forest_sprout": (
        "early",
        14,
        Stats(8, 8, 12, 12, 1, 0.8),
        (
            ActionSpec(
                "root_drain",
                "Root drain",
                6,
                DamageType.POISON,
                cooldown=2,
                status_id="rooted",
                status_duration=2,
                heal=3,
            ),
        ),
        "controller",
    ),
    "wolf": (
        "mid",
        18,
        Stats(12, 15, 5, 11, 1, 0.88, 0.1, 0.12),
        (
            ActionSpec(
                "pack_bite", "Pack bite", 8, cooldown=2, status_id="bleed", status_duration=3
            ),
        ),
        "aggressive",
    ),
    "bandit": (
        "mid",
        20,
        Stats(12, 14, 8, 12, 2, 0.86, 0.09, 0.14),
        (
            ActionSpec(
                "pilfer",
                "Pilfering cut",
                7,
                cooldown=2,
                status_id="weakened",
                status_duration=2,
                tags=("flee",),
            ),
        ),
        "cunning",
    ),
    "orc_brute": (
        "mid",
        24,
        Stats(18, 7, 5, 18, 4, 0.72, 0.02, 0.12),
        (
            ActionSpec(
                "enrage",
                "Enraged smash",
                13,
                accuracy=0.72,
                cooldown=3,
                status_id="rage",
                status_duration=2,
                tags=("desperate", "self_status"),
            ),
        ),
        "aggressive",
    ),
    "cultist_mage": (
        "mid",
        25,
        Stats(6, 9, 17, 10, 1, 0.84, 0.04, 0.08),
        (
            ActionSpec(
                "hex",
                "Withering hex",
                9,
                DamageType.ARCANE,
                cooldown=2,
                status_id="weakened",
                status_duration=3,
            ),
        ),
        "caster",
    ),
    "ogre": (
        "elite",
        35,
        Stats(20, 5, 5, 22, 5, 0.68, 0.0, 0.1),
        (
            ActionSpec(
                "ground_slam",
                "Ground slam",
                15,
                accuracy=0.7,
                cooldown=3,
                status_id="stunned",
                status_duration=1,
            ),
        ),
        "brute",
    ),
    "wraith": (
        "elite",
        38,
        Stats(7, 15, 17, 12, 0, 0.88, 0.18, 0.1),
        (
            ActionSpec(
                "phase_drain",
                "Phase drain",
                12,
                DamageType.ARCANE,
                cooldown=2,
                heal=5,
                status_id="weakened",
                status_duration=2,
            ),
        ),
        "cunning",
    ),
    "necromancer": (
        "elite",
        45,
        Stats(7, 9, 20, 14, 2, 0.83, 0.03, 0.09),
        (
            ActionSpec(
                "raise_dead",
                "Raise dead",
                target=TargetType.SELF,
                cooldown=4,
                heal=16,
                status_id="shield",
                status_duration=2,
                status_potency=3,
                tags=("recover",),
            ),
            ActionSpec(
                "death_bolt",
                "Death bolt",
                14,
                DamageType.ARCANE,
                cooldown=2,
                status_id="poison",
                status_duration=2,
            ),
        ),
        "caster",
    ),
    "ancient_dragon": (
        "boss",
        100,
        Stats(24, 12, 19, 28, 8, 0.84, 0.06, 0.16),
        (
            ActionSpec(
                "dragonfire",
                "Dragonfire",
                19,
                DamageType.FIRE,
                cooldown=3,
                status_id="burn",
                status_duration=3,
                tags=("desperate",),
            ),
            ActionSpec(
                "wing_guard",
                "Wing guard",
                target=TargetType.SELF,
                cooldown=3,
                status_id="guarded",
                status_duration=2,
                status_potency=6,
                tags=("defend",),
            ),
        ),
        "boss",
    ),
}


def create_character(class_id: str, name: str, seed: int | None = None) -> PlayerCharacter:
    key = class_id.strip().lower().replace(" ", "_")
    if key not in CLASS_DEFINITIONS:
        raise ContentNotFoundError(
            f"unknown class '{class_id}'; choose: {', '.join(CLASS_DEFINITIONS)}"
        )
    stats, abilities, archetype = CLASS_DEFINITIONS[key]
    rng = random.Random(seed)
    weapon = Weapon(
        f"{key}_weapon",
        f"{key.title()} weapon",
        damage=5 + stats.strength // 4,
        accuracy_bonus=(rng.random() - 0.5) * 0.02,
    )
    armor = Armor("traveler_tunic", "Traveler tunic", protection=2, material="leather")
    return PlayerCharacter(
        actor_id="player",
        name=name.strip() or "Adventurer",
        level=1,
        stats=replace(stats),
        body_parts=_body(stats.vitality),
        resources={"stamina": ResourcePool(100, 100), "mana": ResourcePool(80, 80)},
        abilities=abilities,
        equipment={"weapon": weapon, "torso": armor},
        inventory=[Weapon("iron_sword", "Iron sword", Rarity.UNCOMMON, damage=8)],
        archetype=archetype,
        class_id=key,
    )


def create_enemy(enemy_id: str, level: int, seed: int | None = None) -> Enemy:
    key = enemy_id.strip().lower().replace(" ", "_")
    if key not in ENEMY_DEFINITIONS:
        raise ContentNotFoundError(
            f"unknown enemy '{enemy_id}'; choose: {', '.join(ENEMY_DEFINITIONS)}"
        )
    if level < 1 or level > 99:
        raise ValueError("enemy level must be between 1 and 99")
    tier, reward, base_stats, abilities, archetype = ENEMY_DEFINITIONS[key]
    scale = level - 1
    stats = replace(
        base_stats,
        strength=base_stats.strength + scale,
        vitality=base_stats.vitality + scale,
        intellect=base_stats.intellect + scale // 2,
        armor=base_stats.armor + scale // 3,
    )
    rng = random.Random(seed)
    weapon = Weapon(
        f"{key}_natural_weapon",
        f"{key.replace('_', ' ').title()} attack",
        damage=4 + stats.strength // 4,
        accuracy_bonus=(rng.random() - 0.5) * 0.02,
    )
    return Enemy(
        actor_id=f"enemy:{key}",
        name=key.replace("_", " ").title(),
        level=level,
        stats=stats,
        body_parts=_body(stats.vitality),
        resources={"stamina": ResourcePool(100, 100), "mana": ResourcePool(100, 100)},
        abilities=abilities,
        equipment={"weapon": weapon},
        archetype=archetype,
        enemy_id=key,
        experience_reward=reward * level,
        tier=tier,
    )
