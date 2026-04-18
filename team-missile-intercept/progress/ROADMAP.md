# Roadmap — What's Next

> Context: Milestones E – I are complete. Milestone I closed three
> game-engine gaps surfaced during live demo review: real win
> conditions (per-site HP + Blue budget + 3600 s safety cap replacing
> the old 600 s time cap), ballistic + HGV spawn in a 10 km far-north
> strip with reentry altitude floors (ballistic ≥ 20 km, HGV ≥ 30 km),
> and HGV manoeuvre freedom (default straight-line flight plus an
> `override_maneuver(turn_dir, g_load)` hook so a future Red AI can
> drive HGV trajectories per-tick with the 8 G / KE-bleed / 500 m/s
> stall physics still enforced). The sim now has a proper game loop
> for Red / Blue AI layers to plug into.
> Time remaining until Hack Day: ~1 week (April 25, 2026).

## What Milestone I Did to the Old Roadmap

Items now **closed**:

- ✅ **Route 7 — Base HP + economy.** `Site.hp` now decrements on leak
  (drone 5 / cruise 15 / ballistic 30 / HGV 40); `World.blue_budget`
  starts at $120 M and is deducted per interceptor launch from
  `spec.usd_cost`. `Scenario.winner` resolves to `'red' | 'blue' |
  'draw' | None` with the rules Red-loses-on-site-HP-0 /
  Blue-loses-on-budget-exhaustion / Draw-on-3600 s-safety-cap. Server
  stops on `scenario.done`; HUD renders HP bars, budget bar, and a
  full-screen end-of-match overlay.
- ✅ **Ballistic / HGV spawn cleanup.** Strategic-range weapons now
  originate in a 10 km strip at the far-north arena edge (Y 235–245 km)
  with an X across the full arena width. Altitude floors: ballistic
  ≥ 20 km, HGV ≥ 30 km. Old `STRAIT_OFFSET_BALLISTIC` /
  `STRAIT_OFFSET_HGV` retired; `STRAIT_CENTER_Y` stays for drone /
  cruise fallback.
- ✅ **HGV scripted jink removed.** Default HGV flies straight to its
  pre-selected target. External override hook
  `Threat.override_maneuver(turn_dir, g_load)` stores a per-tick
  commanded lateral accel; g_load clamped to `spec.max_g`, KE bleed
  still quadratic in (G/Gmax)², 500 m/s stall floor preserved.

Items **surfaced** by Milestone I:

- **SLM as ballistic fallback** is wired in `FALLBACK_RULES[BALLISTIC]`
  but never fires in practice because `PRIMARY_RULES[BALLISTIC]`
  blocks on PAC-3 / PAC-2 ready time. Rule-based engagement ladder is
  queued for replacement by a learned Blue AI decision layer; this
  gap closes with that refactor.
- **Red AI HGV control.** Override hook is in place; a Red AI needs to
  call it every tick with a real-time decision based on nearest
  interceptor, threat-to-target urgency, and KE budget. That is the
  first concrete customer of the hook.

## What Milestone H Did to the Old Roadmap

Items now **closed**:

- ✅ **Per-launcher range math in engagement decisions** —
  `_try_fire`, `_time_to_enter_range`, `_primary_available_in_time`
  in `blue_ai` all iterate launchers individually. Forward SLS /
  SLM no longer take shots they can't physically make; CIWS point-
  defense checks each launcher's envelope.
- ✅ **Rebalance for G geometry** — 3 iterations of forward launcher
  redeployment (south_central_peninsula + south_small_island +
  south_forward_island) brought Blue 0/20 → 30-40%, draws 0 → 35-45%,
  Red 20/20 → 25%. Spec's ±3 tolerance window satisfied.
- ✅ **Out-of-arena site filter** — Saab locations at `saab_y > 1080`
  (Meridia capital, Southern Redoubt, Callhaven, Solano) no longer
  appear in `SOUTH_SITES`; threats no longer chase phantom
  `world_y < 0` targets past the base.
- ✅ **Visible Red launcher boxes** — drones and cruise spawn from
  3 + 2 red-tinted boxes on north islands / mainland, positions
  north-land-validated at module load.

Items **surfaced** by Milestone H (now reclassified as Milestone J):

