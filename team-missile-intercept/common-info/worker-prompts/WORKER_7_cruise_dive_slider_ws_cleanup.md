# Worker 7 — cruise_sub terminal dive + slider 50× + WS typed-frame fix + ISSUES close

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingy\Documents\github\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Chen runs under bypass. Budget: ~1.5–2 h. Four commits.

**Prerequisite:** Worker 6 (M-TIER2.6-AUDIT) must have landed. Confirm `git log --oneline -8` shows `1d9e06b docs(game-core): audit close — deferred items into ISSUES, contract seams documented` at (or near) the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names (cruise_sub, HGV, drone, ballistic, PAC-2 / 3, IRIS-T, RBS 70, CIWS) and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task. All prose uses game-dev framing ("threat", "intercept", "game", "arcade"); avoid operational/tactical language.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). Push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `1d9e06b` (Worker 6 audit-close commit, or newer).

Start by reading:
- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — Issues **#13 cruise_sub**, **#15 pac_3 default**
- `team-missile-intercept/game-core/AUDIT_2026-04-19.md` — Section on main.js typed-frame discard
- `team-missile-intercept/game-core/CONTRACT_SEAMS.md` — Phase FSM + WS message schema (for Subtask C)
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`

Key runtime files:
- `team-missile-intercept/backend/sim/entities.py` — Threat class; HGV glide-path block lines ~251–333 is the reference pattern for cruise terminal dive. cruise_sub update block is also in here (grep for `kind == "cruise_sub"` or similar).
- `team-missile-intercept/backend/sim/types.py` — ThreatSpec + per-kind spec instances
- `team-missile-intercept/backend/sim/config.py` — constants, speed slider backend validate range at `server.py:98–103`
- `team-missile-intercept/backend/server.py` — speed validation
- `team-missile-intercept/frontend/index.html` — speed slider `max` attribute
- `team-missile-intercept/frontend/js/main.js` — line ~39 is the WS frame router that currently silently drops `phase_change` / `error` typed frames
- `team-missile-intercept/frontend/js/hud.js` — where a toast-style ephemeral error message could live (for Subtask C)
- `team-missile-intercept/backend/test_balance.py`, `test_balance_baseline.py`, `test_threat_impact.py` — tests that will reflect cruise dive changes

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker7-preflight"` and pop at end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -5` — confirm `1d9e06b` or newer is at top. If older, STOP and report.
6. Run preflight tests as baseline — record which pass:
   - `python team-missile-intercept/backend/test_match_phase.py`
   - `python team-missile-intercept/backend/test_engagement_mode.py`
   - `python team-missile-intercept/backend/test_threat_impact.py`
   - `python team-missile-intercept/backend/test_hgv_impact.py`
   - `python team-missile-intercept/backend/test_ballistic_cep.py`
   If any fails, STOP and report starting state is broken.

# Task

Four subtasks in order. One commit per subtask. Push each after local tests pass.

## Subtask A — cruise_sub terminal dive (Issue #13 option a, ~45–60 min)

**Background:** W6 baseline (`balance_baseline_2026-04-20.json`) shows cruise_sub is functionally a non-threat: in the no_blue scenario, 8 cruise spawned, 0 leaked, 0 ground-impacted, 8 still-alive-at-end. Root cause: cruise_sub's current terminal profile pops up to ~300 m and holds — with W5's `requires_ground_impact=True` rule, cruise can never trigger leak damage because z never drops to ground_eps.

**Design target (operator decision, 2026-04-19 — Chen picked option a from ISSUES.md #13):**

Give cruise_sub a drone-style terminal dive so it can reach z=0 near its target. Reference pattern: HGV's glide-path dive (entities.py ~lines 251–333, landed by W3 in commit `2b54ca2`). Cruise_sub's situation is much easier than HGV's — it's subsonic (~Mach 0.7–0.8), cruise altitude is low (~300 m), and the dive only needs to cover ~300 m of vertical travel vs. HGV's 35 km.

**Implementation:**

1. Find the cruise_sub update block in `entities.py`. Identify where the current terminal / pop-up behavior lives (likely a proximity-based altitude override or a hard-coded waypoint ladder).
2. Add a terminal-dive gate similar to drone's or HGV's — e.g. when horizontal distance to target `dh < 5000 m` (tune so the dive is visible but not abrupt), switch from cruise altitude-hold to a drone-style 3D waypoint aim: `desired_vel` points at the target's 3D position `(x_target, y_target, 0)` at current `cruise_speed`. Use the HGV block's structure as template but simpler (no glide-path angle computation — cruise just aims at the 3D target directly in terminal phase).
3. Keep pre-terminal cruise behavior unchanged — cruise_sub keeps its low-altitude sea-skimming profile until the terminal gate triggers.
4. Preserve any `override_maneuver` hook if cruise_sub has one (grep — probably doesn't, since cruise doesn't have the HGV real-time override contract). If it does, the override bypasses the new terminal dive the same way it bypasses HGV's glide.
5. No new ThreatSpec field is required unless you need to parameterise the terminal gate distance — if so, add `terminal_dive_dh: float` to ThreatSpec with a default of 0.0 (meaning "no terminal dive"), and set it on cruise_sub's spec instance. Do NOT add it to other kinds' spec instances; leave them at the default.

**Verification:**

1. Add `backend/test_cruise_impact.py` mirroring the shape of `test_hgv_impact.py`:
   - Spawn N = 20 cruise_sub via Red AI, no Blue interception.
   - Expect ground-impact fraction ≥ 0.70 (cruise has less precision than HGV's glide, but should be far better than today's 0/8).
   - Record median horizontal CEP vs target — expect ≤ 2500 m (similar ballpark to HGV).
   - Verdict-raising: `sys.exit(1)` if ground-impact fraction < 0.70 or median CEP > 3000 m. Follow the pattern W6 established in `05cf91e` for `test_hgv_impact.py` / `test_ballistic_cep.py`.
2. Rerun `test_balance.py` to confirm cruise_sub now leaks in the 20-match sweep (expect at least a few cruise leaks, not exactly zero like W5's post-state).
3. Rerun `test_balance_baseline.py --quick` to update numbers; commit a fresh `backend/balance_baseline_2026-04-19b.json` if the delta is large (optional — if the JSON is semantically-similar to `2026-04-20.json` you can skip and note in the commit body).

**Commit:** `fix(game-core): cruise_sub terminal dive — Issue #13 option a`

