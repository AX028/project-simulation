# Migration from the prototype

The v1 package preserves the prototype's concepts while replacing its deleted package imports,
conflicting constructors, import-time demonstrations, and visual/ML dependencies.

| Prototype area | v1 replacement |
| --- | --- |
| `character.py`, `barbarian.py`, `rogue.py`, `wizard.py` | Typed actors and six class definitions in `models.py` and `content.py` |
| `enemies.py`, `enemy_ai.py`, `DQN.py`, `NLU.py` | Twelve enemy definitions and deterministic `UtilityDecisionPolicy` |
| `body_parts.py`, `take_damage.py`, `execute_attack.py` | `BodyPartState` and `CombatEngine` |
| Armor, inventory, and status modules | Typed `Item`, `Weapon`, `Armor`, and `StatusEffect` models |
| `map_generation.py`, `chunkloading.py` | Headless NumPy generation and versioned HDF5 `WorldStore` |
| `map_frontend.py`, `physics.py` | Intentionally omitted from the headless v1 scope |
| Root-level demos | `python -m project_simulation` subcommands and automated tests |

Imports should now come from `project_simulation`; the deleted underscore-prefixed packages and
flat root modules are not compatibility shims. PR #2's useful chunk reconstruction idea is covered
by `WorldStore.read` and its round-trip tests.

