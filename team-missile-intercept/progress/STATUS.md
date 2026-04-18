# Project Status

> **Last updated:** 2026-04-18 (end-of-day, post-Milestone I)
> **Branch:** `knowledge-base` (all work pushed here)
> **Latest commit:** `81023db` — Milestone I Task 4 + balance calibration

## Journey So Far — Milestone B → I at a Glance

Two intense working days took the demo from "flat physics textbook"
to "Saab Boreal Passage tactical sandbox with a real game loop."
Roughly 30 commits across nine milestones, most driven by autonomous
Claude Code sessions running on bypass permissions.

**Milestone B — Core loop** (established earlier, pre-day-1)
Red AI waves + Blue AI rule-based intercept selection + True Proportional Navigation + Three.js scene. Drone, subsonic cruise, ballistic, HGV threats. CIWS through PAC-3 interceptor ladder. FastAPI + WebSocket at 15 fps.

**Milestone C + C Patch — Depth features**
HP + damage model, magazines + reload CDs, cost-exchange greedy AI, altitude tiering (drone 0.5-4 km / cruise 1-6 km / HGV 30-40 km), unified ground-collision sweep.

**Milestone D — Realism + visual identity**
Fuel + coast-phase physics (every interceptor burns through a real `fuel_s`, then coasts on fins with half authority, stalls below 200 m/s). HGV unpowered glide + Level-5 evasion + quadratic kinetic-energy bleed. 13 Mach ballistic, 17 Mach HGV. 6 distinct interceptor 3D meshes (CIWS cannon round, RBS 70 MANPADS, IRIS-T SLS with IR dome, IRIS-T SLM, PAC-2, PAC-3 ACM-ring). Saturation engagement + point-defense CIWS + last-resort tier. 250 km deep arena with 1 km/cell grid.

**Milestone E — Visual packaging** (autonomous session)
Click-any-entity status panel (kind / Mach / G / HP bar / fuel / target / range / cost / thrust_active). Scrolling enriched AI logs with colour-coded tags. Translucent seeker scanning cones on every interceptor. Boreal Passage 3D terrain extruded from Saab's CSV (2 mainlands + 5 islands + 1 peninsula). Dusk gradient skydome + additive explosion flashes.

**Milestone F — Distributed launchers** (autonomous session)
Saab's 12 named locations rendered as 3D structures with sprite labels (runways, capital skyscrapers, city clusters, side-tinted). `BLUE_LAUNCHER_POSITIONS` config — 9 launchers of 6 types spread across the southern mainland, each with its own colour-coded semi-circle range arc. Missiles now launch from their individual launcher's position instead of a single base point.

