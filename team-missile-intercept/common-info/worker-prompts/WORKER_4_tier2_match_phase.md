# Worker 4 — M-TIER2 Match Phase state machine

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingy\Documents\github\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Intended to run under bypass permissions for ~3–5 hours without further input.

**Prerequisite:** Worker 3 (M-TIER1.5 HGV + ballistic) must have landed before starting this worker. Confirm `git log --oneline -10` on `new-teamwork-split-V1` shows the four M-TIER1.5 commits above `ad1f64f`.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. Any entity names and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task. All prose in commits, comments, and docs should use game-dev framing ("match", "phase", "game", "arcade", "player") and avoid operational/tactical language.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). You will push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: the fourth M-TIER1.5 commit from Worker 3 (an ISSUES.md docs commit). Confirm via `git log --oneline -6` — you should see `docs(game-core): ISSUES update — M-TIER1.5` (or similar) at the top.

Start by reading these files:

- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/progress/ROADMAP.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — **primary task tracker**, read Issue #1 (restart button — already done) and Issue #7 (deployment UI — M-TIER2-J, this worker is the prerequisite) in full
- `team-missile-intercept/game-core/CHEN_BACKLOG.md` — backlog item #2 "Match Phase state" is the direct source of this task
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`
- `team-missile-intercept/common-info/KNOWN_DOC_RUNTIME_DRIFT.md`

Key runtime files you will touch or read:

- `team-missile-intercept/backend/server.py` — FastAPI + WebSocket entry point; sim loop (`dt = config.DT`, `n = max(1, int(sim_steps_per_stream * self.speed))`); `reset` command handler already exists (from Issue #1 / Worker 2 subtask 1)
- `team-missile-intercept/backend/sim/world.py` — `World` class, `step(dt)`, `self.t`
- `team-missile-intercept/backend/sim/red_ai.py` — wave-based spawner; call site in server.py passes `world.t` each tick
- `team-missile-intercept/backend/sim/scenarios.py` — `build_default_scenario()`, `Scenario.winner` (which already returns `'red'` / `'blue'` / `None`)
- `team-missile-intercept/backend/sim/types.py` — if adding phase enum as a type
- `team-missile-intercept/frontend/js/hud.js` — Restart button already exists (Issue #1). Add phase indicator + Start/Pause here
- `team-missile-intercept/frontend/js/main.js` — WebSocket message handlers on the client side
- `team-missile-intercept/frontend/index.html` — HUD HTML elements
- `team-missile-intercept/frontend/style.css` — phase overlay styles (may reuse the end-of-match overlay from Issue #1)

# Pre-flight

Before touching anything:

1. `git status` — must be clean. If dirty, `git stash push -m "worker4-preflight"` and continue; pop at the end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -6` — confirm Worker 3 commits are present. If the M-TIER1.5 commits are absent, STOP and report — this worker is blocked.

# Task

Six subtasks, executed in order. **One atomic commit per subtask.** Push each commit immediately after it lands.

## Subtask A — Phase enum + transitions (backend type, 30–45 min)

**Design target:** four phases with strict legal transitions.

Phases: `setup`, `running`, `paused`, `finished`.

