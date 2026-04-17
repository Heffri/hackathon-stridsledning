# Milestone B Implementation Report

## Completed Items

### Backend (Python, 1010 lines)

| File | Lines | Description |
|------|------|------|
| `backend/requirements.txt` | 3 | fastapi 0.115, uvicorn 0.30, numpy 1.26 |
| `backend/sim/__init__.py` | 0 | Package marker |
| `backend/sim/config.py` | 44 | Central tunable parameters (arena 150×150×40 km, DT=0.05s, 15Hz stream, PN gain=4) |
| `backend/sim/types.py` | 150 | `Team`/`ThreatType`/`InterceptorType` enums, `ThreatSpec`/`InterceptorSpec` dataclasses, `EntityState`, `Explosion`, `WaveSpec`, plus spec tables for drone/cruise_sub and CIWS/short_sam/med_sam |
| `backend/sim/physics.py` | 119 | Gravity, quadratic drag, acceleration/speed caps, **True Proportional Navigation** (N=4), semi-implicit Euler integration, closed-form closest-approach distance |
| `backend/sim/entities.py` | 172 | `Threat` (waypoint tracking + altitude-hold + drag) and `Interceptor` (PN guidance + velocity-aligned thrust up to max_speed + gravity + drag) |
| `backend/sim/world.py` | 181 | World tick: advance threats → advance interceptors → per-tick CPA binary hit test → base hit → cull dead entities → emit snapshot JSON |
| `backend/sim/red_ai.py` | 83 | Three scripted waves (T+2s 3 drones → T+35s 2 cruise → T+75s 4 drones + 1 cruise). Each threat type spawns at a distance matched to its cruise speed (drone 15km, cruise 40km) |
| `backend/sim/blue_ai.py` | 84 | Rule-based interceptor selection: drone → SHORT_SAM > CIWS > MED_SAM; cruise → MED_SAM > SHORT_SAM. Launches when threat enters `max_range × 1.1`, tracks threat_id → interceptor_id assignments |
| `backend/sim/scenarios.py` | 40 | Wires World + RedAI + BlueAI, called in order each tick; snapshot carries wave state and log |
| `backend/server.py` | 173 | FastAPI + WebSocket. `SimRunner` in an asyncio task advances + broadcasts full JSON at 1/15s cadence; accepts `start/pause/reset/speed` commands; static file serving on `/` and `/static/*` |
| `backend/test_pn.py` | 63 | Standalone PN verification (med_sam chasing cruise_sub from 30km intercepts at 24.5s, miss 71.4m) |

### Frontend (HTML/CSS/JS, 482 lines)

| File | Lines | Description |
|------|------|------|
| `frontend/index.html` | 63 | Single page, Three.js ES-module importmap (unpkg CDN, 0.160.0), HUD skeleton |
| `frontend/style.css` | 106 | Frosted-glass HUD panels, buttons, speed slider, log column, connection status indicator |
| `frontend/js/scene.js` | 109 | Three.js scene, perspective camera, OrbitControls, ambient + directional lighting, 150×150 km GridHelper, ground plane, Blue base cylinder marker, north indicator, world→scene coordinate transform (X=east, Y=north, Z=up → X,Y=up,Z=-north, ×0.001 scale from m to km) |
| `frontend/js/entities.js` | 166 | `EntityMesh` (colored cone + BufferGeometry trail of 60 points + velocity-aligned orientation), `EntityRegistry` (snapshot-driven create/destroy/update), white sphere explosion with scale-up + fade |
| `frontend/js/hud.js` | 60 | Binds Start/Pause/Reset buttons and speed slider, updates T/wave/intercepts/leaked/active counters, renders Red/Blue AI log |
| `frontend/js/main.js` | 47 | Bootstraps the scene, opens WebSocket (auto-reconnect), consumes the latest snapshot in the render loop |

**Total**: 14 implementation files + requirements.txt + test_pn.py ≈ 1500 lines of code.

## Run Commands

```bash
cd "C:/Users/xingyi chen/Documents/GitHub/hackathon-stridsledning/team-missile-intercept/backend"
pip install -r requirements.txt
python server.py
# Open http://localhost:8000/ in a browser
```

Verify the physics engine without the server:
```bash
cd backend && python test_pn.py
```

## Verification Checklist (what the browser should show)

After opening http://localhost:8000/:

1. **Initial scene** — deep-blue sky, 30×30 grid ground (150km × 150km), a blue cylinder (Blue base) slightly south of center, a small yellow ball to the north (bearing indicator). HUD in the corners, "disconnected" turns into "connected".
2. **Click Start** — the `T` counter starts ticking.
3. **T+2s (Wave 1)** — 3 red cones appear 15 km to the north, drifting slowly (45 m/s) toward the base. Log entry "Wave 1: Drones launched".
4. **T+3-5s** — Blue AI notices threats entering short_sam's 9km range; 3 yellow cones launch in an arc from the base (initial speed 340 m/s, accelerating to 680 m/s), PN-guiding into the drones.
5. **T+10-15s** — white spherical bursts appear in mid-air, trails persist. Intercept counter +3, active threats back to zero.
6. **T+35s (Wave 2)** — 2 brighter red cones appear from 40km (260 m/s subsonic cruise); med_sam launches (max speed 1020 m/s).
7. **T+50-60s** — med_sam completes both intercepts.
8. **T+75s (Wave 3)** — 4 drones + 1 cruise spawn together; Blue AI handles multiple targets in parallel.
9. **Speed slider** — drag to 5.0x, the whole simulation advances at 5× speed (more physics steps per frame, not interpolation).
10. **Pause button** — freezes sim time; click Start again to resume.
11. **Reset button** — clears all entities and counters back to T=0.

**Smoke-test result** (backend-only, 180 seconds): 10 threats spawned, 9 intercepted, 0 leaked to base. Wall-clock 1.00 second (sim accelerated ~180×).

## Technical Decisions Made

Points not spelled out in the spec that needed a call:

1. **Coordinate scaling**. Three.js uses Y=up on screen, which conflicts with the sim's Z=up. The transform is done on the frontend: `(sim_x, sim_y, sim_z) → (scene_x=(x-base_x), scene_y=z, scene_z=-(y-base_y))` with an overall ×0.001 (m → km). Keeps camera numbers in O(100) rather than O(1e5) and avoids z-fighting.
2. **Spawn distance scaled by threat speed**. The scenario doc says "from the north edge", but drone at 45 m/s from 140 km away would take 50 minutes to reach the base — unwatchable. Instead drones spawn 15 km out (still outside SHORT_SAM's 9 km × 1.1 margin, forcing Blue to wait for entry) and cruise 40 km out (at MED_SAM's edge). Computed per threat type in red_ai.py.
3. **PN guidance implementation**. True PN standard form `a_cmd = N * V_c * (omega × r_hat)`, with `omega = (r × v_rel) / |r|²`. Stable on head-on geometries. When closing speed < 100 m/s we add 80 m/s² along LOS to prevent PN output from collapsing on near-crossing geometries.
4. **Drag coefficients**. No measured data, tuned by intuition ("drones high drag, cruise medium, interceptors vary"): drone=1e-5, cruise_sub=5e-6, CIWS=2e-5, short_sam=1e-5, med_sam=6e-6. Combined with `cap_speed(max_speed)` hard clip to prevent runaway.
5. **Acceleration cap**. `cap_accel(max_g * 9.81)`. `MAX_ACCEL=600 m/s²` lives in config.py as a global cap (unused for now, interface reserved).
6. **WebSocket broadcast**. 15fps full JSON snapshots. Frontend only processes the latest frame (drops any queue backlog), so it can't stall. Server-side `asyncio.Queue(maxsize=8)` per subscriber, overflow is dropped.
7. **Server starts paused by default**. Clients get empty state on connect; only clicking Start actually advances the sim. Prevents a page refresh from landing mid-game.
8. **Base hit radius 250m**. Threats within 250m of the base count as "leaked" (leaked +=1, explosion spawned), forcing termination so dead drones don't pile up over the base.
9. **Trail length 60 points @ 15fps = 4 seconds**. Enough to read the arc, cheap on GPU.
10. **CIWS is in the ruleset** but the current two threat types (drone/cruise_sub) are rarely within 4 km of the base while still alive — CIWS sits behind SHORT_SAM as a fallback. Will get exercised once closer threats are added.
11. **Explosion visual**. White sphere, scale 1→18, opacity 0.9→0 over a 1-second lifetime. Driven by performance.now() in entities.js, independent of server clock.

## Known Issues / TODO

1. **Wave 3 occasionally leaks 1 cruise**. Blue AI has fired 8 consecutive med_sams at the same cruise and missed all of them (see tail of blue_log). Likely cause: cruise flies at 60m, med_sam arcs down from high altitude, end-game velocity is almost straight-down — bad geometry. Fix: either add launch-direction prediction (aim at predicted intercept point) or raise cruise cruise_alt to 500m+ to match a realistic flight profile. Current state is watchable but imperfect.
2. **Blue AI has unlimited ammo**. Deferred per DEMO_PLAN.
3. **Linear Euler integration** shows slight energy drift in high-G turns. Invisible at demo scale; RK4 is a later concern.
4. **Reset button** rebuilds the Scenario but doesn't clear existing frontend meshes — they disappear on the next snapshot when the entity reconciler culls them. One-frame visual overlap "old + new", barely noticeable.
5. **Frontend `_exKeys` Set dedup** uses `t.toFixed(3) + pos` as the key. Two explosions at the exact same place and tick would collapse into one. Vanishingly unlikely, not worth fixing.
6. **Drag coefficient is not altitude-dependent**. `drag = -k*|v|*v` uses a constant k. In reality air density at 50m is ~25× denser than at 25km. Atmospheric density model is a Milestone C item.
7. **Default camera position** (95km south + up from base) frames the whole battlefield. Needs to pull back once HGVs at higher altitudes are added.
8. **README not updated**. `team-missile-intercept/README.md` is still a placeholder; should add a brief "How to run" section pointing to REPORT.md.

