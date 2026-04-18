# Game-Core Ownership Package

This folder is the first ownership package for `team-missile-intercept/game-core/`.

It is a documentation-only module boundary pass for Chen. No runtime code is moved in this session. The current runnable shells remain:

- `team-missile-intercept/backend/`
- `team-missile-intercept/frontend/`

## Why This Exists

Session 0 defined `game-core/` as the ownership home for base gameplay and runtime tuning before AI specialists plug into the sim. This package records what Chen owns now, what the runtime shells still host temporarily, and which interfaces AI and UI work should treat as stable.

## What Game-Core Owns

Game-core is the authority for:

- scenario lifecycle and match phases
- world tick, state mutation, leak handling, and win conditions
- launchers, sites, budget, HP, and other playable-state rules
- runtime tuning values and placement data that affect gameplay
- snapshot and event contracts consumed by the frontend
- stable integration surfaces used by Blue AI and Red AI

## What Game-Core Does Not Own

Game-core is not the primary owner of:

- Blue-side and Red-side decision policy details in `backend/sim/blue_ai.py` and `backend/sim/red_ai.py`
- map provenance, terrain transforms, and land/sea data authority
- presentation-only HUD styling, scene visuals, meshes, and model assets
- intercept math validation sign-off and numeric acceptance criteria

## Current Runtime Reality

Right now, the base game lives mostly inside `backend/sim/`, while `backend/server.py` and `frontend/js/main.js` act as thin composition roots. The HUD and page files are still the active UI shell, but the meaning of the data they display belongs to game-core.

## Read Order

1. `OWNERSHIP.md`
2. `RUNTIME_MAP.md`
3. `CANDIDATE_FILES_TO_OWN.md`
4. `CHEN_BACKLOG.md`

## Package Contents

- `README.md` - purpose and module summary
- `OWNERSHIP.md` - ownership boundary for Chen and the shell split
- `RUNTIME_MAP.md` - current runtime-to-game-core map and active contracts
- `CANDIDATE_FILES_TO_OWN.md` - concrete files Chen should own now
- `CHEN_BACKLOG.md` - practical next steps for the base game package
