# Migration from the prototype

The v1 package preserves the prototype's concepts while replacing deleted package imports,
conflicting constructors, import-time demonstrations, and visual/ML dependencies.

| Prototype area | v1 / WORLDSTATE replacement |
| --- | --- |
| `character.py`, `barbarian.py`, `rogue.py`, `wizard.py` | Typed actors and six class definitions in `models.py` and `content.py` |
| `enemies.py`, `enemy_ai.py`, `DQN.py`, `NLU.py` | Twelve enemy definitions and deterministic `UtilityDecisionPolicy` |
| `body_parts.py`, `take_damage.py`, `execute_attack.py` | Body-part combat plus spatial/anatomical injury systems |
| Armor, inventory, and status modules | Typed items, weapons, armor, statuses, physical inventory, and encumbrance |
| `map_generation.py`, `chunkloading.py` | Headless NumPy generation and versioned HDF5 `WorldStore` |
| `map_frontend.py`, `physics.py` | Graphics remain omitted; physical behavior is now represented through `spatial.py`, `navigation.py`, `doors.py`, `projectiles.py`, and related WORLDSTATE modules |
| Root-level demos | `python -m project_simulation` subcommands, deterministic text-world sessions, and automated tests |

Imports should come from `project_simulation`; deleted underscore-prefixed packages and flat root
modules are not compatibility shims.

The WORLDSTATE branch deliberately keeps simulation headless while adding systems that would be
expensive to represent graphically: persistent NPC cognition, long-running settlements/factions,
true spatial relationships, physical information routes, injuries, projectiles, sound propagation,
and scalable levels of detail.
