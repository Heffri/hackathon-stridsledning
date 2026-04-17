# Project Status

> **Last updated:** 2026-04-17 (Milestone E session)
> **Branch:** `knowledge-base` (all work pushed here)
> **Latest commit:** `1068d72` (Milestone E Task 5 — sky + bloom)

## Where We Are: Milestone E — Complete

Milestone E is a pure frontend visual-packaging pass on top of Milestone D, plus the Boreal Passage 3D terrain. Everything through Milestone E is implemented and pushed. No backend changes — every snapshot field needed was already in `EntityState.to_dict()` from Milestone D.

The demo now has:

- **Click-to-inspect status panel** — click any missile/threat → glass-morphism panel shows kind real name (Shahed/Kalibr/Iskander/Kinzhal for threats, Lvkv 90/RBS 70 NG/IRIS-T SLS/SLM/PAC-2/PAC-3 for interceptors), speed + Mach, client-side G-load, HP bar, motor status, fuel remaining, altitude, target, range, USD cost. Lingers for ~1 s on "DESTROYED" after death.
- **Enriched AI decision logs** — two scrollable side panels (Blue left / Red right), up to 120 entries with auto-scroll, coloured priority tags (`[CIWS]` tan, `[FALLBACK]` amber, `[LAST RESORT]` red + tinted background), 6 px weapon-colour dot prefix on every line.
- **Seeker scanning cones** — every non-CIWS interceptor renders a 10 km × 8° translucent forward cone at its nose. Cyan default, orange when target is within 2 km. Hidden when target is dead.
- **Boreal Passage 3D terrain** — Saab's scenario geometry baked from the CSV into `frontend/js/terrain_data.js`: 2 mainlands, 5 islands, 1 peninsula, 12 named locations parsed. Extruded 300 m above sea; Blue base sits on the southern mainland, threats spawn over the northern mainland with a visible strait between.
- **Dusk sky + brighter flashes** — shader-material gradient skydome (dark-blue zenith → amber horizon), explosions use additive blending + bigger initial sphere so they read as flashes.

## Where We Are: Milestone D — Complete (still valid)

Milestone D is a full physics-realism + AI-behaviour + visual-identity pass on top of Milestone C Patch. See `REPORT.md` "Milestone D" section for the detailed change log. Everything through Milestone D is implemented, tested, and pushed.

The sim now has:

- **6 interceptor types with distinct 3D meshes and colours** — CIWS (tan cannon round, no flame), RBS 70 NG (olive MANPADS), IRIS-T SLS (with seeker dome), IRIS-T SLM (orange, no dome), Patriot PAC-2 (pink, tail-fins-only), Patriot PAC-3 MSE (purple, ACM ring).
- **Fuel + coast phase physics** — every interceptor has `fuel_s` (4 s CIWS → 41 s PAC-2 per WEAPON_SPECS.md). After burnout the exhaust flame disappears, sustain thrust stops, max_g drops to 0.5×, atmosphere-scaled drag kicks in, and the interceptor self-destructs below 200 m/s (stall).
- **HGV kinetic-energy bleed + Level-5 evasion** — HGV glides unpowered; commanded G causes quadratic speed loss (120 m/s/s at max G); Level-5 jink at 8 G triggers when an interceptor is within 12 km; stalls below 500 m/s. High-speed realistic turn-radius (`R = v²/a`) limits apply: Mach 17 HGV with 10 G has ~347 km turn radius and basically flies straight until it bleeds speed.
- **Saturation engagement** — Blue AI tracks up to 3 simultaneous interceptors per threat, fires as long as expected in-flight damage < threat HP. CIWS is point-defense override (fires on any threat inside 4 km regardless of gate). Last-resort tier fires anything in the arsenal when primary + fallback are dry and impact is under 15 s away.
- **Realistic threat speeds** — ballistic 4459 m/s (13 Mach), HGV 5831 m/s (17 Mach). Spawn distances: HGV 180 km, ballistic 120 km, cruise 60 km, drone 30 km.
- **Expanded 250 km arena** with 1 km/cell grid (CIWS 4 cells, RBS 70 9, SLS 12, SLM 40, PAC-3 60, PAC-2 70 — operator can eyeball ranges from the HUD).
- **Base leak detection** uses 1500 m horizontal disc (matches visual base marker). HGV terminal dive entry moved to 30 km so aim CEP dropped from 1472 m → 18 m.
- **Server default port 5174** (Windows reserves 8000/8080/8088). Override via `PORT` env var. See `NOTES_MODEL_AND_PORT.md` for the full trap.