Include in the commit body:
- Pre-fix no_blue cruise numbers (0 leaked / 0 ground-impacted / 8 still-alive, from `balance_baseline_2026-04-20.json`)
- Post-fix equivalent numbers
- Median CEP from the new test

Push to origin.

**STOP conditions:**
- Ground-impact fraction < 0.70 after 2 attempts — STOP, report; the gate geometry may need operator input.
- Physics NaN / altitude oscillation > 1 km — STOP, report.
- Any existing test regresses → revert and report; balance shift inside the no-Blue cruise scenario is expected and not a regression.

## Subtask B — Speed slider 20× → 50× (~10 min)

**Background:** operator reported during W5/W6 smoke test: demo pacing needs higher max speed so drones crossing 180 km don't force judges to wait 10+ minutes. Plan: open at high speed for Red AI's scouting phase (drones + cruise), drop to 5× when the real attack starts.

**Changes:**

1. `frontend/index.html`: speed slider `max` attribute — change `20` → `50`. If the `step` attribute needs adjusting for smooth UX, leave it alone unless obviously wrong.
2. `team-missile-intercept/backend/server.py`: speed validation range at lines ~98–103. Change upper bound `20.0` → `50.0`. Keep lower bound (`0.1`) unchanged.
3. Verify the `hud.js` label rendering (from W1 M-TIER1-SPEED commit `f3a3ad3`) still formats sensibly at 50× — no change expected but grep for `20` in `hud.js` to be safe.

**Verification:**

- Backend: no new tests needed. Quickly verify the validation range accepts 50.0 and rejects 50.1 by inspection.
- Frontend: cannot fully verify without browser smoke test. Commit body should note "frontend max slider untested by headless worker; visual verification by Chen after restart."

**Commit:** `feat(frontend+server): speed slider 20× → 50× (demo pacing)`

Push to origin.

**STOP conditions:**
- Something else in the codebase hard-codes 20 as a speed ceiling. If you find one, fix it in the same commit.

## Subtask C — WS typed-frame handler in `main.js` (~15–20 min)

**Background:** W6 audit (AUDIT_2026-04-19.md Section E) found that `frontend/js/main.js:39` routes incoming WS frames by checking `typeof data.t === "number"` (snapshot path). Typed frames sent by the server like `{type: "phase_change", phase}` and `{type: "error", reason, from, to}` get silently discarded because they have no `.t`. The HUD stays correct for normal flows because `snap.phase` is on every snapshot, but illegal phase-transition errors vanish without any user feedback.