- **Milestone J — Deployment UI (pre-game phase)** — let the
  operator (human or AI) place Blue launcher positions before each
  scenario start. Scope: drag-drop on the scene, constraint =
  `point_on_south_land`, AI-auto button that picks positions to
  maximise coverage of the active target list. ~3-4 hours. With
  `LauncherMesh` now a Group (Milestone H Part 4), the scene-graph
  side is already prepared — moving the Group moves box + ring
  together.
- ✅ (closed in Milestone I) **Drone sim-cap note** — the 1200 s cap
  was replaced with a 3600 s safety net, so drones on the 1206–1776 s
  transit from North Remote Island now get to land properly.

## What Milestone G Did to the Old Roadmap

Items now **closed**:

- ✅ Launchers-on-land validation — every
  `BLUE_LAUNCHER_POSITIONS` entry is now ray-cast point-in-polygon'd
  against the Saab south-side polygons at config.py import.
- ✅ Narrative fix: threats no longer spawn inside Blue territory
  (strait centerline anchor).
- ✅ Single-base target model replaced by 7-site target model with
  per-site leak tracking and HUD. (Reduced to 3 sites in H2 after
  out-of-arena filter.)

Items newly **surfaced** by Milestone G** (and status now):

- **Smarter Red AI target selection** — still weighted random
  across the 3 in-arena sites. Pattern waves would add demo
  narrative variety.
- **Site HP + economy** — `Site.hp` exists in the dataclass but
  is never decremented. Wire `Site.hp -= kind_damage` on leak
  events, add a win condition when any site reaches 0, and the
  demo has real stakes instead of a leak counter.

## What Milestone F Did to the Old Roadmap

Items now **closed**:

- ✅ Terrain stretch polish — `BOREAL_LOCATIONS` now renders as 3D
  structures (runway + tower, capital skyline, major-city cluster)
  with canvas-textured Sprite labels. Done as Milestone F Task 1.
- ✅ Distributed launcher visualisation — 9 coloured boxes + per-
  launcher range arcs replace the base-centred stack. Done as
  Milestone F Task 2b.

Items **surfaced** by Milestone F:

- ✅ (closed in Milestone H) — **Per-launcher range math in
  engagement decisions**. Now refactored in `blue_ai`.
- **Placement AI / Deployment UI** — still open, refined into
  "Milestone J — Deployment UI" (see top of this ROADMAP).

## What Milestone E Did to the Old Roadmap

Route 2 items closed:

- ✅ Route 2 Task 1 — Per-entity status panel (click-to-inspect, 300 px glass panel with Mach/G/HP/fuel/target/range/cost)
- ✅ Route 2 Task 2 — AI decision log enrichment (120-entry scrolling panels, coloured tags, weapon-colour dots)
- ✅ Route 2 Task 3 — Seeker scanning cones (every non-CIWS interceptor, cyan → orange at 2 km)
- ✅ Route 2 Task 4 — Boreal Passage 3D terrain (8 extruded landmasses from Saab CSV)
- ✅ Route 2 Task 5 — Sky / polish (dusk gradient skydome + additive explosion flashes)
- ✅ (From Milestone D) Route 2 Task 3 original intent (per-kind distinct meshes) — still valid.

Route 2 is **fully closed**. Remaining routes:

- Route 3 — PN precision upgrade (RK4 + sub-tick guidance). Would shrink ballistic leak rate.
- Route 4 — Overnight self-play tuning
- Route 5 — Radar / sensor model
- Route 6 — Red AI Levels 3 / 4 / 5 (adaptive waves, stealth, real-time HGV)
- ✅ (closed in Milestone I) Route 7 — Base HP + economy.

New items **surfaced by Milestone D**:

- Radar / sensor model (blue_ai is still omniscient; `sensors-c2.md` has the formula)
- Red AI Level 3/4/5 (wave scripts are dumb). Milestone I gave the
  Red AI a concrete hook: `Threat.override_maneuver(turn_dir, g_load)`
  is the per-tick control input for HGV; Red AI Level 5 will use it.
- ✅ (closed in Milestone I) Base HP / economy — leaks now cost HP;
  PAC-3 cost is deducted from a finite budget.

New items **surfaced by Milestones F / G / H / I** (repeated for
visibility alongside the route list):

