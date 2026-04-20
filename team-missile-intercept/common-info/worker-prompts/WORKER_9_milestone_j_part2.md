# Worker 9 — M-TIER2-J Part 2: Buy vehicle / roster add-remove (Issue #6)

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Chen runs this **with supervision** — daytime session, needs browser smoke checks on subtasks C/D/E. Budget: ~3.5–4.5 h. Six subtasks → six commits.

**Prerequisite:** W8 (M-TIER2-J Part 1) must have landed + W8-post diagnostic commits landed. Confirm `git log --oneline -12` shows at least `edf426d diag(game-core): keep 2nd HGV diag harness — Trial D (PAC-3 forward) signal` near the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task. Use game-dev framing ("launcher placement", "roster", "buy vehicle", "deployment phase", "arcade") in all prose.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). Push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `edf426d` or newer.

Start by reading:
- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — **Issue #6 (buy vehicle)** is the primary target; **Issue #7 (Deployment UI)** context (Part 1 landed 2026-04-20)
- `team-missile-intercept/game-core/CHEN_BACKLOG.md` — item **#3 Part 2** has scope notes
- `team-missile-intercept/game-core/CONTRACT_SEAMS.md` — phase FSM, WS schema
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`

Key runtime files (most already exist from W8 Part 1 — this worker extends them):
- `team-missile-intercept/backend/sim/config.py` — `BLUE_LAUNCHER_POSITIONS`, `BLUE_BUDGET_START = 120_000_000`
- `team-missile-intercept/backend/sim/types.py` — `INTERCEPTOR_SPECS`, `InterceptorType` enum (values: `ciws`, `rbs_70`, `iris_t_sls`, `iris_t_slm`, `pac_2`, `pac_3`)
- `team-missile-intercept/backend/sim/launcher.py` — `Launcher` dataclass + `LauncherFleet` — W8 landed stable `Launcher.id`
- `team-missile-intercept/backend/sim/world.py` — `world.blue_budget`, `world.launchers` access (note: launchers live on `scenario.blue.launchers`, not `world.launchers` — clarify during reconnaissance)
- `team-missile-intercept/backend/sim/scenarios.py` — `Scenario.__init__`, snapshot
- `team-missile-intercept/backend/server.py` — `_place_launcher_cmd` + `_ai_auto_cmd` landed in W8 Subtask B (around line 156–245). Extend.
- `team-missile-intercept/frontend/js/hud.js` — SETUP ribbon from W8 Subtask D
- `team-missile-intercept/frontend/js/drag_launchers.js` — drag handler from W8 Subtask E
- `team-missile-intercept/frontend/js/launchers.js` — LauncherRegistry, per-launcher Three.js Groups

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker9-preflight"` and pop at end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -10` — confirm `edf426d` or newer is at top. If older, STOP and report.
6. Preflight baseline tests:
   - `python team-missile-intercept/backend/test_match_phase.py` — must pass.
   - `python team-missile-intercept/backend/test_match_phase_integration.py` — must pass.
   - `python team-missile-intercept/backend/test_engagement_mode.py` — must pass.
   - `python team-missile-intercept/backend/test_launcher_id.py` — must pass (W8).
   - `python team-missile-intercept/backend/test_placement_api.py` — must pass (W8).
   - `python team-missile-intercept/backend/test_cruise_impact.py` — must pass.
   - `python team-missile-intercept/backend/test_hgv_impact.py` — must pass.
   - `python team-missile-intercept/backend/test_ballistic_cep.py` — must pass.
7. Optional sanity: start server (`python team-missile-intercept/backend/server.py`), load browser, confirm W8 ribbon + drag-drop still work. Stop server.

If any preflight test fails, STOP and report.

# Design targets

## Budget economics

- `world.blue_budget` starts at `$120_000_000` (config.BLUE_BUDGET_START) and is already deducted per-interceptor at launch time (`spec.usd_cost` via `blue_ai._fire`, unchanged).
- **New**: each launcher instance has a **base cost** deducted once from `world.blue_budget` when the operator places it (via `add_launcher`). Refunded in full when removed (`remove_launcher`). Move (`place_launcher` from W8) stays free.
- Scenario starts with the config-default roster **pre-placed and pre-paid** — their base cost does NOT come out of the budget at scenario construction. This preserves the existing demo feel (operator sees a full defender set on Start) and keeps budget arithmetic consistent for the default run.
- Removing a config-default launcher DOES refund its base_cost, so the operator can "sell the default pac_3 and buy two slm" style roster edits while staying inside budget.

## Launcher base cost table (commit these values to config.py)

```python
# config.py — new dict, alongside BLUE_LAUNCHER_POSITIONS
LAUNCHER_BASE_COSTS: Dict[str, int] = {
    "ciws":       500_000,
    "rbs_70":   1_000_000,
    "iris_t_sls": 2_000_000,
    "iris_t_slm": 5_000_000,
    "pac_2":   10_000_000,
    "pac_3":   15_000_000,
}
```

Default roster cost check (do not commit code that silently breaks the invariant):
- 3 ciws × $0.5M = $1.5M
- 2 rbs_70 × $1M = $2M
- 2 iris_t_sls × $2M = $4M
- 2 iris_t_slm × $5M = $10M
- 1 pac_2 × $10M = $10M
- 1 pac_3 × $15M = $15M
- **Total default roster base cost: $42.5M**

With $120M starting budget and the default roster **pre-paid**, operator has $120M for interceptors + optional new launchers. If operator removes a default and re-adds later: net zero budget. If operator adds extras: budget drops. Makes sense as a game-balance lever.

These are arcade-game numbers ("unit stats", not real-world prices). Flag the dict with a `# TODO: tune against balance sweep post-Hack-Day` comment.

