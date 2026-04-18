# Pipeline Notes

## Current Model Pipeline

The active project does not have a separate art import pipeline yet.

Current flow:

1. Backend snapshot emits entity `kind`, `team`, position, velocity, and
   state.
2. `frontend/js/entities.js` selects a procedural mesh in `buildModel()`.
3. `EntityMesh.update()` orients the root group to the velocity vector.
4. Optional runtime-generated presentation layers attach on top:
   - exhaust plume
   - seeker cone
   - trail
   - explosion flash

Parallel visual pipelines:

- `frontend/js/launchers.js` builds launcher boxes and range rings.
- `frontend/js/sites.js` builds site rings and leak badges.
- `frontend/js/scene.js` builds terrain, landmarks, sea, grid, and sky.

## Current Conventions

### Mesh-forward axis

The live code assumes every entity model points along local `+Y`.

That convention is important because the generic orientation code does this:

- start with local up vector `(0, 1, 0)`
- rotate the mesh so `+Y` matches velocity direction

If Sebastijan introduces imported models later, the easiest path is to export
them with the same "nose forward = local +Y" convention.

### Fin and wing convention

`NOTES_MODEL_AND_PORT.md` documents the current geometry convention for
four-fin bodies:

- `X` = radial extent
- `Y` = chord along the body
- `Z` = tangential thickness

That note is worth keeping because it prevents the common "square sleeve"
mistake when building fins from boxes.

### Labels and simple textures

The current project uses runtime `CanvasTexture` generation for:

- terrain landmark labels
- site leak badges

There are no imported image textures in the active runtime.

## Practical Boundaries

Sebastijan owns the presentation layer, but some changes still need Chen:

| Change type | Safe for Sebastijan alone? | Why |
|---|---|---|
| Improve mesh silhouette without changing runtime contracts | Usually yes | Presentation-only |
| Replace procedural landmark kit with better visual kit | Usually yes | Still visual, as long as coordinates stay consistent |
| Change launcher/site positions | No | Affects gameplay geography and balance |
| Change map crop, transform, or site list | No | Affects runtime assumptions |
| Introduce new runtime asset loading path | Coordinate first | Touches integration and packaging |

## Recommended Future File Homes

These directories are recommendations for the next asset phase. They are not
created in this session.

| Future asset type | Recommended home |
|---|---|
| Raw art inputs, concept exports, source meshes | `team-missile-intercept/models/` |
| Runtime-ready `.glb` or `.gltf` exports | `team-missile-intercept/models/` |
| Texture, decal, and material assets | `team-missile-intercept/models/` |
| Asset naming guides, scale sheets, and visual standards | `team-missile-intercept/models/` |
| Raw terrain or map reference inputs from outside the repo | `team-missile-intercept/common-info/source-data/` |
| Map-owned generated terrain derivatives | `team-missile-intercept/maps/` |

Practical split:

- `common-info/source-data/` for provenance-controlled external inputs
- `maps/` for terrain/map-owned derivatives and docs
- `models/` for owned visual assets, packaging notes, and runtime-ready model
  files

## Risks To Carry Forward

| Risk | Why it matters |
|---|---|
| No asset loader pipeline yet | Imported models will need a packaging decision before they can ship cleanly |
| Procedural and source-driven visuals are mixed in code | Ownership is clear, but implementation is still scattered across `frontend/js/` |
| Terrain transform logic is duplicated outside `models/` | Visual and gameplay geography can drift |
| Visual landmarks and gameplay sites are not the same set | A prettier city model alone will not automatically change gameplay targets |

## Best Next Step

Before building new assets, Sebastijan should decide which classes stay
procedural and which classes should become imported assets first:

- landmarks
- launcher pads
- SAM batteries
- missile/threat bodies
- terrain shell

That decision will keep the first real `models/` cutover small and controlled.
