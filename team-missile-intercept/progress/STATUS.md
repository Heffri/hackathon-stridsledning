# Project Status

> **Last updated:** 2026-04-17
> **Branch:** `knowledge-base` (all work pushed here)
> **Latest commit:** `763bce5` (REPORT.md translated to English)

## Where We Are: Milestone C Patch — Complete

Everything through Milestone C Patch is implemented, tested, and pushed. The simulation is playable end-to-end with:

- 6 threat types (drone, subsonic cruise, ballistic, HGV + the framework for supersonic/stealth)
- 5 interceptor types (CIWS, RBS 70, IRIS-T SLM, PAC-2 GEM+, PAC-3 MSE)
- HP + damage model (direct hit vs proximity, linear falloff)
- Magazine + reload CDs per launcher (cost-exchange greedy Blue AI)
- 3D battlefield with clear altitude tiering (drone 0.5-4 km, cruise 1-6 km, HGV/ballistic 25-40 km)
- VLS vertical launch profile, cruise terminal pop-up, HGV pursuit waypoints
- Unified ground-collision sweep (no more bouncing entities)
- Real-time WebSocket + Three.js rendering at 15 fps
- Launch banner showing real weapon names (Lvkv 90 / RBS 70 NG / IRIS-T SLM / Patriot PAC-2 / Patriot PAC-3)
- HUD ammo panel with reload countdowns

## Current Balance (test_balance.py, 20 matches)

```
Blue win 12/20, draw 5/20, Red win 3/20
avg leaks 1.6 per run, leak range 0..4
HGV kill rate 58%, ballistic kill rate ~65%
```

Every match leaks at least something — no more 100% Blue win rate. Good enough for demo drama.

## Commit History (recent)

```
763bce5  Translate REPORT.md to English for team readability
2b4a368  REPORT: append Milestone C Patch summary
ec584b7  Patch 4: PAC-3 direct_radius 25 m -> 40 m; HGV 15 G -> 10 G
75700c0  Patch 3: centralised ground-collision sweep in World.step
f5cdbeb  Patch 2: HGV — 90 km spawn, 15 G, wide S via pursuit waypoints
a337a03  Patch 1: raise spawn altitudes for clear 3-tier look
5cac8a5  Milestone C report: document bugfixes + HP/ammo + HGV + rebalance
130ee20  Part C: HGV + PAC-3 MSE + wave rebalance
ef3ff29  Part B: HP / damage model + per-launcher magazine & reload
0e3669a  Part A: fix B++ bugs — drone/cruise/ballistic Z + aim, launch banner
1bf8ea6  Add ballistic + full-scenario smoke tests and Milestone B+ report
053c776  Frontend: per-kind procedural meshes + 3D-emphasizing camera view
a8c988a  Add Wave 4 ballistic + Wave 5 mixed; route ballistic to LONG_SAM
125c1e4  Add ballistic threat + LONG_SAM + VLS boost + cruise pop-up
f8ae963  Add Milestone B implementation report
```

Run `git log --oneline -20` for the full history.

## Architecture Map

| Component | File | Purpose |
|-----------|------|---------|
| Config | `backend/sim/config.py` | All tunable parameters |
| Types & specs | `backend/sim/types.py` | Enums, dataclasses, weapon/threat spec tables |
| Physics | `backend/sim/physics.py` | PN guidance, gravity, drag, Euler integration, CPA |
| Entities | `backend/sim/entities.py` | Threat + Interceptor step logic per type |
| Launcher | `backend/sim/launcher.py` | Magazine + reload CD state machine |
| World | `backend/sim/world.py` | Tick loop, HP/damage, ground collision sweep |
| Red AI | `backend/sim/red_ai.py` | 5-wave scripted spawner |
| Blue AI | `backend/sim/blue_ai.py` | Cost-exchange greedy weapon selection |
| Scenarios | `backend/sim/scenarios.py` | World + RedAI + BlueAI orchestration |
| Server | `backend/server.py` | FastAPI + WebSocket + static files |
| Scene | `frontend/js/scene.js` | Three.js scene, camera, ground |
| Entities (client) | `frontend/js/entities.js` | 3D meshes, trails, explosions |
| HUD | `frontend/js/hud.js` | Score, ammo, launch banner, decision log |
| Main | `frontend/js/main.js` | WebSocket client, render loop |

## Design Docs

| Doc | Purpose |
|-----|---------|
| `DEMO_PLAN.md` | Simplified MVP scope (what was built for Milestone B) |
| `PLAN.md` | Full product vision implementation roadmap |
| `GAME_DESIGN.md` | Complete mechanics (control levels, fuel, HP, economy) |
| `WEAPON_SPECS.md` | All weapon parameters with real USD pricing |
| `REPORT.md` | Running implementation log of each milestone |
| `progress/STATUS.md` | This file — current snapshot |
| `progress/ROADMAP.md` | Next-step options |

## Resuming Work on Another Machine

### 1. Clone and checkout

```bash
git clone https://github.com/Heffri/hackathon-stridsledning.git
cd hackathon-stridsledning
git checkout knowledge-base
git pull
```

### 2. Run the simulation

```bash
cd team-missile-intercept/backend
pip install -r requirements.txt
python server.py
# Open http://localhost:8000/ in a browser, click Start
```

### 3. Verify smoke tests

```bash
cd team-missile-intercept/backend
python test_pn.py              # PN guidance sanity check
python test_ballistic.py       # LONG_SAM vs ballistic
python test_full_scenario.py   # Full 5-wave headless run
python test_balance.py         # 20-match balance sweep
```

### 4. Restore context for Claude Code

When starting a new Claude Code session, have it read in order:
1. `CLAUDE.md` (repo root) — project overview
2. `team-missile-intercept/progress/STATUS.md` (this file) — where we are
3. `team-missile-intercept/progress/ROADMAP.md` — what's next
4. `team-missile-intercept/REPORT.md` — full milestone history
5. Relevant code files depending on the task

For quick orientation, a Claude session can be started with:

> Read CLAUDE.md, then team-missile-intercept/progress/STATUS.md and ROADMAP.md to understand current state. Then ask me which route to pursue.

## Known Limitations (carried from REPORT)

1. **PN precision**: Euler 0.05s gives CPA of 20-80 m; real munitions have <5 m. Several spec deviations (linear vs quadratic damage falloff, radius_prox × 6, PAC-3 direct_radius 25 m vs spec 0.3 m) trace back to this.
2. **HGV is pre-programmed** (not Level 5 real-time evasion). Identical trajectory every run.
3. **test_balance.py runs only 400s**, cuts off wave-5 drones before they hit the base. Slightly inflates Blue's win rate.
4. **No terrain heightmap** yet. Flat ground only.
5. **No base HP or budget system**. Sim ends by timeout, not by resource depletion.
6. **Supersonic / stealth cruise not implemented**. CRUISE_SUB is the only cruise variant.
7. **No per-entity status panel** (click entity → show speed/G/HP/fuel). Demo transparency opportunity.

## Team & Deliverables

- **Hack Day:** April 25, 2026, KTH Innovation (09:30-16:30)
- **Grand Finale:** April 27, 2026
- **Presentation:** 4 minutes per team, jury = Saab technical leaders
- **GitHub repo:** `Heffri/hackathon-stridsledning`, branch `knowledge-base`
- **Team lead:** Sebastijan Babic
- **This track's lead:** Xingyi Chen
