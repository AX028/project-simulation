# Project Simulation / WORLDSTATE

Project Simulation is a deterministic, headless RPG simulation framework. The
`worldstate-simulation` branch extends the original combat/world package into a text-first,
physically represented 3D RPG prototype: the engine stores real positions, dimensions, movement,
perception, injuries, NPC knowledge, economy, world events, and persistent consequences, while
rendering the result through text instead of graphics.

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

## WORLDSTATE systems

The current branch includes:

- true XYZ spatial entities with dimensions, facing, velocity, visibility, elevation, and LOS;
- swept movement collision, solid cover, doors, passage clearance, and oversized-actor rejection;
- deterministic projectile trajectories with gravity, drag, lifetime, anti-tunneling sweeps, and
  anatomical ranged impacts;
- body-part combat, armor durability, blood loss, pain, fatigue, hydration, temperature, and
  location-specific injuries;
- physical inventory based on mass, volume, containers, accessibility, and encumbrance;
- openable scene containers with capacity-constrained take/put interactions;
- NPC beliefs separated from objective truth, selective memories, multidimensional relationships,
  utility decisions, GOAP planning, routines, and ambient world movement;
- delayed rumor propagation and belief-grounded dialogue;
- sound propagation with distance attenuation, occlusion loss, hearing thresholds, direction, and
  hearing-derived memories;
- settlements, production, prices, trade, labor, migration, factions, treaties, betrayal memory,
  and event-driven macro simulation;
- five simulation LOD tiers with actor compression/restoration;
- versioned world-state and scheduled-event persistence;
- a playable deterministic text-world session with LOOK, MOVE, INSPECT, TALK, TAKE, PUT, DROP,
  WAIT, ATTACK, SHOOT, OPEN, CLOSE, inventory/status/map commands, and event-sourced replay saves.

See [WORLDSTATE_PLAN.md](WORLDSTATE_PLAN.md) for implementation status and next work.

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

Stable factories and services are exported from `project_simulation`. WORLDSTATE systems are
also exported from the package root so focused simulations can be composed without depending on
the demo session.

## Content

Playable classes: Barbarian, Rogue, Wizard, Ranger, Cleric, and Paladin.

Enemies: Slime, Goblin, Skeleton, Forest Sprout, Wolf, Bandit, Orc Brute, Cultist Mage, Ogre,
Wraith, Necromancer, and Ancient Dragon.

Every combatant has an archetype and at least one unique ability. The built-in utility policy
chooses between engage, defend, recover, flee, and desperate modes using health, resources,
cooldowns, statuses, target condition, archetype weights, and decaying action memory.

## Quality gate

CI runs on Python 3.11 and 3.12. Each quality process is repeated three times:

```bash
python scripts/validate.py --repetitions 3
```

The validator runs pytest, Ruff, and strict mypy. A gate scores 10/10 only when all three
repetitions pass; any failed repetition scores 0/10 and fails CI.

## Persistence

The project currently has several intentionally versioned persistence layers:

- JSON campaign saves;
- HDF5 generated worlds;
- WORLDSTATE macro-state JSON;
- scheduled-event queue JSON;
- deterministic text-world replay saves with state digests.

Incompatible or malformed files raise explicit domain errors rather than silently producing
partial state.

See [MIGRATION.md](MIGRATION.md) for the original prototype mapping and
[CONTRIBUTING.md](CONTRIBUTING.md) for contribution expectations.