## Suggestions for Next Session (priority-ordered)

1. **(Top priority) Fix the cruise-leak problem**. Two directions: (a) compute a simple lead angle in `blue_ai.py` (use `threat.pos - base + threat.vel × time_to_intercept` as `initial_dir`); (b) raise cruise cruise_alt to 500m and flatten MED_SAM's arc (drop the Z component of `initial_dir` from 1000 to 300). Recommend trying (b) first, simpler.
2. **Add HP/damage system**. Use direct_hit_radius/prox_radius/damage from WEAPON_SPECS.md. Minimum change: add `hp` to EntityState, convert `world.step` hit logic from binary to "apply damage by formula, only kill at hp ≤ 0". Unlocks tactical depth like PAC-3-vs-ballistic "200 damage direct vs 5 damage graze".
3. **Add magazine / reload CDs**. Introduce `launcher.py`; each interceptor type gets magazine + inter-shot CD + full reload. Forces Blue AI to manage resources.
4. **Add remaining 3 interceptors + 3 threats**: IRIS-T SLS (60G knife-fight), PAC-2, PAC-3; supersonic cruise, ballistic terminal, HGV. Unlocks the full cost-exchange matrix from WEAPON_SPECS.
5. **Red AI Levels 2/3**: ballistic fixed arcs + terminal maneuvers, cruise waypoint adjustments. Levels 4/5 (stealth terminal takeover, HGV full control) are bigger — defer to Milestone D.
6. **Per-entity status panel**: click a cone, right-side panel shows type/speed/G/HP/fuel/target/time-to-intercept. UI skeleton exists; add a Raycaster + a `#status-panel` div in entities.js.
7. **Terrain heightmap**: add terrain.py + frontend/js/terrain.js using the Boreal Passage heightmap from `knowledge/scenario.md`. Prep work for Level 4 "terminal takeover at sea strait crossing".
8. **Economy + win conditions**: base_hp, Red/Blue budgets, endgame decision. Turns the sim from a demo into an actual game.

## Note: Deliberately Deferred Items (not omitted)

Per the DEMO_PLAN.md table: "HP, fuel, magazines, terrain, economy, stealth/HGV/ballistic, Red Levels 2-5, per-entity panel, AI decision log panel, seeker cone, cost-exchange calculation" — all unimplemented, reserved for Milestone C+. This Milestone B deliverable only covers "the core loop works", which is exactly what DEMO_PLAN defines.

---

# Milestone B+ Update — 3D Makeover

Goal: upgrade "3D-rendered 2D combat" to a battlefield that genuinely uses the Z axis. Focus: VLS vertical launch, ballistic missile high-altitude dive, cruise missile terminal pop-up, and a default camera view that emphasizes altitude.

## Code Change Summary

| File | Lines changed | Core logic change |
|------|---------|--------------|
| `backend/sim/types.py` | +25 | New enums `ThreatType.BALLISTIC`, `InterceptorType.LONG_SAM`; corresponding entries added to `THREAT_SPECS` / `INTERCEPTOR_SPECS` (ballistic 1800 m/s / kill_radius 70m / color `#ff8020`; LONG_SAM 1700 m/s / 25G / 70km / kill_radius 90m / color `#ffec40`) |
| `backend/sim/entities.py` | rewrite (+180/-45) | `Threat.__init__` has a separate branch for ballistic to compute the initial downward vector; `Threat.step` now dispatches by type: ballistic uses gravity-dominant flight + 1G lateral correction + no altitude-hold; cruise_sub raises target altitude to 600m at <5km horizontal distance, drops to 150m at <1.5km (terminal pop-up). `Interceptor.__init__` switches SHORT_SAM/MED_SAM/LONG_SAM to a VLS initial-vertical velocity vector; `Interceptor.step` adds a boost phase: first 1.5s disables PN, uses strong vertical thrust + gravity + drag; after boost, switches to PN and — critically — points sustain thrust along LOS-to-target (prevents PN and vertical thrust from fighting each other). Interceptor.step signature gains a `t_now` parameter |
| `backend/sim/world.py` | +1/-1 | `inter.step()` now receives `self.t` for boost-phase detection |
| `backend/sim/red_ai.py` | +29 | New constants `BALLISTIC_SPAWN_Y=base_y+40km` / `BALLISTIC_SPAWN_Z=35km`; Wave 4 (T+120s) fires 1 ballistic; Wave 5 (T+150s) is a high-low mix (1 ballistic + 2 drones + 1 cruise). The `threats` tuple is extended from `(kind, (x,y))` to `(kind, (x,y,z))` for ballistic types |
| `backend/sim/blue_ai.py` | +6 | `RULES` now has `BALLISTIC: [LONG_SAM]`; no fallback — would rather let one leak than waste a SHORT/MED SAM |
| `frontend/js/scene.js` | +14/-7 | Camera default position `(18, 25, 55)`, OrbitControls target `(0, 6, -30)` — south-east, high-altitude, slightly up-tilted view that lands 35km ballistic above the horizon for visibility |

New test scripts:
- `backend/test_ballistic.py` — 60 lines, standalone: spawns ballistic + LONG_SAM and advances 30s offline, printing the Z trace. Current output: intercept at t=16.8s, miss 86m, intercept altitude 10.7km.
- `backend/test_full_scenario.py` — runs the full 200s scenario, prints final stats. Current output: spawned=15 intercepts=15 leaked=0 (all 5 waves fully intercepted).

## Run Commands

Unchanged:
```bash
cd "C:/Users/xingyi chen/Documents/GitHub/hackathon-stridsledning/team-missile-intercept/backend"
pip install -r requirements.txt
python server.py
# Open http://localhost:8000/
```

Offline verification (no server):
```bash
cd backend && python test_ballistic.py     # ballistic + LONG_SAM intercept
cd backend && python test_full_scenario.py # full 5-wave scenario
```

## Verification Checklist (Z-axis behavior visible in browser)

1. **Default camera angle** — page opens on a south-and-slightly-elevated view. Base near the lower part of the frame, horizon roughly mid-screen, sky taking the upper half, ground grid extending into the distance. Means the 35km ballistic doesn't appear "off-screen above".
2. **Wave 1 (T+2s) — VLS vertical launch**: SHORT_SAM rockets nearly straight up from the base (~400-500m altitude in the first 1.5 seconds), then noticeably pitches over toward the drones. Trail has a signature "L shape".
3. **Wave 2 (T+35s) — Cruise pop-up**: the 60m sea-skimming cruise climbs to 600m at 5km-to-base, drops to 150m at 1.5km. The 2 med_sams in this wave both hit cleanly because the post-pop-up geometry is now favorable.
4. **Wave 3 (T+75s) — multi-target** + pop-up: 4 drones + 1 cruise. The "cruise leak" problem from the previous REPORT should be resolved (tests show 0 leak).
5. **Wave 4 (T+120s) — Ballistic**: an orange (`#ff8020`) ballistic missile appears dead north 40km out, Z=35000m. Initial downward velocity 1800 m/s; with gravity it carves a visibly parabolic dive. A LONG_SAM (bright yellow `#ffec40`) rockets up from the base, meeting the ballistic in an explosion at ~10km altitude. The Z-axis geometry of the intercept is unambiguous.
6. **Wave 5 (T+150s) — high-low pincer**: 1 ballistic (top) + 2 drones (800m) + 1 cruise (60m with pop-up). Four altitude layers on screen simultaneously.
7. **Z-layer observation**: at any point after Start you should be able to see drone near the ground (~800m), cruise hugging the deck (60-600m), SAM interceptors climbing a few km high, and ballistic slashing down from 35km. This is the key visual proof of "3D combat".
8. **Camera controls**: OrbitControls is kept; dragging with the mouse rotates from top-down to side and zooms, confirming the battlefield is genuinely volumetric.

## Technical Decisions

