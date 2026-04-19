# Worker 3 — M-TIER1.5: HGV glide-path dive + ballistic targeting verify + balance baseline

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingy\Documents\github\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. The user (Chen) runs this under bypass permissions; the worker is expected to run ~3–5 hours without further input.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. Any entity names (HGV, ballistic, cruise, drone, PAC-3, CIWS) and numerical stats (speeds, g-loads, ranges) are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task. All prose in commits, comments, and docs should use game-dev framing ("threat", "intercept", "game", "arcade", "simulation") and avoid operational/tactical language.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). You will push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `ad1f64f` (or newer if other workers landed first). Confirm via `git log --oneline -3`.

Start by reading these files:

- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — **primary task tracker**, read Issues #2, #10, #11 in full
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`
- `team-missile-intercept/common-info/KNOWN_DOC_RUNTIME_DRIFT.md`

Key runtime files you will touch or read:

- `team-missile-intercept/backend/sim/entities.py` — Threat class (`Threat.__init__` lines ~83–213; HGV update block lines ~251–333; ballistic update block lines ~335–370)
- `team-missile-intercept/backend/sim/config.py` — HGV spec at lines ~123–134 (`cruise_speed=5831.0`, `cruise_alt=35_000.0`, `max_g=10.0`, `usd_cost=10_000_000`, `requires_ground_impact=True`)
- `team-missile-intercept/backend/sim/red_ai.py` — `_pick_target` (lines ~33–45) returns `(x, y)` from weighted-random pick over `sites.SOUTH_SITES`
- `team-missile-intercept/backend/sim/world.py` — leak detector (per Issue #2, the horizontal-disc + ground-impact gate)
- `team-missile-intercept/backend/sim/types.py` — `Threat` / `ThreatSpec` dataclasses
- `team-missile-intercept/backend/sim/sites.py` — `SOUTH_SITES`, site `leak_radius`
- `team-missile-intercept/backend/test_balance.py`, `test_ballistic.py`, `test_threat_impact.py` — existing headless test templates

# Pre-flight

Before touching anything:

1. `git status` — must be clean. If dirty, `git stash push -m "worker3-preflight"` and continue; pop at the end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1` (should already be on it)
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -5` — confirm HEAD is `ad1f64f` or newer. If older, STOP and report.

# Task

Four subtasks, executed in order. **One atomic commit per subtask.** Push each commit to `origin/new-teamwork-split-V1` immediately after it lands locally and tests pass. Do not batch.

## Subtask A — Ballistic targeting CEP verification (investigative, 30–90 min)

**Claim from 2026-04-19 recon:**
- `entities.py:134–171` solves a projectile-motion trajectory at spawn so the ballistic lands at its pre-selected target `(x, y)` at `z = ground`.
- `entities.py:337–354` re-entry block re-steers horizontal velocity toward the target waypoint, capped at `spec.max_g`.
- `red_ai._pick_target()` returns an `(x, y)` coordinate from `SOUTH_SITES` weighted-random pick.

**Operator observation (Chen, 2026-04-19 evening):** ballistic missiles visually appear not to fly toward a Blue site. Either the recon is wrong, or drift is producing visible offsets. Verify empirically.

**Method:**

1. Read `backend/test_threat_impact.py` and `test_ballistic.py` as templates. Note the existing harness measures impacts vs a single `BLUE_BASE_POS`; you need per-threat target measurement (each ballistic has its own randomly-picked target from `SOUTH_SITES`).
2. Write a new headless test `backend/test_ballistic_cep.py`:
   - For each of `N = 30` trials, spawn exactly 1 ballistic threat via the normal Red AI spawn path (not by hand-constructing one — the spawn path is what we're validating).
   - Tag the pre-selected target `(x_target, y_target)` at spawn by reading `thr.waypoint[:2]`.
   - No Blue AI / no interceptions. Run the sim until the ballistic either ground-impacts (`not thr.state.alive`) or 600 s elapse.
   - Record `(x_impact, y_impact)` = `thr.state.pos[:2]` at death, and `horizontal_miss = hypot(x_impact - x_target, y_impact - y_target)`.
3. Report per trial and aggregate:
   - N spawned, N ground-impacted, N still-alive-at-600s
   - `horizontal_miss` mean, median, p95, max
   - Per-target-site breakdown (which sites get hit, which get missed)
4. **Threshold decision:**
   - **If median horizontal_miss ≤ 1500 m (= typical site `leak_radius`)**: PASS. Ballistic targeting is correct; what Chen observed is expected Euler-0.05 s drift within the leak disc. Write the test file + a short markdown report `backend/ballistic_cep_report.md` (≤ 50 lines, include the numbers) and stop this subtask with no runtime code change.
   - **If median horizontal_miss > 1500 m**: FAIL. Root-cause (check: trajectory solver at `entities.py:134–171` for algebra errors; re-entry steering authority at lines 337–354 for under-demand; Red AI target passing). Fix minimally. Rerun the test until PASS. Document root cause in `backend/ballistic_cep_report.md`.

**Commit:**
- PASS case: `test(game-core): ballistic targeting CEP empirical baseline (Issue #11 verify)`
- FAIL-then-FIX case: `fix(game-core): ballistic targeting CEP — Issue #11 verify+fix`

The test file + the report file + any runtime fix go in the same commit. Push to origin.

**STOP condition:** if after 2 attempted root-cause fixes the median CEP is still > 1500 m, STOP, do not commit the partial fix, report findings back to PM and wait.

## Subtask B — HGV default glide-path dive (code change, 1.5–2 h)

**Current state (from 2026-04-19 recon):**
- HGV maintains `cruise_alt = 35_000 m` until horizontal distance-to-target drops below 30 km (see `entities.py:266` — `if dh < 30_000`). Only then does it aim its 3D velocity vector at the waypoint (line ~270) and begin descending.
- At Mach 17 (5831 m/s) with `max_g = 10`, physically descending 35 km vertical requires roughly 27 s × 5831 m/s ≈ 157 km of horizontal distance at the steepest sustainable dive. With only 30 km available inside the gate, HGV flies over the target and exits the leak check window without ground-impact.
- Post-Issue-#2, leak detection requires `z ≤ GROUND_Z + 50 m` for HGV (`requires_ground_impact=True`). Result: 1800 s headless balance run from Worker 2 showed **0 HGV ground-impacts, 0 HGV leaks**. HGV is effectively harmless right now.

**Design target (approved by Chen, 2026-04-19):**

1. **Default behaviour: constant glide-path dive from spawn.** At HGV spawn, compute a target pitch angle `θ_glide = atan(cruise_alt / horizontal_distance_to_target_xy)`. The HGV's default steering maintains this pitch angle throughout flight, so it descends steadily and lands approximately on top of the target `(x, y)` at `z = 0`. Horizontal steering continues to aim at the target `(x, y)` (same as today's cruise phase).
2. **Override hook preserved.** `Threat.override_maneuver(turn_dir, g_load)` continues to work. When an override is active for a given tick, it takes priority over default glide-path steering — same semantics as today's cruise phase override. When the override is released (no call for a tick, or a pass-through sentinel), default glide-path resumes.
3. **Optional short terminal sharpening.** Once the HGV is close to the ground (e.g. altitude < 2 km or `dh < 3 km`, whichever comes first), you may switch to the current "aim 3D velocity at 3D waypoint" terminal logic for final ~second homing. This is cosmetic and optional — do it only if it comes naturally out of the refactor. If it complicates the code, skip.
4. **Game-balance intent:** HGV should reliably hit the ground close to its target with CEP comparable to ballistic (a few hundred m), becoming a serious threat the Blue AI must handle. Red AI's future `override_maneuver` use (Boyu's future work) adds lateral jink on top of the glide path.

