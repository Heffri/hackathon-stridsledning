# Worker 11 — Mouse UX fixes + CIWS lifetime cap + Magazine HUD rework

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Chen runs this **autonomously** (no per-subtask pause) — he'll do a single consolidated browser smoke at the end, so the worker should use `preview_eval` for programmatic self-verification where feasible, then hand over. Budget: ~3–3.5 h. Four subtasks → four commits.

**Prerequisite:** M-TIER3-THREAT-CONTRACT must have landed. Confirm `git log --oneline -6` shows at least `fe2fa44 feat(game-core): M-TIER3-THREAT-CONTRACT — unified Threat control API (Issues #10/#11/#12)` near the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task. Use game-dev framing ("launcher", "magazine", "jink", "roster") in all prose.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). Push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `fe2fa44` (M-TIER3-THREAT-CONTRACT close) or newer.

Start by reading:
- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — focus on **Issues #20 (CIWS)** and #6 / #7 context
- `team-missile-intercept/game-core/CONTRACT_SEAMS.md`
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`

Key files (worker will extend these):
- `team-missile-intercept/frontend/index.html` — HUD structure, right-side Magazine panel
- `team-missile-intercept/frontend/js/hud.js` — Magazine panel render; runs per-snapshot
- `team-missile-intercept/frontend/js/launcher_selection.js` — client-side selection state (`getSelectedLauncherId()`, `setSelectedLauncherId()`)
- `team-missile-intercept/frontend/js/drag_launchers.js` — pointer handlers, raycaster, click-vs-drag discriminator (5 px)
- `team-missile-intercept/frontend/js/launchers.js` — LauncherRegistry: per-launcher `THREE.Group` with box + range ring children
- `team-missile-intercept/frontend/style.css` — ammo / budget / ribbon styling
- `team-missile-intercept/backend/sim/blue_ai.py` — CIWS point-defense block (already landed Issue #20 expected-damage gate; this worker adds a lifetime shot cap on top)
- `team-missile-intercept/backend/test_ciws_saturation.py` — existing baseline; extend or add a sibling test

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker11-preflight"` and pop at end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -8` — confirm `fe2fa44` or newer is at top.
6. Preflight baseline tests (all must pass before starting — if any fail, STOP):
   - `python team-missile-intercept/backend/test_match_phase.py`
   - `python team-missile-intercept/backend/test_match_phase_integration.py`
   - `python team-missile-intercept/backend/test_engagement_mode.py`
   - `python team-missile-intercept/backend/test_launcher_id.py`
   - `python team-missile-intercept/backend/test_placement_api.py`
   - `python team-missile-intercept/backend/test_launcher_base_cost.py`
   - `python team-missile-intercept/backend/test_roster_api.py`
   - `python team-missile-intercept/backend/test_ciws_saturation.py`
   - `python team-missile-intercept/backend/test_winner_budget_not_loss.py`
   - `python team-missile-intercept/backend/test_red_budget.py`
   - `python team-missile-intercept/backend/test_threat_contract.py`
   - `python team-missile-intercept/backend/test_cruise_impact.py`
   - `python team-missile-intercept/backend/test_hgv_impact.py`
   - `python team-missile-intercept/backend/test_ballistic_cep.py`

# Design targets

## Subtask A — Canvas mouse UX fixes (Issue #23, new)

Chen's 2026-04-20 smoke report flagged three browser-default behaviours leaking into the 3D scene:

1. **Left-click-drag paints a text-selection box** over the canvas. Browser is treating the canvas area as selectable content because there's no `user-select: none`.
2. **Right-click shows the browser context menu** (copy / reload / back) instead of doing nothing. Missing `contextmenu` preventDefault.
3. **"Can't grab launcher" ghost**: pointer-down on a launcher sometimes does not engage the drag handler. Very likely the raycaster is hitting the **range ring** (transparent circular mesh) as a child of the launcher `THREE.Group` *before* the launcher box mesh, and the drag handler then either picks the wrong object or bails. W8's drag handler uses `intersectObjects(group, true)` style recursion — range rings intercept.

**Fix pattern:**

1. **CSS (`style.css`):** on the Three.js canvas (grep for the canvas element id — likely `#scene-canvas` or created inside `scene.js`), set:
   ```css
   user-select: none;
   -webkit-user-select: none;
   touch-action: none;
   ```
   Also apply `user-select: none` to the top-level app container so cascaded text selection doesn't re-enter.