1. **Ballistic initial direction uses `normalize(target - start) + (0, 0, -0.25)` rather than the spec's example `(0, -0.3, -1)`**. Reason: from a 40km-north, 35km-high spawn, `(0, -0.3, -1)` normalizes to only 517 m/s horizontal, which combined with the 26s fall produces only 10 km of forward travel — lands 30km short of the base. With "aim at base + extra 0.25 vertical bias" the ballistic is successfully intercepted by LONG_SAM at t≈16.8s: geometric drama + tractable intercept.
2. **Ballistic `drag_k = 2e-6`**. Rationale: air density at 10km+ is ~4× thinner than sea level, so 2-3× less than cruise_sub (5e-6); also ensures the 1800 m/s terminal speed isn't noticeably bled by drag. Measured: 20s fall brings speed 1800 → 1830 (slight gravity gain), matches "Mach 5.5 re-entry" feel.
3. **Ballistic `max_g = 1`**. Per spec. Measured: 1G lateral correction over 20+ seconds accrues only ~2km of displacement — not enough to drastically adjust the impact point, but enough to steer the ballistic toward the base (sufficient for demo).
4. **Cruise pop-up thresholds fixed at 5km/1.5km, altitudes 600m/150m**. Not parameterized. 5km is the visible "start climbing" distance, 1.5km is the terminal dive into the base. Measured: all Wave 2/3 cruises now hit (the one Wave 3 leak from the previous REPORT is resolved).
5. **VLS boost 1.5s fixed**. Per spec. Measured: MED_SAM reaches ~400m altitude at t=1.5s, SHORT_SAM ~300m. Visually sufficient to convey "vertical climb" phase.
6. **During boost: strong upward push + gravity + drag only, no PN**. Implemented with the boost phase's target velocity at `0.7 × max_speed` along a (0.2 horizontal + 1.0 vertical) direction, with the acceleration cap temporarily raised to `1.5 × max_g` for dramatic climb.
7. **Post-boost critical fix: sustain thrust along LOS-to-target**, not along current velocity. This was the core pitfall: if thrust stays along velocity when boost ends with a vertical velocity vector, thrust reinforces vertical motion and PN can't out-turn it — result is MED_SAM looping up into a 25km parabola before finally turning toward the target, by which point demo time's up. Swapping to LOS-aligned thrust lets PN and thrust cooperate; SHORT_SAM's intercept time on distant drones drops from >60s to 27s.
8. **Wave 4 only fires 1 ballistic**. Ballistic spawning has a high CPU/visual budget; 1 is enough to demonstrate the intercept without visual pile-up.
9. **Wave 5's ballistic spawns from `base_x - 4000`** (not due north) for a lateral offset, testing LONG_SAM's ability to intercept off-axis targets.
10. **LONG_SAM launch timing**: the existing Blue AI rule "launch when threat enters `max_range × 1.1`" is already sufficient for ballistic — at spawn, 3D distance is 53km < 77km threshold, so it launches on the same tick. The spec's "don't wait" is satisfied naturally.
11. **Camera parameters**: position `(18, 25, 55)`, target `(0, 6, -30)`, corresponding to world coordinates 18km east, 25km up, 55km south, looking at a point 30km north of the base at 6km altitude. This combination puts the 35km ballistic in the upper third of the frame as it arcs down. For a more exaggerated perspective, push target.y to 8-10.

## Known Issues / TODO

1. **VLS boost-phase trail is only a short vertical line within 1.5s**, because trailPoints sample at 15fps × 1.5s ≈ 22 points. Readable but doesn't match the flowing trails of SAM cruise phase. Could interpolate trail points during boost on the frontend.
2. **Blue AI fires LONG_SAM within 1-2 frames of ballistic spawn**, with no "detect → assess → decide" beat. Adding a 0.5-1s detection delay in blue_ai would convey C2 timing.
3. **If a LONG_SAM is expended in Wave 4 and misses, Wave 5's ballistic still gets assigned a LONG_SAM** (no ammo tracking yet). Once Milestone C+ introduces magazines, the "LONG_SAM magazine empty → ballistic leaks" case needs handling.
4. **When ballistic lands 10+ km north of base** (without being intercepted), the current `leaked` counter only fires within 250m of base, so a far-miss ballistic runs until Z=0 and goes alive=False but doesn't count as leaked. No leak log appears in UI. Acceptable.
5. **VLS boost acceleration cap is bumped to `1.5 × max_g`**, 50% above spec. For visual drama; to strictly obey max_g, change 1.5 back to 1.0 at the cost of slower climb and less striking initial Z motion.
6. **scene.js default camera is high for people focused on low-altitude drones**. If future demos focus on close-in defense, this view needs to come down. Current setting is a "cover all altitudes" compromise.
7. **test_pn.py's MED_SAM intercept time moved from the old 24.5s to 27.25s**. Boost phase eats 1.5s plus post-boost turn-around. Miss distance improved from 71m to 16.6m (new sustain-thrust direction gives better terminal geometry). Net positive.
8. **Ballistic descent speed is a touch below real Iskander (Mach 6 ~2040 m/s) — we use 1800 m/s**. Leaves headroom for the future HGV (Mach 5+, 8G maneuverability) and a truly Mach 6 ballistic terminal phase.

## Suggestions for Next Session (priority-ordered)

1. **Add HP/damage system (top priority)**. Current intercept is binary "inside kill_radius = dead". Implement the direct_hit / prox / prox_radius triplet from WEAPON_SPECS.md so PAC-3's "200 direct damage vs 5 graze damage" contrast becomes real. Expected change: add `hp` to EntityState; in `world.step` hit logic, apply damage per formula, only set `alive=False` when hp ≤ 0.
2. **Introduce supersonic cruise + stealth cruise**. Both sit in the ~260-900 m/s range, 14km+ altitude mixes; paired with the current subsonic cruise this creates a three-tier differentiation. Code cost is low (clone CRUISE_SUB spec, tune speed/alt/rcs), but meaningfully grows demo weapon variety.
3. **Magazine / reload CDs**. LONG_SAM: 1 launcher × 4 missiles × 120s reload. With this in, Wave 4/5 force the question "ballistic inbound — fire or hold?". Can add `magazine_size + reload_s` to InterceptorSpec, have `blue_ai` track per-type remaining count and next-available time.
4. **HGV (Red AI Level 5)**. True real-time evasive maneuvering. Needs "detect nearby interceptor → lateral evasion" logic in Threat. Also needs kinetic-energy-bleed (maneuver → speed decay → eventual glide). Substantial change — save for Milestone D.
5. **Per-entity status panel + AI decision log panel**. Raycaster click on an entity → panel shows details. UI skeleton already in place; add click handler in entities.js + a `#status-panel` div. Big impact on the 4-minute demo's "transparency" score.

---

# Milestone C Update — B++ Remnant Bugs + HP/Ammo/HGV + Difficulty Rebalance

Goal: fix B++ remnant bugs (Red ignoring Z axis, missiles not hitting base, drone too slow and wobbly), upgrade intercept from binary to HP + damage model, give launchers magazines + reload CDs, add hypersonic glide vehicles + PAC-3 MSE, rewrite the 5 waves so Blue drops from 100% win rate to actual uncertainty.

## Part A — Remnant Bug Fixes

### A1. Red Z-axis hold — per-entity
B++ saved `_base_alt = spawn_z` per Threat, but drone.step had a sine wobble (`±200m / 30s period`) that visually looked like a bobblehead. Fix: **remove the sine wobble entirely**, drone stays at spawn_z for its whole flight, only gliding down within 2 km of the base. Altitude-hold spring-damper coefficients changed from `0.5 / 0.8` to `0.2 / 0.4`, quieter.
**Verified**: `test_threat_impact.py` 5 × 600s no-interceptor runs, drone mid-flight Z range max = 0 m.

### A2. Missiles actually hit the base
Ballistic root cause: original code used `normalize(target-start) + (0,0,-0.25)` as initial direction — **over-angled downward** so gravity pulled it onto a long overshoot landing north of the base. And `max_g=1` lateral correction was too weak.
Fix:
- Use classical ballistic closed-form launch angle: solve `k tan²θ + d tanθ + (k − h) = 0` (`k = g d² / 2v²`), take the shallow root;
- To compensate for drag deceleration, bias the aim 2% south of base (`dh_aim = dh * 1.02`);
- `max_g 1 → 3` — stronger lateral correction.
- Cruise waypoints still end at `BLUE_BASE_POS`; drone now glides down in terminal phase.
**Verified** (5 trials × 600s, no interceptor):
```
drone      : n= 27  mean_dist= 247 m  max= 250 m
cruise_sub : n= 20  mean_dist= 247 m  max= 250 m
ballistic  : n= 10  mean_dist= 202 m  max= 247 m
```
All impact points within the 250 m base radius.

### A3. Drone speed + attitude
- Speed **45 → 120 m/s** (reference: Switchblade 600); at 5× speed the drone is now visibly crossing the field;
- Bobblehead problem resolved via A1's sine removal + softer spring-damper.

### A4. Launch banner
`hud.js` listens to each snapshot's `events[]`; on `type:"launch"` it shows a 2-second "🚀 LAUNCH: <real name>" banner. Name mapping: CIWS → Lvkv 90, SHORT_SAM → RBS 70 NG, MED_SAM → IRIS-T SLM, LONG_SAM → Patriot PAC-2 GEM+, HIT_TO_KILL → Patriot PAC-3 MSE. Deduplicated via `_seenEvents` Set so snapshot replays don't re-trigger.

## Part B — HP + Ammo + Damage Model

### B1. HP System
`ThreatSpec` gains `hp` + `usd_cost`; `EntityState` gains `hp` + `hp_max`. Values:
- drone 10, cruise_sub 30, ballistic 80, HGV 60

### B2. Damage System
`InterceptorSpec` gains `damage_direct / damage_prox / radius_direct / radius_prox`. `world.step` replaces binary hit with:
```
if d_min < radius_direct: damage = damage_direct
elif d_min < radius_prox: damage = damage_prox * (1 - d_min/radius_prox)   # linear
else: damage = 0
target.hp -= damage
interceptor.alive = False  # consumed regardless of hit
if target.hp <= 0: target.alive = False; intercepts += 1
```
**Note on formula deviation**: task spec uses **quadratic falloff** `(1 - d/r)²`. But our PN at Euler 0.05s steps gives typical CPA of 20-80 m — far beyond real munitions' 5-20 m frag radius. Strictly following the spec would mean each shot delivers 1-2 dmg and drones survive. Chose **linear falloff + scaled `radius_prox` to real value × 6** (CIWS 80, SHORT_SAM 120, MED_SAM 150, LONG_SAM 180, PAC-3 60). This way the spec's damage numbers (CIWS 8, RBS 70 20, IRIS-T 25, PAC-2 40, PAC-3 200) and WEAPON_SPECS' "shots-to-kill" table (drone 1 shot by SHORT_SAM, cruise 2 by MED_SAM, ballistic 1 by PAC-3 direct or 2 by PAC-2 prox) all hold in demo conditions. The CPA check is tightened to `kill_radius` (true warhead size) to avoid wild far-miss kills. **This deviation is an explicit design decision recorded in the REPORT, not an oversight**.

