# Models Ownership Package

This folder is Sebastijan's documentation home for `models/` ownership in the
active `team-missile-intercept/` project.

## What Sebastijan Owns

- 3D entity presentation
- Launcher, site, landmark, and terrain-facing visual packaging
- Model quality, silhouette clarity, material direction, and asset packaging
- Future imported model and texture pipeline decisions

Per `common-info/TEAM_OWNERSHIP_SPEC.md`, Sebastijan is the primary owner for
`models/`. Chen is the required collaborator when a visual change also changes
runtime contracts, geography, or gameplay assumptions.

## Current Runtime Reality

There is no imported model pipeline in the active project yet.

Today's runtime visuals are built mainly from procedural Three.js geometry in:

- `frontend/js/entities.js`
- `frontend/js/launchers.js`
- `frontend/js/sites.js`
- `frontend/js/scene.js`

The only active external visual/map source files in the repo are the Saab CSV
and SVG under `common-info/source-data/saab-provided/`.

## Read Order

1. `models/CURRENT_VISUAL_INVENTORY.md`
2. `models/PIPELINE_NOTES.md`
3. `models/TASKS_FOR_SEBASTIJAN.md`
4. `frontend/js/entities.js`
5. `frontend/js/launchers.js`
6. `frontend/js/sites.js`
7. `frontend/js/scene.js`

## Ownership Map

| Area | Primary owner | Current runtime touchpoints | Review needed |
|---|---|---|---|
| Threat and interceptor meshes | Sebastijan | `frontend/js/entities.js` | Chen if runtime kind contracts change |
| Launcher and site visuals | Sebastijan | `frontend/js/launchers.js`, `frontend/js/sites.js` | Chen if placement/gameplay contracts change |
| Terrain-facing landmark visuals | Sebastijan | `frontend/js/scene.js`, `frontend/js/terrain_data.js` | Chen if geography changes |
| Future imported model packaging | Sebastijan | `models/` | Chen for integration plan |

## Recommended Future File Homes

- Raw concept art, vendor references, and model inputs:
  `team-missile-intercept/models/`
- Runtime-ready exported model files:
  `team-missile-intercept/models/`
- Texture, decal, and material assets:
  `team-missile-intercept/models/`
- Third-party raw source copies that need provenance:
  `team-missile-intercept/common-info/source-data/`

Practical rule: provenance-first source copies live in
`common-info/source-data/`; visual assets owned and maintained by Sebastijan
should live under `models/`.

## Key Takeaways

- The current demo uses code-built procedural meshes, not imported `.glb` or
  `.gltf` assets.
- Runtime label textures are generated with `CanvasTexture` at runtime.
- Terrain visuals are source-driven, but still generated procedurally in
  `scene.js`.
- `models/` is the right place to define the next asset pipeline before any
  runtime move happens.
