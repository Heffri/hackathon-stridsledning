# Tasks For Sebastijan

## Mission

Own the `maps/` and `models/` domains without breaking the current demo.

In practical terms, that means:

- understand how today's terrain and visuals are built
- become the default reviewer for map and visual work
- define the next asset pipeline before runtime files move
- improve terrain, landmarks, launchers, and model quality in a controlled way

## Explicit Ownership Map

| Workstream | Sebastijan owns | Coordinate with |
|---|---|---|
| Terrain presentation and map provenance | Boreal Passage terrain look, source-data hygiene, future terrain derivatives | Chen if geometry changes affect gameplay or transforms |
| Site and launcher geography proposals | Placement proposals, visual readability, map narrative | Chen before runtime/balance-impacting changes |
| Entity model quality | Threat and interceptor look, silhouette clarity, material direction | Chen if kind names or contracts change |
| Landmark and city visuals | Air-base, city, capital representation and future asset replacements | Chen if gameplay target semantics change |
| Asset packaging plan | Decide how imported terrain/model files should enter the repo | Chen for integration cutover |

## First Session Checklist

1. Run the current demo and capture a screenshot pass of terrain, landmarks,
   launchers, site markers, and all missile/threat types.
2. Read `maps/TERRAIN_PIPELINE.md` and `models/CURRENT_VISUAL_INVENTORY.md`.
3. Open `frontend/js/scene.js`, `terrain_data.js`, `entities.js`,
   `launchers.js`, and `sites.js` side by side.
4. Confirm the split between visual landmarks and gameplay sites so future city
   work does not accidentally assume they are already the same system.
5. Decide which asset class should be upgraded first:
   - terrain shell
   - landmark kit
   - launcher kit
   - interceptor/threat meshes

## Good First Deliverables

| Deliverable | Why it is a good starting point |
|---|---|
| Visual style sheet for Boreal Passage | Gives the team a shared look target |
| Naming and scale sheet for current entity kinds | Makes imported-model handoff safer |
| Landmark replacement plan | Low-risk visual improvement area |
| Terrain regeneration note or script plan | Reduces CSV -> baked-JS drift |
| File-home proposal for raw assets vs exports | Prevents repo sprawl once art files arrive |

## Changes That Need Chen In The Loop

| Change | Why |
|---|---|
| Altering map crop, arena fit, or coordinate transforms | Impacts gameplay and backend/frontend agreement |
| Changing launcher or site positions | Impacts balance and land validation |
| Replacing snapshot-driven visual contracts | Impacts runtime integration |
| Introducing a new runtime asset loading path | Impacts packaging and deploy shape |

## Recommended Near-Term Backlog

1. Decide whether terrain should remain source-driven procedural or move toward
   a baked mesh/JSON pipeline.
2. Decide whether the first imported assets should be landmarks, launchers, or
   missile bodies.
3. Unify the story around 12 visual landmarks versus 3 active gameplay sites.
4. Define where future terrain, city, launcher, and vehicle files will live.
5. Document a regeneration workflow so the canonical CSV stays ahead of
   `terrain_data.js`.

## File-Home Recommendation

Use this split unless the team agrees on a different module layout later:

- External raw source copies with provenance:
  `common-info/source-data/`
- Terrain-owned processed outputs and map docs:
  `maps/`
- Model-owned asset files, exports, and packaging docs:
  `models/`

## Success Condition

Sebastijan is fully set up when he can answer these questions without hunting:

- What is the canonical terrain source?
- What parts of the current scene are procedural?
- Which visuals are driven by source data?
- Which visual changes are safe alone versus cross-boundary?
- Where should future terrain, city, launcher, and model files live?