2. **JS (`drag_launchers.js` or `main.js`):** on the canvas element, register:
   ```js
   canvas.addEventListener('contextmenu', (e) => e.preventDefault());
   canvas.addEventListener('selectstart', (e) => e.preventDefault()); // extra safety
   ```
   These must be added once at setup, not inside an animation loop.

3. **Raycast filter (`drag_launchers.js`):** ensure the raycaster that identifies a clicked / hovered launcher **only considers launcher box meshes**, not range rings. Pick ONE approach:
   - (a) **Explicit candidate list:** pass `intersectObjects(launcher_boxes_array, false)` (non-recursive, flat list of box meshes only). Requires `LauncherRegistry` to expose the box mesh list.
   - (b) **userData gate:** tag every range-ring mesh with `userData.raycastable = false` at construction (in `launchers.js`), and in the pointer handler filter `intersects.filter(hit => hit.object.userData.raycastable !== false)`.
   - (c) **Layer mask:** set range ring on a separate Three.js `layers` bit the raycaster doesn't scan.

   Pick whichever fits cleanest into the existing `LauncherRegistry` + `drag_launchers.js` architecture. Commit body must name the approach.

**Self-verify via `preview_eval`:**
- Start the server in background, load the scene, wait for launchers to render
- `preview_eval` to simulate a right-click on the canvas → confirm `document.body.dataset.contextmenuPrevented === 'true'` (or similar marker you set in the handler to prove the prevention ran)
- `preview_eval` to check `getComputedStyle(canvas).userSelect === 'none'`
- `preview_eval` to raycast against the scene at a known launcher's screen position → confirm the first hit's `userData` / name is the launcher box, NOT the range ring

**Commit:** `fix(frontend): canvas user-select + contextmenu + raycast filters out range rings (Issue #23)`

Push.

**STOP:** if the raycast filter approach requires > 80 lines of churn in `LauncherRegistry`, STOP and downgrade to the userData-gate approach.

---

## Subtask B — CIWS lifetime shot cap (Issue #24, refinement of #20)

Chen's 2026-04-20 smoke report: CIWS still fires "a lot" of rounds at drone swarms. Analysis:

