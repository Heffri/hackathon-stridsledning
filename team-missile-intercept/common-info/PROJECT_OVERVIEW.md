# Project Overview

## What The Project Is

`team-missile-intercept/` is the active Saab hackathon demo: a 3D AI-vs-AI
missile interception scenario where Red launches drones, cruise missiles,
ballistic missiles, and HGVs while Blue selects interceptors and computes
real-time intercepts.

## Current Runtime Reality

The demo still runs from the existing runtime shells:

- `team-missile-intercept/backend/`
- `team-missile-intercept/frontend/`

The target domain folders already exist, but they are ownership and planning
packages first, not runtime import roots yet:

- `team-missile-intercept/ai/`
- `team-missile-intercept/math-validation/`
- `team-missile-intercept/maps/`
- `team-missile-intercept/models/`
- `team-missile-intercept/game-core/`

This follows Session 0: logical ownership first, physical extraction later.

## Folder Status

| Status | Folder or area | What it means now |
| --- | --- | --- |
| Active runtime | `backend/`, `frontend/` | Current runnable game shells |
| Active navigation and rules | `common-info/` | Repo structure, ownership, archive, source-data, and onboarding authority |
| Active progress tracking | `progress/` | Current status and roadmap |
| Active product/design docs | `REPORT.md`, `PLAN.md`, `GAME_DESIGN.md`, `WEAPON_SPECS.md` | Historical build log and design/reference docs |
| Active docs-first ownership packages | `ai/`, `math-validation/`, `maps/`, `models/`, `game-core/` | Teammate module homes before runtime extraction |
| Active archive | `archive/` | Frozen historical material kept for traceability |
| Archived | `archive/xingyi-rts/` | Provenance only, not default working area |

## Active Source Data

Canonical active source data lives under:

- `team-missile-intercept/common-info/source-data/saab-provided/`
- `team-missile-intercept/common-info/source-data/knowledge/`

Use `ACTIVE_SOURCE_DATA_INDEX.md` for the file map and
`DEPENDENCY_CUTOVER_REPORT.md` for how the active project was cut over away
from the archived legacy tree.

## Ownership Package Entry Points

Use these as the first docs for each module:

- AI ownership: [../ai/README.md](../ai/README.md)
- Math validation:
  [../math-validation/README.md](../math-validation/README.md)
- Maps ownership: [../maps/README.md](../maps/README.md)
- Models ownership: [../models/README.md](../models/README.md)
- Game-core ownership: [../game-core/README.md](../game-core/README.md)

## What Common-Info Is For

`common-info/` is the shared landing zone for:

- repo-level structure decisions
- ownership boundaries
- runtime safety constraints
- archive and provenance policy
- canonical active source-data records
- teammate orientation into the active project
