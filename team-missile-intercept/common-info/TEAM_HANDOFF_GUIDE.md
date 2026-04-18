# Team Handoff Guide

## Best Default Read Order For Any Teammate

1. [README.md](README.md)
2. [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)
3. [CURRENT_STATE_SUMMARY.md](CURRENT_STATE_SUMMARY.md)
4. [../progress/STATUS.md](../progress/STATUS.md)
5. [../progress/ROADMAP.md](../progress/ROADMAP.md)
6. [KNOWN_DOC_RUNTIME_DRIFT.md](KNOWN_DOC_RUNTIME_DRIFT.md) if your work
   touches behavior, tuning, physics, or AI policy

## Role-Based Starting Points

| Teammate | Start here | Then inspect | Main responsibility |
| --- | --- | --- | --- |
| Emil | [../math-validation/README.md](../math-validation/README.md), [../math-validation/FILES_TO_CHECK.md](../math-validation/FILES_TO_CHECK.md), [../math-validation/PHYSICS_CHECKLIST.md](../math-validation/PHYSICS_CHECKLIST.md) | `backend/sim/types.py`, `config.py`, `physics.py`, `entities.py`, `world.py` | Math correctness, calibration drift, acceptance thresholds |
| Oskar | [../ai/README.md](../ai/README.md), [../ai/blue-team/README.md](../ai/blue-team/README.md), [../ai/INTEGRATION_POINTS.md](../ai/INTEGRATION_POINTS.md) | `backend/sim/blue_ai.py`, `launcher.py`, `scenarios.py` | Blue-side engagement policy |
| Boyu | [../ai/README.md](../ai/README.md), [../ai/red-team/README.md](../ai/red-team/README.md), [../ai/INTEGRATION_POINTS.md](../ai/INTEGRATION_POINTS.md) | `backend/sim/red_ai.py`, `entities.py`, `sites.py` | Red-side wave policy, target choice, HGV control |
| Oskar + Boyu | [../ai/interfaces/README.md](../ai/interfaces/README.md), [../ai/TASKS_FOR_OSKAR_AND_BOYU.md](../ai/TASKS_FOR_OSKAR_AND_BOYU.md) | `scenarios.py`, `world.py`, `types.py` | Shared AI input/output contracts |
| Sebastijan | [../maps/README.md](../maps/README.md), [../maps/DATA_INVENTORY.md](../maps/DATA_INVENTORY.md), [../models/README.md](../models/README.md), [../models/CURRENT_VISUAL_INVENTORY.md](../models/CURRENT_VISUAL_INVENTORY.md) | `backend/sim/terrain.py`, `backend/sim/sites.py`, `frontend/js/scene.js`, `frontend/js/terrain_data.js`, `frontend/js/entities.js`, `frontend/js/launchers.js`, `frontend/js/sites.js` | Maps, models, terrain, landmarks, launcher and site visuals |
| Chen | [../game-core/README.md](../game-core/README.md), [../game-core/OWNERSHIP.md](../game-core/OWNERSHIP.md), [../game-core/RUNTIME_MAP.md](../game-core/RUNTIME_MAP.md), [../game-core/CHEN_BACKLOG.md](../game-core/CHEN_BACKLOG.md) | `backend/sim/scenarios.py`, `world.py`, `config.py`, `launcher.py`, `sites.py`, `types.py`, `backend/server.py`, `frontend/js/main.js` | Game-core rules, integration acceptance, runtime contracts |

## Shared Rules Before Editing

- Treat Session 0 docs in `common-info/` as the authority for structure,
  ownership, archive policy, and runtime safety.
- Treat current runtime code as the source of truth for live behavior unless a
  Session 0 doc explicitly overrides it.
- Do not start new active work from `archive/xingyi-rts/`.
- Use `common-info/source-data/` as the canonical active home for rehomed
  source files.

## When To Re-Read Common-Info First

Come back to this folder first if your task touches:

- module ownership or boundaries
- archive or provenance questions
- source-data location
- runtime-safe restructuring rules
- a conflict between prose docs and current code