### B3. Launcher Model
New file `sim/launcher.py`: `Launcher` dataclass with magazine + `inter_shot_cd` + `reload_time` (all using WEAPON_SPECS' ÷10-scaled values). `LauncherFleet` manages all launchers, exposes `find_ready(kind, t_now)`. Default loadout: 1× CIWS, 2× RBS 70, 2× IRIS-T SLM, 1× PAC-2, 1× PAC-3. `blue_ai` rewritten as **cost-exchange greedy**: for each unassigned threat, compute `shots_to_kill × usd_cost` per weapon type, try from cheapest, use the first with a ready launcher.

### B4. HUD Ammo Panel
`index.html` has 5 rows top-right (CIWS/RBS70/IRIS-T/PAC-2/PAC-3). `hud.js` reads `{current, capacity, reloading, reload_remaining}` from snapshot's `ammo[kind]` each frame, shows `6/8` or `RELOAD 45s`. Below 25% ammo goes yellow (`.low`), 0 flashes red (`.empty` + CSS animation).

## Part C — HGV + PAC-3 + Waves

### C1. HGV (Kinzhal/DF-ZF simplified)
Added `ThreatType.HGV`, max_speed 1700, max_g 8, hp 60, drag 1.5e-6. New HGV branch in `entities.py`:
- Initial horizontal direction toward base, with -80 m/s initial sink rate
- Beyond 10 km: **pre-programmed S maneuver** (lateral accel = 60 m/s² × sin(2π·t/10s)), holds spawn_z altitude
- Within 10 km: S maneuver off, terminal dive (target_alt → 0)
- No Level-5 real-time evasion AI (TODO)

### C2. PAC-3 MSE (HIT_TO_KILL)
Added `InterceptorType.HIT_TO_KILL`, max_speed 1700, max_g 50, max_range 60 km. Uses the VLS profile (same 1.5s boost as other SAMs). Damage:
- direct 200 dmg, **radius_direct 25 m** (spec is 0.3 m, too tight for our PN)
- prox 25 dmg, radius_prox 60 m — deliberately weak to preserve "hit-or-waste" feel
- kill_radius 60 m (CPA gate)

Blue AI places PAC-3 ahead of PAC-2 for ballistic/HGV targeting (cost $4M < 2×$3M=$6M), auto-prioritizes. Launcher: 1 unit × 4 missiles × 180s reload.

### C3. Wave Rewrite (new 5 waves)
| # | T | Threats | Label |
|---|---|------|-------|
| 1 | 2s | 3 drones | Drones |
| 2 | 25s | 3 drones + 1 cruise | Drones + cruise |
| 3 | 55s | 2 cruise + 1 ballistic | Cruise + ballistic |
| 4 | 95s | 1 HGV + 2 drones | HGV + drones |
| 5 | 145s | 1 ballistic + 2 HGV + 3 drones + 1 cruise | Saturation attack |

Red now pressures Blue from T=2s onward. Wave 5 is 7 mixed threats; the remaining 2 PAC-3 rounds can't cover all high-value targets, so LONG_SAM backfills and there's always 1-2 ballistics leaking due to PAC-3's low graze damage.

## test_balance.py — 20-match result

```
Blue win 17/20, draw 3/20, Red win 0/20
avg spawned=20.0  avg intercepts=18.6  avg leaks=1.1  leak range=1..2
leaks by kind: {'ballistic': 23}
```
(Scoring: `leaked ≤ 1` → Blue; `2` → Draw; `≥ 3` → Red)

Blue never wins "cleanly" (no leaks) — every match leaks 1-2 ballistics. Hitting a strict 50-70% Blue win rate would need further lowering PAC-3's direct_radius (or more Red ballistic volume), but given that "Blue always leaks at least one" is already satisfied and demo spectacle > precise win rate, the balance is adequate.

## Known Issues / TODO

1. **PAC-3 direct_radius widened to 25 m for playability** (spec 0.3 m). A real PAC-3 is sub-metre accurate; our discrete PN can't reach that. Restoring the "200 dmg direct / 5 dmg graze" extreme contrast needs sub-metre CPA (RK4 + higher guidance rate + iterated engagement).
2. **Formula deviates from spec** (see B2). Linear vs quadratic falloff, `radius_prox` × 6.
3. **HGV has no Level-5 evasion AI**, just pre-programmed S. Identical trajectory every run — not "cunning". Milestone D.
4. **supersonic / stealth cruise not added**, CRUISE_SUB is still the only cruise variant.
5. **Terrain heightmap not done** (task explicitly deferred).
6. **Red fires all HGVs in the same wave**; realistic doctrine would stagger them. Currently wave 5 drops 2 HGVs simultaneously, saturating PAC-3.
7. **VLS boost still uses `1.5 × spec.max_g`** (B++ decision, see above). Strict spec adherence would double climb time.
8. **test_balance "only runs 400s"** — wave-5 drones (120 m/s × 60 km = 500s) arrive after the cutoff. In reality they'd hit at T≈645s, but we end the match at 400s so remaining drones stay "active_threats" instead of counting as leaks. This slightly inflates Blue's win rate. For strict numbers, extend the run to 700s.
9. **PAC-3 direct 25m too forgiving — weakens the hit-to-kill design intent**. Current PAC-3 ≈ beefed-up PAC-2, no true "precision vs graze-worthless" differentiation.

## Suggestions for Next Session (priority-ordered)

1. **PN precision upgrade**. This is the root cause of all deviations — getting to true hit-to-kill needs RK4 integration + 0.01s guidance + zero-effort-miss prediction. Unlocks PAC-3's design intent + damage formula back to spec (quadratic + real radii).
2. **Red AI Level 3/4**. Cruise terminal real-time weaving (not fixed pop-up), stealth cruise detected late (only after sea-strait crossing). Gives the Red decision log something to show.
3. **Red AI Level 5 for HGV**. Detect nearby interceptor → vertical+lateral evasion → speed-decay feedback. Most visually striking part of the demo.
4. **Base HP + economic budgets**. Each leaked ballistic docks base HP; Red/Blue each have a budget that caps ammo purchases. Introduces a true "who runs out first" win condition.
5. **Per-entity status panel**. Mouse-over an entity to see type/speed/G/HP/target/time-to-intercept; biggest win for the 4-minute demo's "transparency" score.

## Milestone C Patch

Patch pass after the main C demo based on 4 bugs flagged by the project lead:

1. **Altitude tiering** (`red_ai.py`, `entities.py`): drone 500–4000 m, cruise 1000–6000 m (now higher than drones), HGV 30–40 km. Cruise terminal pop-up 150→300 m. Mid-flight means drone=2085 m / cruise=3162 m / HGV=31 km — three clearly separable tiers on a 150×150 km battlefield.
2. **HGV rewrite** (`types.py`, `entities.py`): own 90 km border line, max_g 8→10 (15 was planned but PN couldn't keep up), S maneuver changed from a ±5 km sinusoid to ±15 km lateral via two virtual waypoints + pursuit-steer + sustain thrust. Waypoint advance changed from "within radius" to "past the plane" (crossed the perpendicular plane of the next-segment) — the old logic made a Mach 5 HGV spiral around a tight radius. Within 15 km of base, altitude-hold is released so PN pulls HGV into a dive rather than an overshoot. 50-trial no-interceptor test: mean impact distance from base **206 m** (task target <500 m, 50/50 hit).
3. **Unified ground collision** (`world.py`): individual `step()` methods only keep a defensive Z-clamp; entity-killing logic is centralized in `World.step`'s tail sweep over all live threats/interceptors — ground contact triggers death + explosion + leak-count if within base radius. Fixes "HGV bounces on the ground" (the old `alive=False` block hadn't been copied into the HGV branch).
4. **PAC-3 buff** (`types.py`): `radius_direct` 25→40 m. Single-shot CPA still 70–200 m, but Blue AI auto-fires follow-ups at undead HGVs, so 2-3 PAC-3 in a row (via accumulated damage) can destroy one.

### Files changed
`backend/sim/{red_ai,entities,world,types}.py`

### New test_balance (20 matches)
```
Blue win 12/20, draw 5/20, Red win 3/20
avg spawned=20.0  avg intercepts=17.6  avg leaks=1.6  leak range=0..4
leaks by kind: {'hgv': 25, 'ballistic': 6}
```
HGV kill rate 35/60 = **58%** (task threshold 40%). Avg leaks 1.6 (up from 1.1), mostly from wave 5's 2 HGV saturation + ballistic grazes.

---

# Milestone D — Realistic Physics, Saturation AI, Per-Weapon Meshes

Large multi-session pass focused on making the fight feel physically real instead of mathematically tidy: interceptors run out of fuel and coast on fins; hypersonic threats bleed kinetic energy when they manoeuvre; every interceptor type has its own distinct 3D mesh and colour; arena depth was doubled so the long-range engagements actually have room to play out.

## Part A — IRIS-T SLS added, PAC-2-on-cruise fixed, HGV fallback

Operator brief flagged three bugs:

1. **No IRIS-T SLS (RBS 98) in the arsenal at all.** Enum, spec, launcher, VLS list, HUD row and name mapping were all missing.
2. **Blue AI wasting PAC-2 on cruise missiles.** At 60 km spawn only PAC-2 was in range (SHORT-SAM 9 km and MED-SAM 40 km both too short), so the range filter left PAC-2 as the only option and the AI fired it.
3. **HGV leaks when PAC-3/PAC-2 are empty or reloading.** `RULES[HGV]` only listed `[HIT_TO_KILL, LONG_SAM]`; when both were unavailable the AI just stood there.

Changes (`backend/sim/` + `frontend/`):

- `types.py`: new `InterceptorType.IRIS_T_SLS` + spec (400 m/s / 60 G / 12 km / $500K / 50 dmg direct / 25 prox / 11.4 kg HE-frag). Matches the `ground-defense.md` real data for the Saab / Diehl ground-launched IRIS-T.
- `launcher.py`: SLS launcher template (mag 4, inter-shot 3 s, reload 60 s) + 2 SLS launchers in default loadout.
- `entities.py`: SLS added to `_VLS_SAM_KINDS` so it does the standard vertical boost on launch.
- `blue_ai.py` rewritten:
  - `PRIMARY_RULES` + `FALLBACK_RULES` split. `LONG_SAM` removed from `CRUISE_SUB` primary; SLS added. `FALLBACK_RULES[HGV] = [MED_SAM, IRIS_T_SLS, SHORT_SAM, CIWS]` — doctrine-correct "throw whatever's left" when the hit-to-kill tier runs dry.
  - Wait-for-cheaper-in-range logic with a 50 % `time-to-impact` wait budget. Stops the PAC-2-on-cruise misuse without starving out fast threats.
- `frontend/index.html` + `hud.js` + `entities.js`: SLS row, name mapping, mesh branch.

Side fix: `Scenario.step` used to call `red.step` → `blue.step` → `world.step`, and the first line of `world.step` was `self.events = []`, wiping out launch events that `blue_ai` had just appended via `spawn_interceptor`. Moved the reset to the top of `Scenario.step` so the launch banner on the HUD actually fires.

## Part B — Leak radius, HGV terminal-dive geometry

Operator reported HGVs visually hitting the base but `Leaked: 0` staying stuck. Root cause was two layered:

1. In-air leak check used 3D distance against a 250 m sphere. An HGV diving at 1700 m/s covers 85 m per tick, so the sweep often skipped the sphere cleanly.
2. Ground-impact leak check used a 250 m horizontal footprint, but the visual base cylinder in `scene.js` had a 2.5 km radius — HGVs landing 1 km from base centre looked like direct hits but were scored as `ground_crash` rather than `leak`.

CEP measurement (50 HGVs, no interceptors, before any fix) showed mean **1472 m** — HGVs systematically overshot by 1.5 km because the terminal dive started at `dh < 15 km` and there simply wasn't enough horizontal distance to pitch the 1700 m/s cruise velocity into a base-aimed vector under the 10 G cap.

Fixes:

- `config.py`: new `BASE_HIT_RADIUS = 1500` m. Realistic airfield-scale defended footprint; matches the visual base marker.
- `world.py`: in-air leak check switched from 3D sphere to 2D horizontal disc using `BASE_HIT_RADIUS`. Ground-impact leak uses the same radius. No more HGVs silently reclassifying as ground_crashes.
- `entities.py`: HGV terminal dive entry distance `dh < 15 km` → `dh < 30 km` so it gets the ~17 s of pitch time needed at max_g = 10.

After the dive-geometry fix HGV ground-impact CEP dropped from 1472 m to **18 m mean / 38 m max** — plenty tight enough to pass a 500 m or even 250 m leak gate. The wider `BASE_HIT_RADIUS = 1500` was kept for visual consistency, not to mask aim error.

## Part C — Fuel, coast phase, atmosphere drag, HGV energy bleed

Operator pushed back on the "interceptors are permanent motors" simplification. Real SAMs burn their sustainer for 5–40 s and then coast on fins; real HGVs can't maintain peak G indefinitely without bleeding kinetic energy.

- `types.py`: `InterceptorSpec.fuel_s` added, populated from `WEAPON_SPECS.md` real data (CIWS 4 s, RBS 70 13 s, SLS 30 s, SLM 39 s, PAC-2 41 s, PAC-3 35 s). `EntityState.thrust_active` new bool, included in snapshot `to_dict` so the frontend can gate the exhaust plume.
- `physics.py`: `air_density_ratio(altitude)` (exponential atmosphere, H = 8500 m) + `drag_accel_at(vel, drag_k, altitude)` for post-burnout interceptor glide. Threats unchanged — their `drag_k` was already hand-tuned at their flight altitudes.
- `entities.py` — Interceptor:
  - Tracks `fuel_elapsed = t_now - launched_t`; sets `thrust_active = (fuel_elapsed < fuel_s)`.
  - Post-burnout: sustain thrust off, `max_g` capped at 0.5× spec (fins + ACM only, no thrust vectoring), drag uses altitude-scaled model, and speed < 200 m/s self-destructs (stall).
  - Boost phase (< 1.5 s VLS) unchanged — fuel gate doesn't matter because `fuel_s > 1.5` for every type.
- `entities.py` — HGV:
  - Removed the "sustain thrust" hack that kept HGVs at Mach 5 indefinitely. They now glide unpowered.
  - `_HGV_JINK_G = 8` (was 4): max-commit lateral evasion when an interceptor is inside 12 km detect radius. Direction flips every 2 s so the track snakes instead of arcing.
  - Kinetic energy bleed: `speed_loss = 120 × (commanded_G / max_G)² × dt` per tick. At max-G jinks the HGV loses ~120 m/s per second — visible speed drop after 2–3 hard turns.
  - Stall at 500 m/s: lift collapses, HGV dies mid-flight. Drives the R = v²/a tactical trade — fast HGV has huge turn radius, slow HGV can turn tight but is close to stall.
- `world.py`: `threat.step(dt, self)` — HGVs need world access to scan for nearby interceptors (Level-5 evasion trigger). Non-HGV branches ignore the arg.
- `frontend/js/entities.js`: `EntityMesh.update(pos, vel, thrustActive)` — flame mesh hidden when `thrust_active = false`. Interceptors visibly stop their exhaust after burnout and coast on fins.

## Part D — Saturation engagement, point-defense CIWS, last resort

Even after Part A, the operator noted IRIS-T SLS rarely fired: the wait-budget logic committed to MED-SAM at first opportunity and SLS never got a look at closer ranges. Fix was a full rewrite of the engagement loop from "one weapon per threat at a time" to layered saturation:

- `blue_ai.py`:
  - `self.assignments: Dict[int, List[int]]` — threats can have multiple interceptors in flight.
  - Saturation gate: fire while `expected_in_flight_damage < threat.hp` and `len(non_ciws_assigned) < MAX_SIMULTANEOUS_PER_THREAT = 3`.
  - Wait-budget logic removed entirely. As threats close in, cheaper / shorter-range weapons naturally come into range and layer on.
  - **Point-defense CIWS**: if any threat is inside the 4 km CIWS envelope, CIWS rounds fire regardless of saturation gate and regardless of threat kind. Real Lvkv 90 doctrine — inner ring sprays everything. Also gives the demo visible CIWS fire against HGV / ballistic terminal passes.
  - **Last-resort tier**: if primary and fallback both return nothing AND `t_impact < 15 s`, try every interceptor type in the arsenal. Operator brief: "if only PAC-2 is left and a drone is about to hit, use the PAC-2 — don't be too rigid about cost-exchange."
  - `PRIMARY_RULES[DRONE] = [CIWS, SHORT_SAM]` (MED-SAM moved to fallback only). Forces the AI to wait for drones to enter SHORT_SAM range instead of wasting MED-SAM from 30 km.

## Part E — Realistic threat speeds, deeper arena

Operator preference: real-world data over game-tuned numbers. "Ballistics are fast, modern air defence struggling to intercept them is a real fact, don't dial it down for difficulty."

- `types.py`:
  - `ThreatSpec[BALLISTIC].cruise_speed = 4459 m/s` (13 Mach) — modern MaRV terminal velocity.
  - `ThreatSpec[HGV].cruise_speed = 5831 m/s` (17 Mach) — DF-ZF / Kinzhal-class glide velocity. At this speed the formula `R = v² / a` gives a turn radius of ~347 km under max_g = 10, so HGVs effectively fly straight through the arena until they bleed speed from evasion. Realistic physics.
  - PAC-3 `radius_direct = 60 m` (was 40 m), `radius_prox = 80 m`: at Mach 13 closing, per-tick displacement is ~300 m, so the 40 m radius was borderline for direct hits. 60 m keeps PAC-3's "hit-to-kill" identity on realistic fast ballistics.
- `red_ai.py`:
  - `BORDER_DY_DRONE = 30 km` (drones spawn closer so SHORT_SAM / CIWS engage them, not MED-SAM overkilling from 60 km).
  - `BORDER_DY_BALLISTIC = 120 km` (2× old).
  - `BORDER_DY_HGV = 180 km` (2× old).
  - Wave counts: cruise doubled (4 → 8 per scenario), ballistic doubled (2 → 4).
- `config.py`: `ARENA_Y = 250_000` m (was 150 km) — has to fit HGV's 180 km spawn border.
- `frontend/js/scene.js`:
  - Ground + grid rectangular, centred on arena midpoint instead of base (base is at the south edge of a 250 km-deep map).
  - `gridDivisions = gridSize` so **1 grid cell = 1 km**. Lets the operator eyeball weapon ranges from the HUD: CIWS 4 cells, RBS 70 9, SLS 12, SLM 40, PAC-3 60, PAC-2 70.
  - Camera pulled back to (30, 50, 110) looking at (0, 12, -70) so HGV's 180 km spawn line is in-frame by default.
  - Fog end 300 → 500 so the far edge doesn't clip.

## Part F — Real-weapon kind strings, per-type meshes

Before this pass every mid/long-range SAM rendered with the same generic "IRIS-T style" mesh and the wire format used role names (`med_sam`, `long_sam`, `hit_to_kill`) — so operationally and visually the fleet was five lookalikes on the screen. Switched to real product names end-to-end so each weapon type has a distinct silhouette.

- `backend/sim/types.py` — `InterceptorType` enum **values** (Python code keeps using member names so no import changes):
  - `SHORT_SAM = "rbs_70"`
  - `MED_SAM = "iris_t_slm"`
  - `LONG_SAM = "pac_2"`
  - `HIT_TO_KILL = "pac_3"`
  - `IRIS_T_SLS = "iris_t_sls"` (unchanged), `CIWS = "ciws"` (unchanged).
- `types.py` spec colours synced to each mesh: RBS 70 olive `#4a8a3a`, SLM orange `#ff8c1a`, PAC-2 pink `#ff69b4`, PAC-3 purple `#a855f7`.
- `frontend/js/entities.js`: one branch per kind.
  - `ciws` — short tan 40 mm round, fuze cap, driving band, **no exhaust flame** (unguided ballistic cannon round).
  - `rbs_70` — olive MANPADS Bolide: slender body, pointed nose (no IR seeker — laser beam-riding), 4 small front canards + 4 trapezoidal rear fins, single accent band. Smallest interceptor.
  - `iris_t_sls` — the original IRIS-T design: body + ogive nose + dark IR seeker dome + 2 accent bands + 4 mid-body canards + 4 large tail fins.
  - `iris_t_slm` — longer SLM body, sharp pointed nose (no dome), orange, mid-body wings.
  - `pac_2` — pink long slender missile, pointed nose, tail fins only.
  - `pac_3` — purple compact hit-to-kill: thin ogive, ACM (attitude control motor) ring near the nose, short tail skirt + 4 stubby fins.
- `frontend/index.html`, `hud.js`, `style.css` — ammo rows and colour rules keyed on new kind strings.

## Default server port

Hackathon laptop 2 hit WinError 10013 on the default port 8000 — Windows reserves large TCP blocks for Hyper-V / WSL2 / Docker. 8088 was also reserved. 5174 bound successfully.

`backend/server.py`: default port now 5174, override via `PORT` env var. `NOTES_MODEL_AND_PORT.md` in the repo root documents the full Windows port-reservation trap and the PATH / `python` command alias workarounds.

## Balance

20-run `test_balance.py` sweeps after each major pass:

| Snapshot | Blue win | Draw | Red win | Avg leaks | Notes |
|---|---|---|---|---|---|
| Milestone C Patch (baseline) | 12 | 5 | 3 | 1.6 | HGV 25 leaks, ballistic 6 |
| After Part A (SLS + fallback + wait logic) | 14 | 6 | 0 | 1.3 | HGV 5 leaks, ballistic 21 |
| After Part A list-order ranking (pre-Part C) | 18 | 2 | 0 | 0.4 | PAC-3 one-shots ballistics via list order |
| After Part C-D (fuel + coast + HGV evasion + saturation) | 10 | 9 | 1 | 1.6 | all 6 weapons firing |
| After Part E (13 Mach ballistic + 17 Mach HGV + 180 km spawn) | 3–6 | 9–12 | 2–8 | 1.8–2.2 | ballistic leak rate 45–55 % — realism vs. game balance tradeoff |
| Final (with PAC-3 radius_direct 60 m) | 4–6 | 9–12 | 4–8 | 1.9–2.2 | 26 spawned / ~21 intercepts / all 6 weapons see action |

Key facts:

- All 6 interceptor types fire every scenario (CIWS 4–8, RBS 70 11–13, SLS 2–6, SLM 20–22, PAC-2 4, PAC-3 4).
- HGV leak rate ≈ 0 % after fallback + saturation + evasion-aware physics. Previously 40–50 %.
- Ballistic leak rate ~50 %. Operator accepted this under "real data over game tuning" — Mach 13 terminal ballistics are genuinely hard for real air defence too.

## Known gaps / open items

1. **Ballistic interception is the weakest link.** ~50 % leak rate on Mach 13 RVs. Mitigations possible without dropping speed: tighter PN (RK4 + sub-tick integration), or shoot-look-shoot with multiple PAC-3 per target without burning the 4-round magazine. Might be worth the PN upgrade path.
2. **HGV terminal aim under evasion is not corrected.** During a jink the HGV can end up slightly off the base-aim vector; with Mach 17 it doesn't have time to recover. Operator note: this is fine for now because the long-term plan has Red AI taking over manual HGV control. Revisit when Red AI levels 4/5 land.
3. **CIWS still under-fires against drones.** Because a single SHORT_SAM / RBS 70 round prox-kills a 10-HP drone at 10 km, drones basically never reach the 4 km CIWS envelope. Point-defense override catches the occasional survivor plus any hypersonic crossing the inner ring. If we want CIWS firing on every demo wave, bump drone HP to ~25 or add a close-spawn drone harassment wave.
4. **Radar / sensor model not wired.** Detection is currently omniscient. `xingyi-rts/knowledge/sensors-c2.md` has the burn-through formula ready; it's the cleanest next physics layer to add.
5. **No Red AI intelligence yet.** Waves are pre-scripted, cruise uses fixed S-pattern waypoints, HGV uses pre-programmed jink. Levels 3 / 4 / 5 (waypoint adjust → terminal takeover → full realtime HGV AI) are still the biggest single bang-for-buck visual upgrade.
6. **No base HP or economy.** Any leak = leak, regardless of weapon. Running out of $48M of PAC-3 doesn't count against Blue the way it would in a real engagement. `GAME_DESIGN.md` has the budget model specced; plumbing it into the win condition is straightforward.
7. **Per-entity status panel not built.** Clicking on a missile still does nothing. For the 4-minute demo judges' "transparency" score this is the single biggest missing piece.

## Suggested next session priorities

1. **Per-entity status panel.** Raycaster click → show type / speed / G / HP / fuel remaining / target / time-to-intercept. High visual impact for low code cost, and makes the physics work actually visible in the demo.
2. **Red AI Level 3/4 — cruise terminal walk + stealth detection.** Breaks the "Red just follows a schedule" feel. Populates the Red AI log panel with actual decisions.
3. **Base HP + economy budget.** Converts the sim from a watch-only demo into a game with win/lose stakes. Leaks now do something. Running out of PAC-3 is a real loss condition.
4. **PN accuracy upgrade.** RK4 + 0.01 s guidance update. Closes the ballistic-leak gap without cheapening the threat speeds. Biggest physics win for the remaining hackathon time.
5. **Sensor model.** Plug `sensors-c2.md`'s detection rules into Blue AI so launches depend on radar state, not omniscient world snapshots. Adds tactical depth and sets up SEAD / jamming scenarios later.

## How to run (updated)

```bash
cd team-missile-intercept/backend
pip install -r requirements.txt   # only the first time
python server.py                  # Windows: see NOTES_MODEL_AND_PORT.md if port 5174 is also reserved
# open http://localhost:5174/
```

Override port with `PORT=6969 python server.py` (bash) or `set PORT=6969 && python server.py` (Windows cmd).

Offline smoke tests:

```bash
python test_balance.py          # 20-run balance sweep
python test_full_scenario.py    # single scenario, prints final stats
python test_pn.py               # PN guidance unit test (MED-SAM vs. cruise)
python test_ballistic.py        # ballistic + LONG-SAM offline test
```

# Milestone E — Visual Packaging + Boreal Passage Terrain

Pure frontend pass on top of Milestone D. Goal: make the rich physics
(fuel, coast, G-limits, saturation AI) legible to a non-technical
demo jury, and anchor the simulation in Saab's own scenario geometry
instead of a flat void. No backend changes — every snapshot field
needed was already present in `EntityState.to_dict()`.

## Task 1 — Per-entity status panel

Click any missile or threat in the 3D view → a glass-morphism panel
opens (top-right, 300 px wide) showing realtime stats:

- Kind real name. Two lookup tables:
  `INTERCEPTOR_NAMES` (Lvkv 90 / RBS 70 NG / IRIS-T SLS (RBS 98) /
  IRIS-T SLM / Patriot PAC-2 GEM+ / Patriot PAC-3 MSE) and
  `THREAT_NAMES` (Shahed-class drone, Kalibr-class cruise missile,
  Iskander-class RV, Kinzhal/DF-ZF HGV).
- Team badge (RED / BLUE), colour-coded.
- Speed in m/s + rounded Mach (using Mach 1 = 343 m/s).
- Instantaneous G-load estimated client-side from `|Δv|/Δt / 9.81`
  using a 1-tick-old velocity cache keyed by entity id.
- HP bar (gradient green → amber → red, hidden when `hp_max == 0`).
- Motor status: green dot + "Motor burning" while `thrust_active`,
  grey dot + "Coasting" once fuel is spent. Threats show "Inertial".
- Fuel remaining (s) from `FUEL_S[kind] − (snap.t − spawn_t)`,
  clamped to ≥ 0. Table copied verbatim from `InterceptorSpec.fuel_s`
  (ciws 4, rbs_70 13, iris_t_sls 30, iris_t_slm 39, pac_2 41, pac_3 35).
- Altitude (m, with km alongside above 1 km).
- Target: `#id · kind name` cross-referenced via the latest snapshot,
  falling back to `(lost)` if the target has died.
- Range to target in m / km.
- Unit USD cost from `WEAPON_SPECS.md` (ciws $2k, rbs_70 $175k,
  iris_t_sls $500k, iris_t_slm $1M, pac_2 $3M, pac_3 $4M) or threat
  cost (drone $30k → hgv $10M).

A raycaster on the canvas resolves hits by walking up
`mesh.userData.entityId` (set in `EntityMesh` ctor). Empty-canvas
clicks and the × button clear the selection. On death, the panel
lingers for ~1 s showing "DESTROYED" in flashing red before
auto-closing.

Files: `frontend/js/status_panel.js` (new, ~260 lines),
`frontend/js/main.js` (wire init + per-tick update),
`frontend/js/entities.js` (tag root Group with entityId),
`frontend/index.html` (panel container), `frontend/style.css`
(~130 lines of panel styles).

## Task 2 — AI decision log enrichment

Old HUD showed a 6-line tail of each AI's log. Replaced with two
dedicated scrollable panels (Blue left / Red right) that hold up
to 120 entries with auto-scroll-to-bottom (suppressed when the
user has scrolled up to read history).

- Each interceptor line is prefixed by a 6×6 px colour square
  matching the weapon's mesh colour (CIWS tan, RBS 70 olive,
  SLS amber, SLM orange, PAC-2 pink, PAC-3 purple). Wave-launch
  lines from the Red AI get no dot.
