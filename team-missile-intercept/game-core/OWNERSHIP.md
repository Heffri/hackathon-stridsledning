# Game-Core Ownership Boundary

## Core Rule

Chen owns the base game before AI specialists plug into it. In the current runtime, that means Chen owns the rules of the simulation even when some code still lives under `backend/` or `frontend/`.

## Chen Owns In Base Game Logic

Chen is the primary owner of:

- scenario construction, reset, and match progression
- world state mutation on each tick
- launcher lifecycle, ammo, reload, and placement state
- site registry, site HP, leak accounting, and budget depletion
- win, loss, and draw conditions
- runtime tuning values that change playability or demo balance
- event emission and snapshot shape used by the frontend
- integration acceptance across backend shell, frontend shell, AI modules, maps, and validation

## Runtime, UI, Config, And Tuning Split

| Area | What Chen owns | What stays with the shell or another owner |
|---|---|---|
| Base gameplay rules | Match flow, world rules, launch and leak behavior, site and budget logic, deployment semantics | None; this is game-core territory |
| Backend runtime shell | Meaning of `start`, `pause`, `reset`, and `speed`; what `build_default_scenario()` returns; when a match is considered done | FastAPI wiring, websocket plumbing, static file serving in `backend/server.py` |
| Frontend runtime shell | Snapshot field meanings, event meanings, control semantics, HUD data contract | DOM structure, CSS, rendering, visual polish, scene and registry implementation details |
| Runtime tuning | Arena-facing gameplay constants, site damage, budget start, launcher layout, speed limits, deployment defaults | Terrain provenance and map transform authority remain outside game-core |
| AI integration | Stable objects and hooks AI can rely on | Actual Blue and Red policy logic remains owned by AI specialists |

## Stable Integration Surface For AI

AI work should treat the following as game-core-owned contracts unless Chen explicitly changes them:

- `build_default_scenario()` constructs the runnable match object
- `Scenario.step(dt)` advances one simulation step
- `Scenario.winner` and `Scenario.done` define match outcome and stop conditions
- `Scenario.snapshot()` defines the frontend-facing and tooling-facing runtime state contract
- `World` owns live threats, interceptors, stats, events, and spawn methods
- `sites.SOUTH_SITES` defines active targetable Blue-side sites
- `LauncherFleet` and `RedLauncherFleet` define launcher state and placement data shape
- `Threat.override_maneuver(turn_dir, g_load)` is the current Red HGV control hook
- enums and spec tables in `types.py` define wire-format names and core unit types

## Things AI Should Not Quietly Redefine

Blue AI and Red AI should not silently redefine:

- snapshot keys or event payload shape
- win-condition semantics
- site HP or leak-damage rules
- budget rules
- launcher placement schema
- command semantics for start, pause, reset, or speed

Those are base game contracts, not AI-local policy choices.

## UI Boundary

The UI owns presentation, not gameplay meaning.

Frontend files may change:

- layout
- panel ordering
- colors, typography, and animation
- visual presentation of launchers, sites, and HUD blocks

Frontend files should not redefine:

- what counts as a leak
- what counts as a win
- what a launcher state means
- what a site HP value means
- what a speed multiplier means

## Review Rule

Chen review is required when a change affects:

- match flow
- snapshot or event shape
- launcher or site state
- budget or HP rules
- deployment behavior
- backend/frontend integration behavior that could break runnability
