# Missile Intercept: AI vs AI — Implementation Plan

## Context

Building a 3D missile intercept simulation for the Saab hackathon (April 25). Red AI launches threats, Blue AI selects and guides interceptors using real physics (proportional navigation, not dice rolls). We need to build the entire system from scratch.

## Architecture

```
team-missile-intercept/
├── backend/
│   ├── requirements.txt        # fastapi, uvicorn, numpy
│   ├── server.py               # FastAPI + WebSocket, sim loop
│   ├── sim/
│   │   ├── __init__.py
│   │   ├── types.py            # Dataclasses, enums, weapon spec tables
│   │   ├── physics.py          # 3D kinematics, PN guidance, drag, gravity
│   │   ├── world.py            # SimulationWorld: tick loop, collision detection
│   │   ├── red_ai.py           # Wave spawner + threat flight behavior
│   │   ├── blue_ai.py          # Threat assessment, interceptor selection, launch timing
│   │   └── scenarios.py        # 5-wave demo scenario definitions
│
├── frontend/
│   ├── index.html              # Single page, Three.js from CDN
│   ├── style.css               # HUD styling
│   └── js/
│       ├── main.js             # WebSocket client, app state, controls
│       ├── scene.js            # Three.js scene, camera, ground, lighting
│       ├── entities.js         # 3D meshes for missiles, trails, explosions
│       └── hud.js              # Score, ammo, wave info, AI decision log
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

### Phase 1: Backend core (types.py, physics.py, world.py)
- All dataclasses and weapon spec tables
- Proportional navigation guidance, gravity, drag, Euler integration
- SimulationWorld with step loop, entity management, kill detection

### Phase 2: Red AI + server (red_ai.py, scenarios.py, server.py)
- Wave spawner with 5-wave demo scenario
- Threats fly toward defended target
- FastAPI + WebSocket streaming state JSON

### Phase 3: Frontend basics (scene.js, entities.js, main.js, index.html)
- Three.js scene with ground plane, orbital camera
- WebSocket client parsing state frames
- Red cones moving across 3D map
- **Milestone: red threats visibly fly across screen**

### Phase 4: Blue AI + intercepts (blue_ai.py)
- Threat assessment and cost-optimal interceptor selection
- Launch timing and PN-guided intercept
- Intercept/impact event handling
- **Milestone: full intercept loop working**

### Phase 5: HUD + polish (hud.js, style.css)
- Score panel, ammo bars, wave announcements
- AI decision log showing Blue AI reasoning
- Trajectory trails, explosion effects
- Start/pause/speed controls

### Phase 6: Tuning
- Physics parameters (drag coefficients, speed, G-limits)
- Scenario wave timing and composition
- Camera presets (overview, follow mode)
- Visual polish

## How to Run

```bash
cd backend
pip install -r requirements.txt
python server.py
# Open http://localhost:8000
```