- M-TIER2.8 (Issue #20, commit `bf0c652`) added an `_expected_damage` gate to the CIWS block. Gate is **per-threat** and counts **in-flight** damage. If a CIWS round misses and self-destructs at `fuel_s=4`, expected_damage immediately drops to 0 for that threat → next CIWS round fires → cycle repeats.
- Multiple drones concurrently in the 4 km envelope each have their own `assigned_iids`, so CIWS fires N rounds per drone concurrently.

**Net effect:** M-TIER2.8 stops "dump 30 rounds in one tick" but not the slower "1 round every 4 s as previous rounds die off". Against a drone that takes 6–10 s to cross the envelope, that's still 2–3 rounds with **perfect hits** but 5–8 rounds with typical misses.

**Fix: per-threat lifetime shot cap on `BlueAI`.**

1. Add a new field on `BlueAI`:
   ```python
   # threat_id → cumulative CIWS rounds fired at this threat (alive + dead)
   self.ciws_fired_count: Dict[int, int] = {}
   ```
2. Purge in the `BlueAI.step` top-loop that already purges dead assignment entries — when a threat itself is gone (no longer in `world.threats`), drop its counter entry.
3. Compute a per-threat cap from the threat's spec:
   ```python
   ciws_damage_prox = INTERCEPTOR_SPECS[InterceptorType.CIWS].damage_prox  # 8
   threat_spec_hp = threat.spec.hp  # 10 drone / 30 cruise / 80 ballistic / 60 hgv
   ciws_shot_cap = math.ceil(threat_spec_hp / ciws_damage_prox) + 2  # +2 = slack for misses
   ```
   Rationale for `+2` slack: `damage_prox` assumes a prox-range hit (CPA ≤ `radius_prox = 80 m`). Real CPA distribution has a long tail — allow 2 "try again" shots past the nominal kill count without allowing unbounded spam. Drone cap = ceil(10/8)+2 = **4**. Cruise = ceil(30/8)+2 = **6**. Ballistic = ceil(80/8)+2 = **12** (CIWS can't realistically hit ballistic at Mach 13 but at least the cap is bounded). HGV = ceil(60/8)+2 = **10**.
4. Add the cap check in the CIWS block (just before or after the existing `_expected_damage` gate):
   ```python
   if self.ciws_fired_count.get(tid, 0) >= ciws_shot_cap:
       # lifetime cap reached — stop spraying this threat, save the rounds
       pass  # fall through, no fire
   else:
       # existing expected-damage gate + fire loop, incrementing counter on each fire
   ```
5. Increment `self.ciws_fired_count[tid]` every time a CIWS round is actually fired at `tid`.

**Test:** extend `test_ciws_saturation.py` or add `test_ciws_shot_cap.py`:
- Scenario: single drone spawned just outside the CIWS envelope, flown through it at a trajectory that deliberately causes CIWS rounds to MISS (e.g. spawn at 2 km altitude, drone path passes within 4 km horizontal but at altitude > CIWS kill radius at the crossing moment; or force the drone to survive some rounds by artificially restoring its HP). Assert: total CIWS rounds fired at this threat ≤ `cap + small margin` across the full envelope crossing.
- Alternative (simpler): spawn a drone with HP = 50 (artificially bumped) directly in the envelope; let CIWS fire repeatedly. Assert total CIWS rounds ≤ cap-for-hp-50 = ceil(50/8)+2 = 9. Even if every shot misses, the cap holds.

Second test case: **default scenario full-match** runs through, total CIWS rounds fired < a reasonable upper bound (use `blue.log` count of `[CIWS]` entries).

**Docs:** Issue #24 added to `ISSUES_2026-04-19.md` below Issue #23. Issue #20's state stays Done — #24 is a refinement.

**Commit:** `fix(game-core): CIWS per-threat lifetime shot cap (Issue #24, refinement of #20)`

Push.

**STOP:** if adding the counter breaks any of the 11 existing Blue AI tests, STOP and report — the counter must be purely additive.

---

## Subtask C — Magazine HUD: per-launcher detail view (Issue #25, new)

Chen's 2026-04-20 smoke report: post-W9 Part 2 (buy vehicle), the right-side "Magazine" panel shows per-kind totals (e.g. "PAC-3: 4") which is ambiguous when roster becomes dynamic (is that 1 launcher × 4 rounds, or 2 × 2, or 4 × 1?). Chen wants the panel to show the **selected launcher's detailed status** instead. Nothing selected → hide the panel (or show a placeholder).

**UI design:**

Existing right-side HUD block:
```html
<div class="hud-block ammo" id="ammo-panel">
  <div class="ammo-title">Magazine</div>
  <div class="ammo-row" data-kind="ciws">...</div>
  ...
</div>
```

Rework:

```html
<div class="hud-block ammo" id="ammo-panel">
  <div class="ammo-title" id="ammo-panel-title">Magazine</div>
  <div id="ammo-panel-body">
    <!-- content rendered dynamically by hud.js based on selection -->
  </div>
</div>
```

**States to render:**

1. **No launcher selected** — title "Magazine", body shows placeholder:
   > `Click a launcher to inspect its magazine and reload state.`
   Muted text, no data rows.

2. **Launcher selected** — title "Magazine — {Display Name}", body shows:
   - **Ammo:** `{current} / {capacity}` with a small bar (reuse an existing ammo-bar component if available, else inline bar)
   - **Status:** one of:
     - `Ready` (green) — ammo > 0 AND not in inter-shot cooldown
     - `Reloading` (yellow) — `reloading` flag true, countdown `t_remaining = reload_start_t + reload_time - t_now`
     - `Cooldown` (amber) — between shots, countdown `t_remaining = last_shot_t + inter_shot_cd - t_now`
   - **Base cost:** `${base_cost_usd / 1_000_000}M` (from snapshot, already exposed in W9 Subtask A)
   - Optional: **Position:** `({x/1000:.1f}, {y/1000:.1f}) km` so the operator can sanity-check the placement
   - Optional: **Range:** `{max_range / 1000} km` (static per kind — looked up in a small client-side table)

**Data sources:**
- Selected launcher id: `getSelectedLauncherId()` from `launcher_selection.js`
- Launcher's live snapshot entry: `snap.launchers.find((l) => l.id === selectedId)`. Current snapshot fields: check `scenarios.py::snapshot` output — should include `id`, `kind`, `pos`, `current_ammo`, `magazine_capacity`, `base_cost_usd`, and reload-state fields. If reload-state fields aren't in the snapshot today, add them (additive-only; don't rename existing). Field names to use:
  - `current_ammo` (int)
  - `magazine_capacity` (int)
  - `reloading` (bool)
  - `reload_start_t` (float, sim-time)
  - `reload_time` (float, seconds, from spec)
  - `last_shot_t` (float)
  - `inter_shot_cd` (float, seconds, from spec)
- Current sim time: `snap.t` (exists today)

If some of those fields are not currently in the snapshot, add them. Match existing W9 snapshot conventions — add to the `_launcher_snapshot` helper (or equivalent) in `scenarios.py` or `launcher.py::LauncherFleet.fleet_status`.

**Rendering approach:**

Rewrite the `renderAmmo` (or similarly named) function in `hud.js`. It runs per-snapshot. Read the current selection, render the appropriate state. If the selection id is no longer in the snapshot launcher list, reset to "no selection" state (this already partly happens via the W9 auto-deselect hook).

Remove the old per-kind rows entirely. The JS should not emit them.

**CSS:**

Minimal new rules for:
- `.ammo-placeholder` (muted color, smaller font)
- `.ammo-detail-row` (label + value aligned)
- `.ammo-status.ready` / `.ammo-status.reloading` / `.ammo-status.cooldown` (color cues)

Match the existing glass-morphism aesthetic.

**Self-verify via `preview_eval`:**
- Start server, load scene
- `preview_eval` to programmatically call `setSelectedLauncherId('pac_3_0')` → confirm `document.getElementById('ammo-panel-body').textContent` contains "PAC-3" and ammo fraction text
- `preview_eval` to call `setSelectedLauncherId(null)` → confirm the placeholder text is back
- `preview_eval` to wait for a sim tick during RUNNING and confirm the ammo number updates when an interceptor fires

**Commit:** `feat(frontend): Magazine HUD shows selected launcher detail (Issue #25)`

Push.

**STOP:** if the snapshot field additions require non-additive changes to existing launcher tests (W8 launcher_id, W9 placement_api / roster_api / launcher_base_cost), STOP and report — additions must be purely additive.

---

## Subtask D — Docs close

1. Update `team-missile-intercept/game-core/ISSUES_2026-04-19.md`:
   - Issue **#23 (canvas mouse UX)**: add as new issue. State: Done. Summarise the three fix branches.
   - Issue **#24 (CIWS lifetime cap)**: add as new issue. State: Done. Cross-ref Issue #20 as baseline; describe the counter + cap formula + `+2` slack rationale.
   - Issue **#25 (Magazine HUD per-launcher detail)**: add as new issue. State: Done. Describe the UI states + snapshot field additions.
2. Update `team-missile-intercept/progress/STATUS.md`: append a `0.98 W11 bugfixes + HUD rework` entry under Open Items listing the three issues and key commits.
3. If any snapshot field was added in Subtask C, update `team-missile-intercept/game-core/CONTRACT_SEAMS.md` §2 snapshot-schema section. Additive-only.

**Commit:** `docs: W11 close — mouse UX + CIWS cap + Magazine HUD (Issues #23, #24, #25)`

Push.

# Non-goals / guardrails

- **Do NOT start a server and leave it running at end of session.** W8 left port 5174 occupied. Always `kill` / stop any server you launch for self-verify.
- **Do NOT touch W10's threat-contract changes.** `target_site_id`, `maneuver_schedule`, `_final_target`, flyover fallback, `_active_schedule_accel` — all stay as landed.
- **Do NOT touch Red AI, Blue AI engagement ladder, physics, spec values, balance beyond CIWS cap, threat behaviour.** Only the CIWS point-defense block in `blue_ai.step` changes.
- **Do NOT touch `requires_ground_impact`, `engagement_mode`, `Scenario.winner`, `world.red_budget`.**
- **Do NOT touch cruise terminal dive (W7) or HGV glide-path dive (W3).**
- **Do NOT rework the FINISHED overlay, SETUP ribbon, Pause/Resume, click-to-select, drag-drop core logic.** The drag handler's raycast selector is the only structural change in Subtask A.
- **Do NOT add per-kind ammo totals back** in the Magazine HUD — the point of Subtask C is to get rid of the misleading aggregate view.
- **Do NOT add Blue-AI "re-target on target death" logic** (Chen considered this; decided to wait for Oskar's Issue #19 work).
- **Do NOT change WebSocket snapshot schema except additive fields for Subtask C.**
- **Do NOT rename existing WS commands.**
- **Do NOT commit API keys.**
- **No `--no-verify`, no `git amend`, no force-push.**
- **English** in commits, code, comments, docs.

# Hard rules

- One commit per subtask. 4 subtasks → 4 commits (commits A–D).
- Each commit pushed immediately after local tests pass (and, for frontend subtasks, after `preview_eval` self-checks succeed).
- Each commit ends with the project-convention `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` line.
- If a STOP condition hits in any subtask, ship prior subtasks (if committed), STOP the entire session, and write the final summary including which subtasks failed and why.
- Budget: ~3–3.5 h total.
- **Chen is NOT paired during this run.** Self-verify via `preview_eval` + test scripts. Chen will do a single consolidated browser smoke at the end.

# Browser verification protocol (worker-autonomous)

1. Apply the change locally.
2. Start the server IN BACKGROUND with a short timeout (e.g. 60 s) — use `run_in_background=True` on the Bash tool so it doesn't hang the session.
3. Run `preview_start` against `http://127.0.0.1:5174/` (or whichever port; check env / `config.py`).
4. Use `preview_eval` to run programmatic JS against the loaded page to verify DOM state / event listener wiring / raycast behaviour.
5. When the subtask's self-verification passes, commit + push.
6. **Kill the server before moving on to the next subtask** — `kill %1` or equivalent. The server should NOT survive past the end of the session.

`preview_click` was unreliable for the Pause button in W4. Do not trust it. Use `preview_eval` to programmatically dispatch pointer events if you need interaction: `element.dispatchEvent(new PointerEvent('pointerdown', {clientX, clientY, bubbles: true}))`.

# Post-flight

1. `git status` — clean.
2. `git log --oneline -8` — 4 new commits above `fe2fa44`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity.
4. If stashed at preflight: `git stash pop`.
5. Re-run the full preflight test list PLUS the new test(s). All must still pass.
6. Kill any background server you started. `netstat -ano | grep :5174 | grep LISTENING` should return empty.

# Deliverable — final summary (≤ 500 words)

1. **Commits landed** (4 hashes + one-line each).
2. **Subtask A (mouse UX)** — which raycast filter approach you chose (candidate list / userData gate / layer mask) and why.
3. **Subtask B (CIWS cap)** — cap values per kind, test verification pattern, confirmation that `blue.log` CIWS count stays under a reasonable ceiling in a full-match scenario.
4. **Subtask C (Magazine HUD)** — final UI states, snapshot fields added (if any), `preview_eval` verification outcome.
5. **Subtask D (docs)** — three new issues logged, STATUS + CONTRACT_SEAMS updated.
6. **Test delta** — preflight → postflight, new test counts.
7. **Any blocking or surprising** — especially any flakiness in `preview_eval` raycast verification or snapshot-field additions that needed more work than expected.
8. **For Chen's consolidated smoke pass** — give a punch list:
   - [ ] Right-click on canvas: no browser menu.
   - [ ] Left-drag across canvas: no text-selection box.
   - [ ] Click centre of a launcher box (not ring): reliably selects.
   - [ ] Drag launcher box: moves smoothly, no "can't grab".
   - [ ] CIWS against a drone in live demo: bounded round count.
   - [ ] Select a launcher in SETUP: Magazine panel shows its detail.
   - [ ] Click empty space: Magazine panel shows placeholder.
   - [ ] During RUNNING, select a launcher that fires: ammo count decrements, reload status shows.
   - [ ] AI Auto: roster returns to defaults, budget stays $120M.
9. **Server lifecycle confirmation** — port 5174 is free at session end.
