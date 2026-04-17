# Project Status

> **Last updated:** 2026-04-17 (Milestone F session)
> **Branch:** `knowledge-base` (all work pushed here)
> **Latest commit:** `4844ed7` (Milestone F Task 2b — per-launcher boxes + arcs)

## Where We Are: Milestone F — Complete

Milestone F makes the 3D world legible. Two independent bumps: (1)
every Saab-named location on the Boreal Passage map now renders as an
actual 3D structure with a text label, and (2) every Blue launcher
sits at its own world position with its own coloured box + per-
launcher range arc, and interceptors now spawn from those positions
instead of all sharing a single base point.

The demo now has, on top of Milestone E:

- **12 Saab landmark structures** — each `BOREAL_LOCATIONS` row is
  rendered on the extruded terrain: runway + tower for air bases,
  5-box skyline for capitals, 3-box cluster for major cities. Side-
  tinted emissive (red north, blue south). Canvas-textured Sprite
  labels above each with the real name.
- **9 distributed launcher boxes** — 1 tan CIWS at base, 2 olive
  RBS 70 forward at 25 km north, 2 amber IRIS-T SLS flanking at
  20 km, 2 orange SLM mid-field at 15 km, 1 pink PAC-2 + 1 purple
  PAC-3 offset ±300 m E/W at 8 km north. Boxes dim to 50 % opacity
  and their arcs to 0.15 when the launcher reloads; both restore on
  refill.
- **Per-launcher range arcs** — the old stack of six base-centred
  arcs is gone; each launcher draws its own coloured northern
  semi-circle at its own position.
- **Interceptors launch from launcher positions** — the `_fire`
  path in blue_ai now passes `lch.pos` into `spawn_interceptor`. A
  PAC-3 shot visibly climbs from its purple box, not the base.

Known approximation (documented in REPORT + ROADMAP, deferred): the
engagement-decision math in `blue_ai` still ranks weapons by threat-
to-base distance. Forward-deployed SLS / SLM lose fallback intercepts
against ballistic threats because the base-distance gate passes shots
the launchers physically can't make. Measured cost ≈ 2-6 fewer Blue
wins in a 20-match sweep, almost entirely on ballistic leaks.

## Where We Are: Milestone E — Complete (still valid)

Milestone E is a pure frontend visual-packaging pass on top of Milestone D, plus the Boreal Passage 3D terrain. Everything through Milestone E is implemented and pushed. No backend changes — every snapshot field needed was already in `EntityState.to_dict()` from Milestone D.

The demo has, on top of Milestone D:

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

## Current Balance (test_balance.py, 20 matches, post-Milestone F)

```
Blue win 0–2/20, draw 7–10/20, Red win 11–13/20
avg spawned=26.0  avg intercepts=20.1  avg leaks=2.5–2.6
leaks by kind: mostly {'ballistic': ~52}
```

Drift from the Milestone D/E baseline (Blue 4–6/20, avg leaks 1.9–2.3,
ballistic leaks ~40) is ~2–6 fewer Blue wins per sweep. Root cause is
documented: forward-deployed SLS / SLM launchers take ballistic-
fallback shots they can't physically make because the engagement
decision still uses threat-to-base distance. A refactor to per-
launcher range math is queued in ROADMAP.

All 6 interceptor types still fire per scenario; the HGV intercept
rate is unchanged (HGV fallback is HIT_TO_KILL / LONG_SAM which are
still centred near the base).

## Commit History (recent)

```
4844ed7  Milestone F Task 2b: per-launcher boxes + per-launcher range arcs
0b38fd1  Milestone F Task 2a: distributed launcher positions — backend plumbing
2697e9e  Milestone F Task 1: Saab location landmarks (runways, cities, labels)
5490bc1  Milestone E docs: REPORT section + STATUS / ROADMAP refresh
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
```

Run `git log --oneline -20` for the full history.

## Architecture Map