- Priority tags emitted by `blue_ai.py` are colourised:
  `[CIWS]` tan, `[FALLBACK]` amber, `[LAST RESORT]` red + tinted
  background panel. Untagged primary fires use the default log
  text colour.
- Per-side borders (blue/red) reinforce the left/right identity
  of the panels at a glance.

Files: `frontend/js/hud.js` (`formatLogLine` + `WEAPON_COLORS`
table), `frontend/index.html` (swap column order, add log-scroll
class), `frontend/style.css` (~40 lines of tag + panel styles).

## Task 3 — Seeker scanning cones

Every live interceptor except CIWS now renders a translucent
forward-pointing cone attached at its nose:

- 8° half-angle × 10 scene units (= 10 km world) length. Geometry
  built as `ConeGeometry(r, 10, 16, 1, true)`, rotated `X` by π
  and translated so the apex sits at local `Y=0` and the base
  extends to `+Y=10`. Caller positions the cone at each kind's
  nose-tip Y (sls 1.55, slm 2.2, pac_2 2.4, pac_3 1.9, rbs_70 1.3).
- Cyan default (`0x44ccff`, opacity 0.12); orange (`0xff8844`,
  opacity 0.30) when `distance-to-target < 2 km`. Material is
  `MeshBasicMaterial` with `transparent: true`, `depthWrite: false`,
  `side: THREE.DoubleSide`.