**Implementation notes:**
- The existing HGV update block is at `entities.py:251–333`. The recon shows this block has (1) horizontal direction computation lines ~258–263, (2) terminal dive gate + 3D aim lines ~266–279, (3) cruise altitude-hold spring-damper lines ~280–296.
- Replace the spring-damper altitude hold (line ~285 `target_alt = self._base_alt`) with glide-path altitude descent. One approach: store `glide_path_pitch` on the Threat at spawn (computed from initial `horizontal_distance_to_target`), and each tick compute `target_alt = max(0, self._base_alt - tan(glide_path_pitch) * horizontal_distance_travelled_since_spawn)`. The spring-damper still converges altitude toward this moving `target_alt`, which now descends linearly. Alternatively, steer the velocity vector directly to have a component `-sin(glide_path_pitch) * cruise_speed` on the z-axis each tick.
- Either approach is acceptable. Pick whichever reads more cleanly in context. Do not try to rewrite the HGV update logic wholesale — minimal surgical change preferred.
- `glide_path_pitch` is a new per-instance attribute on `Threat`. Declare it in `__slots__` (see `Threat.__init__` lines ~66–81). Initialise it at HGV spawn time in `__init__` — only when `spec.kind == 'hgv'`; for other kinds leave it as 0 or unused.
- Keep the existing `override_maneuver` plumbing untouched. The glide-path pitch is default behaviour; override bypasses it the same way override bypasses current cruise altitude-hold.