## Current Balance (test_balance.py, 20 matches, post-Milestone D)

```
Blue win 4–6/20, draw 9–12/20, Red win 4–8/20
avg spawned=26.0  avg intercepts=21.3  avg leaks=1.9–2.2
leaks by kind: mostly {'ballistic': ~40, 'hgv': 0}
```

All 6 interceptor types fire per scenario (CIWS 4–8, RBS 70 11–13, SLS 2–6, SLM 20–22, PAC-2 4, PAC-3 4).

HGV leak rate is now ≈ 0 % thanks to saturation fire layered with fallback weapons. Ballistic leak rate ~ 50 % — operator explicitly accepted this under "real data over game tuning" since Mach 13 terminal RVs are a genuinely hard target for real air defence too.

## Commit History (recent)

```
1068d72  Milestone E Task 5: dusk sky gradient + explosion flash
c7acf28  Milestone E Task 4: Boreal Passage 3D terrain
92a8401  Milestone E Task 3: seeker scanning cones on interceptors
c15b44f  Milestone E Task 2: AI decision log enrichment
e0ea4a2  Milestone E Task 1: per-entity status panel
66dee65  Blue AI: DRONE fallback (SLS) + wait-for-primary; range arcs on map
3a67c5a  Docs: Milestone D section in REPORT.md + translate NOTES + update progress/
3e7fafe  Milestone D: realistic physics, saturation AI, per-weapon meshes
49c05d1  Frontend: IRIS-T style interceptor mesh — seeker dome, canards, larger tail fins
9897499  Add progress/ folder for cross-machine work continuity
763bce5  Translate REPORT.md to English for team readability
2b4a368  REPORT: append Milestone C Patch summary
ec584b7  Patch 4: PAC-3 direct_radius 25 m -> 40 m; HGV 15 G -> 10 G
75700c0  Patch 3: centralised ground-collision sweep in World.step
f5cdbeb  Patch 2: HGV — 90 km spawn, 15 G, wide S via pursuit waypoints
```

Run `git log --oneline -20` for the full history.

## Architecture Map

| Component | File | Purpose |
|-----------|------|---------|
| Config | `backend/sim/config.py` | All tunable parameters (arena 150×250 km, leak radius 1500 m, etc.) |
| Types & specs | `backend/sim/types.py` | Enums, dataclasses, weapon/threat spec tables (incl. `fuel_s`, `thrust_active`) |
| Physics | `backend/sim/physics.py` | PN guidance, gravity, atmosphere-scaled drag, CPA, `air_density_ratio` |
| Entities | `backend/sim/entities.py` | Threat + Interceptor step logic; HGV bleed + evasion; interceptor boost/coast |
| Launcher | `backend/sim/launcher.py` | Magazine + reload CD state machine |
| World | `backend/sim/world.py` | Tick loop, HP/damage, ground/leak sweep |
| Red AI | `backend/sim/red_ai.py` | 5-wave scripted spawner with per-kind border distances |
| Blue AI | `backend/sim/blue_ai.py` | Saturation engagement + CIWS point-defense + last-resort tier |
| Scenarios | `backend/sim/scenarios.py` | World + RedAI + BlueAI orchestration (events reset here, not in world.step) |
| Server | `backend/server.py` | FastAPI + WebSocket; PORT env var override |
| Scene | `frontend/js/scene.js` | Three.js scene; 250 km arena; 1 km grid; Boreal Passage terrain; dusk skydome |
| Terrain data | `frontend/js/terrain_data.js` | Boreal Passage polygons + locations, baked from Saab CSV |
| Entities (client) | `frontend/js/entities.js` | Per-kind meshes, trails, seeker cones, explosions, flame toggle |
| HUD | `frontend/js/hud.js` | Score, ammo, launch banner, enriched AI decision logs |
| Status panel | `frontend/js/status_panel.js` | Click-to-inspect per-entity stats |
| Main | `frontend/js/main.js` | WebSocket client, render loop, wire status panel |

