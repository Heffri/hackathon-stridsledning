# Missile Intercept: AI vs AI — Full Implementation Plan

> ⚠️ **This document describes the full final product vision.**
> For the current scope we're building first (simplified playable MVP),
> see **[DEMO_PLAN.md](DEMO_PLAN.md)**.

## Context

Building a 3D missile intercept simulation for the Saab hackathon (April 25). Red AI launches threats, Blue AI selects and guides interceptors using real physics (proportional navigation, not dice rolls). This plan covers the complete vision with all systems (HP, fuel, magazines, terrain, economy). We build it incrementally, starting with the demo scope.

## Related Documents

- **[DEMO_PLAN.md](DEMO_PLAN.md)** — the simplified Milestone B scope we're building first
- **[GAME_DESIGN.md](GAME_DESIGN.md)** — full mechanics (control levels, fuel, HP/damage, magazine, terrain, economy)
- **[WEAPON_SPECS.md](WEAPON_SPECS.md)** — complete weapon parameters (performance, damage, economy, costs)

## Architecture

```
team-missile-intercept/
├── backend/
│   ├── requirements.txt        # fastapi, uvicorn, numpy, scipy (optional)
│   ├── server.py               # FastAPI + WebSocket, sim loop
│   ├── sim/
│   │   ├── __init__.py
│   │   ├── config.py           # All tunable parameters (HP, budgets, scaling)
│   │   ├── types.py            # Dataclasses, enums, weapon spec tables
│   │   ├── physics.py          # 3D kinematics, PN guidance, drag, gravity, speed bleed
│   │   ├── terrain.py          # Heightmap, ground collision, bilinear interpolation
│   │   ├── entities.py         # Missile/threat classes with HP, fuel, magazine state
│   │   ├── launcher.py         # Launcher (magazine + reload CD) for both sides
│   │   ├── world.py            # SimulationWorld: tick loop, collision, HP/damage
│   │   ├── red_ai.py           # 5-tier control (pre-programmed → real-time HGV)
│   │   ├── blue_ai.py          # Threat assessment, weapon selection, real-time guidance
│   │   └── scenarios.py        # Demo scenario definitions + budgets
│
├── frontend/
│   ├── index.html              # Single page, Three.js from CDN
│   ├── style.css               # HUD styling
│   └── js/
│       ├── main.js             # WebSocket client, app state, controls
│       ├── scene.js            # Three.js scene, camera, lighting
│       ├── terrain.js          # Heightmap terrain rendering (displacement map)
│       ├── entities.js         # 3D meshes for missiles, trails, explosions
│       ├── status.js           # Per-entity status panel (fuel/speed/G/HP)
│       └── hud.js              # Score, ammo, AI decision log, speed slider
```

## Core Physics

- **Coordinate system**: X=east, Y=north, Z=up, meters
- **Arena**: 150km x 150km x 40km. Red spawns north, Blue defends south
- **Timestep**: dt=0.05s, WebSocket at 15fps
- **Gravity**: -9.81 m/s^2 on Z
- **Drag**: Simplified quadratic with exponential atmosphere model
- **Guidance**: True Proportional Navigation (N=4) for all interceptors
- **Kill check**: Closest approach distance < kill_radius (no probability dice rolls)

## Weapon Specs

See **[WEAPON_SPECS.md](WEAPON_SPECS.md)** for full data with real-world analogs, USD pricing, and sources.

### Red Arsenal (Threats)

| Type | Real Analog | Speed | Max G | USD/Unit |
|------|-------------|-------|-------|----------|
| Suicide drone | Shahed-136 | 45 m/s | 2G | ~$30K |
| Subsonic cruise missile | Kalibr-class | 260 m/s | 2G | ~$1.5M |
| Supersonic cruise missile | BrahMos-class | 900 m/s | 4G | ~$3M |
| Ballistic missile (terminal) | Iskander SRBM | 2,000 m/s | 1G | ~$3M |
| Hypersonic glide vehicle | Kinzhal/DF-ZF | 1,700 m/s | 8G | ~$10M |

### Blue Arsenal (Interceptors)

| Type | Real Analog | Speed | Max G | Range | USD/Shot |
|------|-------------|-------|-------|-------|----------|
| CIWS | Lvkv 90 (Bofors 3P) | 1,000 m/s | N/A | 4 km | ~$2K |
| Short-range SAM | RBS 70 NG (Saab) | 680 m/s | 20G | 9 km | ~$175K |
| Medium-range SAM | IRIS-T SLM | 1,020 m/s | 40G | 40 km | ~$500K |
| Long-range SAM | Patriot PAC-2 GEM+ | 1,700 m/s | 25G | 70 km | ~$3M |
| Hit-to-kill | Patriot PAC-3 MSE | 1,700 m/s | 50G | 60 km | ~$4M |

