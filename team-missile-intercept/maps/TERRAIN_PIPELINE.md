# Terrain Pipeline

## Current Pipeline At A Glance

1. Canonical active source data lives in
   `common-info/source-data/saab-provided/Boreal_passage_coordinates.csv`.
2. A baked frontend derivative lives in `frontend/js/terrain_data.js`.
3. `frontend/js/scene.js` turns that derivative into rendered terrain and
   landmark visuals.
4. `backend/sim/terrain.py` re-parses the canonical CSV for land validation.
5. `backend/sim/sites.py` separately ports the Saab-to-world transform to place
   gameplay sites.

There is no single shared runtime terrain asset yet. The live pipeline is
split across checked-in JS constants plus Python CSV parsing.

## Canonical Inputs

### Runtime-critical

- `common-info/source-data/saab-provided/Boreal_passage_coordinates.csv`

This file contains:

- 8 terrain polygons
- 12 named locations
- Saab-space coordinates in kilometers
- `record_type`, `side`, `subtype`, `geometry_type`, and `coordinates_km`
  fields

### Doc-only active reference

- `common-info/source-data/saab-provided/the-boreal-passage-map.svg`

This SVG is useful for visual reference and provenance, but the live runtime
does not currently load it.

## Frontend Terrain Generation

### Step 1: Checked-in derivative

`frontend/js/terrain_data.js` contains two baked exports:

- `BOREAL_TERRAIN`
- `BOREAL_LOCATIONS`

Current contents:

- `BOREAL_TERRAIN`: 8 polygons
  - 2 mainlands
  - 5 islands
  - 1 peninsula
- `BOREAL_LOCATIONS`: 12 named locations

This file is already a processed copy of the CSV, not a parser.

### Step 2: Scene transform and crop

`frontend/js/scene.js` applies a hard-coded Saab-space crop and stretch:

```text
SAAB_X_WINDOW = [0, 1667]
SAAB_Y_WINDOW = [280, 1080]
SCENE_X       = [-75, 75]
SCENE_Z_NORTH = -245
SCENE_Z_SOUTH = 5
```

Important implications:

- Saab X is east-positive.
- Saab Y is south-positive.
- Scene Z is south-positive because scene north is `-Z`.
- The Saab crop is non-uniformly stretched into the 150 km x 250 km arena.

### Step 3: Terrain mesh build

`scene.js` builds terrain procedurally:

- `THREE.Shape` from each polygon
- `THREE.ExtrudeGeometry` with `depth = 0.3`
- Flat sea plane underneath
- Mainland and island color variants

Current terrain look:

- stylized flat-topped land masses
- 300 m visual extrusion above the sea plane
- no heightmap
- no imported terrain mesh
- no texture map beyond flat materials

### Step 4: Landmark generation

`scene.js` also turns `BOREAL_LOCATIONS` into procedural landmarks:

- `air_base` -> runway + tower
- `capital` -> 5-box skyline
- `major_city` -> 3-box cluster
- sprite labels generated from canvas at runtime

Important boundary:

- The scene renders all 12 named locations from `BOREAL_LOCATIONS`.
- Gameplay site markers do not use all 12 locations.

## Backend Terrain And Geography Pipeline

### Land-mask validation

`backend/sim/terrain.py` parses the canonical CSV directly at import time and
builds:

- `_SOUTH_POLYGONS`
- `_NORTH_POLYGONS`
- `point_on_south_land(wx, wy)`
- `point_on_north_land(wx, wy)`

Current use:

- `backend/sim/config.py` asserts that Blue launcher positions are on south
  land.
- `backend/sim/config.py` asserts that Red launcher positions are on north
  land.

### Gameplay site placement

`backend/sim/sites.py` ports the Saab-to-world affine transform separately and
builds `SOUTH_SITES`.

Current behavior:

- Converts a curated south-side location list into world coordinates
- Filters out locations outside the 150 km x 250 km arena
- Keeps `Main Base` as an extra gameplay site

Current gameplay site result:

- `Firewatch Station`
- `Spear Point Base`
- `Main Base`

Notably filtered out of gameplay because they fall outside the active arena:

- `Meridia (Capital Y)`
- `Southern Redoubt`
- `Callhaven`
- `Solano`

That means visual landmarks and gameplay sites are not currently the same set.

## Coordinate Systems

### Saab source space

- units: kilometers
- `x`: east-positive
- `y`: south-positive

### World runtime space

- units: meters
- `x`: east-positive
- `y`: north-positive
- `z`: up-positive

### Scene render space

- units: kilometers after `SCALE = 0.001`
- `x`: east-positive
- `y`: up-positive
- `z`: south-positive

### Shared anchor

The live transform is anchored around the Blue base:

```text
BLUE_BASE_POS = (75_000, 5_000, 0)
```

This anchor is hard-coded in the frontend and backend transform math.

## Practical Workflow For Sebastijan

If the terrain source or map geometry changes, the safe order is:

1. Update the canonical source file under `common-info/source-data/`.
2. Update provenance in `common-info/ACTIVE_SOURCE_DATA_INDEX.md` if a new
   source file is introduced.
3. Regenerate or hand-update `frontend/js/terrain_data.js`.
4. Verify `backend/sim/terrain.py` still parses and validates land correctly.
5. Verify `backend/sim/sites.py` still places intended gameplay sites.
6. Verify launcher positions still pass land assertions.
7. Run the demo and visually confirm terrain, landmarks, and site markers.

## Current Risks

- Transform logic is duplicated across `scene.js`, `terrain.py`, and
  `sites.py`.
- `terrain_data.js` is a baked snapshot, so it can drift from the canonical
  CSV.
- Visual landmarks include locations that gameplay currently filters out.
- Terrain is stylized and flat; there is no reusable terrain asset pipeline
  yet.

## Recommended Long-Term Home

Once the repo is ready for physical modularization, the terrain pipeline should
converge so that:

- canonical external inputs stay under `common-info/source-data/`
- generated terrain derivatives live under `maps/`
- map transform logic has one clearly owned implementation path
- frontend and backend stop carrying silently duplicated geometry logic
