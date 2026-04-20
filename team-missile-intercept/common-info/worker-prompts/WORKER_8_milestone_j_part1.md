# Worker 8 — M-TIER2-J Part 1: Deployment UI + pause overlay rework + SETUP ribbon

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingy\Documents\github\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Chen runs this **with supervision** — daytime session, expected to need browser smoke checks. Budget: ~4–5 h. Six subtasks → six commits.

**Prerequisite:** Worker 7 (M-TIER2.7-CRUISE-DIVE) must have landed. Confirm `git log --oneline -8` shows `934a3da docs: W7 close — ISSUES #13 done + #15 accepted + #18 captured + STATUS` at (or near) the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task. Use game-dev framing ("launcher placement", "deployment phase", "game", "arcade") in all prose.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). Push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `934a3da` (Worker 7 close commit, or newer).

Start by reading:
- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — focus on **Issue #7** (Deployment UI / Milestone J)
- `team-missile-intercept/game-core/CHEN_BACKLOG.md` — item **#3** (Deployment Phase and Launcher Placement Support)
- `team-missile-intercept/game-core/CONTRACT_SEAMS.md` — W6 doc on phase FSM, WS schema, spawn contracts
- `team-missile-intercept/game-core/ENGAGEMENT_MODE_DESIGN.md` — W5 design
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`

Key runtime files:
- `team-missile-intercept/backend/sim/config.py` — `BLUE_LAUNCHER_POSITIONS` (lines ~82–90) is the current source-of-truth launcher layout
- `team-missile-intercept/backend/sim/launcher.py` — Launcher class, spawn_launcher-ish pattern
- `team-missile-intercept/backend/sim/scenarios.py` — `build_default_scenario(auto_start=...)` constructs Launchers from config
- `team-missile-intercept/backend/sim/terrain.py` — `point_on_south_land(x, y) -> bool` is the land-only validator
- `team-missile-intercept/backend/sim/world.py` — `World.launchers` dict / list, phase transition logic
- `team-missile-intercept/backend/sim/types.py` — `MatchPhase` enum
- `team-missile-intercept/backend/server.py` — WebSocket command handler (already has `start`, `pause`, `resume`, `reset`, `set_speed` from W1/W4/W7)
- `team-missile-intercept/frontend/index.html` — HUD structure; current central SETUP/PAUSED overlay is here
- `team-missile-intercept/frontend/js/hud.js` — phase chip, overlay rendering, Pause/Resume/Start button wiring (W4 + W7 edits)
- `team-missile-intercept/frontend/js/main.js` — WebSocket routing (W7 patched `phase_change` / `error` typed frames)
- `team-missile-intercept/frontend/js/launchers.js` — Three.js launcher meshes + range rings (Milestone H added range rings parented to launcher Group)
- `team-missile-intercept/frontend/js/three_scene.js` or equivalent — the main Three.js scene, camera, raycaster setup (grep for raycaster / ground plane)
- `team-missile-intercept/frontend/style.css` — overlay styles; phase chip colors (W4 + W7 edits)

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker8-preflight"` and pop at end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -5` — confirm `934a3da` or newer is at top. If older, STOP and report.
6. Run preflight baseline:
   - `python team-missile-intercept/backend/test_match_phase.py` — must pass.
   - `python team-missile-intercept/backend/test_match_phase_integration.py` — must pass.
   - `python team-missile-intercept/backend/test_engagement_mode.py` — must pass.
   - `python team-missile-intercept/backend/test_cruise_impact.py` — must pass (W7's new one).
   - `python team-missile-intercept/backend/test_hgv_impact.py` — must pass.
   - `python team-missile-intercept/backend/test_ballistic_cep.py` — must pass.
7. Start the server briefly (`python team-missile-intercept/backend/server.py`) and verify the existing SETUP overlay + Start Match button still work as a sanity check — then stop the server. (You can skip this if you're confident from the git state; it's a belt-and-suspenders check.)

If any preflight test fails, STOP and report.

# Design targets (read this section carefully — it drives all six subtasks)

## Phase-to-UI mapping

| Phase | Scene behavior | Overlay / Ribbon | HUD buttons |
|---|---|---|---|
| SETUP | Launchers visible, draggable; range rings visible; sim frozen | **Top ribbon** (non-blocking) with "MATCH SETUP — drag launchers, then Start Match" + [AI Auto] + [Start Match] | phase chip gray |
| RUNNING | Normal sim | none | phase chip green; Pause button |
| PAUSED | Frozen mid-match; click-inspect works | **none** (no central overlay — operator needs to inspect battlefield) | phase chip yellow; Pause button flips label to "Resume" |
| FINISHED | Match locked | **Central overlay** with winner + [Restart] button | phase chip red |

The key rework from W4's current state:
- **SETUP** overlay becomes a thin ribbon (not blocking the 3D canvas — needed for launcher drag visibility).
- **PAUSED** central overlay is **removed entirely**. The Pause button in HUD flips to "Resume" when paused.
- **FINISHED** overlay stays central (semantically "make a choice before continuing").

## Launcher drag-drop contract

- **Who can drag:** only during `phase === 'setup'`. Outside SETUP, launchers are immovable; ignore drag attempts.
- **How to drag:** pointer-down on a launcher mesh in the 3D scene → drag follows ground-plane raycast → pointer-up commits.
- **Commit:** on pointer-up, client sends `{cmd: 'place_launcher', launcher_id: '<id>', pos: [x, y]}`. Server validates and responds.
- **Validation (server-side):**
  - Phase must be SETUP (else reject with error frame).
  - Position must satisfy `terrain.point_on_south_land(x, y)` (else reject).
  - Optional: minimum spacing between launchers — **skip for this worker**; future polish.
- **Success response:** server updates launcher position in `world.launchers`; broadcast snapshot. Client sees the authoritative position from next snapshot; the transient drag position is overwritten.
- **Failure response:** `{type: 'error', reason: 'illegal_placement', ...}` typed frame. W7 already wires this into the phase-chip red flash with the reason as tooltip — reuse.
- **Visual snap-back on invalid:** when rejected, the client receives the error frame. The launcher naturally snaps back to its previous position from the next snapshot (which still has the old position since server didn't commit). No additional client logic needed beyond what's already there.

## Launcher identity

Each launcher needs a **stable string ID** for the `place_launcher` protocol. Current code likely uses index within kind (e.g. `"ciws_0"`, `"pac_3_0"`, `"iris_t_sls_1"`). If no stable ID exists yet, add one: `f"{kind}_{index}"` where `index` is the zero-based position in the kind's list inside `BLUE_LAUNCHER_POSITIONS`. Store the ID on the `Launcher` instance (add to `__slots__` + `__init__`). Include the ID in the launcher snapshot dict so the frontend can address it.

## AI-Auto stub

A button labeled "AI Auto" that, when clicked in SETUP, lets the server place launchers via a heuristic. **Stub quality is acceptable** (per ISSUES.md Issue #7). Simplest implementation: reset all launchers to their default `BLUE_LAUNCHER_POSITIONS` values from `config.py`. Commit body documents that a real heuristic belongs to Oskar / future AI work.

## Start Match lock

"Start Match" sends `{cmd: 'start'}` (already implemented in W4). Server's existing phase transition `setup → running` is already the lock: once RUNNING, placement commands are rejected by the SETUP-only gate.

## What is NOT in scope (defer explicitly)

- **Per-launcher "buy vehicle"** (Issue #6 / Part 2 of Milestone J) — out of scope for Part 1. Roster stays at the config default; only re-position.
- **Adding or removing launcher instances** — roster count is fixed to config defaults.
- **Deployment-specific AI beyond the reset-to-default stub**.
- **Launcher-to-launcher minimum spacing validation**.
- **Animating the drag or placement motion** — snap to pointer position is fine.
- **Sebastijan's full maps/ drag UX polish** — we're doing minimum viable drag. Flag anything visually rough in the commit body.

# Task

Six subtasks, in order. One commit per subtask. Push each after local + (where applicable) browser verification.

## Subtask A — Launcher stable ID + snapshot field (backend, ~20–30 min)

1. Audit current `Launcher` class (likely in `backend/sim/launcher.py`). If launchers already have a stable string ID, note where it is and skip code changes; otherwise add `id: str` to `Launcher.__slots__` and populate in `__init__` via `f"{kind}_{index}"`.
2. Populate the ID when constructing launchers in `scenarios.py::build_default_scenario`. `index` is the zero-based position within the kind's list.
3. Include the ID in the launcher dict that gets serialised into the snapshot (grep for `to_dict` or `launcher snapshot` or similar).
4. Unit test: add a small test `test_launcher_id.py` that constructs a default scenario and asserts every launcher has a unique non-empty `id` field matching the `{kind}_{index}` pattern.

**Commit:** `feat(game-core): stable Launcher.id field + snapshot exposure (Issue #7 prereq)`

Push.

**STOP:** if adding the id field breaks any existing test, STOP and report — the field must be purely additive.

## Subtask B — Backend placement API (`place_launcher` + `ai_auto`) (~45–60 min)

1. In `backend/server.py`, add two new WebSocket commands:
   - `{cmd: 'place_launcher', launcher_id: str, pos: [x: float, y: float]}`
     - Reject if phase != SETUP → `{type: 'error', reason: 'illegal_placement', detail: 'phase is <current>, must be setup'}`.
     - Reject if no launcher with that id → `{type: 'error', reason: 'illegal_placement', detail: 'unknown launcher_id'}`.
     - Reject if `not terrain.point_on_south_land(x, y)` → `{type: 'error', reason: 'illegal_placement', detail: 'position not on south land'}`.
     - Success: update `world.launchers[<id>]`'s position in-place. No ack frame necessary (next snapshot carries it).
   - `{cmd: 'ai_auto'}`
     - Reject if phase != SETUP (same error pattern).
     - Success: for every launcher, reset to its default position from `BLUE_LAUNCHER_POSITIONS` in `config.py`.
     - Commit body: "stub AI-Auto — resets to config default; real heuristic deferred to Oskar."
2. Reuse W7's typed-error-frame mechanism. Don't invent new error-frame fields beyond `reason` + `detail`.
3. Integration test `test_placement_api.py`:
   - Construct a fresh world in SETUP. Call `place_launcher` for a known id with valid south-land coords → assert position updated.
   - Call `place_launcher` with coords in the strait (not south land) → assert position unchanged.
   - Call `place_launcher` from RUNNING phase → assert rejected.
   - Call `ai_auto` from SETUP → assert positions reset to config default.
   - Call `ai_auto` from RUNNING → assert rejected.

   (These exercise the WS handler; if the handler isn't easily testable standalone, add a helper function that implements the core logic and is tested directly, with the WS handler being a thin wrapper.)

**Commit:** `feat(server): place_launcher + ai_auto WebSocket commands (Issue #7)`

Push.

**STOP:** if the handler needs major server.py restructuring (more than a small new branch in the existing command dispatcher), STOP and report scope creep.

## Subtask C — Pause overlay removal + Resume button flip (frontend, ~30–45 min)

1. In `frontend/js/hud.js` (or wherever `renderPhaseOverlay` was added by W4), change the PAUSED branch to **return nothing / hide the overlay**. Leave SETUP and FINISHED overlay rendering untouched (SETUP will be reworked into a ribbon in Subtask D; FINISHED stays central).
2. In the same file, change the HUD Pause button behavior:
   - When phase === RUNNING: label/icon says "Pause", click sends `{cmd: 'pause'}`.
   - When phase === PAUSED: label/icon says "Resume", click sends `{cmd: 'resume'}`.
   - When phase === SETUP or FINISHED: button hidden.
3. Phase chip color stays (gray/green/yellow/red per W4).
4. CSS: may need to remove rules that still apply pause-overlay styles even if overlay is hidden. Minimal touch; grep for "paused" in `style.css`.

**Verification:**
- Browser smoke test (Chen-paired): restart server, start match, click Pause → overlay does NOT appear, button label flips to "Resume", chip yellow, 3D scene fully visible, click-to-inspect still works on frozen entities. Click Resume → back to RUNNING.
- Deliver a clear note in the commit body: "pause overlay removed; verified via browser smoke test with Chen — operator can click-inspect frozen entities during pause."

**Commit:** `fix(frontend): pause overlay removed, Resume replaces Pause button (operator UX)`

Push.

**STOP:** if the overlay logic is tangled enough that removing PAUSED branch affects SETUP / FINISHED rendering, STOP — report and defer.

## Subtask D — SETUP overlay → non-blocking ribbon (frontend, ~60–90 min)

1. In `frontend/index.html`, change the SETUP overlay element from a central blocking DIV to a thin top ribbon. Suggested structure:
   ```html
   <div id="setup-ribbon" class="setup-ribbon hidden">
     <span class="setup-ribbon-text">MATCH SETUP — drag launchers to position, then Start Match</span>
     <button id="btn-ai-auto">AI Auto</button>
     <button id="btn-start-match">Start Match</button>
   </div>
   ```
   Width = viewport, height ~44 px, positioned top of screen, `z-index` above the 3D canvas but below the HUD HUD chip, semi-transparent backdrop (CSS).
2. In `hud.js` / overlay render logic:
   - Show ribbon only when phase === SETUP.
   - Keep FINISHED overlay central.
   - "Start Match" button wires to `{cmd: 'start'}` (existing).
   - "AI Auto" button wires to `{cmd: 'ai_auto'}` (new).
3. CSS:
   - `.setup-ribbon` positioned `top: 0; left: 0; right: 0; height: 44px; background: rgba(...);` — pick a colour consistent with the SETUP chip gray.
   - Typography: legible at demo distance.
   - Ensure the 3D canvas fills the rest of the viewport.
4. The existing Start Match button inside the (now-deleted central SETUP overlay) needs removing — don't have two Start Match buttons floating around.

**Verification:**
- Browser smoke test (Chen-paired): restart server → ribbon visible, 3D scene visible below, launchers visible, no central overlay blocking. Click Start Match → ribbon hides, sim starts. Click Reset → back to SETUP, ribbon shows. Click AI Auto → (for this subtask, the backend might not be wired to ai_auto yet if Subtask B hasn't landed — that's expected; the click should at minimum not crash the frontend).

**Commit:** `feat(frontend): SETUP overlay → non-blocking ribbon (Issue #7 prereq for drag-drop)`

Push.

**STOP:** if the overlay is deeply entwined with FINISHED overlay markup such that separating them requires > 100 lines of HTML/CSS churn, STOP — scope is creeping.

## Subtask E — Frontend launcher drag-drop (~60–90 min)

This is the hardest subtask. Expect to iterate.

1. In the Three.js scene setup (find the raycaster pattern — likely in `main.js` or a `three_scene.js`), add a new pointer-down / move / up handler that:
   - Only activates when phase === SETUP.
   - On pointer-down: raycast from the camera through the mouse; if the first hit is a launcher mesh's Group (Milestone H Part 4 parented range ring to launcher Group — that Group is the handle), enter drag mode for that launcher.
   - On pointer-move during drag: raycast onto a virtual ground plane at z=0; set the launcher Group's position to the raycast hit point. The range ring follows automatically (parented).
   - On pointer-up: read the final (x, y), send `{cmd: 'place_launcher', launcher_id: <dragged>.id, pos: [x, y]}`. Exit drag mode.
2. Launcher id: the mesh Group needs to carry its launcher id so the pointer handler can emit the correct payload. Attach as `userData.launcherId` when the Group is constructed (in `launchers.js`).
3. If the server rejects (W7's red phase-chip flash fires), the next snapshot restores the old position — no client-side snap-back needed.
4. Disable OrbitControls (or whatever camera controller is active) while dragging — you don't want the camera moving under the user. Re-enable after pointer-up.
5. Cursor: change to `grab` / `grabbing` when hovering over a launcher in SETUP phase.

**Verification (critical — browser smoke required):**
- Restart server. In SETUP phase, hover over a launcher — cursor becomes grab. Press and drag — launcher moves under pointer. Release on south land — launcher stays in new position (snapshot confirms). Drag into strait / water — launcher snaps back after error flash. Drag during RUNNING — nothing happens (no drag).
- Verify range rings (from Milestone H) follow the dragged launcher.

**Commit:** `feat(frontend): launcher drag-drop during SETUP phase (Issue #7 core)`

Push.

**STOP conditions:**
- Raycasting fails silently (clicks do nothing) → report; may need `Raycaster.firstHitOnly` or mesh ordering fix.
- Camera keeps moving during drag → fix the controller-disable; this is usually a one-line change but easy to miss.
- Drag feels laggy (> 100 ms between pointer and mesh) → may indicate per-frame raycast cost; defer polish if needed.

## Subtask F — Docs + tests close (~30 min)

1. Update `team-missile-intercept/game-core/ISSUES_2026-04-19.md`:
   - Issue **#7 (Deployment UI)**: `**State:**` → `Done Part 1 (M-TIER2-J Part 1, landed 2026-04-19). Operator can drag launchers in SETUP phase; AI Auto resets to config defaults (stub). Part 2 (buy vehicle, Issue #6) remains Open.`
   - Issue **#6 (Per-vehicle magazine / buy vehicle)**: no change (stays Half-implemented); add a one-line note that Part 1 landed as sibling work.
2. Append a new entry in "Tier execution order": `M-TIER2-J-Part1: deployment UI (drag-drop launcher placement, land-only validation, AI-Auto stub). Landed 2026-04-19.` Renumber following items if needed.
3. Update `team-missile-intercept/progress/STATUS.md`: short "M-TIER2-J Part 1 landed" entry with commit range (Subtasks A–E).
4. Update `team-missile-intercept/game-core/CHEN_BACKLOG.md`: mark item **#3 (Deployment Phase and Launcher Placement Support)** as landed Part 1 with commit hashes.
5. If you produced any new design note during this worker (e.g. placement API contract), commit it under `game-core/` with a clear name. Optional — only if it's useful.

**Commit:** `docs: W8 close — M-TIER2-J Part 1 landed, ISSUES #7 Done Part 1`

Push.

# Non-goals / guardrails

- **Do NOT implement "buy vehicle" / launcher roster add/remove.** Part 2 scope.
- **Do NOT tune `BLUE_LAUNCHER_POSITIONS` config values.** Operator positions during SETUP; config is the fallback / AI-Auto target.
- **Do NOT change Red AI, Blue AI, physics, spec values, balance, or threat behavior.**
- **Do NOT touch `requires_ground_impact`, `engagement_mode`, `Scenario.winner`.**
- **Do NOT change anything about cruise / HGV / ballistic — W7 just landed, it stays.**
- **Do NOT rework the FINISHED overlay.** It stays central; restart button stays.
- **Do NOT add terrain height-based validation.** Only `point_on_south_land` (2D) for now. Issue #18 is the future terrain contract.
- **Do NOT change WebSocket snapshot schema beyond adding the launcher `id` field additively.** Clients may assume existing fields.
- **Do NOT rename existing WS commands** (`start`, `pause`, `resume`, `reset`, `set_speed`). Add `place_launcher` + `ai_auto` as new.
- **Do NOT change Three.js camera or scene setup beyond the minimum for drag.** No new lighting, no new helpers.
- **Do NOT commit API keys.**
- **No `--no-verify`, no `git amend`, no force-push.**
- **English** in commits, code, comments, docs.

# Hard rules

- One commit per subtask. 6 subtasks → 6 commits.
- Each commit pushed immediately after local tests pass (and, for frontend subtasks, after Chen confirms the browser smoke looks right).
- Each commit ends with the project-convention Co-Authored-By line.
- If a STOP condition hits, stop the entire session and write the final summary.
- Budget: ~4–5 h. Chen is supervising; pause between subtasks if needed.

# Browser verification protocol

Frontend subtasks (C, D, E) need browser smoke. Pattern:
1. Apply changes locally.
2. Run `python team-missile-intercept/backend/server.py` (or ask Chen to start it).
3. Chen loads `http://127.0.0.1:5174/` in browser.
4. Chen runs the verification steps listed in the subtask.
5. If any step fails, iterate; if it works, commit + push.

**`preview_click` MCP tool was unreliable for the Pause button in W4.** Do not trust `preview_click` for UI interaction. Use programmatic `element.click()` via `preview_eval` if you need automation, but prefer Chen's real mouse/touch as the ground truth for frontend verification.

# Post-flight

1. `git status` — clean.
2. `git log --oneline -10` — 6 new commits above `934a3da`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity.
4. If stashed at preflight: `git stash pop`.
5. Re-run preflight test list. All must still pass. Plus the two new tests (`test_launcher_id.py`, `test_placement_api.py`).

# Deliverable — final summary (≤ 500 words)

1. **Commits landed** (6 hashes + one-line each).
2. **Subtask A (Launcher.id)** — field added? snapshot exposure? test assertion pattern?
3. **Subtask B (placement API)** — WS command details, validation rules, test coverage.
4. **Subtask C (pause rework)** — what was removed, what was repurposed, browser verification outcome.
5. **Subtask D (SETUP ribbon)** — ribbon structure, where it lives in the DOM, Start Match + AI Auto button wiring.
6. **Subtask E (drag-drop)** — raycaster approach, OrbitControls disable, cursor state, browser verification outcome.
7. **Subtask F (docs)** — which issues closed, tier entry added, any new design note.
8. **Test delta** — preflight → postflight, new tests' count.
9. **Anything blocking or surprising** — visual jank flagged for Sebastijan's future polish, any Three.js gotchas encountered, edge cases.
10. **Milestone J Part 2 prep** — what hooks are in place for "buy vehicle" (Issue #6) when that worker comes.
