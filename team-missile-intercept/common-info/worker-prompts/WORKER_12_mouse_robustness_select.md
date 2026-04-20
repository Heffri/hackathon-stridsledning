# Worker 12 — Mouse robustness + launcher click-to-select across phases

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Chen runs this **autonomously** (no per-subtask pause) — he does one consolidated browser smoke at the end. Worker uses `preview_eval` for programmatic self-verification where feasible. Budget: ~1.5–2 h. Three subtasks → three commits.

**Prerequisite:** W11 must have landed. Confirm `git log --oneline -6` shows `d05b017 docs: W11 close — mouse UX + CIWS cap + Magazine HUD (Issues #23, #24, #25)` near the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). Push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `d05b017` or newer.

Start by reading:
- `CLAUDE.md` (repo root)
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — Issues #23 (landed W11), #25 (landed W11), and (new) #26 / #27 that this worker ships
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`

Key files (worker will touch these; read them before editing):
- `team-missile-intercept/frontend/js/drag_launchers.js` — pointer handlers, click-vs-drag discriminator (5 px), W11 raycast filter (boxesForHitTest)
- `team-missile-intercept/frontend/js/launcher_selection.js` — selection state + onSelectionChange subscribers
- `team-missile-intercept/frontend/js/main.js` — scene init, OrbitControls wiring, entity click-to-inspect (status panel)
- `team-missile-intercept/frontend/js/scene.js` (or wherever OrbitControls is constructed)
- `team-missile-intercept/frontend/js/hud.js` — renderMagazinePanel (W11); renderPhaseOverlay
- `team-missile-intercept/frontend/js/status_panel.js` — click-to-inspect for threats / interceptors (pre-W8 entity click handler)
- `team-missile-intercept/frontend/style.css` — canvas user-select / touch-action (W11)

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker12-preflight"` and pop at end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -6` — confirm `d05b017` or newer is at top.
6. Preflight baseline tests (all must pass before starting — if any fail, STOP):
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

This worker is **frontend-only** — no backend test additions expected. Existing tests must continue to pass (they will unless W12 accidentally touches backend files, which it should not).

# Design target

Chen's 2026-04-20 post-W11 smoke pass surfaced two clusters of UX defects, both in the frontend pointer-handling architecture:

## Issue #26 — Launcher click-to-select scope

Expected behaviour (operator intent):
- **Any phase (SETUP / RUNNING / PAUSED)**: click on a launcher box selects it → Magazine HUD shows that launcher's detail. Click on empty canvas deselects → Magazine HUD returns to placeholder.
- **SETUP only**: drag-to-reposition on selected launcher is additionally available (W8 behaviour, unchanged).

Current behaviour (bug):
- W8's pointer handler early-returns when `phase !== 'setup'`. The click-vs-drag discriminator logic lives inside that same handler, so **click-to-select is also disabled during RUNNING / PAUSED**. Operator cannot inspect a launcher's magazine during a match. The last SETUP-phase selection persists forever.
- There is no "click empty canvas to deselect" code path. `launcher_selection.setSelectedLauncherId(null)` only fires via the W9 auto-deselect when the selected id disappears from `snap.launchers` (e.g. after Remove), which never happens during a normal match.

## Issue #27 — Mouse/OrbitControls state leakage

Chen reports the following intermittent failures:
- Right-click sometimes shows the browser context menu despite the W11 preventDefault (item #1 "有时出现有时没有").
- Scroll-wheel zoom intermittently stops working.
- Both mouse buttons simultaneously go dead, or just one side dies.
- Click-to-select on a launcher succeeds sometimes and fails silently other times.

Most likely causes (the worker must root-cause during investigation, not just symptomatically patch):
- **OrbitControls.enabled toggled to `false` on pointer-down** for launcher drag, but the restore-to-`true` path is only wired on `pointerup`. If `pointerleave` / `pointercancel` / a right-click during a left-drag / focus loss interrupts the drag, `enabled` stays `false` → wheel zoom + orbit dead until the next successful drag cycle.
- **contextmenu preventDefault attached to `canvas` only**, but the browser fires the event on whatever element was under the pointer at the moment of the right-click release. If pointer moved over an HUD element (e.g. the SETUP ribbon, or the Magazine panel) between down and up, the handler doesn't fire. Fix: attach to `document` or `window` with a guard that only preventDefault for events whose target is inside the canvas / game area.
- **Pointer-capture state leak**: if W11's raycast filter uses `setPointerCapture` on pointerdown and the capture isn't released on all termination paths, the captured element swallows subsequent pointer events.
- **OrbitControls event listeners fighting with the drag handler**: the order in which the two register pointerdown / pointermove listeners matters. If OrbitControls processes the event first and calls `event.preventDefault()` / `stopPropagation()` in certain modes, the drag handler never sees it. Conversely, if the drag handler consumes the event but OrbitControls is STILL processing a previous drag state (because its internal state wasn't reset), it gets stuck.

# Subtasks

## Subtask A — Click-to-select scope: all phases + deselect on empty (Issue #26, ~45–60 min)

1. In `drag_launchers.js`, the `phase === 'setup'` early-return gate stays ONLY for the drag-move branch. Rework the handler so:
   - `pointerdown` always arms click-vs-drag detection (records start position + timestamp).
   - `pointermove` past the 5 px threshold + SETUP phase enters drag mode.
   - `pointermove` past the 5 px threshold + any other phase does NOT drag (drag is SETUP-only) — the pointer gesture is then treated as an OrbitControls orbit (i.e. do not call `setSelectedLauncherId`, let OrbitControls have it).
   - `pointerup` inside the 5 px threshold on a launcher mesh → `setSelectedLauncherId(hitLauncherId)` regardless of phase.
   - `pointerup` inside the 5 px threshold on empty canvas → `setSelectedLauncherId(null)`.

2. The raycast at pointerup should use the W11 `boxesForHitTest` candidate list. If the raycast returns no launcher hit, interpret as "empty canvas click" and deselect.

3. Selection clearing on phase transitions — DO NOT auto-clear on SETUP→RUNNING. Operator may want to keep an inspection selection from SETUP into RUNNING. The auto-clear in `hud.js` that fires when the selected id disappears from `snap.launchers` is the only implicit clear. All other clears are operator-initiated (click empty or click Remove).

4. Update `getSelectedLauncherId()` consumers that may have been SETUP-gated. `hud.js::renderMagazinePanel` already runs per-snapshot regardless of phase (W11), so the Magazine detail will populate whenever a launcher is selected in any phase. No change needed there — verify.

5. Self-verify via `preview_eval`:
   - Load scene, phase=setup → programmatically click on a launcher box's screen coords → confirm `getSelectedLauncherId()` returns the hit id.
   - Transition to RUNNING via `sendCmd({cmd: 'start'})` → click on a DIFFERENT launcher → confirm selection updates.
   - Click on empty canvas (e.g. top-left corner screen coord with no launcher under) → confirm `getSelectedLauncherId()` returns null.
   - Verify during RUNNING that OrbitControls still orbits when drag-past-threshold happens on empty canvas.

**Commit:** `feat(frontend): launcher click-to-select works in every phase + empty-canvas deselect (Issue #26)`

Push.

**STOP:** if the fix requires restructuring the pointerdown / pointermove / pointerup listener topology beyond the drag-move gate change (i.e. > 80 lines of churn), STOP and report scope creep.

## Subtask B — Mouse / OrbitControls robustness (Issue #27, ~45–60 min)

Root-cause the intermittent mouse / zoom failures. Do NOT just add symptomatic patches — identify WHICH of the probable causes above is hitting and fix that one, plus add regression guards against the others.

Required fixes (in priority order):

1. **OrbitControls.enabled restore invariant.** Wrap the drag lifecycle so `controls.enabled = true` is GUARANTEED to restore on every termination path: normal pointerup, pointercancel, pointerleave off the canvas, visibility-change (tab hide), right-click during an active left-drag. Use a try/finally block or a top-level cleanup function called from every possible terminator. Track the drag state in a single module-level variable so "drag is active" has ONE source of truth.

2. **contextmenu coverage.** Attach the preventDefault listener to the window (or document body) with a guard that only preventDefault's when `event.target.closest('#scene-container, #view-canvas')` (the canvas or an overlay inside the game scene). If the operator right-clicks on an HTML button like Remove or the speed slider, the browser menu SHOULD be suppressed there too. Preventing menus on HUD text is also acceptable. Be conservative — do not prevent menu on `<input>` / `<select>` elements (operator may need right-click for paste in speed slider).

3. **Pointer capture cleanup.** If W11 or W8 uses `setPointerCapture`, audit that every termination path calls `releasePointerCapture(pointerId)`. Add the release to the same cleanup function as step 1.

4. **Raycast on OrbitControls-owned events.** Check whether the click-to-select handler correctly coexists with OrbitControls. A common Three.js pattern: OrbitControls listens on the renderer's `domElement`; custom handlers should also listen on that same element, not `window`. If the custom handler listens on `window`, OrbitControls may grab the pointerdown first and internal state may prevent the custom handler from seeing pointerup. Verify both handlers attach to the same target.

5. **Wheel event.** OrbitControls consumes `wheel` for zoom. If a drag handler or another listener calls `preventDefault` on wheel, zoom dies. Audit for stray wheel listeners — they should not exist in W8/W9/W11 scope, but if found, remove them.

Self-verify via `preview_eval`:
- Simulate a right-click (pointerdown + pointerup with button=2) on the canvas centre → confirm `document.body` has no active browser menu. Repeat 10 times, assert no failure.
- Simulate a drag (pointerdown, pointermove > threshold, pointercancel) → confirm `controls.enabled === true` after the cancel.
- Simulate a visibility change during a drag (dispatch `visibilitychange` event) → confirm `controls.enabled === true` after.
- Simulate a wheel event on the canvas → confirm `controls.getDistance()` or equivalent zoom state changed.
- Simulate alternating left-click-drag and right-click on the canvas 20 times → confirm neither breaks.

**Commit:** `fix(frontend): OrbitControls lifecycle + contextmenu coverage + pointer capture cleanup (Issue #27)`

Push.

**STOP:** if the investigation reveals the root cause is a third-party library bug (e.g. OrbitControls in three.js 0.160.0 has a known issue), STOP and report — do NOT patch vendor code. Chen can decide whether to pin a different version.

## Subtask C — Docs close (~15–30 min)

1. Update `team-missile-intercept/game-core/ISSUES_2026-04-19.md`:
   - Issue **#26 (Launcher click-to-select scope)** — add as new issue. State: Done. Summarise the two fixes (all-phase scope + empty-canvas deselect) and commit hash.
   - Issue **#27 (Mouse / OrbitControls robustness)** — add as new issue. State: Done. Name the root cause found, list the five fix branches actually applied, commit hash.
2. `team-missile-intercept/progress/STATUS.md`: append a `0.99 W12 bugfixes — mouse + click-to-select` entry under Open Items listing #26 / #27 + commits.
3. `team-missile-intercept/game-core/CONTRACT_SEAMS.md`: if the pointer-handler topology changed enough to matter for a future worker, add a one-paragraph note to §8 or similar. Otherwise skip.

**Commit:** `docs: W12 close — mouse UX + click-to-select scope (Issues #26, #27)`

Push.

# Non-goals / guardrails

- **Do NOT touch any backend file.** This worker is frontend-only. Backend regression tests must pass unchanged.
- **Do NOT modify `launcher_selection.js`'s public API.** `getSelectedLauncherId`, `setSelectedLauncherId`, `onSelectionChange` signatures stay as-is.
- **Do NOT change the Magazine HUD rendering** (W11's renderMagazinePanel is the consumer — it doesn't need changes; the selection plumbing feeding it is what's fixed).
- **Do NOT rework the W8 drag-to-move mechanism** beyond the phase-gate tweak in Subtask A. Drag is SETUP-only; click-to-select is everywhere.
- **Do NOT change the status panel** (threat/interceptor click-to-inspect). That code path is separate and works per Chen's report.
- **Do NOT change WebSocket commands / snapshot schema.** Pure frontend changes.
- **Do NOT commit API keys.** **No `--no-verify`, no `git amend`, no force-push.**
- **English** in commits, code, comments, docs.
- **Kill the server before ending the session.** W8 left 5174 occupied; W11 respected the rule. W12 must too.

# Hard rules

- One commit per subtask. 3 subtasks → 3 commits.
- Each commit pushed immediately after local tests pass and `preview_eval` self-checks succeed.
- Each commit ends with the project-convention `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` line.
- If a STOP condition hits in any subtask, ship prior subtasks (if committed), STOP, and write the final summary including which subtask failed and why.
- Budget: ~1.5–2 h total.
- **Chen is NOT paired during this run.** Self-verify via `preview_eval`. Chen will do a single consolidated browser smoke at the end.

# Browser verification protocol (worker-autonomous)

1. Apply the change locally.
2. Start the server in background with a short timeout (e.g. 60 s), `run_in_background=True`.
3. `preview_start` against `http://127.0.0.1:5174/` (or the active port).
4. `preview_eval` to run programmatic JS: dispatch pointer events, check selection state, assert OrbitControls.enabled, check for absence of browser menu, etc.
5. Commit + push when self-verify passes.
6. **Kill the server** between subtasks and at session end. Port 5174 must be free at final.

# Post-flight

1. `git status` — clean.
2. `git log --oneline -8` — 3 new commits above `d05b017`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity.
4. If stashed at preflight: `git stash pop`.
5. Re-run the full preflight test list. All must still pass. No new backend tests expected.
6. `netstat -ano | grep :5174 | grep LISTENING` → empty.

# Deliverable — final summary (≤ 500 words)

1. **Commits landed** (3 hashes + one-line each).
2. **Subtask A (click-to-select scope)** — how the pointer handler was refactored; whether the W8 drag-move path stayed intact; browser-verification outcome.
3. **Subtask B (mouse robustness)** — **root cause found** (one or more of the probable causes listed), list of 5 fix branches applied, `preview_eval` regression pattern (20× alternating clicks, visibility-change drag, wheel zoom, etc.).
4. **Subtask C (docs)** — which issues logged, STATUS / CONTRACT_SEAMS updated.
5. **Test delta** — preflight → postflight, all existing tests still green.
6. **Any blocking / surprising** — especially if OrbitControls revealed a library-version issue, or if the pointer-capture audit found a bug we didn't predict.
7. **For Chen's consolidated smoke pass** — give a crisp punch list:
   - [ ] SETUP: click a launcher → Magazine HUD updates. Click empty → placeholder.
   - [ ] Start Match. RUNNING: click a launcher → Magazine HUD updates. Click empty → placeholder.
   - [ ] PAUSED: selection works the same as RUNNING.
   - [ ] Right-click on canvas 10 times in a row: no browser menu once.
   - [ ] Scroll-wheel zoom: works immediately after any launcher click/drag cycle (no state leak).
   - [ ] Drag launcher in SETUP, let pointer leave canvas mid-drag: orbit resumes, controls responsive.
   - [ ] Alternate left-click and right-click 20+ times: neither breaks.
   - [ ] Click a drone / interceptor during RUNNING: status panel shows (unchanged from before — regression check).
8. **Server lifecycle confirmation** — port 5174 free at session end.