**Design target:**

Route typed frames to appropriate handlers:

1. On `{type: "phase_change", phase}`: optional — the snapshot-based phase chip already updates. You may either (a) ignore these (current snapshot path is sufficient), or (b) use these to trigger a short "MATCH STARTED / PAUSED / RESUMED / FINISHED" transient toast. Pick whichever is simpler. If you pick (a), document it in the commit body.
2. On `{type: "error", reason, from, to}`: show a brief visual indication. Options:
   - Briefly flash the phase chip red with the reason as a tooltip.
   - Add a small "Error: <reason>" line that fades after ~3 s.
   - Log to `console.warn` (always do this regardless of visual).
   Pick the simplest visible path. Must not block the UI or require user dismissal.
3. Unknown typed frames (`type` field present but not handled): log to `console.warn` with the frame dump for future debugging; do not crash.

**Implementation constraint:**

- Minimal diff. ≤ 40 lines added across main.js + hud.js + style.css combined.
- No new HTML elements in index.html if you can avoid it — reuse existing HUD structure.
- Must not regress the snapshot path — existing snapshot handling stays untouched.

**Verification:**

- Cannot fully verify without browser smoke test. Commit body should note "browser smoke test deferred to Chen; unit verification: main.js routing logic is purely additive and does not alter snapshot handling."
- If you can run a quick syntax-level sanity (e.g. node -c on the file, or just read the diff carefully), do.

**Commit:** `fix(frontend): route WS typed frames (phase_change, error) — W6 audit E follow-up`

Push to origin.

**STOP conditions:**
- If the change would require restructuring main.js's frame router (more than trivial), STOP and note "scope exceeded — defer to Milestone J worker who reworks main.js anyway."

## Subtask D — ISSUES close + #18 add + STATUS + CHEN_BACKLOG (~20 min)

1. **`team-missile-intercept/game-core/ISSUES_2026-04-19.md`:**

   a. **Issue #13 cruise_sub**: change `**State:**` to `Done (M-TIER2.7, option a). Cruise gains drone-style terminal dive triggered by dh<Nkm; no-blue baseline impact: <N> leaked / <N> ground-impacted (from <0 / 0>).` Fill in your numbers.

   b. **Issue #15 pac_3 default flipped prox→htk**: change `**State:**` to `Accepted (operator decision 2026-04-19). Rationale: pac_3 is physically HTK-class; the default flip is semantically correct. Balance drift (+4 HGV / +14 drone leaks per 20-match) will be recovered by Oskar's future Blue AI using lead-prediction to exploit pac_3's 60 m radius_direct. No revert planned.`

   c. **Add new Issue #18** (new section after Issue #17, before the "Merge map — how the 12 raw items collapse" closing section). Use this text verbatim:

   ```
   ## Issue 18 — Cruise missile terrain-following (future, blocked on maps/ elevation API)

   - **State:** Open (blocked on maps/ publishing a terrain height API)
   - **Category:** New feature / cross-team dependency
   - **Owner:** Chen (cruise_sub consumer) + Sebastijan (maps/ elevation data + API)
   - **Merges with:** Issue 13 (cruise_sub terminal dive) — this is the follow-up that lands when terrain ships
   - **Tier:** 3 (post terrain landing; not Hack Day critical)

   **What:** Real-world cruise missiles use terrain contour matching to avoid flying into mountains. Currently the game has no elevation terrain — only 2D land/sea polygons — so cruise_sub flies at a fixed low altitude with no obstacle awareness. Once Sebastijan lands 3D terrain, cruise_sub needs obstacle-avoidance.

   **Design target:**

   1. `maps/` publishes `terrain.height_at(x, y) -> float` (elevation above sea level in metres) as a stable public API. Sebastijan owns the data + implementation. Out-of-bounds return value and unit convention (metres above sea level) agreed on Chen ↔ Sebastijan at publish time.
   2. cruise_sub's update block in `entities.py` samples terrain height `N` metres ahead of the flight path each tick, compares against the cruise's current altitude + safety margin, and:
      - **Simple (Tier 3 target):** pitch up smoothly to clear the obstacle; resume sea-skimming after the obstacle passes.
      - **Later (Tier 4):** lateral bank + maneuver around the obstacle for a stealthier flight profile.
   3. Drone / ballistic / HGV are exempt — drone is intentionally "dumb / cheap / expendable"; ballistic arcs over terrain; HGV flies at 35 km cruise altitude so terrain is irrelevant.

   **Touchpoints (future):** `backend/sim/terrain.py` (new `height_at` function), `backend/sim/entities.py` (cruise_sub update block adds terrain lookahead), `maps/` package data + `TERRAIN_PIPELINE.md` contract doc.

   **Cross-team coordination:** Sebastijan commits to a stable `terrain.height_at(x, y)` signature before Chen consumes it. Both sides agree on units (metres above sea level) and out-of-bounds behaviour (return 0.0? raise? document).

   **Not doing now:** no cruise changes this week beyond W7's terminal dive (Issue #13). This issue waits for maps/ to publish elevation.
   ```

   d. **Cross-team coordination table**: add a new row for Issue #18 terrain-following, referencing Chen (cruise consumer) and Sebastijan (maps/ elevation publisher) as the two owners. Keep the existing rows untouched.

   e. Append a new entry under "Tier execution order": `M-TIER2.7-CRUISE-DIVE: cruise_sub terminal dive + slider 50× + WS typed-frame routing + Issue #18 future-cruise-terrain-following captured. Landed 2026-04-19.` Renumber following items if needed.