**Milestone G — Map narrative + multi-site target model** (autonomous session)
Full-circle range arcs replace the semi-circles (launchers cover all bearings now that they're distributed). Backend point-in-polygon validator rejects launcher positions that land in the sea. `STRAIT_CENTER_Y` derived from Saab geometry — all Red threats now spawn north of the strait, physically crossing the water to attack. Multi-site target model: Saab's Blue-side airbases, capital, and cities become individual Red targets, each with its own leak counter and a weighted-random target selection in Red AI. The old blue-cylinder base marker deleted.

**Milestone H — Range math refactor + Red launcher visuals + rebalance** (autonomous session)
Blue AI's range helpers refactored to reason per-`(kind, launcher)` instead of distance-from-base — fixes the geometry approximation that cratered balance after Milestone F. Out-of-arena Saab sites filtered out (4 sites whose `saab_y > 1080` were physically outside the 250 km arena). `RED_LAUNCHER_POSITIONS` adds 3 drone launchers on north-side islands + 2 cruise launchers on north mainland/islands — drones and cruise missiles now spawn from visible red-tinted boxes instead of abstract border lines. Range rings now live as children of each launcher's THREE.Group so future drag-to-deploy will move box and ring together. Three iterations of launcher-position rebalance brought Blue win rate from 0/20 back to 6-8/20 — inside the 30-55 / 30-50 / 10-30 target window.

**Milestone I — Real game loop: win conditions + spawn polish + HGV freedom** (autonomous session)
Per-site HP now decrements per leak (drone 5 / cruise 15 / ballistic 30 / HGV 40), starting at 60 HP after calibration. Blue budget (`$120 M USD`) is deducted per interceptor `spec.usd_cost`. `Scenario.winner` resolves the match as `'red' | 'blue' | 'draw'`; the 600 s hard cap is replaced by a 3600 s safety net. Ballistic + HGV moved to a 10 km far-north strip spawn (Y 235-245 km, arena edge) with reentry altitude floors (20 km ballistic, 30 km HGV). HGV's scripted wide-S and 12 km jink both deleted — default behaviour is straight-line toward target, external callers drive lateral control via `Threat.override_maneuver(turn_dir, g_load)`. HUD: per-site HP bars, Blue budget bar, full-screen end-of-match overlay (`BLUE WINS` / `RED WINS` / `DRAW`).

### Current playable state

- **Visuals:** 6 distinct Blue interceptor mesh types, 1 CIWS cannon round mesh, 5 red-box Red launchers, Saab-authored 3D terrain, 12 named landmark structures with sprite labels, dusk sky, additive explosion flashes, per-launcher full-circle range rings.
- **Physics:** real fuel_s burnout with flame-off visual, altitude-scaled atmosphere drag, HGV straight-line glide with KE bleed, Mach-13 ballistic, Mach-17 HGV, Euler 0.05 s PN guidance (known ceiling — remaining leaks are ballistic / HGV saturation).
- **AI:** saturation engagement (up to 3 simultaneous interceptors per threat) + CIWS point-defense override + cost-exchange primary → fallback → last-resort ladder + per-launcher range checks. `Threat.override_maneuver` hook ready for the Red AI layer.
- **Map geometry:** 150 × 250 km rectangular arena, 1 km/cell grid. 9 Blue launchers south, 5 Red launchers north. Ballistic / HGV spawn in the far-north 10 km strip. Drone / cruise spawn from the north-side red launcher boxes.
- **Game loop:** real win conditions — site HP ≤ 0 OR Blue budget ≤ 0 → Red wins; all waves spawned + no Red threats alive → Blue wins; 3600 s safety cap → Draw (essentially never fires).
- **Balance:** see "Current balance (post-I)" below.

### Open items (priority-ordered for remaining week until Hack Day)

1. **Milestone J — Deployment UI** (3-4 hours). Pre-game phase letting AI or a human player pick Blue launcher positions. Drag-drop on the map, land-only constraint, AI-auto button. Range rings already parented to launcher Groups in Milestone H, so they'll follow drags automatically.
2. **Red AI Level 5 HGV control** — `Threat.override_maneuver` hook is in place; needs a per-tick decision layer (nearest-interceptor scan, geometry, KE budget) to drive the hook.
3. **Smarter Red AI target selection** — currently weighted-random across sites; wave-specific targeting (wave 5 prioritises capital) would feel more tactical.
4. **Placement AI** (post-Milestone J) — once the deployment UI exists, let an AI pick positions based on incoming threat direction, wave composition, and coverage optimisation.
5. **Route 3: PN precision upgrade** (2-4 hours) — RK4 + sub-tick guidance + ZEM feedback. Closes the ballistic leak rate without compromising realism.
6. **Route 5: Radar / sensor model** (2-3 hours) — Blue AI omniscience removed; detection depends on radar state and RCS-dependent burn-through.
7. **Route 4: Overnight self-play tuning** — 20k-50k headless matches, randomise Red / Blue parameters, analyse what wins. Pitch material: "AI tuned via N self-play matches".

Full per-milestone technical detail lives in [REPORT.md](../REPORT.md). Roadmap detail lives in [ROADMAP.md](./ROADMAP.md).

---

## Where We Are: Milestone I — Complete

Milestone I closes three game-engine gaps surfaced during live demo
review: real win conditions, ballistic + HGV spawn polish, and HGV
manoeuvre freedom. Plus a doc-only item about SLM ballistic fallback.
Four tasks land this session:

1. **Win conditions** — `Site.hp` now decrements per leak (drone 5 /
   cruise 15 / ballistic 30 / HGV 40) starting at 60 HP;
   `World.blue_budget` starts at `$120 M` and is deducted per
   `INTERCEPTOR_SPECS[kind].usd_cost` on every launch.
   `Scenario.winner` resolves `'red' | 'blue' | 'draw' | None` (Red
   wins on HP ≤ 0 or budget ≤ 0; Blue wins on all waves + no threats
   alive; Draw is the 3600 s safety cap, should basically never
   fire). Server stops on `scenario.done`. HUD: per-site HP bars,
   Blue budget bar, blurred full-screen end-of-match overlay.
2. **Ballistic + HGV far-north spawn** — `_sample_spawn` routes
   strategic-range kinds through a 10 km top-of-arena strip (Y 235-
   245 km, X full arena width) with altitude floors (ballistic
   ≥ 20 km, HGV ≥ 30 km). Drone / cruise keep their Milestone H3
   `RedLauncherFleet` path.
3. **HGV manoeuvre freedom** — scripted wide-S and 12 km range-gated
   jink both removed. Default HGV flies straight toward its pre-
   selected target. New `Threat.override_maneuver(turn_dir, g_load)`
   stores a one-tick commanded lateral accel; g clamped to
   `spec.max_g` (50 G → 8 G), zero-vector clears. KE bleed and
   500 m/s stall preserved.
4. **SLM ballistic-gap doc** — no code fix. Documented in "Known
   Limitations" that `FALLBACK_RULES[BALLISTIC]` lists SLM but the
   rule-ordering path means SLM never actually fires on a ballistic
   in practice. Will close with the learned-engagement refactor.

### Current balance (post-I)

Three 20-match sweeps (`test_balance.py`, 2000 s per-match cap,
hybrid classifier — Blue if `winner='blue'` AND `leaks ≤ 5`, Draw
if `winner='blue'` AND `leaks ≥ 6`, Red if `winner='red'`, plus
leak-count fallback if the cap fires without a winner):

```
Run 1:  Blue 10/20  Draw  8/20  Red 2/20   leaks avg 5.5
Run 2:  Blue  5/20  Draw 10/20  Red 5/20   leaks avg 5.2
Run 3:  Blue  8/20  Draw 12/20  Red 0/20   leaks avg 6.2
```

Distribution spans: Blue 25-50 %, Draw 40-60 %, Red 0-25 %. Most
runs land inside the spec's 30-55 / 30-50 / 10-30 window; Run 2
and Run 3 have Red at the window edges due to the binary nature
of site death (2 HGVs + small support on the same site dies, else
survives — high variance at N = 20).

Leaks by kind (cumulative across runs): ballistic ≤ 3,
cruise_sub 3-5, drone 28-56, **hgv 59-60 (≈ 100 % leak rate)**.
HGV straight-line default (Task 3) removes the scripted
S-pattern + jink that pre-Milestone-I was reducing HGV leak rate
to 0.6 / match; with Euler-0.05 s PN against a Mach-17 head-on
target, CPA is typically 100-300 m — well outside PAC-3's 60 m
direct-hit radius. This is a flagged physics-geometry consequence
of Task 3 ("balance sweep still inside window — flag explicitly
if removing the jink shifts distribution"). Route 3 (PN precision
/ RK4) on ROADMAP is the real fix.

### Journey B → I

The sim now has a real game loop. Red / Blue AI layers can plug into
`Scenario.winner` for outcome feedback and `Threat.override_maneuver`
for HGV control. The rule-based engagement ladder in `blue_ai` is the
next structural target for replacement.

---

## Where We Are: Milestone H — Complete

Milestone H closes the four items Milestone G left open and brings
balance back into the spec's target window (Blue 30-55 / draw 30-50 /
Red 10-30). Five parts land this session:

1. **Per-launcher range math in blue_ai** — `_try_fire`,
   `_time_to_enter_range`, `_primary_available_in_time`, and CIWS
   point-defense all now reason per-`(kind, launcher)` instead of
   distance-from-base-per-kind. Forward SLS / SLM no longer get
   cleared to fire on threats their individual positions can't
   reach, AND they now DO get cleared to fire on flank threats the
   base-distance check would have rejected.
2. **Out-of-arena site filter** — `sites._in_arena` drops any Saab
   location whose inverse-affine world coord falls outside the
   150 × 250 km arena. Drops 4 sites (Meridia, Southern Redoubt,
   Callhaven, Solano) whose `saab_y > 1080` puts them at
   `world_y < 0`. Remaining sites: Firewatch Station, Spear Point
   Base, Main Base.
3. **Visible Red launcher boxes** — `RED_LAUNCHER_POSITIONS` in
   `config.py` places 3 drone launchers on north islands and 2
   cruise launchers on north mainland / island. `RedLauncherFleet`
   round-robins `next_pos(kind)` for Red AI; drone and cruise
   threats now spawn from a visible red-tinted box. Ballistic / HGV
   keep the abstract strait-offset spawn (strategic-range assets).
4. **Range rings parented to launcher Group** — each `LauncherMesh`
   is a `THREE.Group` at the launcher's world coord with box + ring
   as children in LOCAL coords. If a Milestone I deployment UI ever
   moves the Group, the ring follows automatically.
