# Runtime Stability Rules

## Purpose

This document defines what must be preserved while restructuring so the current game stays runnable.

## Runtime-Critical Areas to Preserve

The following areas are runtime-critical right now:

### Backend runtime shell

- `team-missile-intercept/backend/server.py`
- `team-missile-intercept/backend/sim/`

Especially critical inside `backend/sim/`:

- `config.py`
- `scenarios.py`
- `world.py`
- `types.py`
- `entities.py`
- `physics.py`
- `blue_ai.py`
- `red_ai.py`
- `launcher.py`
- `sites.py`
- `terrain.py`

### Frontend runtime shell

- `team-missile-intercept/frontend/index.html`
- `team-missile-intercept/frontend/style.css`
- `team-missile-intercept/frontend/js/`

Especially critical inside `frontend/js/`:

- `main.js`
- `scene.js`
- `entities.js`
- `launchers.js`
- `sites.js`
- `hud.js`
- `status_panel.js`
- `terrain_data.js`

### External data that the current runtime still depends on

- `team-missile-intercept/common-info/source-data/saab-provided/Boreal_passage_coordinates.csv`

Reason:

- `team-missile-intercept/backend/sim/terrain.py` currently resolves that canonical active copy directly at runtime.

### Active reference material with live design value

These are not runtime-executed, but they are still active reference dependencies for the team project:

- `team-missile-intercept/common-info/source-data/saab-provided/the-boreal-passage-map.svg`
- `team-missile-intercept/common-info/source-data/knowledge/ground-defense.md`
- `team-missile-intercept/common-info/source-data/knowledge/threats.md`
- `team-missile-intercept/common-info/source-data/knowledge/air-assets.md`
- `team-missile-intercept/common-info/source-data/knowledge/sensors-c2.md`
- `team-missile-intercept/common-info/source-data/knowledge/SOURCES.md`
- `team-missile-intercept/common-info/source-data/knowledge/scenario.md`

## What Must Not Move in the First Restructuring Pass

Do not move in the first pass:

- `team-missile-intercept/backend/`
- `team-missile-intercept/frontend/`
- Any file under `team-missile-intercept/backend/sim/`
- Any file under `team-missile-intercept/frontend/js/`
- `team-missile-intercept/common-info/source-data/saab-provided/`

Do not rename in the first pass:

- `backend/server.py`
- `backend/sim/scenarios.py`
- `backend/sim/config.py`
- `frontend/js/main.js`
- `frontend/js/scene.js`

Do not change path assumptions in the first pass:

- `terrain.py` path resolution to the canonical Saab CSV under `team-missile-intercept/common-info/source-data/saab-provided/`
- Frontend imports rooted from `frontend/js/main.js`
- Static file serving assumptions in `server.py`

## What Should Be Wrapped Rather Than Deeply Refactored

Wrap these first. Do not deeply refactor them in the early passes:

### Runtime entry and wiring

- `backend/server.py`
- `frontend/js/main.js`

These should remain stable composition roots while module seams are added behind them.

### Scenario and snapshot contract

- `build_default_scenario()`
- `Scenario.step()`
- `Scenario.snapshot()`
- The JSON snapshot shape consumed by the frontend registries and HUD

These should be adapter-protected before any deeper split.

### Terrain and map path assumptions

- `backend/sim/terrain.py`
- `frontend/js/terrain_data.js`
- Scene-side coordinate transforms in `frontend/js/scene.js`

These are tightly coupled to Boreal Passage source data and should be wrapped behind map interfaces before relocation.

### Launcher, site, and runtime tuning sources

- `backend/sim/config.py`
- `backend/sim/launcher.py`
- `backend/sim/sites.py`

These are active sources of truth for current placement, runtime tuning, and gameplay state. They should not be fragmented early.

## First-Pass Safe Changes

Safe in early restructure sessions:

- Documentation additions
- Dependency inventories
- Thin wrappers
- Adapter layers
- Validation-only additions
- Small internal helper extraction where old import paths still work

## First-Pass Unsafe Changes

Unsafe in early restructure sessions:

- Renaming snapshot keys without a dedicated integration change
- Moving active runtime files to target folders before wrappers exist
- Splitting `backend/sim/` into multiple new roots in one pass
- Moving the canonical Saab source data while `terrain.py` still reads it
- Changing the frontend import graph and backend wiring at the same time

## Rules for Later Sessions

- If a change touches a runtime-critical path, preserve the old runnable entry path until the replacement is proven.
- Prefer wrappers and adapters over immediate file relocation.
- Treat `team-missile-intercept/common-info/source-data/saab-provided/` as frozen-in-place until the active runtime no longer depends on it.
- If there is any doubt whether a file is runtime-critical, assume it is and defer the move.
