# Docs Index

## Start Here

- [README.md](README.md) - main landing page for active teammates
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - what the project is, what is
  active, and where modules live
- [CURRENT_STATE_SUMMARY.md](CURRENT_STATE_SUMMARY.md) - short snapshot of the
  current demo and current module state
- [TEAM_HANDOFF_GUIDE.md](TEAM_HANDOFF_GUIDE.md) - role-based starting points

## Current State And Planning

- [../progress/STATUS.md](../progress/STATUS.md) - current named milestone
  state and playable snapshot
- [../progress/ROADMAP.md](../progress/ROADMAP.md) - open follow-up routes and
  next work, with some historical sections that should be read carefully
- [../REPORT.md](../REPORT.md) - milestone-by-milestone build history

## Session 0 Structure Rules

- [MODULARIZATION_SPEC.md](MODULARIZATION_SPEC.md) - target module structure
  and boundary rules
- [TEAM_OWNERSHIP_SPEC.md](TEAM_OWNERSHIP_SPEC.md) - who owns which module
- [RESTRUCTURE_SEQUENCE.md](RESTRUCTURE_SEQUENCE.md) - safe order for later
  restructuring
- [RUNTIME_STABILITY_RULES.md](RUNTIME_STABILITY_RULES.md) - protected runtime
  paths and early-pass safety rules
- [ARCHIVE_POLICY.md](ARCHIVE_POLICY.md) - how archived material must be
  handled

## Source Data And Provenance

- [ACTIVE_SOURCE_DATA_INDEX.md](ACTIVE_SOURCE_DATA_INDEX.md) - canonical active
  source files
- [DEPENDENCY_CUTOVER_REPORT.md](DEPENDENCY_CUTOVER_REPORT.md) - what was cut
  over from the archived legacy tree
- `source-data/` - active Saab-provided and knowledge-source material

## Ownership Packages

- [../ai/README.md](../ai/README.md) - AI ownership package
- [../math-validation/README.md](../math-validation/README.md) - math audit
  package
- [../maps/README.md](../maps/README.md) - maps ownership package
- [../models/README.md](../models/README.md) - models ownership package
- [../game-core/README.md](../game-core/README.md) - game-core ownership
  package

## Product And Design References

- [../PLAN.md](../PLAN.md) - full implementation vision
- [../GAME_DESIGN.md](../GAME_DESIGN.md) - mechanics and design rules
- [../WEAPON_SPECS.md](../WEAPON_SPECS.md) - reference weapon/spec table

## Drift And Safety

- [KNOWN_DOC_RUNTIME_DRIFT.md](KNOWN_DOC_RUNTIME_DRIFT.md) - highest-impact
  doc/runtime mismatches to keep in mind
- [REPO_ONBOARDING_NOTES.md](REPO_ONBOARDING_NOTES.md) - short repo onboarding
  note that now points into this package

## Runtime Touchpoints

These are code entry points, not docs, but they matter for orientation:

- `backend/server.py`
- `backend/sim/scenarios.py`
- `backend/sim/world.py`
- `backend/sim/blue_ai.py`
- `backend/sim/red_ai.py`
- `backend/sim/terrain.py`
- `frontend/js/main.js`
- `frontend/js/hud.js`
- `frontend/js/scene.js`