2. **`team-missile-intercept/progress/STATUS.md`:** add a short entry "M-TIER2.7-CRUISE-DIVE landed" with the commit range (Subtask A + B + C).

3. **`team-missile-intercept/game-core/CHEN_BACKLOG.md`:** if any backlog items map to these fixes, minimal edits to mark them. If nothing maps, skip.

4. **`team-missile-intercept/game-core/AUDIT_2026-04-19.md`:** optional — add a one-line "Follow-up" note under Section E saying the main.js typed-frame gap was addressed in commit `<hash>`.

**Commit:** `docs: W7 close — ISSUES #13 done + #15 accepted + #18 captured + STATUS`

Push to origin.

# Non-goals / guardrails

- **Do NOT touch Milestone J scope**: no deployment UI, no pause-overlay rework, no SETUP overlay changes, no launcher drag/drop. That's the W8 / Milestone J daytime worker under Chen's supervision.
- **Do NOT rework main.js's frame router** beyond minimal addition of typed-frame handling. If the fix is more than ~40 lines, STOP and defer.
- **Do NOT change other threat kinds' behavior** — only cruise_sub gets the terminal dive. Drone / ballistic / HGV behaviors unchanged.
- **Do NOT change interceptor behavior** or spec values.
- **Do NOT touch `requires_ground_impact` flag** on any spec.
- **Do NOT change physics** (integrator, dt, PN gain, MAX_ACCEL, gravity).
- **Do NOT touch `blue_ai.py` or `red_ai.py`** beyond whatever the cruise-dive requires in Red AI's cruise waypoint pipeline (minimal).
- **Do NOT change `Scenario.winner` rules.**
- **Do NOT commit API keys.**
- **No `--no-verify`, no `git amend`, no force-push.**
- **English** in commits, code, comments, docs.

# Hard rules

- One commit per subtask. 4 subtasks → 4 commits.
- Push each commit immediately after local tests pass.
- Each commit ends with the project-convention Co-Authored-By line.
- STOP rules as per subtask. Stop whole session on any STOP trigger.
- Budget: ~1.5–2 h. If context or time fills, stop gracefully with whatever landed.

# Post-flight

1. `git status` — clean.
2. `git log --oneline -8` — confirm 4 new commits above `1d9e06b`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent.
4. If stashed at preflight: `git stash pop`.
5. Re-run preflight test list. All must still pass.

# Deliverable — final summary (≤ 300 words)

Structured report, not prose:

1. **Commits landed** — 4 hashes + one-line each.
2. **Subtask A (cruise dive)** — gate geometry chosen (dh threshold), ground-impact fraction, median CEP, old vs new no-blue leak count.
3. **Subtask B (slider 50×)** — files touched, any unexpected 20× hard-codes found.
4. **Subtask C (typed frames)** — which path you picked for phase_change and error; any remaining gaps flagged for Milestone J worker.
5. **Subtask D (docs)** — ISSUES #13 / #15 state lines, tier entry added.
6. **Test delta** — preflight vs postflight, any numbers that moved.
7. **Anything surprising** — short; Chen is pairing with this worker in near-real-time.
