# WORLDSTATE Implementation Plan

This branch extends Project Simulation toward a deeply simulated, text-first 3D RPG while preserving the existing deterministic combat/world framework.

## Quality gate

Every quality process is repeated three times on Python 3.11 and Python 3.12.

- pytest: 10/10 only if all three repetitions pass.
- Ruff: 10/10 only if all three repetitions pass.
- mypy: 10/10 only if all three repetitions pass.
- Overall: 10/10 only when every gate is 10/10 on both Python versions.
- Any reproducible failure resets the affected checkpoint to 0/10 until corrected.

The validation runner lives at `scripts/validate.py`.

## Phase 1 — Foundation — implemented
- Deterministic seeds and existing versioned persistence retained.
- Genuine 3D transforms, bounds, velocity, distance, facing, and occlusion.
- Perception produces observations instead of exposing objective world state.
- Narrative, relative, and tactical text views.

## Phase 2 — NPC cognition — implemented
- Objective truth separated from NPC knowledge and belief.
- Selective memories carry importance, emotion, confidence, source, accuracy, tags, and decay.
- Relationships track trust, respect, fear, affection, resentment, familiarity, and dependency.
- Transparent utility scoring for immediate choices.
- Deterministic GOAP-style planning for multi-step goals.
- Routine schedules with exact overlap detection.
- Urgent goals can override routines through `NPCController`.

## Phase 3 — Physical consequences — implemented foundation
- Blood volume/loss, hydration, caloric reserve, fatigue, sleep debt, and core temperature.
- Location-specific injuries with pain, bleeding, mobility, manipulation, and infection risk.
- Physical inventories use mass, volume, length, containers, accessibility, and continuous encumbrance.
- Spatial combat checks actual distance and weapon reach.
- Weapon mass/speed produce impact energy.
- Armor, physiology, and encumbrance alter combat outcome.
- Spatial hits create persistent physiological injuries.

## Phase 4 — Persistent world — implemented foundation
- Event scheduling replaces per-frame updates for distant systems.
- Five LOD tiers: immediate, local, settlement, region, world.
- Settlements track population, food, labor, security, livestock, prices, and wealth.
- Factions track membership, wealth, military power, territory, relations, and institutional memory.
- WORLDSTATE macro state has deterministic versioned JSON persistence.

## Phase 5 — Economy and demographics — implemented foundation
- Commodity markets track stock, demand, and dynamic price pressure.
- Production recipes consume inputs and labor and create outputs.
- Trade routes impose capacity, transport cost, and risk.
- Transfers preserve commodity quantity.
- Settlement attractiveness produces migration pressure.
- Migration preserves total population and transfers occupations.
- Unemployed residents can fill demanded occupations.

## Phase 6 — System interaction — active
Completed:
- Ecological pressure changes settlement livestock, security, and prices.
- Injuries and encumbrance affect movement and combat.
- Relationship trust affects information confidence.
- Routine behavior and urgent plans interact.
- Migration responds to settlement conditions.

Next:
1. Delayed rumor propagation over social/travel networks.
2. Faction diplomacy and treaty/betrayal memory.
3. Settlement production chains connected directly to macro event simulation.
4. Migration and occupation changes triggered automatically by economic conditions.
5. Spatial movement/reach integration into full multi-turn encounters.
6. Persist scheduled events and higher-detail actor state.
7. Promote and demote entities between LOD tiers while preserving aggregates.

## Phase 7 — Playable text-world prototype — planned
1. Add a small authored/procedural village scenario.
2. Add natural command parsing for LOOK, MOVE, INSPECT, TALK, TAKE, WAIT, and ATTACK.
3. Render observations through the current narrative/tactical text layer.
4. Advance NPC routines and macro events while the player acts.
5. Save/load a complete prototype campaign.
6. Add deterministic replay tests for full player command sequences.

## Testing expansion
Current tests cover deterministic world generation, combat, cognition, perception, occlusion, memory decay, planning, information confidence, physiology, encumbrance, spatial combat, economy conservation, long-running settlement simulation, LOD boundaries, migration invariants, routines, persistence, and integration behavior.

Planned stress suites:
- multi-year settlement/economy simulation;
- thousands of rumor transmissions with bounded confidence;
- repeated save/load/replay equivalence;
- hundreds of NPC routine/GOAP decisions;
- cross-LOD promotion/demotion invariants;
- long spatial-combat campaigns with injury accumulation.
