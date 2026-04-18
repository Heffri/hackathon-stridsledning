# Current Visual Inventory

This inventory separates what currently exists in the demo from what is still
missing, and it explicitly marks each item as procedural, source-driven, or
not yet present as an imported asset.

## High-Level Summary

- Imported runtime model files: none
- Imported runtime texture files: none
- Runtime-generated canvas textures: yes
- Procedural Three.js geometry: most of the active visual stack
- Source-driven procedural visuals: terrain and landmark placement

## Entity Mesh Inventory

| Kind | Team | Current visual form | Source type | Runtime file |
|---|---|---|---|---|
| `drone` | Red | Flat delta-wing body with rear propeller disc | Procedural | `frontend/js/entities.js` |
| `cruise_sub` | Red | Slender cruise missile with mid-wings and cruciform tail | Procedural | `frontend/js/entities.js` |
| `ballistic` | Red | Larger reentry body with pointed nose and 4 tail fins | Procedural | `frontend/js/entities.js` |
| `hgv` | Red | Dart-like hypersonic glide body with dorsal and side fins | Procedural | `frontend/js/entities.js` |
| `ciws` | Blue | Stubby cannon shell, no flame | Procedural | `frontend/js/entities.js` |
| `rbs_70` | Blue | Compact MANPADS-style missile with canards and rear fins | Procedural | `frontend/js/entities.js` |
| `iris_t_sls` | Blue | IRIS-T-style missile with seeker dome, bands, canards, tail fins | Procedural | `frontend/js/entities.js` |
| `iris_t_slm` | Blue | Longer orange IRIS-T variant with pointed nose | Procedural | `frontend/js/entities.js` |
| `pac_2` | Blue | Long pink missile with tail fins only | Procedural | `frontend/js/entities.js` |
| `pac_3` | Blue | Compact purple hit-to-kill missile with ACM ring | Procedural | `frontend/js/entities.js` |

## Launcher And Site Visuals

| Visual element | Current count/state | Source type | Runtime file | Notes |
|---|---|---|---|---|
| Blue launcher boxes | 9 instances | Procedural | `frontend/js/launchers.js` | One `THREE.Group` per launcher |
| Blue launcher range rings | 9 instances | Procedural | `frontend/js/launchers.js` | Full-circle rings, dim on reload |
| Red launcher boxes | 5 instances | Procedural | `frontend/js/launchers.js` | No range rings |
| Gameplay site rings | 3 current in-arena site markers | Procedural | `frontend/js/sites.js` | `Firewatch Station`, `Spear Point Base`, `Main Base` |
| Site leak badges | Runtime-created when needed | Procedural plus runtime canvas texture | `frontend/js/sites.js` | Only visible when leaks > 0 |

## Terrain And Landmark Visuals

| Visual element | Current count/state | Source type | Runtime file | Notes |
|---|---|---|---|---|
| Terrain landmasses | 8 polygons | Source-driven procedural | `frontend/js/terrain_data.js`, `frontend/js/scene.js` | Extruded from baked polygon constants |
| Named landmarks | 12 locations | Source-driven procedural | `frontend/js/terrain_data.js`, `frontend/js/scene.js` | All 12 visual locations render |
| `air_base` landmarks | Runway + tower kit | Source-driven procedural | `frontend/js/scene.js` | Built from boxes |
| `capital` landmarks | 5-box skyline kit | Source-driven procedural | `frontend/js/scene.js` | Built from boxes |
| `major_city` landmarks | 3-box cluster kit | Source-driven procedural | `frontend/js/scene.js` | Built from boxes |
| Landmark labels | 12 runtime sprite labels | Source-driven procedural plus runtime canvas texture | `frontend/js/scene.js` | Labels always face the camera |

Important mismatch:

- The scene renders 12 visual landmarks.
- The gameplay target model currently uses only 3 in-arena sites plus the
  base marker logic from the backend snapshot.

## Effects And Presentation Layer

| Visual element | Source type | Runtime file | Notes |
|---|---|---|---|
| Exhaust plumes | Procedural | `frontend/js/entities.js` | Visible only while thrust is active |
| Seeker cones | Procedural | `frontend/js/entities.js` | Shifts cyan to orange near lock |
| Trails | Procedural | `frontend/js/entities.js` | Dynamic line geometry |
| Explosions | Procedural | `frontend/js/entities.js` | Additive white sphere flash |
| Dusk skydome | Procedural shader | `frontend/js/scene.js` | No sky texture file |
| Sea plane | Procedural | `frontend/js/scene.js` | Flat material |
| Grid | Procedural | `frontend/js/scene.js` | Rectangular custom grid |

## What Is Not Present Yet

| Missing asset class | Current state |
|---|---|
| `.glb` / `.gltf` runtime models | Not present |
| Imported texture atlas or image-driven materials | Not present |
| Dedicated terrain mesh export pipeline | Not present |
| Dedicated city/building asset library | Not present |
| Dedicated vehicle launcher asset pack | Not present |

## Practical Interpretation For Sebastijan

Today, the live visual language is "procedural shapes with careful silhouette
design." If Sebastijan wants to improve fidelity, the first decision is not
"which model file do we tweak," but "which visual classes should remain
procedural and which should graduate into imported assets."
