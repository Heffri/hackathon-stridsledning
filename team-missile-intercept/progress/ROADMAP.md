# Roadmap — What's Next

> Context: Milestone C Patch is complete. Demo is playable end-to-end with realistic balance.
> Time remaining until Hack Day: ~1 week (April 25, 2026).

## The Four Routes

Four distinct directions to pursue next. They are **not sequential** — pick based on what matters most for the April 25 demo.

---

### Route 1 — Manual Verification (do this first)

**Effort:** 10 minutes
**Blocking:** Should be done before committing to any other route

Open the demo, run all 5 waves, confirm the Milestone C Patch actually fixed what it claims to fix:

- [ ] Altitude tiers are clearly visible (drone low, cruise mid, HGV/ballistic high)
- [ ] Cruise flies higher than drones (fixed from previous "cruise below drone" bug)
- [ ] HGV lands on base when not intercepted (not 47 km behind)
- [ ] HGV does not bounce on the ground — any touch = instant explosion
- [ ] PAC-3 can destroy an HGV (may take 2-3 shots due to PN precision limits)
- [ ] Ballistic missile clearly nose-dives from 30-40 km altitude
- [ ] Launch banner shows real weapon names on every SAM launch
- [ ] Ammo panel updates per launcher, reload countdown visible when empty

```bash
cd team-missile-intercept/backend
python server.py
# http://localhost:8000/  → click Start
```

If anything is broken, log it as a fresh bug before moving on.

---

### Route 2 — Visual Packaging (recommended next)

**Effort:** 3-5 hours (one to two delegate sessions)
**Impact:** Highest for demo-day perception

Saab's jury judges a 4-minute demo on **visual clarity** and **AI transparency**. The sim is mechanically complete but visually austere. This route makes the product *look* like a product.

**Concrete tasks, priority-ordered:**

1. **Per-entity status panel** (~1 hour)
   - Raycaster click on a cone → right-side panel shows type, speed, G, HP, fuel, target ID, time-to-intercept
   - UI skeleton already exists; just wire it up
   - Biggest single win for "transparency" scoring

2. **AI decision log panel** (~45 min)
   - Scrolling left-side log showing Blue AI's reasoning: "Selected IRIS-T SLM (MED_SAM) vs Cruise #42 — cost ratio 0.67, 2 shots expected"
   - Data already in snapshot events; just render it

3. **Seeker scanning cone on interceptors** (~45 min)
   - Semi-transparent cyan cone projected forward from each SAM's nose
   - Turns green when it has track lock on its target
   - Classic missile-visualization aesthetic that judges recognize instantly

4. **Boreal Passage terrain** (~2 hours)
   - Use `xingyi-rts/saab-provided/the-boreal-passage-map.svg` for the landmass outline
   - Either extrude the SVG, procedurally generate a heightmap, or use real DEM data
   - Makes the demo feel grounded in Saab's own scenario
   - Blocker: no implementation yet — need to plan first

5. **Sky, atmospheric fog, post-processing** (~30 min)
   - Gradient sky, distance fog, bloom on explosions
   - Small polish, high perceived quality

**Order recommendation:** 1 → 2 → 3 → 5 → 4 (terrain is the biggest single task, do it last if time allows).

---

### Route 3 — Physics Precision Debt (technical cleanup)

**Effort:** 2-4 hours
**Impact:** Medium (enables spec-accurate damage values)

All the "deviation" notes in REPORT.md stem from the same root cause: our PN guidance produces CPA of 20-80 m, while real munitions intercept at <5 m. Fixing this unlocks:

- PAC-3's true "hit-to-kill vs graze worthless" design intent
- Quadratic damage falloff as the original WEAPON_SPECS intended
- Sub-metre CPA on ballistic intercepts

**Tasks:**

1. Replace Euler integration with RK4 in `physics.py`
2. Subdivide the 0.05s tick into 5× 0.01s guidance updates for interceptors
3. Optional: implement Zero-Effort-Miss (ZEM) feedback in PN for improved endgame precision
4. Revert PAC-3 `radius_direct` from 40 m back to spec 0.3 m
5. Revert damage falloff from linear to quadratic `(1 - d/r)²`
6. Revert `radius_prox` from ×6 back to spec values
7. Re-run `test_balance.py` and retune any numbers that shifted

**When to pick this:** If Route 2 is done and you want to pitch Saab on "we implement real guidance physics, not game approximations." Otherwise defer — the demo works fine without it.

---

### Route 4 — Overnight Self-Play Tuning

**Effort:** 1 hour to build + overnight runtime + 1 hour morning analysis
**Impact:** Medium-high if pitched right to the jury

Headless batch runner runs 20,000-50,000 matches overnight on the laptop (CPU-only, no GPU needed). Parameters randomized:
- Red attack composition, timing, waypoints, altitudes
- Blue AI cost-exchange thresholds, weapon selection priorities
- Budget ratios

Output: SQLite/CSV of every match, winner, leak count, which threats got through, ammo consumed.

Morning analysis produces:
1. Optimal Blue AI tuning (highest win rate vs random Red strategies)
2. Vulnerability map (which Red attacks consistently beat Blue)
3. Pitch material: "Our AI was tuned via 30,000 self-play matches"

**Prerequisite:** The sim must have genuine balance (Blue sometimes loses). ✅ This is already true after Milestone C Patch.

**Not blocked by:** Route 2 or 3. Can run in parallel with visual work.

**Hardware setup:** Laptop plugged in, sleep disabled, performance mode. No dGPU needed — this is pure numpy.

---

## Recommended Path

Given one week until April 25:

**Day 1 (today):** Route 1 — verify Patch worked.

**Day 2-3:** Route 2 tasks 1-3 (status panel + decision log + seeker cones). This is the biggest demo-quality lift per hour of work.

**Day 4:** Route 2 task 4 (terrain). Or Route 4 if visual plateaued.

**Day 5:** Route 2 task 5 + general polish. Dry-run the demo end-to-end, record a video.

**Day 6:** Route 4 overnight run (data for "our AI is tuned on N matches" pitch line).

**Day 7 (morning of Hack Day):** Only cosmetic tweaks. No new features.

Route 3 is **not on the critical path**. Add it only if something else frees up.

---

## Not on the List (deliberately)

Things that are *not* in any of the four routes, because they are either (a) beyond the time budget or (b) lower impact than the top-four work:

- Red AI Level 4 (stealth cruise terminal takeover)
- Red AI Level 5 (HGV real-time evasion)
- Supersonic cruise missile (we have subsonic, adding more variants isn't needed for demo)
- Stealth cruise missile
- Economy system (Red/Blue budgets, base HP depletion)
- Multiplayer / networked mode
- LLM commander-chat interface (OpenRouter integration)
- Real SRTM terrain data

If any of these become important, they warrant their own dedicated session.

---

## How to Start a Delegate Session for Any Route

Template for spinning up a Claude session on any of these routes:

```
# Task: <Route number and name>

Working directory: C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning\
Branch: knowledge-base (read git log to see current head)

## Read first (once):
1. CLAUDE.md
2. team-missile-intercept/progress/STATUS.md
3. team-missile-intercept/progress/ROADMAP.md
4. team-missile-intercept/REPORT.md (recent milestone sections only)

## Scope
Copy the specific route section from ROADMAP.md above.

## Rules
- English for all code, commits, docs
- Commit per feature, push to knowledge-base
- Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
- No Agent delegation (you are already the delegate)
- No backend polling loops (use short tests that exit)

## Deliverables
- Code pushed to knowledge-base
- Update progress/STATUS.md with what was done
- Append a new section to REPORT.md

Begin.
```