**Headless verification:**

Extend the Subtask A test or add `backend/test_hgv_impact.py`. Same harness shape: spawn `N = 30` HGV threats via Red AI, no Blue interception, run to each threat's death or 600 s.

**Required assertions:**
- **Ground-impact fraction ≥ 0.80** (of `N = 30`, at least 24 reach `z ≤ 50 m` and die via the leak / ground-impact path).
- **Median horizontal_miss at ground impact ≤ 2500 m.** (Loose because HGV has more integration drift than ballistic; tighten if measurements allow.)
- **No physics explosions.** No NaN in `pos` or `vel`, no altitude oscillation > 5 km amplitude.

Also rerun `backend/test_balance.py` (full 1800 s scenario) once and capture HGV columns: spawned, intercepted, leaked, ground-impacted. Expect HGV leak count / ground-impact count to be **> 0** now (any non-zero is progress; typical 1–5 per 1800 s run with current waves).

**Commit:** `fix(game-core): HGV default glide-path dive — Issue #10 subtask (Tier 1.5 balance)`

Include in the commit:
- `backend/sim/entities.py` — glide-path logic
- `backend/sim/types.py` if you added a `glide_path_pitch` field there instead of __slots__ on Threat directly (pick one home, not both)
- `backend/test_hgv_impact.py` (or extended `test_ballistic_cep.py`)
- `backend/hgv_impact_report.md` (short, same shape as ballistic report)

Push to origin.

**STOP conditions:**
- After 2 attempts, ground-impact fraction < 0.80 → STOP, report.
- Physics NaN or explosion on any spawn → STOP, report immediately.
- HGV oscillates altitude (> 5 km amplitude) → STOP, report (the spring-damper constants may need tuning, but do not tune without PM sign-off).

## Subtask C — Balance regression baseline (30–60 min)

**Purpose:** capture today's threat-vs-defense numbers as a regression tripwire for future refactors (RK4, unified contract, etc.). Future workers diff their results against this baseline to confirm no silent drift.

**Method:**
1. Add `backend/test_balance_baseline.py` (or extend `test_balance.py` — your call; if extending, keep the existing output intact).
2. Script runs three controlled headless scenarios and writes a structured JSON blob:
   - **Scenario 1: full match.** Default `BLUE_LAUNCHER_POSITIONS`, default waves, Blue AI on, 1800 s. Capture per-kind: `{spawned, intercepted, leaked, ground_impacted, still_alive_at_end}`.
   - **Scenario 2: no-Blue.** Same, but Blue AI disabled (threats unopposed). Measures intrinsic threat effectiveness independent of defense performance.
   - **Scenario 3: per-kind targeting CEP.** Reuses the Subtask A / B harness to emit CEP for each kind (drone, cruise, ballistic, HGV).