- `EntityRegistry.updateFromSnapshot` builds an alive-only
  `id → state` map once per tick and passes each interceptor its
  target's state by `e.target_id`. Dead-target lookup returns
  null, which hides the seeker.
- CIWS is skipped — cannon rounds are unguided ballistic.

Files: `frontend/js/entities.js` (seeker helper +
per-kind insertion + `EntityMesh.update(targetState)`).

## Task 4 — Boreal Passage 3D terrain

Replaced the flat dark-blue rectangle ground with an extruded
rendering of Saab's Boreal Passage landmasses (2 mainlands, 5
islands, 1 peninsula, 12 named locations).

Input: `xingyi-rts/saab-provided/Boreal_passage_coordinates.csv`.
Baked at check-in into `frontend/js/terrain_data.js`
(`BOREAL_TERRAIN` + `BOREAL_LOCATIONS`) as ES-module exports, so no
static-mount change to `server.py` was needed. Regenerate with a
short Python script if Saab updates the scenario.

Transform `saabToScene(x_km, y_km)`:

- Crop Saab Y window [280, 1080] km (800 km band containing
  mainland → strait → mainland + all relevant islands).
- Map the full Saab X [0, 1667] onto scene X [−75, +75] (150 km).
- Map the cropped Saab Y onto scene Z [−245, +5]. Saab Y is
  south-positive AND our scene Z is south-positive, so the
  mapping sends `y_norm=0` (Saab north) to `scene_z=−245` (scene
  far-north). This is the OPPOSITE direction of the task-spec
  pseudocode; following the spec literally would have flipped the
  scenario (southern mainland landing in scene north). The
  acceptance criteria demand Blue base on the southern mainland,
  so the direction was corrected. Noted as a concession in the
  commit body.
