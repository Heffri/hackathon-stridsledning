# Current State Summary

Prepared from the active docs and current runtime inspection on 2026-04-18.

## Project Snapshot

- The active project is `team-missile-intercept/`, a 3D AI-vs-AI missile
  interception demo for the Saab hackathon.
- The latest named milestone in the progress docs is Milestone I: real win
  conditions, Blue budget, per-site HP, far-north strategic spawns, and an
  HGV control hook.
- The demo still runs from `backend/` and `frontend/`. The new module folders
  are ownership packages first, not extracted runtime modules yet.

## What Is Live Right Now

- Blue and Red gameplay still execute from `backend/sim/blue_ai.py` and
  `backend/sim/red_ai.py`.
- Match lifecycle, budget, site HP, launcher state, and snapshot publishing
  still live under `backend/sim/` plus the shell files `backend/server.py`
  and `frontend/js/main.js`.
- Canonical active source data lives under `common-info/source-data/`, not
  under `archive/xingyi-rts/`.
- AI, math-validation, maps, models, and game-core now each have a docs-first
  ownership package for teammate handoff and later extraction planning.

## Active, Planned, And Archived Areas

- Active runtime: `backend/`, `frontend/`
- Active shared docs and source data: `common-info/`, `progress/`
- Active docs-first module homes: `ai/`, `math-validation/`, `maps/`,
  `models/`, `game-core/`
- Active archive home: `archive/`
- Archived now: `archive/xingyi-rts/`

## Current High-Value Starting Points

- If you need orientation: [README.md](README.md)
- If you need module ownership: [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) and
  [TEAM_HANDOFF_GUIDE.md](TEAM_HANDOFF_GUIDE.md)
- If you need current milestone state: [../progress/STATUS.md](../progress/STATUS.md)
- If you need next-step planning: [../progress/ROADMAP.md](../progress/ROADMAP.md)
- If you need active source paths: [ACTIVE_SOURCE_DATA_INDEX.md](ACTIVE_SOURCE_DATA_INDEX.md)

## Current Likely Next Work

The live open work described across `STATUS.md`, `ROADMAP.md`, and the new
ownership packages clusters around:

- deployment UI and placement phase support
- Red HGV control through `Threat.override_maneuver(...)`
- smarter Red target selection
- PN precision and other math-validation debt
- radar/sensor model work
- continued stabilization of AI-facing and game-core-facing contracts

## Important Caution

Some older status and roadmap prose is now behind the code. Before making
physics, balance, or AI decisions from prose alone, read
[KNOWN_DOC_RUNTIME_DRIFT.md](KNOWN_DOC_RUNTIME_DRIFT.md).
