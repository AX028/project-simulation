"""Public API for Project Simulation."""

from .api import (
    CLASS_DEFINITIONS,
    ENEMY_DEFINITIONS,
    CombatEngine,
    UtilityDecisionPolicy,
    WorldStore,
    create_character,
    create_enemy,
    generate_world,
    load_game,
    run_encounter,
    save_game,
)
from .models import (
    Action,
    Actor,
    BodyPart,
    CombatMode,
    DamageType,
    EncounterResult,
    EncounterState,
    GameState,
    PlayerCharacter,
    WorldConfig,
    WorldMap,
)

__all__ = [
    "CLASS_DEFINITIONS",
    "ENEMY_DEFINITIONS",
    "Action",
    "Actor",
    "BodyPart",
    "CombatEngine",
    "CombatMode",
    "DamageType",
    "EncounterResult",
    "EncounterState",
    "GameState",
    "PlayerCharacter",
    "UtilityDecisionPolicy",
    "WorldConfig",
    "WorldMap",
    "WorldStore",
    "create_character",
    "create_enemy",
    "generate_world",
    "load_game",
    "run_encounter",
    "save_game",
]

__version__ = "1.0.0"
