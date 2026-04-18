# Active Source Data Index

## Purpose

This index lists the canonical active source-data files that the
`team-missile-intercept/` demo may depend on. These copies live under
`team-missile-intercept/common-info/source-data/` so the archived
`team-missile-intercept/archive/xingyi-rts/` tree can remain
provenance-only without breaking the active demo.

## Canonical Roots

- Saab source material:
  `team-missile-intercept/common-info/source-data/saab-provided/`
- Knowledge references:
  `team-missile-intercept/common-info/source-data/knowledge/`

## Active Files

| Canonical path | Source origin | Status | Current consumers |
|---|---|---|---|
| `team-missile-intercept/common-info/source-data/saab-provided/Boreal_passage_coordinates.csv` | `team-missile-intercept/archive/xingyi-rts/saab-provided/Boreal_passage_coordinates.csv` | Runtime-critical | `backend/sim/terrain.py`, terrain provenance in `frontend/js/terrain_data.js`, terrain notes in `REPORT.md` |
| `team-missile-intercept/common-info/source-data/saab-provided/the-boreal-passage-map.svg` | `team-missile-intercept/archive/xingyi-rts/saab-provided/the-boreal-passage-map.svg` | Doc-only active source | `progress/ROADMAP.md`, Boreal Passage provenance |
| `team-missile-intercept/common-info/source-data/knowledge/ground-defense.md` | `team-missile-intercept/archive/xingyi-rts/knowledge/ground-defense.md` | Doc-only active source | `WEAPON_SPECS.md`, archive/provenance docs |
| `team-missile-intercept/common-info/source-data/knowledge/threats.md` | `team-missile-intercept/archive/xingyi-rts/knowledge/threats.md` | Doc-only active source | `WEAPON_SPECS.md`, archive/provenance docs |
| `team-missile-intercept/common-info/source-data/knowledge/air-assets.md` | `team-missile-intercept/archive/xingyi-rts/knowledge/air-assets.md` | Doc-only active source | `WEAPON_SPECS.md`, archive/provenance docs |
| `team-missile-intercept/common-info/source-data/knowledge/sensors-c2.md` | `team-missile-intercept/archive/xingyi-rts/knowledge/sensors-c2.md` | Doc-only active source | `REPORT.md`, `progress/STATUS.md`, `progress/ROADMAP.md`, archive/provenance docs |
| `team-missile-intercept/common-info/source-data/knowledge/SOURCES.md` | `team-missile-intercept/archive/xingyi-rts/knowledge/SOURCES.md` | Doc-only active source | `WEAPON_SPECS.md`, archive/provenance docs |
| `team-missile-intercept/common-info/source-data/knowledge/scenario.md` | `team-missile-intercept/archive/xingyi-rts/knowledge/scenario.md` | Doc-only active source | Historical terrain/scenario note in `REPORT.md`, Boreal Passage scenario provenance |

## Not Copied

- `team-missile-intercept/archive/xingyi-rts/knowledge/data-model.md`:
  inspected during cutover, but no active runtime or team-doc consumer was
  found.
- `team-missile-intercept/archive/xingyi-rts/knowledge/doctrine.md`:
  inspected during cutover, but no active runtime or team-doc consumer was
  found.

## Rules

- Treat `team-missile-intercept/common-info/source-data/` as the only
  canonical active home for rehomed source data.
- Treat the matching files under
  `team-missile-intercept/archive/xingyi-rts/` as archived originals for
  provenance, not as active dependencies.
