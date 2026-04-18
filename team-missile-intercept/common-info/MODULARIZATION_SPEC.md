# Modularization Specification

## Purpose

This document is the single source of truth for the repository modularization plan before any broad restructuring begins.

Scope of this document:

- Architecture and ownership blueprint only
- No file moves, renames, or deletions are authorized by this document
- `team-missile-intercept/` is the active project
- `team-missile-intercept/archive/xingyi-rts/` is the archived legacy tree; any still-needed active source material must be rehomed under `team-missile-intercept/common-info/source-data/`

## Non-Negotiable Constraints

- Keep the current game runnable throughout the restructuring
- Keep `backend/` and `frontend/` working as the current runtime shells until later migration phases are complete
- Do not create new active gameplay logic inside `team-missile-intercept/archive/xingyi-rts/`
- Treat `common-info/` as the canonical location for repo-level structure decisions

## Target Modular Structure

The target structure for the active project is:

```text
team-missile-intercept/
├─ ai/
├─ game-core/
├─ maps/
├─ models/
├─ math-validation/
├─ common-info/
└─ archive/
```

This is the target domain structure, not the immediate runtime structure. During the transition, `backend/` and `frontend/` remain in place and act as integration shells until the restructure sequence allows deeper moves.

## Module Definitions

### `ai/`

Purpose:

- Blue-side decision logic
- Red-side decision logic
- Target selection
- Placement AI
- Learned or scripted policy layers
- AI evaluation harnesses and behavior notes

Examples of future contents:

- Blue engagement policy
- Red maneuver policy
- HGV control logic
- Scenario-specific AI adapters

Out of scope:

- Terrain source data
- Scene assets
- Core world tick ownership
- Final authority on intercept math correctness

### `game-core/`

Purpose:

- Simulation state
- World tick and entity lifecycle
- Scenario orchestration
- Launchers, sites, budgets, win conditions
- Runtime configuration and tuning
- Stable interfaces consumed by AI and frontend integration

Examples of future contents:

- World state model
- Scenario builders
- Event and snapshot contracts
- Runtime rules and tuning tables

Out of scope:

- Visual asset pipeline
- Archived source material

### `maps/`

Purpose:

- Boreal Passage map logic
- Terrain and coordinate transforms
- Site and launcher geography
- Map preprocessing and provenance records
- Land/sea validation utilities

Examples of future contents:

- Terrain source ingestion
- Coordinate conversion helpers
- Location metadata
- Map reference notes

Out of scope:

- General gameplay rules
- AI policy logic

### `models/`

Purpose:

- 3D entities, meshes, materials, labels, and visual effects
- Visual launcher, site, and map presentation assets
- Rendering-side model definitions

Examples of future contents:

- Interceptor and threat meshes
- Terrain presentation assets
- Landmark visuals
- HUD-facing model metadata where it is presentation-only

Out of scope:

- Core scenario rules
- Numerical validation

### `math-validation/`

Purpose:

- Intercept math validation
- Guidance validation
- Numerical acceptance criteria
- Gold scenarios and validation fixtures
- Precision-debt tracking and calibration sign-off

Examples of future contents:

- PN/RK4 comparison fixtures
- Reference intercept cases
- Validation scripts
- Balance-impact notes for math changes

Out of scope:

- Map assets
- UI assets
- General archive storage

### `common-info/`

Purpose:

- Repo-level architecture rules
- Ownership rules
- Restructure sequencing
- Archive policy
- Shared terminology and structural decisions

This folder is the documentation authority for restructuring decisions.

### `archive/`

Purpose:

- Frozen material that is no longer active runtime or active roadmap content
- Historical references kept for traceability
- Retired docs, data, and snapshots once they are safely decoupled from runtime

Archive material is read-mostly and must not become a hidden active dependency.

## Current-to-Target Mapping

The current active runtime is still split by technical shell:

- `backend/`
- `frontend/`

The target domain mapping is:

| Current area | Target module |
|---|---|
| `backend/sim/blue_ai.py`, `backend/sim/red_ai.py` | `ai/` |
| `backend/sim/world.py`, `backend/sim/scenarios.py`, `backend/sim/launcher.py`, `backend/sim/sites.py`, `backend/sim/types.py`, runtime rule parts of `backend/sim/config.py` | `game-core/` |
| `backend/sim/physics.py`, validation scripts, intercept reference fixtures | `math-validation/` |
| `backend/sim/terrain.py`, `frontend/js/terrain_data.js`, Boreal map provenance, coordinate transforms | `maps/` |
| `frontend/js/entities.js`, `frontend/js/scene.js`, `frontend/js/launchers.js`, `frontend/js/sites.js`, visual assets and model definitions | `models/` |
| These specification files and future restructure docs | `common-info/` |
| Retired material after safe cutover | `archive/` |

`backend/server.py` and `frontend/js/main.js` are transitional composition roots. They should stay thin and should not become the long-term home for domain logic.

## Boundary Rules

1. `ai/` may depend on stable APIs from `game-core/` and on validated math interfaces, but it must not own the runtime world loop.
2. `game-core/` is the authority for simulation flow, scenario state, runtime tuning, and the snapshot contract consumed by the frontend.
3. `maps/` owns geography, coordinate logic, and terrain provenance. It must not silently redefine gameplay balance rules.
4. `models/` owns presentation assets and scene-side representations. It must not silently redefine game rules.
5. `math-validation/` owns correctness validation, acceptance thresholds, and reference math cases. Runtime math changes should be validated here before they are treated as accepted.
6. `common-info/` is the only place where repo-wide modularization decisions should be locked.
7. `archive/` is for frozen material only. Active runtime code must not gain new dependencies on `archive/`.

## Transitional Rules

- The first restructure passes are logical and documentary, not physical.
- The current import graph remains valid until explicit integration shims exist.
- No active runtime file should be moved only because its eventual domain is now known.
- If a new file must be added before the move phase, place it where the runtime can use it safely, then record the exception in `common-info/`.

## Rules for Later Sessions

- Treat this document as the source of truth before proposing any folder move.
- Do not move `backend/` or `frontend/` entry paths in the first pass.
- Do not add new active project logic to `team-missile-intercept/archive/xingyi-rts/`.
- If a session changes module boundaries, it must update this file first or in the same session.
