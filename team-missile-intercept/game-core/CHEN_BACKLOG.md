# Chen Backlog

This backlog is for the base game package, not for AI policy depth or art polish. Each item is framed to keep the demo runnable while AI work evolves.

## 1. Align Speed Control With Runtime Capability

Priority: High

Why it belongs to Chen:

- speed semantics are part of the base game loop
- `backend/server.py` already accepts up to `20.0x`
- `frontend/index.html` and `frontend/js/hud.js` currently expose only `0.5x` to `5.0x`

Target outcome:

- one clear speed contract across backend and frontend
- support for practical demo speeds such as `5x`, `10x`, and `20x`
- HUD always shows the real active speed multiplier

Likely touchpoints:

- `backend/server.py`
- `frontend/index.html`
- `frontend/js/hud.js`

## 2. Add Explicit Match Phase State

Priority: High

Why it belongs to Chen:

- game-core should own whether the sim is in setup, running, paused, or finished
- deployment UI and future AI placement both need a stable phase model

Target outcome:

- formal phase model such as `setup`, `running`, `paused`, `finished`
- snapshot publishes phase cleanly
- backend shell and frontend shell consume the same phase contract

Likely touchpoints:

- `backend/sim/scenarios.py`
- `backend/server.py`
- `frontend/js/main.js`
- `frontend/js/hud.js`

## 3. Deployment Phase And Launcher Placement Support

Priority: High

Why it belongs to Chen:

- launcher placement, land validation, and scenario start semantics are base game responsibilities
- AI placement can only plug in cleanly after the base placement contract exists

Target outcome:

- pre-match deployment phase before wave clock starts
- placement payload schema for Blue launchers
- validation path that keeps the runtime runnable even if AI placement is absent
- default fallback layout remains the current config-driven one

Likely touchpoints:

- `backend/sim/config.py`
- `backend/sim/launcher.py`
- `backend/sim/scenarios.py`
- `backend/server.py`
- frontend shell files that send placement data

## 4. Game-Loop Polish

Priority: Medium

Why it belongs to Chen:

- match pacing, reset behavior, and stop conditions are core loop concerns

Target outcome:

- cleaner reset semantics
- clearer handling of match end, restart, and safety-cap edge cases
- less logic hidden in shell files

Likely touchpoints:

- `backend/sim/scenarios.py`
- `backend/sim/world.py`
- `backend/server.py`

## 5. HUD And Base UI Improvements

Priority: Medium

Why it belongs to Chen:

- frontend owns presentation, but Chen owns the meaning of the HUD data
- several operator-facing states are really game-core states in disguise

Target outcome:

- phase-aware controls
- clearer site HP and budget summaries
- next-wave or setup-state visibility
- better end-of-match summary for demo use

Likely touchpoints:

- `frontend/index.html`
- `frontend/style.css`
- `frontend/js/hud.js`
- `backend/sim/scenarios.py`

## 6. Stabilize The AI Integration Surface

Priority: Medium

Why it belongs to Chen:

- AI specialists need a contract they can trust while base game work continues

Target outcome:

- document and preserve stable interfaces around `World`, `Scenario`, sites, launchers, and `Threat.override_maneuver`
- prefer additive snapshot changes over breaking renames
- preserve `build_default_scenario()` as the runnable composition entry until wrappers exist

Likely touchpoints:

- `backend/sim/scenarios.py`
- `backend/sim/world.py`
- `backend/sim/sites.py`
- `backend/sim/launcher.py`
- `backend/sim/entities.py`

## 7. Keep The Game Runnable During AI Evolution

Priority: High

Why it belongs to Chen:

- Chen is the integration owner
- AI work will move faster if the runtime shell stays stable

Target outcome:

- no breaking path changes in early passes
- adapters before refactors
- smoke checks around scenario build, snapshot shape, and frontend control flow

Recommended guardrails:

- keep `backend/server.py` and `frontend/js/main.js` thin
- preserve `Scenario.step()` and `Scenario.snapshot()` behavior while adding seams behind them
- treat snapshot keys as backward-compatible unless there is an explicit integration change