- Milestone J — Deployment UI (pre-game placement of Blue launchers
  on `BLUE_LAUNCHER_POSITIONS` via drag-drop on the map, with
  AI-auto option).
- Smarter Red AI target selection (Milestone G surface, still open).
- SLM ballistic fallback never fires — rule-ordering gap documented
  in STATUS. Closes with the learned-Blue-AI refactor.

## The Four Routes (Updated)

Pick based on what matters most for the April 25 demo.

---

### Route 1 — Manual Verification (do this first after every session)

**Effort:** 10 minutes
**Blocking:** Should be done before any other route on a fresh clone

Open the demo, run all 5 waves, confirm Milestone D works end to end:

- [ ] All 6 interceptor meshes render distinctly (CIWS tan cannon, RBS 70 olive MANPADS, SLS with seeker dome, SLM orange pointed, PAC-2 pink tail-fins-only, PAC-3 purple ACM ring)
- [ ] Exhaust plume disappears on each interceptor at its fuel_s second (PAC-3 at 35 s, PAC-2 at 41 s, SLM at 39 s, SLS at 30 s, RBS 70 at 13 s)
- [ ] CIWS fires when anything crosses 4 km (tan rounds streaming out, no flame)
- [ ] HGV visibly jinks when interceptors close to 12 km, with perceptible speed loss after hard turns
- [ ] HGV dives onto base (CEP within 1.5 km) — no more 1.5 km overshoot
- [ ] Ammo panel shows 6 rows with real weapon names, reload countdowns when empty
- [ ] Launch banner shows correct real weapon names on every launch
- [ ] 1 km/cell grid is readable: count 4 cells from base = CIWS range edge
- [ ] `[FALLBACK]` and `[LAST RESORT]` tags appear in Blue AI log when PAC-3/PAC-2 are empty

```bash
cd team-missile-intercept/backend
python server.py
# http://localhost:5174/  → click Start
```

Log anything broken as a bug before moving on.

---

### Route 2 — Visual Packaging (recommended next)

**Effort:** 2–4 hours (one to two delegate sessions)
**Impact:** Highest for demo-day perception

Saab's jury judges on visual clarity + AI transparency. After Milestone D the sim is rich physics-wise but the operator still can't inspect individual entities or see Blue AI's reasoning in real time.

**Concrete tasks, priority-ordered:**

1. **Per-entity status panel** (~1 hour) ← **biggest single win**
   - Raycaster click on an entity → right-side panel shows: type, speed, G, HP, fuel remaining (s), thrust_active bool, target ID, time-to-intercept
   - Data is already in the EntityState snapshot; just wire UI
   - Makes the Milestone D physics work (fuel / coast / HP) visible to judges

2. **AI decision log enrichment** (~45 min)
   - Blue AI already logs lines like "iris_t_slm → cruise_sub (hp 30/30, 1 in flight, inbound +25 dmg, rng 44.2 km)"
   - Add the current log buffer to a scrolling panel in the HUD (not the current 6-line tail)
   - Colour-code `[FALLBACK]` and `[LAST RESORT]` entries to highlight AI flexibility

3. **Seeker scanning cone on interceptors** (~45 min)
   - Semi-transparent cyan cone projected forward from each interceptor's nose
   - Turns green when locked (close to target)
   - Classic missile-visualization aesthetic

4. **Sky, fog, bloom polish** (~30 min)
   - Gradient sky (already better than before — fog end 500), add bloom on explosions
   - Small polish, high perceived quality

5. **Boreal Passage terrain** (~2 hours)
   - Use `xingyi-rts/saab-provided/the-boreal-passage-map.svg` for landmass outline
   - Extrude the SVG into a low-poly terrain mesh
   - Makes the demo feel grounded in Saab's own scenario
   - Big task — do this last if time allows

**Order recommendation:** 1 → 2 → 3 → 4 → 5.

---

### Route 3 — Physics Precision Debt (closes the ballistic leak gap)

**Effort:** 2–4 hours
**Impact:** Medium (unlocks spec-accurate damage values; fixes ballistic leak rate)

All "spec deviation" notes trace back to Euler 0.05 s giving CPA of 20–80 m vs real munitions' <5 m. Milestone D bandaged PAC-3 with `radius_direct = 60 m` but the real fix is better guidance math.

**Tasks:**