## WS command contract

Two new commands added alongside W8's `place_launcher` + `ai_auto`:

### `{cmd: 'add_launcher', kind: str, pos: [x: float, y: float]}`

- Reject if phase != SETUP → `{type: 'error', reason: 'illegal_placement', detail: 'phase is <current>, must be setup'}`.
- Reject if `kind` is not a known `InterceptorType` value → `{type: 'error', reason: 'illegal_placement', detail: 'unknown launcher kind <kind>'}`.
- Reject if `not terrain.point_on_south_land(x, y)` → `{type: 'error', reason: 'illegal_placement', detail: 'position not on south land'}`.
- Reject if `world.blue_budget < LAUNCHER_BASE_COSTS[kind]` → `{type: 'error', reason: 'insufficient_budget', detail: 'need $<cost>, have $<budget>'}`.
- Success: construct a new `Launcher` (full magazine, default reload state), append to `scenario.blue.launchers.launchers`, deduct base_cost from `world.blue_budget`, assign a unique ID of the form `f"{kind}_{next_idx}"` where `next_idx` is one past the current max within-kind index.

### `{cmd: 'remove_launcher', launcher_id: str}`

- Reject if phase != SETUP.
- Reject if no launcher with that id → `{type: 'error', reason: 'illegal_placement', detail: 'unknown launcher_id'}`.
- Success: find the launcher, refund its base_cost to `world.blue_budget` (clamped at `BLUE_BUDGET_START` so refunds never exceed starting budget — e.g. if operator somehow spent-then-refunded into a virtual surplus, we cap at the origin), remove from the fleet list.

## Snapshot additions

Each launcher entry in the snapshot gains a `base_cost_usd: int` field (pulled from `LAUNCHER_BASE_COSTS[kind]` at snapshot time — additive-only, no breaking changes). Frontend reads this to render the ribbon roster summary and tooltips.

## Ribbon UI additions (SETUP phase only)

The W8 SETUP ribbon gains three new controls beside the existing `[AI Auto]` + `[Start Match]`:

1. **Roster dropdown** — lists the 6 launcher kinds with their base costs, e.g. `PAC-3 MSE ($15M)`. Chen's phrasing is acceptable: use the display-name string from an internal lookup, not the raw enum.
2. **[+ Add]** button — sends `{cmd: 'add_launcher', kind: <dropdown value>, pos: <default spawn point>}`. Default spawn point: centre of south mainland, e.g. `(config.BLUE_BASE_POS[0], config.BLUE_BASE_POS[1])` or the arena centre-south. Operator drags after (W8 drag still works).
3. **[− Remove]** button — only enabled if a launcher is currently selected (via click). Sends `{cmd: 'remove_launcher', launcher_id: <selected>}`. Button disables / un-highlights the launcher once confirmed by the next snapshot.

Budget display: the existing HUD budget bar is sufficient. **Do not** add a second budget readout in the ribbon — avoid visual duplication.

## Launcher selection (click-to-select) — needed for Remove

Add a click handler (distinct from the drag handler W8 added) on the Three.js scene: pointer-down + pointer-up on the **same** launcher mesh Group within a small screen-distance threshold (e.g. <4 px) = click, not a drag. Clicks during SETUP:
- Select the clicked launcher. Visual feedback: emissive outline / bright ring / scale pulse — pick one lightweight.
- Clicking empty scene space or another launcher deselects / re-selects.