### Blue Ammo Budget

| Type | Count | Total Value |
|------|-------|-------------|
| CIWS bursts | 14 | ~$28K |
| Short-range SAM | 16 | ~$2.8M |
| Medium-range SAM | 12 | ~$6M |
| Long-range SAM | 4 | ~$12M |
| Hit-to-kill | 2 | ~$8M |
| **Total** | **48** | **~$28.8M** |

Limited ammo forces the Blue AI to make cost-efficient decisions. The AI computes real-time cost-exchange ratios (interceptor cost / threat cost) and refuses to fire Patriot ($4M) at a drone ($30K). See WEAPON_SPECS.md for full cost matrix.

## Blue AI Decision Logic

1. Each tick: scan active threats without assignments
2. Assess each threat: type, speed, trajectory, time-to-impact, altitude
3. Select interceptor: minimize (cost / effectiveness), where effectiveness = speed_ratio * maneuverability_ratio * kill_radius_factor
4. Launch timing: when threat enters 1.1x interceptor max range
5. **Key insight**: The AI recommending "don't shoot" (or "use a cheaper option") is smarter than always firing the best weapon

## Demo Scenario (5 waves)

| Wave | Time | Threats | Challenge |
|------|------|---------|-----------|
| 1 | T+2s | 3x scout drones | Easy warmup — CIWS/short SAM |
| 2 | T+30s | 2x subsonic cruise missiles | Medium SAM territory |
| 3 | T+60s | 5x drones + 1x supersonic cruise | Tests prioritization |
| 4 | T+100s | 1x ballistic + 4x distraction drones | Forces long SAM/HTK use |
| 5 | T+140s | 1x hypersonic + 2x supersonic + 3x subsonic + 8x drones | Full assault |

## WebSocket Protocol

Server sends full state snapshots (all entities + events + score + ammo) at 15fps as JSON. Client sends control commands (start/pause/speed/reset). No delta compression needed at <100 entities.

## Implementation Phases

### Phase 1: Backend core physics
- `config.py`: all tunable parameters in one place
- `types.py`: dataclasses, enums, weapon spec tables with HP/damage/fuel/magazine
- `physics.py`: PN guidance, gravity, drag, Euler integration, **speed bleed from G**
- `terrain.py`: heightmap load, bilinear interpolation, ground collision check
- `entities.py`: Missile/Threat classes with HP, fuel, status
- `launcher.py`: Launcher magazine + reload CD

### Phase 2: World + Red AI + server
- `world.py`: tick loop, collision detection, HP/damage resolution
- `red_ai.py`: 5-tier control — pre-programmed, waypoint-adjustable, terminal-takeover, real-time
- `scenarios.py`: demo scenario + initial budgets
- `server.py`: FastAPI + WebSocket streaming state JSON

### Phase 3: Frontend basics
- `index.html` + `scene.js`: Three.js scene, orbital camera, lighting
- `terrain.js`: heightmap terrain rendering (displacement map)
- `entities.js`: 3D meshes, trails, explosions
- `main.js`: WebSocket client, state parsing
- **Milestone: threats visibly fly across 3D terrain**

### Phase 4: Blue AI + real-time guidance
- `blue_ai.py`: threat assessment, cost-exchange + HP math, weapon selection
- Real-time guidance per in-flight interceptor (PN for all SAMs, ballistic prediction for CIWS)
- Magazine + reload enforcement
- **Milestone: full intercept loop with HP, damage, fuel, reload working**

### Phase 5: HUD + status display
- `status.js`: per-entity panel (fuel/speed/G/HP)
- `hud.js`: score, base HP, budgets, ammo, AI decision log
- Speed slider (0.5x / 1x / 2x / 5x / 10x)
- Trajectory trails, explosion effects

### Phase 6: Tuning & polish
- Balance playtesting: budget ratios, HP values, damage numbers, speed bleed coefficients
- Scenario composition
- Camera presets, visual polish
- Red AI intelligence: smart waypoint planning, HGV evasion tactics

## How to Run

```bash
cd backend
pip install -r requirements.txt
python server.py
# Open http://localhost:8000
```