Legal transitions:
- `setup → running` — via `start` command (player clicks "Start Match" in HUD, or headless test calls the start handler directly).
- `running → paused` — via `pause` command.
- `paused → running` — via `resume` command.
- `running → finished` — automatic, when `Scenario.winner(world)` returns a non-None winner.
- `paused → finished` — same automatic check, in case winner is decided while paused (unusual but possible).
- `finished → setup` — via `reset` command (reuse the existing reset handler from Issue #1; it now transitions to `setup` first, then auto-advances to `running` on next `start`).

Illegal transitions return an error to the client and do not mutate state.

**Implementation:**
1. Add `MatchPhase` as a string Enum (or `Literal["setup", "running", "paused", "finished"]` type alias — whichever is idiomatic for the existing codebase; check neighbouring files). Put it in `backend/sim/types.py` alongside other core types.
2. Add `phase: MatchPhase` attribute on `World` (default `"setup"` at construction).
3. Add a helper `World.transition(to: MatchPhase) -> bool` that enforces the legal-transition table. Return `True` on success, `False` on illegal. Do not raise — the server layer converts illegal to a WebSocket error response.
4. Add unit tests in `backend/test_match_phase.py`:
   - All legal transitions succeed.
   - All illegal transitions return False and leave phase unchanged.
   - Finished → setup is the only path out of finished (via reset).

**Commit:** `feat(game-core): MatchPhase enum + legal transition table (Issue #7 prereq)`

Push to origin.

## Subtask B — Phase-gated sim behaviour (backend, 45–75 min)

**Design target:** the sim loop respects the current phase.

**Changes to `backend/server.py`:**
- In the main sim-tick loop, before calling `world.step(dt)` and `red_ai.step(world.t, world)`:
  - If `world.phase == "setup"`: do not advance world.t, do not call red_ai.step, do not call world.step. The scene still renders (snapshots still flow to the client) but nothing evolves.
  - If `world.phase == "paused"`: same as `setup` — no advancement. The scene freezes mid-match.
  - If `world.phase == "running"`: normal tick (red_ai.step + world.step).
  - If `world.phase == "finished"`: do not advance. Scenario winner is captured; client shows restart overlay.
- After each `world.step`, evaluate `Scenario.winner(world)`. If non-None and phase is `running`, transition to `finished`. (This is existing behaviour elevated into the phase FSM.)

**Important invariant:** sim-time `world.t` only advances in `running` phase. All timers (reload, fuel, CD) that compare against `world.t` therefore automatically freeze during pause / setup. This is the correct behaviour — verify by reading the existing timer comparisons in `launcher.py` (`t_now` at lines ~45–48, 53–54, 59, 63–65) and `entities.py` (fuel at ~552–553). No changes needed there; the `world.t` freeze handles it.

**Backward-compat escape hatch:** for headless tests that don't know about phases (test_balance.py, test_threat_impact.py, etc.), the default should be that a freshly constructed `World` starts in `setup` but auto-advances to `running` on the first call to a convenience helper, e.g. `World.start_match()` or `build_default_scenario(auto_start=True)`. Pick an API that doesn't break existing tests. Grep for tests that construct `World()` directly and make sure they still pass.

**Verify:** extend `test_match_phase.py` with integration checks:
- Construct world in setup. Advance N sim ticks. `world.t == 0` and `len(world.threats) == 0`.
- Transition to running. Advance N sim ticks. `world.t > 0` and red AI has spawned at least some threats (pick a tick count that guarantees a spawn given default waves).
- Transition to paused mid-match. Advance N sim ticks. `world.t` did not advance; existing threats are still at their same positions.
- Transition back to running. Things resume.

**Commit:** `feat(game-core): phase-gated sim advancement + setup / pause freeze`

Push to origin.

## Subtask C — WebSocket phase commands (protocol, 30–45 min)

**Current state:** `server.py` already handles a `reset` command (from Issue #1 / Worker 2). Add three new commands in the same handler.

**New WebSocket commands (client → server):**
- `{ cmd: "start" }` — transitions `setup → running`. Error if current phase is not `setup`.
- `{ cmd: "pause" }` — transitions `running → paused`. Error if not running.
- `{ cmd: "resume" }` — transitions `paused → running`. Error if not paused.
- (`reset` — existing; extend to set the final phase explicitly to `setup` so the next `start` advances to running correctly.)

**Server → client:**
- Each snapshot broadcast now includes a `"phase"` field with the current phase string.
- On successful transition, send a `{ type: "phase_change", phase: "<new>" }` acknowledgment message (separate from the periodic snapshot).
- On illegal transition, send `{ type: "error", reason: "illegal_transition", from: "<p1>", to: "<p2>" }`.

**Verify:** add WebSocket-level tests if the project has a test harness for server.py (check `test_full_scenario.py`). If no WS test harness exists, document this in the commit message as "WS command tested manually by browser; unit tests cover phase state only." — do not build a new WS test harness for this alone.

**Commit:** `feat(server): WebSocket phase commands (start, pause, resume) — Issue #7 prereq`

Push to origin.

## Subtask D — Frontend HUD phase indicator + Start/Pause buttons (frontend, 60–90 min)

**Design target:**

1. **Phase indicator** — top-left HUD (or wherever the existing status chips live; check `frontend/index.html` and `hud.js`). Shows current phase as a labelled chip: "SETUP" / "RUNNING" / "PAUSED" / "FINISHED". Colour-coded if easy (grey / green / yellow / red or similar).
2. **Start Match button** — visible only when `phase === "setup"`. Centre-screen call-to-action (can reuse the end-of-match overlay style from Issue #1 — same overlay element, different content). Click sends `{ cmd: "start" }`. On `phase_change` ack, overlay hides.
3. **Pause button** — visible in `phase === "running"` state, probably in the main control panel next to the speed slider. Click sends `{ cmd: "pause" }`. Icon or label "Pause".
4. **Paused overlay** — visible when `phase === "paused"`. Centre-screen, dimmed scene behind (use CSS `opacity` or a semi-transparent backdrop), single "Resume" button sends `{ cmd: "resume" }`. Reuse the end-of-match overlay markup where possible.
5. **Finished overlay** — already exists from Issue #1. Verify it still shows and the Restart button still works. Restart now transitions through `finished → setup → running` in two steps (via the existing `reset` handler + the new auto-start flow). If you want, make Restart send `{ cmd: "reset" }` immediately followed by `{ cmd: "start" }` — but only if this works cleanly. Otherwise, extend the `reset` handler to accept an optional `then_start: true` flag, or just make `reset` auto-advance to `running` (i.e. `reset` puts world in setup then immediately into running — Chen will accept this since Milestone J Part 1 will later change reset semantics).

**CSS:** reuse existing overlay styles from `style.css`. If you must add CSS, keep it compact (≤ 50 lines new).

**Verify manually (since we don't have headless browser CI):**
- Open browser, see phase chip shows SETUP, Start overlay visible, no sim motion.
- Click Start. Chip flips to RUNNING, sim starts, threats spawn.
- Click Pause. Chip flips to PAUSED, sim freezes, Resume overlay visible. Existing threats stay on-screen at their last position.
- Click Resume. Chip flips to RUNNING, sim continues from where it left off.
- Wait for match to finish (or force it by advancing time). Chip flips to FINISHED, existing restart overlay shows.
- Click Restart. World resets, phase goes back to RUNNING (via setup then auto-start) OR back to SETUP waiting for Start — either is acceptable as long as it's functional.

**Commit:** `feat(frontend): HUD phase chip + Start/Pause/Resume overlays — Issue #7 prereq`

Push to origin.

## Subtask E — Integration test + full-scenario coverage (30–60 min)

Extend `backend/test_full_scenario.py` (or add `test_match_phase_integration.py`) with:
- Happy-path match lifecycle: setup → running → finished (let scenario.winner trigger).
- Pause mid-match: setup → running → paused → running → finished.
- Reset after finish: finished → setup → running.
- Illegal transition rejection: setup → paused (should fail), running → setup (should fail), etc.
- Verify that `world.t` freezes during pause via before/after comparison.

Run all existing tests to confirm nothing regressed:
- `python -m pytest backend/` (or whichever invocation the project uses — check `backend/requirements.txt` / `README.md`)
- If pytest is not configured, run each `test_*.py` directly with `python backend/test_<name>.py` and confirm they still print expected output.

**Commit:** `test(game-core): match phase integration + full-scenario coverage`

Push to origin.

## Subtask F — Docs: ISSUES.md + CHEN_BACKLOG.md + STATUS.md (20–30 min)

Update:
- **`ISSUES_2026-04-19.md`:** Issue #1 state stays `Done`; add a one-line note: "Restart flow extended via Match Phase state machine (M-TIER2-PHASE, landed 2026-04-19)." Issue #7 state: change the "Design target" bullet that mentions "setup phase in the Match Phase state machine" to reference "landed in M-TIER2-PHASE". Append a new entry in "Tier execution order" under Tier 2: `3. **M-TIER2-PHASE:** Match Phase state machine (setup / running / paused / finished). Landed 2026-04-19. Prerequisite for M-TIER2-J.` Renumber the existing Tier 2 item accordingly (Milestone J becomes item 4).
- **`CHEN_BACKLOG.md`:** mark item #2 "Match Phase state" as landed with the commit hashes.
- **`team-missile-intercept/progress/STATUS.md`:** add a short "Match Phase state machine landed (M-TIER2-PHASE)" entry in the current-milestone section with the commit range.

**Commit:** `docs: ISSUES + backlog + STATUS update — M-TIER2-PHASE`

Push to origin.

# Non-goals / guardrails

- **Do not implement Milestone J Part 1** (deployment UI / launcher placement). That is the next worker (Worker 5). The `setup` phase here is a shell — for now, setup phase just waits for `start`, no placement UI.
- **Do not touch the speed slider behaviour.** Pause does NOT equal speed 0 — speed is per-tick step count scaling, phase is whole-loop gating. They are independent. Do not try to unify them.
- **Do not change the existing `Scenario.winner` rules.** Worker 2 already landed the multi-site loss rule (Issue #9 interim). Leave it.
- **Do not touch `restart-overlay` WIP files on `knowledge-base-V0.5-archive`.** You are on `new-teamwork-split-V1`.
- **Do not add new Three.js geometry or new entity kinds.** All Three.js changes are HUD overlay HTML/CSS only.
- **Do not rename the existing `reset` WebSocket command.** Extend it if needed, but keep the name stable for frontend compat.
- **Do not break headless tests** (`test_balance.py`, `test_threat_impact.py`, `test_ballistic.py`, `test_full_scenario.py`, `test_pn.py`, `test_damage_debug.py`, plus anything Worker 3 added). They should all still pass.
- **No `--no-verify`, no `git amend`, no force-push.**
- **Never commit API keys.**
- **English only** in commits, code, comments, docs.

# Hard rules

- One commit per subtask. Six subtasks → six commits.
- Push each commit immediately after local tests pass.
- Each commit message ends with a Co-Authored-By line for the worker model, matching project convention.
- If any subtask hits a STOP condition, stop the session and write the final summary. Do not attempt subsequent subtasks.
- STOP conditions:
  - Any existing test suite fails after a subtask lands → revert the failing change, stop, report.
  - Browser manual verification shows major breakage (blank screen, WebSocket disconnect loop, phase indicator never updates) → stop, report.
  - Subtask touches > 3 frontend files with large diffs (> 200 lines each) → stop, report — scope is creeping.
- You have ~3–5 hours of budget. If you exceed that or context fills, stop gracefully.

# Post-flight

1. `git status` — must be clean.
2. `git log --oneline -10` — confirm 6 new commits sit above the Worker 3 tip.
3. `git push origin HEAD:new-teamwork-split-V1`.
4. If you stashed at pre-flight, `git stash pop`.

# Deliverable — final summary (≤ 400 words)

Write it back to the user (Chen) with this structure:

1. **Commits landed** (hashes + one-line each, expected 6).
2. **Phase state machine** — which four phases, which transitions, where the code lives.
3. **WebSocket protocol** — new `start` / `pause` / `resume` commands, the `phase_change` ack, the `error` response for illegal transitions.
4. **Frontend changes** — which files touched, which HUD elements added.
5. **Test coverage** — what the new tests verify, which existing tests still pass.
6. **Browser manual verification outcome** — did Start / Pause / Resume / Restart all work? Any visual weirdness?
7. **Anything blocking Milestone J Part 1** — the deployment UI needs the `setup` phase to be a real placement screen. What hooks did you leave / expose for that worker?
8. **Anything else surprising** — drift, hidden couplings, WebSocket reconnection behaviour on pause (does the client reconnect survive across phases?).
