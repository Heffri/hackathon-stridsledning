# Current Runtime Map

## Transitional Reality

`backend/` and `frontend/` are still the runnable shells. Game-core ownership is logical first, physical later.

The current live flow is:

1. `backend/server.py` builds the scenario and accepts control commands.
2. `Scenario.step()` orchestrates Red AI, Blue AI, then the world tick.
3. `World.step()` mutates gameplay state, resolves hits and leaks, and records events.
4. `Scenario.snapshot()` publishes the stable runtime state contract.
5. `frontend/js/main.js` fans that snapshot into scene registries, HUD, and status panel.

## Ownership Map

| Current file | Current runtime role | Game-core ownership status | Notes |
|---|---|---|---|
| `backend/server.py` | Thin backend composition root | Integration shell under Chen review | Should stay thin; do not grow gameplay rules here |
| `backend/sim/scenarios.py` | Scenario assembly, step order, winner, done, snapshot | Primary game-core file | Main authority for match lifecycle |
| `backend/sim/world.py` | World tick, collisions, leaks, stats, event log, budget | Primary game-core file | Main authority for playable-state mutation |
| `backend/sim/config.py` | Runtime tuning, caps, launcher placements, budget and site damage values | Primary game-core file for gameplay/tuning sections | Map-coupled placement values still require map collaboration |
| `backend/sim/launcher.py` | Blue and Red launcher state, ammo, reload, placement shape | Primary game-core file | Key future seam for deployment phase |
| `backend/sim/sites.py` | Active Blue-side site registry, HP reset, targetable site data | Primary game-core file | Site list is a stable contract for AI and HUD |
| `backend/sim/types.py` | Enums, entity state, spec tables, wave spec | Primary game-core file | Wire-format values live here |
| `backend/sim/entities.py` | Threat/interceptor step logic and HGV override hook | Shared boundary; likely future game-core seam | Needs coordination with math-validation because physics and lifecycle meet here |
| `backend/sim/blue_ai.py` | Blue-side engagement decisions | AI-owned consumer of game-core | Should consume game-core contracts, not own them |
| `backend/sim/red_ai.py` | Red-side wave spawning and target choice | AI-owned consumer of game-core | Uses game-core sites, world, launchers, and HGV hook |
| `frontend/index.html` | Page shell and HUD slots | Frontend shell under Chen review for contract changes | UI structure only |
| `frontend/style.css` | HUD and overlay presentation | Frontend shell under Chen review for contract changes | Visual ownership, not gameplay ownership |
| `frontend/js/hud.js` | Renders stats, site HP, budget, winner, ammo, logs | Frontend shell that consumes game-core contracts | Data semantics belong to Chen |
| `frontend/js/main.js` | Frontend composition root | Integration shell under Chen review | Should stay thin |

## Stable Snapshot Surface

The current snapshot contract published by `Scenario.snapshot()` and `server.py` is the most important stable surface between game-core and the runtime shells.

Active keys today:

- `t`
- `entities`
- `explosions`
- `events`
- `stats`
- `wave`
- `total_waves`
- `red_log`
- `blue_log`
- `ammo`
- `launchers`
- `red_launchers`
- `sites`
- `winner`
- `max_sim_time`
- `running`
- `speed`

## Stable Control Surface

The current command surface from the frontend into the backend shell is:

- `start`
- `pause`
- `reset`
- `speed`

Game-core owns the semantics behind those commands even though `server.py` currently receives them.

## AI-Facing Runtime Surface

The current AI plug-in surface is effectively:

- `RedAI.step(t_now, world)`
- `BlueAI.step(t_now, world)`
- `world.spawn_threat(...)`
- `world.spawn_interceptor(...)`
- `world.threats`
- `world.interceptors`
- `world.events`
- `sites.SOUTH_SITES`
- `Threat.override_maneuver(turn_dir, g_load)`

Future extraction work should preserve these behaviors through wrappers or adapters before any deep move.

## Keep Runnable Rule

Until wrappers exist, treat these as protected seams:

- `build_default_scenario()`
- `Scenario.step()`
- `Scenario.snapshot()`
- `backend/server.py`
- `frontend/js/main.js`

If game-core evolves, the old runnable entry points must keep working.
