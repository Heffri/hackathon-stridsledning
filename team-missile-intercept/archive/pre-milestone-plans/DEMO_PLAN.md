# Demo Plan — Milestone B (Playable MVP)

> **This is the simplified scope for our first internal team demo.**
> For the full final product vision, see [PLAN.md](PLAN.md), [GAME_DESIGN.md](GAME_DESIGN.md), and [WEAPON_SPECS.md](WEAPON_SPECS.md).

## Purpose

A minimal working prototype that demonstrates the core concept — Red AI launching threats, Blue AI intercepting them with physics-based proportional navigation — so the team can see it running and iterate on it.

This is **deliberately stripped down**. We defer all depth features (HP, fuel, magazines, terrain, economy) until after the core loop is proven.

## What You See When You Run It

1. A 3D scene opens in the browser: blue sky, flat grid ground, defended position marker at south center
2. Red cones (threats) spawn from the north edge at scripted wave times
3. Yellow cones (interceptors) auto-launch from the south when threats come into range
4. Interceptors fly curved trajectories (proportional navigation guidance) toward threats
5. White explosion bursts appear on successful intercepts
6. HUD shows: current wave, intercept count, threats remaining
7. Simple controls: Start / Pause / speed slider (0.5x / 1x / 2x / 5x)

That's it. No score screens, no win conditions, no ammo depletion — just a watchable AI vs AI loop.

## What's Included

### Physics
- 3D kinematics (position, velocity, acceleration in numpy)
- Gravity (-9.81 m/s² on Z)
- Simplified drag (quadratic, constant coefficient)
- **True Proportional Navigation** (N=4) guidance for interceptors
- Euler integration at dt=0.05s

### Weapons (simplified subset)

**Red threats:**
- Suicide drone (Shahed) — 45 m/s, low altitude, straight-line flight
- Subsonic cruise missile (Kalibr) — 260 m/s, low altitude, straight-line flight

**Blue interceptors:**
- CIWS (for close-range drones) — instant ballistic
- Short-range SAM (RBS 70 analog) — Mach 2, 9 km
- Medium-range SAM (IRIS-T SLM analog) — Mach 3, 40 km

### AI

**Red AI:** Scripted wave spawner — launches predetermined threats at predetermined times. No mid-flight maneuvering yet.

**Blue AI:** Rule-based weapon selection:
- Drone → CIWS or RBS 70
- Cruise missile → IRIS-T SLM
- Launches when threat enters max range
- PN guidance from launch to intercept or miss

### Kill Detection
- Binary: closest approach distance < kill_radius → hit
- No HP, no damage values, just hit/miss

### Visualization
- Three.js scene loaded from CDN (no build tools)
- Flat ground plane with grid texture
- Simple geometric entities (cones for missiles)
- Trail lines behind each entity (last ~50 positions)
- Explosion effect: white sphere that scales up and fades
- Orbital camera controls

## What's Deliberately NOT Included

| Feature | Why deferred |
|---------|--------------|
| HP & damage system | Binary kill works for core loop, add depth later |
| Fuel timer | Let missiles fly freely for now |
| Magazine & reload CD | Unlimited ammo for first demo |
| Terrain heightmap | Flat ground is easier and still looks fine |
| Economy / base HP / budgets | No win/loss mechanic needed yet |
| Stealth cruise, HGV, ballistic | 3 weapon types is enough to show the pattern |
| Red AI levels 2-5 | Straight-line flight is fine for first demo |
| Waypoint adjustment / terminal takeover | Level 1 only (pre-programmed) |
| Per-entity status panel (fuel/G/speed/HP) | Nice-to-have, not core |
| AI decision log panel | Nice-to-have, not core |
| Seeker scanning cone visual | Polish, add after core works |
| Cost-exchange calculation | Blue AI uses simple rules, no cost math yet |

All of these are in the full spec and will be added in subsequent sessions. They are deferred, not abandoned.

## Simplified File Structure

```
team-missile-intercept/
├── backend/
│   ├── requirements.txt        # fastapi, uvicorn, numpy
│   ├── server.py               # FastAPI + WebSocket
│   └── sim/
│       ├── __init__.py
│       ├── config.py           # Tunable parameters
│       ├── types.py            # Dataclasses (simple — no HP/fuel yet)
│       ├── physics.py          # PN guidance, gravity, drag, integration
│       ├── entities.py         # Threat & Interceptor classes
│       ├── world.py            # Tick loop, collision detection (binary)
│       ├── red_ai.py           # Scripted wave spawner
│       ├── blue_ai.py          # Rule-based weapon selection + PN guidance
│       └── scenarios.py        # 3-5 wave demo scenario
│
└── frontend/
    ├── index.html              # Single page, Three.js from CDN
    ├── style.css               # HUD styling
    └── js/
        ├── main.js             # WebSocket client + app state
        ├── scene.js            # Three.js scene, camera, ground plane
        ├── entities.js         # 3D meshes, trails, explosions
        └── hud.js              # Score, controls, speed slider
```

10 backend files + 4 frontend files. No terrain.js, no status.js, no launcher.py — those come later.

## How to Run (once built)

```bash
cd team-missile-intercept/backend
pip install -r requirements.txt
python server.py

# Then open http://localhost:8000 in a browser
```

## What Good Looks Like

After starting, within 15 seconds you should see:
- T+2s: 3 red drones spawn from north edge
- T+5s: Yellow interceptors launch from south, visible curved trajectories
- T+8-12s: White explosion bursts, drone count drops
- T+30s: Second wave (cruise missiles) spawns
- Continues through scripted waves

Frame rate should be smooth (60 fps rendering, 20 Hz physics on backend).

## Next Steps After Demo Works

Priority order for adding depth (full vision in [PLAN.md](PLAN.md)):

1. **Explosion + trail polish** — make intercepts look good
2. **HP & damage system** — replace binary kill, enables multi-hit tactics
3. **Magazine & reload** — force tactical choices about ammo
4. **Terrain heightmap** — enables terrain-following cruise missiles
5. **Remaining weapon types** — stealth cruise, ballistic, HGV, IRIS-T SLS, PAC-2/PAC-3
6. **Red AI levels 2-5** — waypoint adjustment, terminal takeover, real-time HGV control
7. **Economy & win conditions** — makes the sim a real game
8. **Per-entity status HUD + decision log** — transparency for demo judges

Each of these is self-contained and can be added without rewriting the core. That's why we start with the minimal loop.