3. Write output as `backend/balance_baseline_2026-04-19.json` (commit the JSON alongside the script — it's the baseline).
4. Script should accept `--quick` flag for a faster 600 s run (used by workers in a hurry), default is the full 1800 s.
5. Add a short `backend/BALANCE_BASELINE_README.md` (< 40 lines) explaining: (a) how to rerun, (b) how to diff future runs vs. the committed JSON, (c) what numbers are expected to be roughly stable vs. vary.

**Commit:** `test(game-core): balance regression baseline suite`

Push to origin.

**STOP conditions:**
- Scenario 1 full run exceeds 15 minutes of wall-clock → cut scenario to `--quick` 600 s default, commit that, report.
- JSON output size > 1 MB → something is being dumped per-tick, not aggregated; fix aggregation.

## Subtask D — Update ISSUES_2026-04-19.md (docs, 10–20 min)

Open `team-missile-intercept/game-core/ISSUES_2026-04-19.md` and update the `**State:**` lines for the issues this worker touched:

- **Issue #2 (HGV airburst):** leave as `Done (M-TIER1-UX subtask 3)`, but add a one-line note under it: "HGV now physically reaches ground via Issue #10 glide-path dive subtask (M-TIER1.5)."
- **Issue #10 (HGV default + flyover):** change `**State:**` to `Partially done — HGV default glide-path dive landed (M-TIER1.5). Full unified contract (target_site_id field, maneuver_schedule, flyover fallback) remains Open, Tier 3.`
- **Issue #11 (drone/ballistic default):** change `**State:**` based on Subtask A outcome. If PASS: `Default target-at-spawn empirically verified (M-TIER1.5 — CEP median <N>m, see backend/ballistic_cep_report.md). maneuver_schedule + override enforcement remain Open, Tier 3.` Fill in `<N>` with the number. If FAIL-then-FIXED, say so briefly instead.
- Append to the "Tier execution order" section a new line under Tier 1:
  `2.5 **M-TIER1.5-HGV-BALLISTIC:** HGV default glide-path dive + ballistic targeting verify + balance baseline. Landed 2026-04-19.`

**Commit:** `docs(game-core): ISSUES update — M-TIER1.5 HGV + ballistic`

Push to origin.

# Non-goals / guardrails

- **Do not touch any other ISSUES.md entries** (Issues #1, #3, #4, #5, #6, #7, #8, #9, #12) — their state is owned by other workers / Chen.
- **Do not add `Threat.target_site_id` field.** That is part of the full unified contract (Issue #10 Tier 3) and is out of scope here. Keep the `(x, y)` waypoint interface.
- **Do not add `maneuver_schedule` to Threat.** Same reason — out of scope.
- **Do not touch frontend files.** All work here is backend + test + docs.
- **Do not touch `restart-overlay` WIP files on `knowledge-base-V0.5-archive`.** You are on `new-teamwork-split-V1`; this should not come up.
- **Do not rewrite HGV update logic wholesale.** Minimal surgical glide-path addition, preserving override hook.
- **Do not tune spec constants** (cruise_speed, cruise_alt, max_g, usd_cost) without PM sign-off. If your glide-path math depends on a tuning change, STOP and report instead.
- **Do not change leak-detector code** in `world.py`. The 1500 m disc + `requires_ground_impact` gate stays as-is.
- **No `--no-verify`, no `git amend`, no force-push.**
- **Never commit API keys** (OpenRouter / Gemini / any). Not expected to come up; just in case.
- **English only** in commits, code, comments, docs.

# Hard rules

- One commit per subtask. Four subtasks → four commits.
- Push each commit immediately after local tests pass: `git push origin HEAD:new-teamwork-split-V1`.
- Each commit message ends with a Co-Authored-By line for the worker model, matching project convention.
- If any subtask hits a STOP condition, stop the entire worker session immediately and write the final summary with what landed and what is outstanding. Do not attempt subsequent subtasks.
- You have ~3–5 hours of budget. If you exceed that or context fills, stop gracefully with whatever is committed.

# Post-flight

1. `git status` — must be clean.
2. `git log --oneline -10` — confirm 3–4 new commits sit above `ad1f64f`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity push.
4. If you stashed at pre-flight, `git stash pop`.

# Deliverable — final summary (≤ 400 words)

Write it back to the user (Chen) with this structure:

1. **Commits landed** (hashes + one-line each).
2. **Subtask A (ballistic) outcome**: PASS / FAIL-then-FIXED / STOPPED. Key numbers: median CEP, ground-impact rate.
3. **Subtask B (HGV glide-path) outcome**: PASS / STOPPED. Key numbers: ground-impact fraction, median CEP, balance test HGV leak count before / after.
4. **Subtask C (baseline)** outcome: file path of the JSON, wall-clock of one full run.
5. **Subtask D (ISSUES update)** outcome: which issues updated.
6. **Anything blocking or surprising** — physics anomalies, hidden couplings you hit, specs that felt wrong. Flag but do not fix.
7. **Next-worker handoff notes** — what the Match Phase worker (Worker 4) or the future Issue #10 contract worker should know.