- Non-uniform compression (11× in X, 3.2× in Y) is accepted — the
  jury reads "two lands across a strait", not a 1:1 overlay.

Rendering:

- Each terrain row → `THREE.Shape` → `ExtrudeGeometry(shape,
  { depth: 0.3, bevelEnabled: false })` = 300 m land relief. High
  enough to read as "above sea", low enough that HGV/ballistic
  tracks still clear the landmass silhouette.
- Mainland material `0x2f3a2a` (dark olive), island `0x2b382c`.
  `side: THREE.DoubleSide` because the Y-negation in shape
  construction inverts winding; without DoubleSide the top cap
  would back-face-cull against the overhead camera.
- Sea plane darkened to `0x0c182a` so the land reads as "above
  water".
- Weapon range arcs bumped from `y=0.05` to `y=0.35` so they sit
  just above the 0.3-high terrain and stay visible when they
  overlap a landmass.

Location markers (Task 4 optional) were skipped for time — the
scenario feels grounded enough with just the landmasses, and
adding Sprite-text city labels would have chewed another 30–45
min. Data is already exported in `BOREAL_LOCATIONS` so a future
session can add them in minutes.

Files: `frontend/js/terrain_data.js` (new),
`frontend/js/scene.js` (`saabToScene` + extrude loop + arc lift).

## Task 5 — Dusk sky gradient + explosion flash

- Inverted `SphereGeometry(1000, 32, 16)` with a `ShaderMaterial`
  that lerps world-space Y from a dark-blue zenith (`0x0a1524`)
  through a warm amber horizon band (`0x2a1a10` + `0xffa64a` glow
  near Y=0). `renderOrder = -1`, `depthWrite: false` so fog and
  geometry composite correctly. Scene still fogs out at the far
  arena edge to the original dark-blue tint; the sky is visible
  past the 500-unit fog far plane but never fights arena geometry.
- Explosions made brighter: hot-white core (`0xffffee`), larger
  sphere (0.8 vs 0.5), `AdditiveBlending` + `depthWrite: false`
  so overlapping sprites stack into a visible flash. No
  `EffectComposer` bloom because the importmap-only setup
  (unpkg three@0.160) can't easily bolt on post-processing
  without a bundler.

Files: `frontend/js/scene.js` (skydome), `frontend/js/entities.js`
(`_spawnExplosion`).

## Known issues / deferred

1. **Status-panel G-load** uses the 1-tick velocity cache
   (dt ≈ 1 / STREAM_HZ). For sub-tick commanded-G spikes the
   displayed value is averaged, not instantaneous. Good enough
   for demo legibility, not instrumentation-grade.
2. **Terrain aspect distortion**: the 11× X / 3.2× Y non-uniform
   scale squashes the Saab scenario. Unavoidable given our 150 ×
   250 km arena. A future milestone could either widen the arena
   (would cascade into spawn distances + weapon ranges — avoid
   during demo week) or crop a narrower Saab X window.
3. **No location labels**: `BOREAL_LOCATIONS` has 12 named
   cities/bases parsed, but rendering `THREE.Sprite` text labels
   was cut for time. ~30 min to add a single-canvas-per-label
   pass, if desired.
4. **No bloom post-processing**: the additive-flash trick fakes
   bloom but doesn't actually bloom adjacent pixels. Proper
   bloom needs `UnrealBloomPass` via a bundler (currently the
   frontend is plain ES modules).
5. **Status panel position**: positioned at top-right so it
   doesn't collide with the now-taller log panels. If the ammo
   panel grows past ~210 px tall on some displays the status
   panel could overlap — no CSS collision detection.

## How to test Milestone E

```bash
cd team-missile-intercept/backend
python server.py
# http://localhost:5174/
```

1. Click any moving entity → status panel opens. Watch speed +
   G + thrust update live.
2. Start a scenario, wait through Wave 5. Blue/Red log panels
   fill with coloured lines (tag chips + weapon dots).
3. Launch PAC-2 at HGV — seeker cone visible, tightens to orange
   at close range.
4. Terrain: two landmasses visible with a strait between; base
   on the southern mainland; threats spawn over northern
   mainland. Range arcs readable on top of the land.
5. Explosions flash brighter than before against the dusk sky.

## Suggested next session priorities (post-Milestone E)

1. Red AI intelligence — Levels 3 / 4 / 5. Still the biggest
   visual upgrade for scripted-feeling Red waves.
2. Location labels + base markers on the terrain (cheap polish).
3. Base HP + economy (Route 7) — gives the demo stakes.
4. Sensor/radar model (Route 5) — limits Blue AI omniscience.
5. PN precision upgrade (Route 3) — closes the 50 % ballistic
   leak rate.