1. Replace Euler with RK4 in `physics.integrate`
2. Subdivide the 0.05 s tick into 5× 0.01 s guidance updates for interceptors
3. Optional: implement Zero-Effort-Miss (ZEM) feedback in PN
4. Revert PAC-3 `radius_direct` from 60 m back toward spec 0.3 m
5. Revert damage falloff from linear to quadratic `(1 - d/r)²`
6. Revert `radius_prox` multipliers (see Milestone C REPORT notes for the ×6 hack)
7. Re-run `test_balance.py` and retune wave counts / loadouts if needed

**When to pick this:** If Route 2 is done and you want to pitch Saab on "we implement real guidance physics, not game approximations." Also closes the 50 % ballistic leak rate if that bothers anyone.

---

### Route 4 — Overnight Self-Play Tuning

**Effort:** 1 hour to build + overnight runtime + 1 hour morning analysis
**Impact:** Medium-high if pitched right

Headless batch runner runs 20,000–50,000 matches overnight on the laptop (CPU-only). Parameters randomized:

- Red attack composition, timing, waypoints, altitudes, spawn distances
- Blue AI saturation cap, last-resort threshold, primary/fallback ordering
- Interceptor spec tweaks (`kill_radius`, `radius_prox`)

Output: SQLite of every match, winner, leak count, which threats got through, ammo consumed, fuel-at-impact.

Morning analysis produces:

1. Optimal Blue AI configuration (highest win rate vs random Red compositions)
2. Vulnerability map (which Red attacks consistently beat Blue)
3. Interceptor efficiency stats (PAC-3 direct-hit rate, MED-SAM avg dmg-per-shot, SLS useful range)
4. Pitch material: "Our AI was tuned via 30,000 self-play matches"

