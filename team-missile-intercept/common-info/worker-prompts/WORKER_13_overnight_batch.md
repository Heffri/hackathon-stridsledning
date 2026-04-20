# Worker 13 — Overnight batch (W12 + paper cuts + baseline + perf + polish)

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Chen is **asleep** during execution — zero human pairing, worker runs fully autonomously with `preview_eval` self-verification. Budget: ~5–7 h total. **Hard per-phase STOP rules below.** Each phase commits before moving on, so a late-phase stop doesn't lose earlier work.

**Prerequisite:** W11 landed. Confirm `git log --oneline -6` shows `8c44a57 docs(worker-prompts): W12 — mouse robustness + launcher click-to-select scope` or later near the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). Push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `8c44a57` or newer.

Start by reading:
- `CLAUDE.md` (repo root)
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md`
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/progress/ROADMAP.md`
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`
- `team-missile-intercept/common-info/worker-prompts/WORKER_12_mouse_robustness_select.md` — **full W12 spec used in Phase 1-3 below**

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker13-preflight"` and pop at end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -6` — confirm `8c44a57` or newer.
6. Run the full preflight baseline test list (all must pass before proceeding — if any fail, STOP):
   - `python team-missile-intercept/backend/test_match_phase.py`
   - `python team-missile-intercept/backend/test_match_phase_integration.py`
   - `python team-missile-intercept/backend/test_engagement_mode.py`
   - `python team-missile-intercept/backend/test_launcher_id.py`
   - `python team-missile-intercept/backend/test_placement_api.py`
   - `python team-missile-intercept/backend/test_launcher_base_cost.py`
   - `python team-missile-intercept/backend/test_roster_api.py`
   - `python team-missile-intercept/backend/test_ciws_saturation.py`
   - `python team-missile-intercept/backend/test_ciws_shot_cap.py`
   - `python team-missile-intercept/backend/test_winner_budget_not_loss.py`
   - `python team-missile-intercept/backend/test_red_budget.py`
   - `python team-missile-intercept/backend/test_threat_contract.py`
   - `python team-missile-intercept/backend/test_cruise_impact.py`
   - `python team-missile-intercept/backend/test_hgv_impact.py`
   - `python team-missile-intercept/backend/test_ballistic_cep.py`

---

# Phase 1-3 — W12 content (mouse + click-to-select) [MUST SHIP]

**Execute Subtasks A, B, and C as specified in `team-missile-intercept/common-info/worker-prompts/WORKER_12_mouse_robustness_select.md`.** Read that entire file. Apply all three subtasks exactly as specified. Three commits:

- Phase 1 (= W12 Subtask A) → commit `feat(frontend): launcher click-to-select works in every phase + empty-canvas deselect (Issue #26)`
- Phase 2 (= W12 Subtask B) → commit `fix(frontend): OrbitControls lifecycle + contextmenu coverage + pointer capture cleanup (Issue #27)`
- Phase 3 (= W12 Subtask C) → commit `docs: W12 close — mouse UX + click-to-select scope (Issues #26, #27)`

Push after each. Self-verify per the W12 prompt's `preview_eval` steps.

**Hard STOP rule for Phase 1-3:** if a subtask takes longer than 90 min of wall-clock and still hasn't committed, STOP that subtask, commit any partial progress if it's obviously correct, and move to Phase 4. Do NOT let a stuck subtask eat the whole overnight budget.

---

# Phase 4 — Issue #17 paper cut: `test_threat_impact.py` reset_leaks (~5-15 min)

Already tracked in `game-core/ISSUES_2026-04-19.md` Issue #17. The fix is a one-liner: `test_threat_impact.py` loops trials with a fresh `World` but never calls `sites.reset_leaks()`, so the module-level `SOUTH_SITES` singleton's leak counter + hp accumulate across trials. Harmless today (the test doesn't assert on leak counts) but a trap for the next worker adding one.

Apply the fix — option (a) from the Issue: add `sites.reset_leaks()` at the top of each trial loop. Surgical.

Re-run the test and any neighbours to confirm no regression.

**Commit:** `fix(test): test_threat_impact resets sites between trials (Issue #17)`

Push.

**Hard STOP rule for Phase 4:** if the test happens to already have the fix (i.e. someone shipped it silently), note that in the morning summary and move on — do NOT re-apply.

---

# Phase 5 — Post-M-TIER3 balance baseline refresh (~10-15 min + sim wall-clock)

Run the full `test_balance_baseline.py` and write the output to a NEW file named
`balance_baseline_2026-04-21_post_w13.json` so the existing
`balance_baseline_2026-04-19.json` (M-TIER1.5),
`balance_baseline_2026-04-20.json` (M-TIER2.5),
and `balance_baseline_2026-04-20_post_tier28.json` (M-TIER2.8) are all preserved.

Use the `--out` flag: `python test_balance_baseline.py --out balance_baseline_2026-04-21_post_w13.json`

Update the `baseline_name` field inside the JSON to `"M-TIER3 + W11 + W12 consolidated baseline"`.

Update `team-missile-intercept/backend/BALANCE_BASELINE_README.md`:
- Add this file to the "What's here" list and mark it the current reference.
- Add a new "2026-04-21 entry (M-TIER3 + W11/W12)" section documenting the diff vs the 2026-04-20 post-TIER2.8 numbers. The substantive changes since 2026-04-20:
  - Red budget pool ($100M, default waves $54.33M in, $45.67M out)
  - Unified threat-control contract (maneuver_schedule additive, flyover-fallback retargets)
  - CIWS lifetime shot cap (4 per drone / 6 per cruise / 10 per HGV / 12 per ballistic)
  - Click-to-select + mouse robustness (pure UX, no physics impact)
- Single-run numbers jitter inside RedAI-rng noise; compare medians, not exact values.

**Do NOT run `test_balance.py` 20-match sweep.** That takes 5-15 min wall-clock and is noisy single-shot — Chen can run it on demand.

**Commit:** `docs(balance): post-W13 baseline snapshot + README entry`

Push.

---

# Phase 6 — Perf investigation + PERF_NOTES (~60-90 min, MUST produce notes file even if no fixes)

Chen has reported demo-time sluggishness. Goal: **root-cause with instrumentation, apply ONLY low-risk easy wins, document findings for future workers**.

## 6.1 — Backend tick-cost profiling (~20 min)

Write a short profiling harness in `backend/perf_probe.py` (ephemeral — will be committed as part of notes). Run a 600 s default scenario headless with `cProfile`, save to `perf_profile_2026-04-21.txt`. Extract the top 20 hottest functions by cumulative time.

Pattern (paraphrase; adapt to actual module layout):
```python
import cProfile, pstats
from sim.scenarios import build_default_scenario
def run():
    scn = build_default_scenario(auto_start=True)
    for _ in range(int(600.0 / 0.05)):
        scn.step(0.05)
        if scn.winner is not None: break
cProfile.run("run()", "/tmp/scn.prof")
pstats.Stats("/tmp/scn.prof").strip_dirs().sort_stats("cumulative").print_stats(20)
```

## 6.2 — Frontend audit via reading + `preview_eval` (~20 min)

- Read `frontend/js/main.js`, `scene.js`, `entities.js` (client-side), `launchers.js`.
- Identify patterns likely to eat frame budget:
  - Mesh / geometry allocation per-snapshot (should be pooled)
  - Material instantiation in hot paths
  - Repeated DOM queries (`document.getElementById` per-frame)
  - Stale meshes not disposed on entity death
- Use `preview_eval` during a short RUNNING session to query:
  - Number of THREE Meshes in the scene
  - Number of DOM nodes
  - `performance.memory.usedJSHeapSize` growth over 30 s
- Log findings.

## 6.3 — Apply low-risk easy wins ONLY

Only apply fixes where both:
- Fix is < 20 lines per file
- Zero risk of changing game behaviour / breaking tests

Acceptable easy-win patterns:
- Cache a DOM element lookup in module-scope instead of querying each frame.
- Dispose a geometry / material when its owning mesh is removed.
- Move an array allocation out of a hot loop.
- Throttle a HUD update that runs 15× per snapshot when once is enough.

**Do NOT** rewrite mesh pooling, swap rendering backends, change snapshot rate, or touch physics integration. Those are out of scope.

## 6.4 — Produce PERF_NOTES

Write `team-missile-intercept/game-core/PERF_NOTES_2026-04-21.md` with:
- Backend top-5 hotspots from cProfile (function, percentage, what it does).
- Frontend audit findings (mesh count, heap growth, DOM query hot-spots).
- List of low-risk fixes applied (one bullet each) or "no easy wins found — demo is GPU-bound / cache-bound".
- Candidate future investigations (NOT applied tonight): mesh pooling, BufferGeometry migration, snapshot delta protocol, LOD, etc.
- Honest assessment: is the lag real (machine-agnostic) or machine-dependent (Chen's laptop only)?

Delete `backend/perf_probe.py` before committing OR keep it in a `backend/tools/` subdir if it's reusable. Worker decides.

**Commit:** `perf: measure + document runtime hotspots + low-risk easy wins`

Push.

**Hard STOP rule for Phase 6:** **ALWAYS ship the PERF_NOTES file, even with zero code changes applied.** The notes are the deliverable; the fixes are optional bonus. If profiling fails or the investigation takes > 90 min, write up what was found, commit, move on.

---

# Phase 7 (OPTIONAL — skip if behind schedule) — Minor demo-recovery UX (~30-45 min)

Small usability additions that help the 4-min demo survive on a fresh laptop. **Skip entirely if Phase 1-6 consumed > 5.5 h of the budget.**

## 7.1 — Camera reset button / keyboard shortcut

- Add a small `R` keyboard-shortcut handler (on `window`) that:
  - Resets the OrbitControls target to scene origin + a sensible default camera position
  - Resets zoom to a fit-the-arena distance
- Add a small `[Reset Camera]` button in the bottom HUD bar (alongside existing Reset / Pause / speed controls)
- Both wire to the same reset function.
- Justification: if the operator accidentally pans too far during the 4-min demo, this is a one-key recovery.

## 7.2 — HUD instructional hint (SETUP only)

In the SETUP ribbon, add a short hint line:
> `Click launcher to inspect · Drag in SETUP to reposition · R to reset camera`

Keep terse, match existing ribbon aesthetic. Only rendered during SETUP phase; hidden in RUNNING / PAUSED / FINISHED.

**Commit:** `feat(frontend): R-to-reset-camera + SETUP ribbon hint line (demo recovery)`

Push.

**Hard STOP for Phase 7:** if the camera reset reveals an OrbitControls issue that's > 30 lines of churn, STOP this phase — Phase 2's OrbitControls fix will have overlap. Skip Phase 7 and move to Phase 8.

---

# Phase 8 — Grand docs close (~15-30 min)

Single commit consolidating everything landed tonight:

1. `team-missile-intercept/game-core/ISSUES_2026-04-19.md`:
   - Issue #17 → state → Done, phase 4 commit ref
   - Issue #26 → Done (phase 1)
   - Issue #27 → Done (phase 2)
   - Issue #28 → add as new issue for perf investigation findings; state Done
   - Issue #29 (if camera reset landed in Phase 7) → Done
2. `team-missile-intercept/progress/STATUS.md`: append `1.0 W13 overnight batch landed` block summarising every phase's commits.
3. If Phase 7 landed, add note to `CONTRACT_SEAMS.md` about the keyboard shortcut namespace (so future workers know `R` is taken).

**Commit:** `docs: W13 overnight batch close`

Push.

---

# Non-goals / hard guardrails for the whole night

- **Do NOT change Red AI, Blue AI engagement ladder, physics, spec values, balance thresholds, threat behaviour, launcher specs, budget values.** Phase 1-3 is frontend; Phase 4 is a test-harness one-liner; Phase 5 is data collection; Phase 6 is investigation + low-risk fixes only; Phase 7 is UX polish.
- **Do NOT touch anything in the Tier 4 / Oskar / Boyu / Sebastijan column** (stealth cruise, arena rescale, nuclear warhead, Red AI policy, Blue AI lead prediction, terrain, models, sensors).
- **Do NOT do an RK4 / guidance precision upgrade.** That's Route 3 on ROADMAP and needs supervised numerical validation.
- **Do NOT refactor beyond what each phase's spec calls for.** No "while I'm here" cleanups.
- **Do NOT change WebSocket commands / snapshot schema except additive fields explicitly called out.**
- **Do NOT commit API keys.**
- **No `--no-verify`, no `git amend`, no force-push.**
- **English** in commits, code, comments, docs.
- **Kill the server before ending each phase and at session end.** W8 left 5174 occupied; W11 / W12 respected the rule. W13 must too.

# Phase progression hard rules

- **Each phase commits + pushes BEFORE starting the next.** Non-negotiable. A stuck or interrupted session must leave committed progress.
- **Per-phase hard wall-clock limit:**
  - Phase 1: 90 min
  - Phase 2: 90 min
  - Phase 3: 30 min
  - Phase 4: 20 min
  - Phase 5: 20 min
  - Phase 6: 90 min
  - Phase 7: 45 min (or skip)
  - Phase 8: 30 min
  - **Total soft budget: 6 h. Total hard ceiling: 7 h.** If cumulative wall-clock exceeds 7 h, STOP regardless of phase, commit anything correct, ship morning summary.
- **Skip rules:** if Phase N exceeds its wall-clock limit, skip to Phase N+1 with any committed progress in place. Write about the skip in the morning summary.
- **Fail-safe:** after every commit, run the full preflight test list. If any existing test fails, **revert the commit** (`git revert` — do NOT `git reset --hard`) and note the regression in the morning summary.

# Browser verification protocol (worker-autonomous)

1. Apply the change locally.
2. Start the server in background, short timeout (60 s), `run_in_background=True`.
3. `preview_start` against the active port.
4. `preview_eval` to run programmatic JS assertions.
5. Commit + push on pass.
6. **Kill the server** before moving to the next phase.

Do NOT trust `preview_click` for UI interaction (W4 lesson). Use `preview_eval` to dispatch synthetic pointer events.

# Post-flight

1. `git status` — clean.
2. `git log --oneline -15` — every committed phase above `8c44a57`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity.
4. If stashed at preflight: `git stash pop`.
5. Full preflight test list must pass end-to-end.
6. `netstat -ano | grep :5174 | grep LISTENING` → empty.

# Morning summary (≤ 800 words) — what Chen reads when he wakes up

At the top, a one-paragraph TL;DR: "Shipped N of 8 phases. Highlights: X, Y, Z. Skipped / stopped: A, B. Key browser smoke items for Chen."

Then per phase:

1. **Phase 1 (click-to-select scope)** — pointer-handler refactor notes, self-verify outcome.
2. **Phase 2 (mouse robustness)** — root cause named, five fix branches applied, 20× alternate-click regression result.
3. **Phase 3 (W12 docs)** — issues #26/#27 filed.
4. **Phase 4 (#17 paper cut)** — shipped? noop?
5. **Phase 5 (baseline)** — new file name, key numbers, README diff summary.
6. **Phase 6 (perf)** — top-5 hotspots, easy wins applied, PERF_NOTES path. Honest assessment of demo-feel lag cause.
7. **Phase 7 (demo recovery)** — landed or skipped; if landed, `R` binding confirmed.
8. **Phase 8 (docs)** — issues closed.

**Chen's consolidated smoke punch list for morning** (subset of what Chen should tap through):

- [ ] Right-click canvas 10 times: no menu.
- [ ] SETUP → click a launcher → Magazine HUD shows detail.
- [ ] Click empty: Magazine → placeholder.
- [ ] Start Match. RUNNING → click a different launcher → Magazine updates.
- [ ] Wheel zoom works before / during / after a drag cycle.
- [ ] Alternate left-click and right-click 20×: neither breaks.
- [ ] Drag launcher in SETUP, pointer leaves canvas mid-drag, returns: orbit resumes, no stuck state.
- [ ] If Phase 7 landed: press `R` → camera re-centres.
- [ ] `port 5174` free at end of your session too (worker confirmed at end of its own session).

**Anything blocking or surprising** — library-version issues, stubborn bugs left on the table, scope pushes.

**Server lifecycle confirmation** — `netstat` output showing port free.

---

# Priority summary (for the worker's own planning)

**Ship-or-die:** Phases 1, 2, 3 (W12 content). Chen asked for these first.
**Ship if Phases 1-3 behaved:** Phases 4, 5, 8 (paper cut, baseline snapshot, docs).
**Stretch:** Phases 6, 7.
**Never:** backend AI/physics/balance changes, Tier 4 items, RK4 upgrade.
