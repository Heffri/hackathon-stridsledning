# Maps Ownership Package

This folder is Sebastijan's documentation home for `maps/` ownership in the
active `team-missile-intercept/` project.

## What Sebastijan Owns

- Boreal Passage terrain presentation direction
- Map provenance and source-data hygiene
- Coordinate-transform decisions and map preprocessing proposals
- Site and launcher geography proposals
- Future terrain, city-footprint, and land-mask asset packaging

Per `common-info/TEAM_OWNERSHIP_SPEC.md`, Sebastijan is the primary owner for
`maps/`. Chen is the required collaborator when geography changes affect
runtime assumptions, gameplay balance, or integration contracts.

## Current Runtime Reality

`maps/` is a documentation home right now, not the live runtime entry point.
Today's map pipeline still lives in these files:

- `frontend/js/terrain_data.js`
- `frontend/js/scene.js`
- `backend/sim/terrain.py`
- `backend/sim/sites.py`
- `backend/sim/config.py`

That means Sebastijan owns the domain, but the current code is still split
across `frontend/` and `backend/` until a later move session.

## Read Order

1. `maps/TERRAIN_PIPELINE.md`
2. `maps/DATA_INVENTORY.md`
3. `common-info/ACTIVE_SOURCE_DATA_INDEX.md`
4. `frontend/js/scene.js`
5. `backend/sim/terrain.py`
6. `backend/sim/sites.py`

## Ownership Map

| Area | Primary owner | Current runtime touchpoints | Review needed |
|---|---|---|---|
| Terrain source provenance | Sebastijan | `common-info/source-data/saab-provided/`, `common-info/ACTIVE_SOURCE_DATA_INDEX.md` | Chen if active inputs change |
| Land masks and map transforms | Sebastijan | `backend/sim/terrain.py`, `backend/sim/sites.py`, `frontend/js/scene.js` | Chen |
| Terrain presentation | Sebastijan | `frontend/js/terrain_data.js`, `frontend/js/scene.js` | Chen if gameplay geography changes |
| Site and launcher geography proposals | Sebastijan | `backend/sim/config.py`, `backend/sim/sites.py`, `frontend/js/launchers.js`, `frontend/js/sites.js` | Chen |

## Recommended Future File Homes

- Canonical third-party or Saab-provided source inputs:
  `team-missile-intercept/common-info/source-data/`
- Map ownership docs, decisions, inventories, and handoff notes:
  `team-missile-intercept/maps/`
- Future generated terrain derivatives such as baked JSON, processed polygon
  sets, or rebuild scripts:
  `team-missile-intercept/maps/` as the long-term module home
- Future city-footprint, coastline, or land-mask working files:
  `team-missile-intercept/maps/` once the team is ready to move them out of
  `frontend/` and `backend/`

Practical rule: external source copies belong under
`common-info/source-data/`; map-owned derived assets and documentation belong
under `maps/`.

## Key Takeaways

- The canonical active Saab map source is the CSV under
  `common-info/source-data/saab-provided/`.
- The frontend terrain is a checked-in baked derivative, not the canonical
  source.
- The backend separately parses the CSV for land validation, so transform
  drift is a real integration risk.
- The current terrain is a stylized extruded polygon map, not a heightmap or
  imported mesh pipeline.