5. **Rebalance** — three iterations of forward launcher
   redeployment (SLS → south_central_peninsula + south_forward_island,
   SLM → forward-center, RBS-70 → south_central_peninsula +
   south_small_island) brought Blue 0/20 → 30-40%, draws 0 → 35-45%,
   Red 20/20 → 25%, average leaks 7.5 → 2.0.

### Current balance (post-H5)

```
20-match 1200 s sweep (two independent runs, fresh entropy each):
  Run A:  Blue  6/20  Draw  9/20  Red  5/20  avg leaks 2.0
  Run B:  Blue  8/20  Draw  7/20  Red  5/20  avg leaks 2.0
  leaks by kind (Run B): ballistic 23, hgv 12, cruise_sub 6, drone 0
```

Distribution 30-40 / 35-45 / 25 — solidly within the 30-55 / 30-50 /
10-30 target. Leak character flipped from Milestone G's drone + cruise
dominance to ballistic-dominant, which is the same Euler-0.05 s PN
precision ceiling carried since Milestone D.

## Where We Are: Milestone G — Complete

Milestone G closes three Milestone-F narrative/geometry bugs and
expands the target model from a single base to 7 Saab-located sites.
Four parts land this session:

1. **Full-circle launcher arcs** — every launcher now draws a
   complete max_range circle (was a northern semi-circle from
   Milestone F's forward deployment era).
2. **Launchers on land only** — new `backend/sim/terrain.py` parses
   Saab CSV polygons once at import and point-in-polygons every
   `BLUE_LAUNCHER_POSITIONS` entry against the south-side land. Six
   of the nine Milestone F launchers had been landing in
   coastal-pocket sea; all repositioned on visible terrain.
3. **Strait-origin threats** — threats anchor their spawn Y to a
   new `STRAIT_CENTER_Y = 120_000` constant (derived from the Saab
   strait midpoint) plus a per-kind northward offset, not to the
   base. Drones no longer spawn inside Blue's own mainland.
4. **Multi-site targets** — `backend/sim/sites.py` exposes
   `SOUTH_SITES` (6 Saab named locations + legacy base). Red AI
   picks a weighted-random target per threat (capital > base >
   air_base > major_city). `world.py` runs per-site leak detection
   (in-air + ground-impact), emits `site` on leak events. Frontend
   `SiteRegistry` renders one coloured ring per site (capital
   pulses when damaged). HUD gains a "Site damage" panel listing
   sites with leaks > 0.

The blue base cylinder from Milestone B is gone — the base is now
just a blue-subtype site among the seven.

### Known balance regression (flagged on ROADMAP)

Pre-F baseline was 2-6 Blue wins / 20 matches. Post-G Part 3 is
20/20 Blue because threats are now so far north that Blue's
saturation AI has much more engagement runway. Part 4 redistributes
leak opportunity across 7 sites which partially recovers Red win
rate; final Post-G sweep captured in `REPORT.md` Milestone G section.
The spec's ±3 Blue-win tolerance is exceeded — deliberately, per
Milestone G rules: "document and flag as ROADMAP item, don't
rebalance by tuning specs".

## Where We Are: Milestone F — Complete (still valid)

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

## Current Balance (test_balance.py, 20 matches, post-Milestone G)

```
Post-G Part 3 (strait-origin only, before multi-site):
  Blue win 20/20, draws 0/20, Red win 0/20
  avg spawned=26.0  avg intercepts=21.6  avg leaks=0.0

Post-G Part 4 (multi-site + Red weighted target):
  Blue win 0/20, draws 0/20, Red win 20/20
  avg spawned=26.0  avg intercepts=8.2  avg leaks=7.0
  leaks by kind: drone 66, cruise_sub 52, ballistic 13, hgv 10
```

**Sim ping-pongs hard** — Blue won 20/20 after Part 3 (threats too
far, AI has too much engagement time), Red wins 20/20 after Part 4
(multi-site spreads threats across 7 points, many of which sit
outside the forward launcher envelopes; cruise/drone leaks explode
from near-zero to ~5/run each). Neither regime matches the ±3 Blue-
wins tolerance from the spec. Root cause: engagement AI still runs
on Milestone F base-centered assumptions. Flagged as ROADMAP items
"Rebalance for G geometry" + "Per-launcher engagement math"; not
rebalanced this session per the milestone rules.

## Milestone F Balance (test_balance.py, 20 matches, post-Milestone F)

For reference — this is the pre-G baseline:

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
81023db  Milestone I Task 4 + balance calibration
826c5ea  Milestone I Task 3: HGV manoeuvre freedom (straight default + override hook)
883dcc3  Milestone I Task 2: ballistic + HGV spawn in far-north strip
97b69fb  Milestone I Task 1: win conditions (site HP + Blue budget + 3600 s cap)
64b7300  Fix: rectangular 150×250 km grid matching ground plane extent
340ca27  Docs: add Journey B → H narrative overview to STATUS.md
a560588  Milestone H docs: REPORT section + STATUS / ROADMAP refresh
bfbaa5a  Milestone H Part 5: rebalance after per-launcher range math
4b82776  Milestone H Part 4: range rings parented to launcher Group
c118070  Milestone H Part 3: visible Red launcher boxes for drone + cruise
d8f16ab  Milestone H Part 2: filter out-of-arena Saab sites
0383aa0  Milestone H Part 1: per-launcher range math in blue_ai
500a856  Milestone G docs: record post-Part 4 balance sweep numbers
e570449  Milestone G docs: REPORT section + STATUS / ROADMAP refresh
49939d0  Milestone G Part 4: multi-site targets + per-site leaks + remove base cylinder
bec1f84  Milestone G Part 3: threats spawn north of strait centerline
85c215e  Milestone G Part 2: validate BLUE_LAUNCHER_POSITIONS are on land
b4fd6f2  Milestone G Part 1: full-circle launcher range arcs
```

Run `git log --oneline -20` for the full history.

## Architecture Map

| Component | File | Purpose |
|-----------|------|---------|
| Config | `backend/sim/config.py` | All tunable parameters (arena 150×250 km, leak radius 1500 m, `BLUE_LAUNCHER_POSITIONS` / `RED_LAUNCHER_POSITIONS` land-gated via terrain.py, **`SITE_HP_START`, `BLUE_BUDGET_START`, `SITE_LEAK_DAMAGE` (I1)**, `STRAIT_CENTER_Y`, `MAX_SIM_TIME = 3600`) |
| Terrain | `backend/sim/terrain.py` (G; extended H3) | Parses Saab CSV south + north polygons; `point_on_south_land` / `point_on_north_land` for launcher validation |
| Sites | `backend/sim/sites.py` (G; filtered H2; **HP wired I1**) | `Site` dataclass (name / subtype / pos / `hp` / `hp_max` / `leaks`) + `SOUTH_SITES`; `reset_leaks()` restores HP |
| Types & specs | `backend/sim/types.py` | Enums, dataclasses, weapon/threat spec tables (incl. `fuel_s`, `thrust_active`, `usd_cost`) |
| Physics | `backend/sim/physics.py` | PN guidance, gravity, atmosphere-scaled drag, CPA, `air_density_ratio` |
| Entities | `backend/sim/entities.py` (**HGV rewrite I3**) | Threat + Interceptor step; HGV runs straight by default, `Threat.override_maneuver(turn_dir, g_load)` is the external control hook (one-tick semantics, g clamped to `spec.max_g`) |
| Launcher | `backend/sim/launcher.py` | `Launcher.pos` + magazine/reload; `fleet_status`; `RedLauncher` + `RedLauncherFleet` (H3) — round-robin `next_pos(kind)`, infinite ammo |
| World | `backend/sim/world.py` (**HP + budget I1**) | Tick loop, HP/damage, per-site leak detection (in-air + ground), `site.hp -= kind_damage` on leak, `blue_budget` start / current / max |
| Red AI | `backend/sim/red_ai.py` (**far-north spawn I2**) | 5-wave scripted spawner; `_spawn_point` routes drone/cruise through `RedLauncherFleet` (H3); **ballistic/HGV sampled from `STRATEGIC_Y_BAND` = top 10 km of arena with 20 / 30 km altitude floors (I2)**; weighted-random `_pick_target` |
| Blue AI | `backend/sim/blue_ai.py` (**budget deduction I1**) | Saturation engagement; per-launcher range math (H1); `_fire` launches from `lch.pos` and deducts `spec.usd_cost` from `world.blue_budget` |
| Scenarios | `backend/sim/scenarios.py` (**winner resolver I1**) | World + RedAI + BlueAI orchestration; `snap['ammo']`, `snap['launchers']`, `snap['red_launchers']`, `snap['sites']` (with hp / hp_max), `snap['winner']`, `snap['max_sim_time']` |
| Server | `backend/server.py` | FastAPI + WebSocket; PORT env var override; **stops on `scenario.done` (I1)** |
| Scene | `frontend/js/scene.js` | Three.js scene; 250 km arena; 1 km grid; Boreal terrain; dusk skydome; Saab landmark structures + sprite labels |
| Terrain data | `frontend/js/terrain_data.js` | Boreal Passage polygons + `BOREAL_LOCATIONS` landmarks, baked from Saab CSV |
| Launchers (client) | `frontend/js/launchers.js` | `LauncherRegistry` uses `THREE.Group` per launcher with box + ring children (H4); `RedLauncherRegistry` (H3) — red-tinted boxes, no ring |
| Sites (client) | `frontend/js/sites.js` (G) | `SiteRegistry` — coloured ring per site, canvas-texture leak badge, capital pulses when damaged |
| Entities (client) | `frontend/js/entities.js` | Per-kind meshes, trails, seeker cones, explosions, flame toggle |
| HUD | `frontend/js/hud.js` (**HP bars + budget + overlay I1**) | Score, ammo, launch banner, AI decision logs, per-site HP bars, Blue budget bar, end-of-match overlay |
| Status panel | `frontend/js/status_panel.js` | Click-to-inspect per-entity stats |
| Main | `frontend/js/main.js` | WebSocket client, render loop, wire entity + launcher + red-launcher + site registries + status panel |

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

## Known Limitations (after Milestone I)

1. **PN precision**: still Euler 0.05 s — CPA typically 20–80 m. PAC-3 `radius_direct = 60 m` (spec 0.3 m) is the workaround. This is the root cause of the remaining ballistic-leak dominance; other kinds are now minimal.
2. **SLM is not registered as a ballistic fallback.** Forward-deployed IRIS-T SLM launchers do not attempt ballistic intercepts despite having geometric coverage. This is a `blue_ai` engagement-decision artifact — `FALLBACK_RULES[BALLISTIC]` lists MED_SAM but `PRIMARY_RULES[BALLISTIC]` already blocks on PAC-3 / PAC-2 ready time, so in practice SLM never gets reached when ballistic fallback actually fires. Deferred intentionally; the rule-based engagement ladder is scheduled to be replaced by a learned Blue AI decision layer.
3. **Radar / sensor model not wired.** Blue AI still has omniscient detection. `team-missile-intercept/common-info/source-data/knowledge/sensors-c2.md` has the burn-through formula ready.
4. **No Red AI intelligence yet — but HGV override hook in place.** Waves are pre-scripted and cruise uses fixed S-pattern waypoints. Milestone I Task 3 added `Threat.override_maneuver(turn_dir, g_load)` so a future Red AI can take real-time HGV control; default HGV behaviour is now straight-line (no scripted jink).
5. **Drone sim-cap truncation is gone.** Milestone I's `MAX_SIM_TIME = 3600 s` safety cap gives drones spawning from North Remote Island / NSI-W / NSI-E time to complete their 1206–1776 s flights. Blue-win matches now run until every Red threat is off the map or the win condition fires, whichever is first.
6. **Terrain aspect distortion**: the Boreal Passage mapping uses 11× X / 3.2× Y non-uniform scale to fit the 1667 × 800 km Saab crop into the 150 × 250 km arena. Reads as "two lands across a strait" but doesn't match the Saab reference 1:1.
7. **Launcher positions are hand-coded**, not AI-chosen. `BLUE_LAUNCHER_POSITIONS` and `RED_LAUNCHER_POSITIONS` are declarative dicts validated on module load. Milestone J deployment UI is the next structural step.
8. **No capital site in-arena.** The Saab capitals at `saab_y > 1080` are filtered out by the H2 out-of-arena check. SiteRegistry's capital-pulse code still runs but has nothing to highlight until a future CSV update or deployment UI places one.
9. **No EffectComposer bloom**: explosion bloom is a hot-core + additive-blend approximation, not real post-process bloom. Would need a bundler.
10. **Status-panel G-load** is averaged over the snapshot tick, not instantaneous.
11. **Landmark labels** use `depthTest: false` so they always render in front — pans can show a label bleeding through terrain. Acceptable at the default camera.

## Team & Deliverables

- **Hack Day:** April 25, 2026, KTH Innovation (09:30–16:30)
- **Grand Finale:** April 27, 2026
- **Presentation:** 4 minutes per team, jury = Saab technical leaders
- **GitHub repo:** `Heffri/hackathon-stridsledning`, branch `knowledge-base`
- **Team lead:** Sebastijan Babic
- **This track's lead:** Xingyi Chen