| Component | File | Purpose |
|-----------|------|---------|
| Config | `backend/sim/config.py` | All tunable parameters (arena 150×250 km, leak radius 1500 m, `BLUE_LAUNCHER_POSITIONS`) |
| Types & specs | `backend/sim/types.py` | Enums, dataclasses, weapon/threat spec tables (incl. `fuel_s`, `thrust_active`) |
| Physics | `backend/sim/physics.py` | PN guidance, gravity, atmosphere-scaled drag, CPA, `air_density_ratio` |
| Entities | `backend/sim/entities.py` | Threat + Interceptor step logic; HGV bleed + evasion; interceptor boost/coast |
| Launcher | `backend/sim/launcher.py` | `Launcher.pos` + magazine/reload CD; `fleet_status` → `{by_kind, launchers}` |
| World | `backend/sim/world.py` | Tick loop, HP/damage, ground/leak sweep |
| Red AI | `backend/sim/red_ai.py` | 5-wave scripted spawner with per-kind border distances |
| Blue AI | `backend/sim/blue_ai.py` | Saturation engagement; `_fire` launches from `lch.pos`, not base |
| Scenarios | `backend/sim/scenarios.py` | World + RedAI + BlueAI orchestration; `snap['ammo']` + `snap['launchers']` split |
| Server | `backend/server.py` | FastAPI + WebSocket; PORT env var override |
| Scene | `frontend/js/scene.js` | Three.js scene; 250 km arena; 1 km grid; Boreal terrain; dusk skydome; Saab landmark structures + sprite labels |
| Terrain data | `frontend/js/terrain_data.js` | Boreal Passage polygons + `BOREAL_LOCATIONS` landmarks, baked from Saab CSV |
| Launchers (client) | `frontend/js/launchers.js` | `LauncherRegistry` — per-launcher coloured box + northern range arc, reload-dimmed |
| Entities (client) | `frontend/js/entities.js` | Per-kind meshes, trails, seeker cones, explosions, flame toggle |
| HUD | `frontend/js/hud.js` | Score, ammo (reads `snap.ammo` = by_kind), launch banner, AI decision logs |
| Status panel | `frontend/js/status_panel.js` | Click-to-inspect per-entity stats |
| Main | `frontend/js/main.js` | WebSocket client, render loop, wire entity + launcher registries + status panel |

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

## Known Limitations (after Milestone F)

1. **PN precision**: still Euler 0.05 s — CPA typically 20–80 m. PAC-3 `radius_direct = 60 m` (spec 0.3 m) is the workaround. This is the root cause of the ballistic-leak rate.
2. **Ballistic leak rate ~65 %** (post-F): Mach 13 RVs are hard, and the Milestone F forward deployment now costs SLS/SLM a handful of fallback intercepts on ballistic threats. Route 3 (RK4) + a per-launcher engagement-math refactor are the two real fixes.
3. **Engagement decisions still use base-distance**: `_try_fire` / `_time_to_enter_range` / `_primary_available_in_time` in `blue_ai` all compute range from `BLUE_BASE_POS`, even though each weapon now fires from up to 25 km forward. Explicit Milestone F concession; queued in ROADMAP.
4. **HGV terminal aim under evasion is not corrected.** A hard jink can nudge the HGV off the base-aim vector. Fine for now — Red AI Level 4/5 is planned to take over manual HGV control.
5. **CIWS under-fires on drones.** RBS 70 at 10 km prox-kills a 10-HP drone, so drones basically never reach the 4 km CIWS envelope. Point-defense override catches occasional survivors + hypersonic crossings.
6. **Radar / sensor model not wired.** Blue AI still has omniscient detection. `xingyi-rts/knowledge/sensors-c2.md` has the burn-through formula ready.
7. **No Red AI intelligence.** Waves are pre-scripted, cruise uses fixed S-pattern waypoints, HGV jink is scripted.
8. **No base HP or economy.** Any leak = leak. Running out of expensive PAC-3 rounds doesn't count against Blue.
9. **Terrain aspect distortion**: the Boreal Passage mapping uses 11× X / 3.2× Y non-uniform scale to fit the 1667 × 800 km Saab crop into the 150 × 250 km arena. Looks like "two lands across a strait" but doesn't match the Saab reference 1:1.
10. **Launcher positions are hand-coded**, not AI-chosen. `BLUE_LAUNCHER_POSITIONS` is a declarative dict the scenarios consume at reset — a placement AI hook is the next structural step.
11. **No EffectComposer bloom**: explosion bloom is a hot-core + additive-blend approximation, not real post-process bloom. Would need a bundler.
12. **Status-panel G-load** is averaged over the snapshot tick, not instantaneous.
13. **Landmark labels** use `depthTest: false` so they always render in front — pans can show a label bleeding through terrain. Acceptable at the default camera.

## Team & Deliverables

- **Hack Day:** April 25, 2026, KTH Innovation (09:30–16:30)
- **Grand Finale:** April 27, 2026
- **Presentation:** 4 minutes per team, jury = Saab technical leaders
- **GitHub repo:** `Heffri/hackathon-stridsledning`, branch `knowledge-base`
- **Team lead:** Sebastijan Babic
- **This track's lead:** Xingyi Chen
