# WORLDSTATE Implementation Plan

WORLDSTATE extends Project Simulation into a deterministic, deeply simulated, text-first 3D RPG
while retaining the original combat/content/world-generation APIs.

## Quality gate

Every quality process is repeated three times on Python 3.11 and Python 3.12.

- pytest: 10/10 only if all three repetitions pass;
- Ruff: 10/10 only if all three repetitions pass;
- mypy: 10/10 only if all three repetitions pass;
- overall: 10/10 only when every gate is 10/10 on both Python versions;
- any reproducible failure resets the current checkpoint to 0/10 until corrected.

The validation runner is `scripts/validate.py`.

## Implemented

### Spatial and physical world
- XYZ positions, orientation, velocity, dimensions, mass, distance, elevation, and LOS.
- Swept movement collision and high-speed anti-tunneling checks.
- Solid cover, physical doors, locks, destruction, passage width/height, and oversized-actor
  rejection.
- Narrative, relative, and tactical text rendering.
- Vision with illumination/contrast and occlusion.
- Sound propagation with inverse-distance attenuation, occlusion loss, thresholds, sensitivity,
  direction, and hearing-derived memories.
- Deterministic 3D projectiles with mass, gravity, drag, lifetime, impact energy, owner exclusion,
  and swept collision.
- Shared time-of-day, weather, wind, precipitation, and temperature state drives vision,
  projectiles, sound, movement, and physiology.

### Characters, combat, and survival
- Original body-part combat plus true spatial weapon reach.
- Armor coverage/durability and persistent anatomical injuries.
- Blood loss, pain, fatigue, hydration, nutrition reserve, sleep debt, and temperature.
- Physical inventory based on mass, volume, dimensions, containers, accessibility, and continuous
  encumbrance.
- Openable scene containers with constrained storage, explicit access time, and take/put flows.
- Ranged weapons, ammunition, anatomical aiming, obstruction/interception, door damage, and
  projectile wounds.
- Deterministic skill progression with difficulty, novelty, training modes, cross-skill transfer,
  and physiology/context-sensitive performance.

### NPC cognition and social systems
- Objective reality separated from NPC knowledge and belief.
- Selective memories with importance, emotion, confidence, source, accuracy, decay, and tags.
- Multidimensional relationships and target-specific emotions.
- Utility-based immediate decisions and deterministic GOAP multi-step planning.
- Exact daily routines plus urgent-goal overrides.
- Ambient NPC movement while player time advances.
- Rumor propagation with explicit social/travel links, delay, confidence decay, and cycle control.
- Belief-grounded dialogue with knowledge-bounded answers and relationship-based refusal/trust.

### Persistent world and macro simulation
- Event-driven simulation with five LOD tiers.
- Actor abstraction/restoration preserving salient cognition and physical aggregates.
- Settlements with population, food, wealth, labor, security, livestock, and prices.
- Commodity production, demand/supply pricing, trade routes, transport cost, and risk.
- Employment response, attractiveness, and population-conserving migration.
- Factions, relations, treaties, treaty expiration/breaking, betrayal memory, and cooperation.
- Versioned WORLDSTATE macro persistence and scheduled-event queue persistence.

### Playable deterministic text world
- LOOK, MOVE, INSPECT, MAP, STATUS, WAIT, ATTACK, ADVANCE, TAKE, PUT, DROP, INVENTORY, TALK,
  OPEN, CLOSE, SHOOT, HELP, and QUIT.
- Real time advancement drives physiology, ambient NPC routines, and macro events.
- Event-sourced deterministic replay saves with state digests and tamper detection.
- Replay digest currently covers actor/combat/skill state, inventory/world/scene-container items,
  doors, ranged weapons, sound events, heard memories, scenery, time, transcript, and command
  history.

## Current implementation priorities

1. More complete world-object interaction: breaking objects and construction/destruction.
2. Playable macro coupling: wire settlement production, migration, faction activity, and
   information propagation schedules into text-world sessions and replay digests.
3. Higher-detail persistence/checkpoints so very long replay histories can compact safely.
4. Larger authored/procedural prototype region with several buildings, professions, wildlife, and
   competing factions.

## Testing strategy

New systems should receive:
- focused behavioral tests;
- boundary/error tests;
- deterministic replay tests where applicable;
- conservation/invariant tests for accumulated state;
- long-run/stress tests for systems that evolve over time.

The repository's CI repeats the complete pytest/Ruff/mypy suite three times on both supported
Python versions.
