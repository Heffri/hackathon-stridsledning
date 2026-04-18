# Dependency Cutover Report

## Scope

Goal: remove active runtime and active team-documentation dependencies on the
legacy `xingyi-rts` project before physically archiving that tree.

Cutover date: 2026-04-18
Archive follow-up date: 2026-04-18

The physical archive now lives at:

`team-missile-intercept/archive/xingyi-rts/`

## Dependencies Found

| Active location | Archived dependency found | Class | Action | Result |
|---|---|---|---|---|
| `team-missile-intercept/backend/sim/terrain.py` | `team-missile-intercept/archive/xingyi-rts/saab-provided/Boreal_passage_coordinates.csv` | Runtime-critical | Copied CSV into `team-missile-intercept/common-info/source-data/saab-provided/` and repointed runtime path | Cut over |
| `team-missile-intercept/frontend/js/terrain_data.js` | Comment cited the archived CSV | Doc-only active | Updated comment to canonical active source-data path | Cut over |
| `team-missile-intercept/WEAPON_SPECS.md` | Archived knowledge docs | Doc-only active | Copied source docs into `team-missile-intercept/common-info/source-data/knowledge/` and updated citations | Cut over |
| `team-missile-intercept/REPORT.md` | Archived sensor, scenario, and terrain provenance refs | Doc-only active | Copied needed source docs and updated references to canonical paths | Cut over |
| `team-missile-intercept/progress/STATUS.md` | Archived sensor reference | Doc-only active | Updated reference to canonical path | Cut over |
| `team-missile-intercept/progress/ROADMAP.md` | Archived sensor and SVG references | Doc-only active | Copied source files and updated roadmap references | Cut over |
| `team-missile-intercept/common-info/*` | Older docs still described the legacy tree as the active source location | Doc-only active | Updated shared docs to point at canonical source data and the archived provenance path | Cut over |
| Repo-level onboarding docs | Older wording still pointed at the legacy tree | Doc-only active | Updated `README.md`, `AGENTS.md`, and `CLAUDE.md` during the archive follow-up | Cut over |

## Source Files Copied Into The Canonical Active Home

- `team-missile-intercept/common-info/source-data/saab-provided/Boreal_passage_coordinates.csv`
- `team-missile-intercept/common-info/source-data/saab-provided/the-boreal-passage-map.svg`
- `team-missile-intercept/common-info/source-data/knowledge/ground-defense.md`
- `team-missile-intercept/common-info/source-data/knowledge/threats.md`
- `team-missile-intercept/common-info/source-data/knowledge/air-assets.md`
- `team-missile-intercept/common-info/source-data/knowledge/sensors-c2.md`
- `team-missile-intercept/common-info/source-data/knowledge/SOURCES.md`
- `team-missile-intercept/common-info/source-data/knowledge/scenario.md`

## Inspected But Not Active

- `team-missile-intercept/archive/xingyi-rts/knowledge/data-model.md`: no
  inbound runtime or active team-doc reference found.
- `team-missile-intercept/archive/xingyi-rts/knowledge/doctrine.md`: no
  inbound runtime or active team-doc reference found.

## Archive Follow-Up Result

- The legacy tree was physically moved from the repo root into
  `team-missile-intercept/archive/xingyi-rts/`.
- Canonical active source data remained under
  `team-missile-intercept/common-info/source-data/`.
- Repo-level onboarding docs were updated so `team-missile-intercept/` is
  clearly the only active project.

## Verification

Runtime-relevant sanity check run from `team-missile-intercept/backend`:

```bash
python -c "from sim.terrain import _CSV_PATH, point_on_south_land; from sim.scenarios import build_default_scenario; scenario = build_default_scenario(); print(_CSV_PATH); print(point_on_south_land(75000, 5000)); print(len(scenario.snapshot()['sites']))"
```

Expected verification goals:

- `_CSV_PATH` resolves into `team-missile-intercept/common-info/source-data/saab-provided/Boreal_passage_coordinates.csv`
- `point_on_south_land(75000, 5000)` returns `True`
- `build_default_scenario()` succeeds, proving the backend import chain still
  works after the terrain path cutover

Actual result:

- `_CSV_PATH` resolved to `C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\common-info\source-data\saab-provided\Boreal_passage_coordinates.csv`
- `point_on_south_land(75000, 5000)` returned `True`
- `build_default_scenario()` succeeded and `scenario.snapshot()['sites']`
  returned `3`
- Expected site-filter log still appeared for the 4 out-of-arena Saab
  locations, confirming the normal terrain/site import path remained intact
