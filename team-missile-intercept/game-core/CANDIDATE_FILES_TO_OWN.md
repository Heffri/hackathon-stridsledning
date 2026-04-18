# Candidate Files Chen Should Own Now

This list is about ownership, not file moves. The code stays where it is for now.

## Primary Ownership Now

These files are already functioning as base game logic and should be treated as Chen's primary ownership set:

| File | Why it belongs to Chen now |
|---|---|
| `backend/sim/scenarios.py` | Owns scenario assembly, step order, winner resolution, and published snapshot contract |
| `backend/sim/world.py` | Owns world tick, hit resolution, leak accounting, site damage, budget stats, and event emission |
| `backend/sim/config.py` | Owns runtime tuning and gameplay constants such as speed limits, site HP, leak damage, budget start, and launcher placements |
| `backend/sim/launcher.py` | Owns launcher magazines, reloads, launcher placement state, and launcher status contract |
| `backend/sim/sites.py` | Owns the active site registry, HP reset behavior, and targetable Blue-side locations |
| `backend/sim/types.py` | Owns core enums, wire-format names, entity snapshot shape, and gameplay spec tables |

## Integration Shell Files Chen Should Review

These files are still shells, but Chen should be the default reviewer whenever their behavior changes because they expose or consume game-core contracts:

| File | Why Chen should review it |
|---|---|
| `backend/server.py` | It is the backend composition root for scenario lifecycle and control commands |
| `frontend/js/main.js` | It is the frontend composition root for snapshot consumption |
| `frontend/js/hud.js` | It renders game-core-owned stats, site HP, budget, ammo state, and winner state |
| `frontend/index.html` | It defines the shell slots for HUD controls, overlays, and status blocks tied to game-core state |
| `frontend/style.css` | It styles game-core-driven HUD states such as budget, site HP, and match outcome |

## Shared-Boundary Candidate

This file is not a clean single-owner case yet, but Chen should treat it as a near-term boundary to formalize:

| File | Why it matters |
|---|---|
| `backend/sim/entities.py` | It contains threat and interceptor step behavior plus `Threat.override_maneuver`, which is a game-core lifecycle hook consumed by Red AI and constrained by physics |

## Explicitly Not Chen's Primary Ownership

These files should not be treated as Chen-owned game-core files unless the module boundaries change later:

| File or area | Primary owner instead |
|---|---|
| `backend/sim/blue_ai.py` | Blue AI owners |
| `backend/sim/red_ai.py` | Red AI owners |
| `backend/sim/terrain.py` | Maps owner |
| `backend/sim/physics.py` | Math-validation owner for correctness sign-off |
| `frontend/js/scene.js`, `frontend/js/entities.js`, `frontend/js/launchers.js`, `frontend/js/sites.js` | Maps/models/frontend presentation owners, with Chen review if contracts change |

## Practical Rule For Current Sessions

If a task changes:

- match flow
- site HP or budget logic
- launcher placement data or ammo lifecycle
- snapshot keys or event shape
- speed-control semantics
- deployment-phase behavior

then Chen should be the primary owner or required reviewer even if the edited file still sits under `backend/` or `frontend/`.