**Prerequisite:** Sim has genuine balance ✅ (Blue doesn't always win since Milestone D).

**Not blocked by:** Route 2 or 3. Can run in parallel.

**Hardware setup:** Laptop plugged in, sleep disabled, performance mode. No dGPU needed — pure numpy.

---

### Route 5 — New: Radar / Sensor Model

**Effort:** 2–3 hours
**Impact:** Medium (adds tactical depth; sets up SEAD / jamming scenarios)

Currently Blue AI sees every threat instantly with perfect position. Real IADS has detection ranges, RCS-dependent burn-through, and terrain masking. `xingyi-rts/knowledge/sensors-c2.md` has the spec.

**Tasks:**

1. Add radar sites to the scene (at base + maybe forward-deployed)
2. Per-radar detection check: `burn_through_range(rcs, jamming)` on each threat each tick
3. Threats become "detected" only when any radar sees them — Blue AI can only target detected threats
4. Visual: threat mesh dims when not detected, brightens when locked
5. Stealth cruise (RCS 0.01 m²) becomes genuinely different from subsonic cruise (RCS 0.08 m²)

**When to pick this:** If visual polish is done and you want the next tactical layer.

---

### Route 6 — New: Red AI Levels 3/4/5

**Effort:** 3–5 hours depending on depth
**Impact:** Medium-high for AI transparency / demo variety

Current Red AI is Level 1 (pre-programmed waves). Adding adaptive behaviour:

- **Level 3** (cruise waypoint adjust): cruise detects SAM launches, nudges waypoints to complicate intercept geometry
- **Level 4** (stealth cruise terminal takeover): stealth cruise stays quiet until crossing a threshold, then does aggressive terminal maneuvers
- **Level 5** (HGV real-time control): HGV jink is currently a pre-scripted sine + bleed. Level 5 adds genuine "detect nearby interceptor → evade" decisions based on target state, with real-time aim correction so the HGV still hits base after evading.

**When to pick this:** If the demo feels too scripted. Level 5 HGV is specifically on the critical path for the user's "Red AI takes over HGV" plan.

---

### Route 7 — New: Base HP + Economy

**Effort:** 1–2 hours
**Impact:** Medium — turns the sim from watch-only into a game with win/loss stakes

Currently any leak = leak, regardless of weapon. PAC-3 expense doesn't matter.

**Tasks:**

1. Add `base_hp` to `World` (starts at 100)
2. Each leak event deducts damage based on threat type (drone 5, cruise 15, ballistic 30, HGV 40)
3. Add Red + Blue USD budgets. Each launch deducts `spec.usd_cost`.
4. Win conditions: Blue loses if `base_hp ≤ 0` OR `budget ≤ 0`. Red loses if all waves spawn AND no active threats AND Red budget spent.
5. HUD: two bars for base_hp (red) and Blue budget (green).
6. The Wave 5 saturation now has teeth: Blue needs to survive on a finite budget.

**When to pick this:** If the demo feels like a fireworks show without stakes. Lightweight change with high perceived depth.

---

### Milestone J — Deployment UI

**Effort:** 3–4 hours
**Impact:** Medium-high — turns the demo from a fixed simulation into
a "what-if" lab where jurors can try placements themselves

Right now `BLUE_LAUNCHER_POSITIONS` is a hardcoded dict. Milestone H
Part 4 refactored each `LauncherMesh` into a `THREE.Group`
specifically to prepare for this step — moving the Group moves box
+ ring together, so the frontend side of a drag-drop interaction
already works.

**Scope (as outlined by the operator):**

- Pre-game phase: after clicking Start but before Red's first wave
  fires, the scene is paused on a placement screen.
- Operator drags each Blue launcher box on the scene floor. The
  Group position updates per drag event; the range ring follows
  automatically.
- Land-only constraint: drop is rejected if `point_on_south_land`
  returns False (snap back to last valid position).
- "AI Auto" button: runs a placement heuristic (currently a stub;
  could be extended later with coverage-optimisation over the
  weighted target-site list) and populates positions in one click.
- Persist chosen positions back into the backend via WebSocket
  message; server re-instantiates `LauncherFleet` before starting
  the Red AI wave clock.

**Why now:** the map is complete (terrain, landmarks, site rings),
threats are on-land-validated, Blue launchers are Group-parented,
and `terrain.point_on_south_land` is the constraint API. Only the
drag interaction and backend re-instantiation need new code.

---

## Recommended Path (1 week to April 25)

**Day 1 (today / tomorrow):** Route 1 — verify Milestone E visually. Click-test entities, confirm Boreal terrain renders, watch Wave 5 end-to-end.

**Day 2:** Route 6 Level 5 HGV, or Route 7 base HP. The sim is visually complete; the missing axis is either "Red side feels more intelligent" (Route 6) or "Blue has stakes" (Route 7). Route 7 is the cheaper bang-for-buck (1–2 h).

**Day 3:** Whichever of Route 6 / Route 7 wasn't done on Day 2. Also consider Route 5 (radar / sensor) if the "omniscient Blue AI" bothers anyone.

**Day 4:** Terrain location labels (Sprite-text for cities/bases), and general demo choreography — camera angles, default wave sequence, HUD layout sweep.

**Day 5:** Route 4 overnight self-play runner kickoff.

**Day 6:** Morning: analyse Route 4 output ("our AI was tuned via N matches"), bake the punchline into the pitch. Afternoon: dry-run demo end-to-end, record a video.

**Day 7 (morning of Hack Day):** Only cosmetic tweaks. No new features.

Route 3 (PN precision) remains **not on the critical path**. The demo works fine with current bandaged values. Add it only if everything else frees up or if the 50 % ballistic leak rate becomes a pitch problem.

---

## Not on the List (deliberately)

- Multiplayer / networked mode
- LLM commander-chat interface (OpenRouter integration)
- Real SRTM terrain data (SVG extrusion is the MVP)
- Supersonic / stealth cruise (not needed for demo arc)

If any of these become important, they warrant their own session.

---

## How to Start a Delegate Session for Any Route

```
# Task: <Route number and name>

Working directory: <your path>\hackathon-stridsledning\
Branch: knowledge-base (run `git log --oneline` to see current head)

## Read first (once):
1. CLAUDE.md (repo root)
2. team-missile-intercept/progress/STATUS.md
3. team-missile-intercept/progress/ROADMAP.md
4. team-missile-intercept/REPORT.md (Milestone D is the last section)

## Scope
Copy the specific route section from ROADMAP.md above.

## Rules
- English for all code, commits, docs
- Commit per feature, push to knowledge-base
- Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
- Default port is 5174, override with PORT env var if reserved
- Do not skip hooks with --no-verify unless asked

## Deliverables
- Code pushed to knowledge-base
- Update progress/STATUS.md to reflect new work
- Append a new section to REPORT.md

Begin.
```
