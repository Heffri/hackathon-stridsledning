# Data Inventory

This file lists the active source data and map-related references that matter
for Sebastijan's takeover of terrain, geography, and visual map assets.

## Canonical Active Source Files

| Path | Type | Status | Current use | Notes |
|---|---|---|---|---|
| `common-info/source-data/saab-provided/Boreal_passage_coordinates.csv` | Saab-provided source data | Runtime-critical | Parsed by `backend/sim/terrain.py`; baked into `frontend/js/terrain_data.js`; referenced in `REPORT.md` | Canonical active map source |
| `common-info/source-data/saab-provided/the-boreal-passage-map.svg` | Saab-provided visual reference | Doc-only active source | Referenced by roadmap/provenance docs | Not currently loaded by runtime |

## Active Knowledge References Useful For Map/Model Work

| Path | Type | Current use | Why Sebastijan should care |
|---|---|---|---|
| `common-info/source-data/knowledge/scenario.md` | Scenario reference | Used for scenario framing in docs | Contains Boreal Passage scenario framing and map-area context |
| `common-info/source-data/knowledge/ground-defense.md` | Defense-system reference | Used by weapon/docs work | Useful for launcher and SAM visual fidelity |
| `common-info/source-data/knowledge/threats.md` | Threat reference | Used by docs and AI framing | Useful for threat-shape and role reference |
| `common-info/source-data/knowledge/air-assets.md` | Air-asset reference | Doc-only active source | Useful if Blue-side aircraft or support assets are visualized later |
| `common-info/source-data/knowledge/sensors-c2.md` | Sensor reference | Referenced by roadmap/status | Useful for future radar, mast, and C2 visual assets |
| `common-info/source-data/knowledge/SOURCES.md` | Source catalog | Doc-only active source | Citation trail for future asset research |

## Derived Runtime Data Already In Repo

These are active runtime inputs, but they are not canonical source files:

| Path | Type | Derived from | Notes |
|---|---|---|---|
| `frontend/js/terrain_data.js` | Checked-in terrain and landmark constants | `Boreal_passage_coordinates.csv` | Frontend baked derivative |
| `backend/sim/terrain.py` | Runtime parser and land-mask helper | `Boreal_passage_coordinates.csv` | Backend reads canonical CSV directly |
| `backend/sim/sites.py` | Gameplay site placement logic | Saab-space location coordinates | Carries its own transform math |

## Provenance Rules

- `team-missile-intercept/archive/xingyi-rts/` is provenance-only.
- If Sebastijan needs an older map input from
  `team-missile-intercept/archive/xingyi-rts/`, the active copy must first be
  rehomed under `common-info/source-data/`.
- `common-info/ACTIVE_SOURCE_DATA_INDEX.md` is the authoritative index for
  canonical active source files.

## Current Gaps

| Gap | Current state | Why it matters |
|---|---|---|
| Shared terrain asset package | Not present | Frontend and backend rely on separate representations |
| Terrain rebuild script | Not present in active repo | `terrain_data.js` is a manual baked artifact |
| Imported city/terrain/vehicle model library | Not present | All runtime visuals are procedural today |
| Dedicated `maps/` runtime assets | Not present yet | This folder is documentation-first in the current phase |

## Recommended Future Homes

| Future asset type | Recommended home | Reason |
|---|---|---|
| Canonical external map inputs | `common-info/source-data/` | Repo policy says active source data lives here |
| Map-owned processed derivatives | `maps/` | Sebastijan-owned module home |
| Terrain rebuild scripts and transform notes | `maps/` | Keeps pipeline knowledge with the owner |
| Screenshot overlays, alignment notes, coastline experiments | `maps/` | Practical documentation workspace |

## Takeover Summary

For map work, treat `Boreal_passage_coordinates.csv` as the source of truth,
`terrain_data.js` as a checked-in derivative, and `terrain.py` plus `sites.py`
as current backend consumers that must stay aligned with any terrain update.
