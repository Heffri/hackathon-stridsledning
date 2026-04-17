# Roadmap — What's Next

> Context: Milestone E is complete. Milestone D gave the sim realistic physics (fuel / coast / atmosphere), saturation AI, per-weapon 3D meshes, 250 km arena, and real-world threat speeds. Milestone E added visual packaging: per-entity status panel, enriched AI logs, seeker cones, Boreal Passage 3D terrain, and dusk sky + explosion flashes.
> Time remaining until Hack Day: ~1 week (April 25, 2026).

## What Milestone E Did to the Old Roadmap

Route 2 items now **closed**:

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
- Route 7 — Base HP + economy
- Terrain **stretch polish**: render `BOREAL_LOCATIONS` city/base labels as Sprites (~30 min work, deferred in Milestone E for time).

New items **surfaced by Milestone D**:

- Radar / sensor model (blue_ai is still omniscient; `sensors-c2.md` has the formula)
- Red AI Level 3/4/5 (wave scripts are dumb; HGV jink is pre-scripted not adaptive)
- Base HP / economy (leaks need consequences; PAC-3 cost needs to matter)

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
