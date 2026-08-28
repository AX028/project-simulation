# Project Simulation

Project Simulation is a deterministic, headless fantasy RPG framework. It combines procedural
world layers, body-part combat, equipment, status effects, progression, and explainable utility
decisions in a small Python package and command-line experience.

> The source is publicly viewable. No license has been granted yet.

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
.venv/Scripts/activate
python -m pip install -e ".[dev]"
python -m project_simulation classes
python -m project_simulation play --class ranger --enemy necromancer --level 3 --seed 42 --save campaign.json --world world.h5
python -m project_simulation inspect campaign.json
python -m project_simulation replay campaign.json --enemy necromancer
```

The same seed and inputs produce the same world and encounter. No graphics, assets, GPU, or
machine-learning runtime is required.

## Framework API

```python
from project_simulation import (
    EncounterState,
    UtilityDecisionPolicy,
    WorldConfig,
    WorldStore,
    create_character,
    create_enemy,
    generate_world,
    run_encounter,
)

hero = create_character("paladin", "Aster", seed=7)
enemy = create_enemy("wraith", level=3, seed=8)
state = EncounterState({hero.actor_id: hero, enemy.actor_id: enemy})
result = run_encounter(state, UtilityDecisionPolicy(), seed=7)

world = generate_world(WorldConfig(width=128, height=128, chunk_size=16), seed=7)
WorldStore.write(world, "world.h5")
```

Stable factories and services are exported from `project_simulation`. Extension points include
`DecisionPolicy.choose_action`, `CombatEngine.resolve_turn`, and `WorldStore.read/write`.

## Content

Playable classes: Barbarian, Rogue, Wizard, Ranger, Cleric, and Paladin.

Enemies: Slime, Goblin, Skeleton, Forest Sprout, Wolf, Bandit, Orc Brute, Cultist Mage, Ogre,
Wraith, Necromancer, and Ancient Dragon.

Every combatant has an archetype and at least one unique ability. The built-in utility policy
chooses between engage, defend, recover, flee, and desperate modes using health, resources,
cooldowns, statuses, target condition, archetype weights, and decaying action memory.

## Development

```bash
pytest
ruff check .
mypy src/project_simulation
```

The JSON campaign and HDF5 world formats both carry schema versions. Incompatible or damaged
files fail with an explicit domain error instead of silently producing partial state.

See [MIGRATION.md](MIGRATION.md) for the legacy prototype mapping and [CONTRIBUTING.md](CONTRIBUTING.md)
for contribution expectations.