## Design Docs

| Doc | Purpose |
|-----|---------|
| `DEMO_PLAN.md` | Simplified MVP scope (what was built for Milestone B) |
| `PLAN.md` | Full product vision implementation roadmap |
| `GAME_DESIGN.md` | Complete mechanics (control levels, fuel, HP, economy) |
| `WEAPON_SPECS.md` | All weapon parameters with real USD pricing |
| `REPORT.md` | Running implementation log of each milestone |
| `NOTES_MODEL_AND_PORT.md` | Mesh-building conventions + Windows port traps |
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
# Open http://localhost:5174/ in a browser, click Start
```

If port 5174 is reserved on this machine (see `NOTES_MODEL_AND_PORT.md`):

```bash
PORT=6969 python server.py       # bash / Git Bash
set PORT=6969 && python server.py  # Windows cmd
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
4. `team-missile-intercept/REPORT.md` — full milestone history (Milestone D is the last section)
5. Relevant code files depending on the task

For quick orientation, a Claude session can be started with:

> Read CLAUDE.md, then team-missile-intercept/progress/STATUS.md and ROADMAP.md to understand current state. Then ask me which route to pursue.

## Known Limitations (after Milestone E)

1. **PN precision**: still Euler 0.05 s — CPA typically 20–80 m. PAC-3 `radius_direct = 60 m` (spec 0.3 m) is the workaround. This is the root cause of the ballistic-leak rate.
2. **Ballistic leak rate ~50 %**: Mach 13 RVs are hard. Options: RK4 + sub-tick PN (Route 3), or accept and pitch as realism. Operator has explicitly picked the latter.
3. **HGV terminal aim under evasion is not corrected.** A hard jink can nudge the HGV off the base-aim vector. Fine for now — Red AI Level 4/5 is planned to take over manual HGV control.
4. **CIWS under-fires on drones.** RBS 70 at 10 km prox-kills a 10-HP drone, so drones basically never reach the 4 km CIWS envelope. Point-defense override catches occasional survivors + hypersonic crossings.
5. **Radar / sensor model not wired.** Blue AI still has omniscient detection. `xingyi-rts/knowledge/sensors-c2.md` has the burn-through formula ready.
6. **No Red AI intelligence.** Waves are pre-scripted, cruise uses fixed S-pattern waypoints, HGV jink is scripted.
7. **No base HP or economy.** Any leak = leak. Running out of expensive PAC-3 rounds doesn't count against Blue.
8. **Terrain aspect distortion**: the Boreal Passage mapping uses 11× X / 3.2× Y non-uniform scale to fit the 1667 × 800 km Saab crop into the 150 × 250 km arena. Looks like "two lands across a strait" but doesn't match the Saab reference 1:1.
9. **No terrain location labels**: `BOREAL_LOCATIONS` exports 12 named cities/bases but rendering Sprite labels was cut for time. ~30 min to add.
10. **No EffectComposer bloom**: explosion bloom is a hot-core + additive-blend approximation, not real post-process bloom. Would need a bundler.
11. **Status-panel G-load** is averaged over the snapshot tick, not instantaneous.

## Team & Deliverables

- **Hack Day:** April 25, 2026, KTH Innovation (09:30–16:30)
- **Grand Finale:** April 27, 2026
- **Presentation:** 4 minutes per team, jury = Saab technical leaders
- **GitHub repo:** `Heffri/hackathon-stridsledning`, branch `knowledge-base`
- **Team lead:** Sebastijan Babic
- **This track's lead:** Xingyi Chen