The selection state is transient client-side state (frontend-only). Remove button reads from it.

## AI Auto extended

`ai_auto` now restores both **roster** and **positions** to the config default:
1. Remove every current launcher (refund budget).
2. Add one launcher per `BLUE_LAUNCHER_POSITIONS` entry (deduct budget per add).
3. Net budget change equals zero IF the current roster was exactly the default AND all budget previously spent was refundable. If operator was mid-match-budget-spending already, net may diverge — that's expected.

**Keep the simple stub framing:** a real placement heuristic is still Oskar's future scope.

## What is NOT in scope

- No minimum-spacing validation between launchers (same as Part 1 — future polish).
- No per-kind placement restrictions (e.g. "PAC-3 must be behind CIWS"). Operator plans with the land-only constraint.
- No roster cap (operator can fill the map with PAC-3s if budget allows — that's a gameplay choice, not a rule to enforce).
- No per-kind visual badge / cost-display-on-mesh — keep purely ribbon-side for this worker.
- No animation on add/remove — just snap in / snap out via snapshot.
- No "buy interceptors separately" — interceptor cost stays per-launch at `fire` time, unchanged.
- No drag-to-place-during-add (click Add → launcher spawns at default point, operator drags). Drag-to-place-from-dropdown is polish, defer.
- No refund cap per-kind or per-operator action. Budget clamp is the only guard.

# Task

Six subtasks, in order. One commit per subtask. Push each after local + (where applicable) browser smoke.

## Subtask A — LAUNCHER_BASE_COSTS config + snapshot field (~30 min)

1. Add `LAUNCHER_BASE_COSTS: Dict[str, int]` dict to `backend/sim/config.py` with the six values above + the `# TODO: tune against balance sweep post-Hack-Day` comment.
2. Extend the per-launcher snapshot dict (the one that feeds `snap['launchers']`) to include `base_cost_usd: int` pulled from `LAUNCHER_BASE_COSTS[launcher.kind.value]`.
3. Short unit test `test_launcher_base_cost.py`: build a default scenario, assert every snapshot launcher has the right `base_cost_usd` per the table, assert total default roster base cost = `$42_500_000`.

**Commit:** `feat(game-core): LAUNCHER_BASE_COSTS config + snapshot exposure (Issue #6 prereq)`

Push.

**STOP:** if the snapshot shape change breaks any existing test or requires non-additive changes to `server.py` / frontend, STOP and report.

## Subtask B — Backend add_launcher + remove_launcher (~45–60 min)

1. In `backend/server.py`, add two new WS command handlers alongside `_place_launcher_cmd` / `_ai_auto_cmd`:
   - `_add_launcher_cmd(cmd)` per the contract above.
   - `_remove_launcher_cmd(cmd)` per the contract above.
2. Dispatch from `handle_command` by `cmd == 'add_launcher'` / `cmd == 'remove_launcher'`.
3. Helper function — consider factoring a small `_deduct_budget(world, amount, action)` utility if the logic would otherwise duplicate. Don't over-refactor.
4. Next-index logic for add: scan existing launchers of the matching kind, take `max_idx + 1`. Must not collide with any existing id.
5. Integration test `test_roster_api.py` — cover:
   - `add_launcher` with valid kind + valid south-land pos + sufficient budget → asserts launcher added, budget decreased by exact base_cost, new launcher id present in snapshot.
   - `add_launcher` with insufficient budget → reject, no state change.
   - `add_launcher` with bad kind / bad pos → reject.
   - `remove_launcher` for a known id → asserts launcher removed, budget incremented by exact base_cost (clamped at `BLUE_BUDGET_START`).
   - `remove_launcher` for unknown id → reject.
   - Both commands from RUNNING phase → reject.
   - Round-trip: add then immediately remove → net zero budget change.
6. Extend `_ai_auto_cmd` to restore roster (not just positions):
   - Remove every current launcher (refund).
   - Add one launcher per `BLUE_LAUNCHER_POSITIONS` entry (deduct).
   - Test: after `ai_auto` the snapshot roster exactly matches the config default (same ids + same positions).

**Commit:** `feat(server): add_launcher + remove_launcher + ai_auto roster restore (Issue #6)`

Push.

**STOP:** if the add/remove logic needs to touch the blue_ai tick loop or launcher assignments dict for correctness, STOP — that's a sign of hidden coupling, report scope creep.

## Subtask C — Frontend ribbon roster dropdown + Add/Remove buttons (~60–90 min, browser smoke)

1. Extend the W8 SETUP ribbon (`frontend/index.html` / `frontend/js/hud.js`) with:
   - A `<select id="roster-kind">` with 6 options showing `{display_name} (${base_cost_m}M)` — display names example: CIWS / RBS-70 / IRIS-T SLS / IRIS-T SLM / PAC-2 GEM-T / PAC-3 MSE. Cost display: base_cost_usd / 1_000_000 + "M", e.g. "$15M".
   - `<button id="btn-add-launcher">+ Add</button>`
   - `<button id="btn-remove-launcher" disabled>− Remove</button>`
2. Wire Add: reads dropdown value + a default pos (centre of south land, use `(config.BLUE_BASE_POS[0], config.BLUE_BASE_POS[1])` — derive server-side default or hardcode a safe centre like `(75_000, 10_000)`), sends `{cmd: 'add_launcher', kind, pos}`. Operator drags afterward.
3. Wire Remove: when a launcher is selected (from Subtask D), button is enabled and sends `{cmd: 'remove_launcher', launcher_id}`.
4. CSS: keep the ribbon visually compact. Do NOT make it double-height or visually cluttered; judges should still see the 3D scene clearly.
5. Error-frame handling: reuse the W7 red-phase-chip-flash with the reason tooltip — server's `insufficient_budget` / `illegal_placement` errors flash as usual. No new UX invention.

**Browser smoke (Chen-paired):**
- Open, in SETUP, pick PAC-3 from dropdown, click Add → new purple launcher appears at default pos (operator drags to a chosen spot). HUD budget drops by $15M.
- Click Remove on the new launcher (after select — Subtask D). Budget restores.
- Try Add when budget too low (spam Add) — see red flash + tooltip "insufficient_budget".
- AI Auto button still works: resets roster to default, budget matches expected net (approximately $120M minus any mid-setup spend that wasn't refunded).

**Commit:** `feat(frontend): SETUP ribbon roster dropdown + Add/Remove buttons (Issue #6)`

Push.

**STOP:** if the ribbon layout requires > 80 lines of CSS churn to accommodate the new controls, STOP and simplify.

## Subtask D — Launcher click-to-select (~30–45 min, browser smoke)

1. In the drag handler (frontend/js/drag_launchers.js or wherever), detect "click" vs "drag" via a pixel-distance threshold on pointer-down → pointer-up delta (e.g. <4 px = click).
2. On click of a launcher's mesh Group during SETUP:
   - Set the launcher id as the current selected id in a simple frontend module-level state.
   - Visual feedback: apply a subtle outline or emissive boost to the selected launcher's Group (pick the simpler one, it's fine to show a bright wire-frame ring or scale by 1.05x).
   - Enable the Remove button in the ribbon.
3. On click of empty scene space: deselect, hide outline, disable Remove button.
4. On drag (when the pointer-move exceeds threshold): cancel any pending click; drag proceeds as per W8.
5. Outside SETUP: click does nothing (match W8's drag gating).

**Browser smoke (Chen-paired):**
- In SETUP, click a PAC-3 launcher — subtle visual select, Remove button enables. Click empty space — deselect. Drag-then-release — no select (it was a drag).

**Commit:** `feat(frontend): launcher click-to-select in SETUP (Issue #6 prereq for Remove)`

Push.

**STOP:** if click vs drag disambiguation is flaky (selects happen during drags or vice versa), iterate on the threshold; if still flaky after 2-3 tries, STOP and report (may need time-based instead of distance-based discriminator).

## Subtask E — AI Auto extended to restore roster (~20–30 min, browser smoke)

This subtask's backend work lands in Subtask B. Subtask E is frontend sanity + docs:

1. Confirm frontend doesn't need changes — ai_auto just triggers a snapshot roster reset; `LauncherRegistry` should handle additions / removals via the existing snapshot-diff path.
2. If the `LauncherRegistry` has a stale-id cleanup issue after `ai_auto` (ids that no longer exist in snapshot but still render as meshes), fix it here — standard snapshot-diff pattern. If it already handles it gracefully, verify and move on.

**Browser smoke (Chen-paired):**
- Add 2–3 extra PAC-3s, drag them around. Click AI Auto. Expect: extras removed, default roster reappears at default positions, budget restored to $120M (modulo any mid-setup interceptor fires that already deducted — there won't be any since we're in SETUP).

**Commit:** `fix(frontend): LauncherRegistry handles roster diff on ai_auto (Issue #6)`

Push. If no frontend change is needed (registry already diffs cleanly), skip this commit and note in Subtask F.

**STOP:** if registry needs a major rework to support roster diff, STOP — may indicate W8's LauncherRegistry wasn't written against a dynamic roster.

## Subtask F — Docs close (~30 min)

1. Update `team-missile-intercept/game-core/ISSUES_2026-04-19.md`:
   - Issue **#6 (buy vehicle)**: `**State:**` → `Done (M-TIER2-J Part 2, landed 2026-04-20). Operator can add/remove launchers during SETUP with budget deduction/refund via WebSocket commands add_launcher + remove_launcher. ai_auto extended to restore the full config-default roster. See commit list below.`
   - Issue **#7 (Deployment UI)**: add a closing note that Part 2 is landed and the full Milestone J scope is now complete.
2. Update `team-missile-intercept/progress/STATUS.md`: append a "M-TIER2-J Part 2 landed" entry in the Open Items / tier block.
3. Update `team-missile-intercept/game-core/CHEN_BACKLOG.md` item **#3** — mark Part 2 Done, list the commit hashes.
4. If the default-roster base-cost invariant ($42.5M) changes during balance tuning later, it's captured in the `LAUNCHER_BASE_COSTS` TODO comment from Subtask A.

**Commit:** `docs: W9 close — M-TIER2-J Part 2 landed, ISSUES #6 Done`

Push.

# Non-goals / guardrails

- **Do NOT change `world.blue_budget` starting value or the $120M constant.**
- **Do NOT introduce new launcher kinds** — the 6 existing kinds stay as the full roster.
- **Do NOT tune `LAUNCHER_BASE_COSTS` numbers beyond the table above**; flag the `# TODO` comment for post-Hack-Day tuning.
- **Do NOT touch Red AI, Blue AI, physics, interceptor specs, balance, or threat behaviour.**
- **Do NOT touch `requires_ground_impact`, `engagement_mode`, `Scenario.winner`.**
- **Do NOT touch the W8 drag-drop logic** beyond the click-vs-drag discriminator in Subtask D.
- **Do NOT rework the FINISHED overlay or the W8 Pause/Resume logic.**
- **Do NOT implement any form of "lead prediction" or pre-launch** — that's Issue #19 / Oskar scope.
- **Do NOT add refund limits per-kind or per-operator-action** — budget clamp is the only guard.
- **Do NOT change WebSocket snapshot schema beyond adding `base_cost_usd` additively.**
- **Do NOT rename existing WS commands** (`start`, `pause`, `resume`, `reset`, `set_speed`, `place_launcher`, `ai_auto`). Add `add_launcher` + `remove_launcher` as new.
- **Do NOT commit API keys.**
- **No `--no-verify`, no `git amend`, no force-push.**
- **English** in commits, code, comments, docs.

# Hard rules

- One commit per subtask. 6 subtasks → 6 commits (or 5 if Subtask E is a no-op).
- Each commit pushed immediately after local tests pass (and, for frontend subtasks, after Chen confirms the browser smoke).
- Each commit ends with the project-convention `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` line.
- If a STOP condition hits, stop the entire session and write the final summary.
- Budget: ~3.5–4.5 h. Chen is supervising; pause between subtasks if needed.

# Browser verification protocol

Same as W8. Chen runs the real browser; use `preview_eval` for programmatic JS checks if absolutely needed but do not trust `preview_click` for UI. Ground truth = Chen's mouse.

# Post-flight

1. `git status` — clean.
2. `git log --oneline -12` — new commits above `edf426d`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity.
4. If stashed at preflight: `git stash pop`.
5. Re-run preflight test list. All must still pass. Plus the two new tests (`test_launcher_base_cost.py`, `test_roster_api.py`).

# Deliverable — final summary (≤ 500 words)

1. **Commits landed** (hashes + one-line each).
2. **Subtask A (base cost)** — values used, snapshot field location, test coverage.
3. **Subtask B (add/remove/ai_auto roster)** — command details, validation rules, test coverage, refund clamp behavior.
4. **Subtask C (ribbon roster)** — HTML/CSS summary, Add + Remove wiring, error-frame reuse.
5. **Subtask D (click-to-select)** — discriminator threshold used, visual feedback approach, browser verification outcome.
6. **Subtask E (ai_auto frontend)** — whether LauncherRegistry needed changes; any registry diff bug found and fixed.
7. **Subtask F (docs)** — which issues closed, what was updated.
8. **Test delta** — preflight → postflight, new test counts.
9. **Anything blocking or surprising** — visual jank flagged for Sebastijan's future polish, any hidden coupling discovered, edge cases.
10. **Next step candidates** — Tier 3 (Red budget pool / unified threat contract) is now the next tier. Flag any Part 2 follow-ups that surfaced.
