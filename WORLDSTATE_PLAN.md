# WORLDSTATE Implementation Plan

This branch extends Project Simulation toward a deeply simulated, text-first 3D RPG while preserving the existing deterministic combat/world framework.

## Phase 1 — Foundation
- Keep deterministic seeds, versioned persistence, current factories, and the CLI.
- Add genuine 3D transforms and bounds.
- Add perception as derived observations instead of exposing world truth directly.
- Add narrative, relative, and tactical text views.

## Phase 2 — NPC cognition
- Separate objective world state from NPC knowledge and belief.
- Store selective memories with importance, emotion, confidence, source, accuracy, and decay.
- Represent relationships across trust, respect, fear, affection, resentment, familiarity, and dependency.
- Use transparent utility scoring for action selection.

## Phase 3 — Physical consequences
- Add lightweight physiology: blood volume/loss, hydration, caloric reserve, fatigue, sleep debt, core temperature.
- Track location-specific injuries and performance penalties.
- Replace slot inventory assumptions with mass, volume, item length, containers, accessibility, and continuous encumbrance.

## Phase 4 — Persistent world
- Use event scheduling instead of updating every entity every frame.
- Support five simulation LOD tiers: immediate, local, settlement, region, world.
- Model settlements with population, food, labor, security, livestock, prices, and wealth.
- Model factions with membership, wealth, military power, territory, relations, and institutional memory.

## Phase 5 — System interaction
- Make ecological pressure alter settlement resources and prices.
- Propagate injuries into movement/combat performance.
- Let memories and beliefs alter NPC utility choices.
- Promote/demote simulation detail without discarding high-level consequences.

## Phase 6 — Integration
- Add these systems to the public package API.
- Add deterministic tests for perception, occlusion, memory decay, utility choice, inventory constraints, physiology, settlement consequences, and tactical rendering.
- Preserve compatibility with the existing combat/content/persistence tests.

## Next implementation targets
1. Connect spatial state directly to combat reach and movement.
2. Add body-region wound effects to existing BodyPart combat.
3. Add NPC schedules and GOAP-style multi-step planning.
4. Add rumor/information propagation through relationship graphs.
5. Add settlement migration, occupations, production chains, and faction diplomacy.
6. Persist WORLDSTATE state in versioned save files.
7. Extend the CLI into an exploratory text-world prototype.
