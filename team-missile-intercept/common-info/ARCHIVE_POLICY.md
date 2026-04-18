# Archive Policy

## Purpose

This document defines how archived material is handled now that the legacy
`xingyi-rts` tree has been physically moved and the active demo has been cut
over to canonical source data under `common-info/source-data/`.

## Current Archive State

- Physical archive location:
  `team-missile-intercept/archive/xingyi-rts/`
- Canonical active source-data location:
  `team-missile-intercept/common-info/source-data/`
- Active runtime shells remain:
  `team-missile-intercept/backend/` and `team-missile-intercept/frontend/`

Earlier versions of this document blocked physical archive moves until runtime
and documentation dependencies were cut over. That condition is now
satisfied.

## Why The Physical Archive Move Is Safe

The move is safe because all of the following are true:

1. The active runtime no longer reads files from the archived tree.
2. Still-needed source assets were copied into
   `team-missile-intercept/common-info/source-data/`.
3. Active onboarding and shared docs now treat `team-missile-intercept/` as
   the only active project.
4. The current game still builds and runs from the existing backend/frontend
   shells.

See `DEPENDENCY_CUTOVER_REPORT.md` and `ACTIVE_SOURCE_DATA_INDEX.md` for the
cutover record and source-of-truth file map.

## Archive Rules

- Treat `team-missile-intercept/archive/xingyi-rts/` as read-mostly
  provenance and historical reference material.
- Do not add new active gameplay logic, runtime dependencies, or onboarding
  paths there.
- Do not repoint active runtime code back into `archive/`.
- If archived material is still needed by the active project, copy the active
  version into `common-info/source-data/` and record it in
  `ACTIVE_SOURCE_DATA_INDEX.md`.
- If a future session needs to preserve more historical context, place that
  material under `team-missile-intercept/archive/` and label it clearly as
  archived.

## Archived Material That Must Remain Discoverable

| Archived path | Why it still matters |
|---|---|
| `team-missile-intercept/archive/xingyi-rts/saab-provided/Boreal_passage_coordinates.csv` | Archived original for the active canonical copy at `team-missile-intercept/common-info/source-data/saab-provided/Boreal_passage_coordinates.csv` |
| `team-missile-intercept/archive/xingyi-rts/saab-provided/the-boreal-passage-map.svg` | Archived original for the active canonical copy at `team-missile-intercept/common-info/source-data/saab-provided/the-boreal-passage-map.svg` |
| `team-missile-intercept/archive/xingyi-rts/knowledge/ground-defense.md` | Archived original for the active canonical copy at `team-missile-intercept/common-info/source-data/knowledge/ground-defense.md` |
| `team-missile-intercept/archive/xingyi-rts/knowledge/threats.md` | Archived original for the active canonical copy at `team-missile-intercept/common-info/source-data/knowledge/threats.md` |
| `team-missile-intercept/archive/xingyi-rts/knowledge/air-assets.md` | Archived original for the active canonical copy at `team-missile-intercept/common-info/source-data/knowledge/air-assets.md` |
| `team-missile-intercept/archive/xingyi-rts/knowledge/sensors-c2.md` | Archived original for the active canonical copy at `team-missile-intercept/common-info/source-data/knowledge/sensors-c2.md` |
| `team-missile-intercept/archive/xingyi-rts/knowledge/SOURCES.md` | Archived original for the active canonical copy at `team-missile-intercept/common-info/source-data/knowledge/SOURCES.md` |
| `team-missile-intercept/archive/xingyi-rts/knowledge/scenario.md` | Archived original for the active canonical copy at `team-missile-intercept/common-info/source-data/knowledge/scenario.md` |

## Active Boundary

The archive is not part of the active runtime boundary.

Active work should start from:

- `team-missile-intercept/common-info/`
- `team-missile-intercept/progress/`
- `team-missile-intercept/backend/`
- `team-missile-intercept/frontend/`

## Related Docs

- `ACTIVE_SOURCE_DATA_INDEX.md`
- `DEPENDENCY_CUTOVER_REPORT.md`
- `REPO_ONBOARDING_NOTES.md`
- `../archive/README.md`