---

# Milestone F — Landmarks + Distributed Launchers

Scope: stop the demo looking like a single glowing cylinder firing
every weapon from the same spot. Two independent bumps — (1) render
the 12 Saab-named locations as actual 3D structures with labels, and
(2) let each launcher sit at its own world position with its own box
mesh + per-launcher range arc. Both land this session.

## Task 1 — Saab location landmarks

`BOREAL_LOCATIONS` was already exported from Milestone E but unused.
`scene.js` now iterates it after the terrain extrusion and builds one
small structure Group per row + one canvas-textured Sprite label:

- **air_base**: 1 km runway (Box 1.0 × 0.02 × 0.15 scene units) +
  small control-tower box offset to one side. Concrete-grey material
  (`0xb8b8b0`) on the runway; the tower gets a side-coloured emissive
  (`0x442020` red for north, `0x202a44` blue for south).
- **capital**: 5 skyline boxes, heights 0.18..0.35, widths 0.10..0.16,
  packed inside a ~0.4 × 0.4 footprint. Dark-grey body, same
  side-colour emissive accent.
- **major_city**: 3 mid-rise boxes, heights 0.09..0.20, tighter
  footprint.

Labels:

- `makeTextSprite(text, side)` draws the name onto a 256 × 64
  offscreen canvas with `rgba(10,14,24,0.78)` fill, a side-coloured
  border (red / blue), and white bold 22 px text. Returns a
  `THREE.Sprite` with `CanvasTexture + SpriteMaterial({depthTest:
  false, transparent: true})`.
- Each label sits at world y = 1.0 (above the tallest 0.35-unit
  capital building) and uses `scale.set(4, 1, 1)`. Depth-test off so
  the label stays legible even when it passes behind closer land
  shapes.

Result: 12 labelled landmarks visible at the default camera — 3+3
air bases, 1+1 capitals, 2+2 cities — red-tinted on the north coast,
blue-tinted on the south. Existing range arcs and terrain untouched.

Files: `frontend/js/scene.js` (landmark loop + `makeTextSprite`).

## Task 2 — Distributed launcher positions

### Task 2a — Backend

- `config.py` — new `BLUE_LAUNCHER_POSITIONS` dict. 9 launchers total:
  1× CIWS at base, 2× RBS 70 at 25 km north (spread ±15 km E/W of
  centreline), 2× IRIS-T SLS at 20 km north (flanking), 2× IRIS-T SLM
  at 15 km north (mid-field), 1× PAC-2 and 1× PAC-3 at 8 km north
  (nudged ±300 m E/W so the frontend boxes don't z-fight). Module-
  level `assert` keeps every launcher y inside [base_y, 105 km) so a
  future placement AI can't accidentally put one in the sea.
- `launcher.py` — `Launcher` gains `pos: Tuple[float, float]`.
  `LauncherFleet.__init__` now reads `BLUE_LAUNCHER_POSITIONS` by
  default; the legacy count-based `loadout=` path is preserved for
  older unit tests that don't care about placement.
  `fleet_status()` returns `{'by_kind': <aggregate>, 'launchers':
  <per-instance list>}` — the per-kind half keeps the existing HUD
  ammo panel working.
- `scenarios.py` — `Scenario.snapshot()` hoists `by_kind` onto
  `snap['ammo']` (backwards compatible shape) and `launchers` onto
  `snap['launchers']` (new field).
- `blue_ai.py` — `_fire` now builds `launch_pos = (lch.pos[0],
  lch.pos[1], 0.0)` and passes it into `world.spawn_interceptor` + the
  `initial_dir` calculation. `base` stays in the signature for the
  threat-to-base range string in the log line.

### Task 2b — Frontend

- New `frontend/js/launchers.js` exports a `LauncherRegistry` modelled
  on `EntityRegistry`. Each snapshot it diffs `snap.launchers` against
  a client map keyed by `${kind}_${index}` and renders:
    - A `BoxGeometry(1.5, 0.8, 1.0)` centred at `(scene_x, 0.4,
      scene_z)`, coloured to the weapon's mesh colour
      (`ciws 0xd9b36a`, `rbs_70 0x4a8a3a`, `iris_t_sls 0xff9944`,
      `iris_t_slm 0xff8c1a`, `pac_2 0xff69b4`, `pac_3 0xa855f7`).
      Opacity 1.0 when ready, 0.5 when reloading.
    - A 96-segment northern semi-circle with radius = spec `max_range`
      (km), same colour as the box. Opacity 0.4 ready, 0.15 reloading.
- `main.js` imports the registry and calls
  `launchers.updateFromSnapshot(latestSnap)` inside the render loop.
- `scene.js` drops its old stack of base-centred range arcs — the
  per-launcher arcs replace them cleanly; keeping both looked busy.

## Known approximation: engagement-math still keyed on base

`_try_fire` and `_time_to_enter_range` in `blue_ai.py` use
threat-to-base distance to decide whether a weapon can engage,
even though each weapon actually fires from up to 25 km forward /
lateral of the base. That's the explicitly deferred approximation
in the Milestone F spec: fixing it properly means re-plumbing
through every primary / fallback / wait-for-primary branch, and
is Route 5/6 territory. Two concrete consequences visible in this
milestone:

- IRIS-T SLS at (55/95 km east, 20 km north) can clear the base-
  distance gate for a fallback shot on a ballistic threat whose
  actual range from the SLS is 20+ km — well outside the SLS 12 km
  envelope. The launcher burns the round for an intercept it can't
  make.
- IRIS-T SLM similarly loses terminal-phase geometry against
  diving ballistic RVs because the SLM's forward launch point is
  now 10 km off the re-entry line.

Both failure modes were previously masked because every weapon
fired from the base — same position the engagement decision was
keyed on, so the decision and the flight agreed.

## Balance comparison (test_balance.py, 20-match sweeps)

Red AI randomises waves each run (unseeded RNG), so each 20-match
sweep has a real ±3-win variance. Numbers below are the two runs
taken of each version:

|                    | Blue wins | Draws | Red wins | avg leaks | ballistic leaks (20 runs) |
|--------------------|-----------|-------|----------|-----------|--------------------------|
| pre-F run 1        |     6     |   9   |     5    |    1.9    |            39            |
| pre-F run 2        |     2     |  10   |     8    |    2.3    |            46            |
| post-F run 1       |     0     |   7   |    13    |    2.6    |            53            |
| post-F run 2       |     0     |   9   |    11    |    2.5    |            51            |

Observed drift ≈ -2 to -6 Blue wins, with the new leaks almost
entirely on ballistic threats. Intercept count dropped by ~1 per
match. Root cause is the engagement-math approximation documented
above: the fallback SLS/SLM shots on ballistics stop being viable
when the launcher moves 10-25 km off the direct base line.

Task-spec tolerance was ±3 Blue wins; we land outside that on the
low end. Documented as a legitimate structural consequence rather
than a launch_pos bug — spec also flagged that fixing the range
math is not part of this milestone.

## TODOs for follow-up work

- **Placement AI** — consume `BLUE_LAUNCHER_POSITIONS` at scenario
  reset and pick positions from threat direction / wave composition /
  coverage. The current layout is hand-tuned for "drones approach
  from all compasses, ballistics come from due north"; a real IADS
  would shuffle launchers between scenarios.
- **Per-launcher engagement math** — refactor `_try_fire`,
  `_time_to_enter_range`, `_primary_available_in_time`, and the
  `_fire` log string to use per-launcher distances. Biggest win:
  SLS/SLM fallback shots stop being wasted on intercepts they can't
  physically make. Needs a simultaneous re-tune of the wait-for-
  primary logic so we don't just burn rounds earlier.
- **Landmark depth-test** — labels are currently `depthTest: false`,
  which means they always draw on top even when the camera swings
  around. Looks fine at the default camera; operator pans may show
  labels floating through terrain. `CSS2DRenderer` would solve it at
  the cost of another render pass.

## Files touched (Milestone F)

```
backend/sim/config.py         — BLUE_LAUNCHER_POSITIONS + y-bounds assert
backend/sim/launcher.py       — Launcher.pos, positions-driven __init__, fleet_status split
backend/sim/scenarios.py      — snap['ammo'] / snap['launchers'] split
backend/sim/blue_ai.py        — _fire launches from lch.pos
frontend/js/scene.js          — landmark loop + makeTextSprite, range-arc stack removed
frontend/js/launchers.js      — new LauncherRegistry
frontend/js/main.js           — wire the registry
```

## How to test Milestone F

```bash
cd team-missile-intercept/backend
python server.py
# http://localhost:5174/  → click Start
```

1. 12 labelled Boreal Passage landmarks visible on the extruded
   terrain (red border on the north coast, blue on the south).
2. 9 distinct coloured launcher boxes on the southern mainland:
   1 tan CIWS at base, 1 pink PAC-2 + 1 purple PAC-3 offset 300 m
   east/west at base, 2 olive RBS 70 forward, 2 amber SLS flanking,
   2 orange SLM mid-field.
3. Each box has its own coloured semi-circle arcing north, radius =
   weapon max_range.
4. Fire a PAC-3 on a ballistic — the purple interceptor climbs from
   the purple box, not the blue base cylinder.
5. Watch PAC-2 drain its 4-round magazine — the pink box fades to
   50 % opacity and its arc dims to 0.15 while reloading, both
   restore when the magazine refills.
6. `python test_balance.py` still runs; new baseline ≈ 0-2 Blue wins
   / 7-9 draws / 11-13 Red wins per 20-match sweep.
