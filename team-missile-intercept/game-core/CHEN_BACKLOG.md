# Chen Backlog

This backlog is for the base game package, not for AI policy depth or art polish. Each item is framed to keep the demo runnable while AI work evolves.

## 1. Align Speed Control With Runtime Capability

Priority: High — **Landed 2026-04-19 (M-TIER1-SPEED, extended
M-TIER2.7 to 50× for demo pacing)**. Slider + backend validation
both run 0.5 / 0.1× to 50.0×. HUD label reads the real active
multiplier. No spec change needed — backend was already
constant-`dt`, step-count-scaled before M-TIER1-SPEED.

## 2. Add Explicit Match Phase State

Priority: High — **Landed 2026-04-19 (M-TIER2-PHASE)**.

Commits: `6fcb15c` (enum + transitions), `57e093a` (phase-gated
sim advancement), `79ad5c3` (WebSocket start/pause/resume + acks),
`01a868e` (HUD phase chip + overlays), `b5f0060` (integration tests).

Why it belonged to Chen:

- game-core should own whether the sim is in setup, running, paused, or finished
- deployment UI and future AI placement both need a stable phase model

Delivered:

- `MatchPhase` enum + 6-edge legal-transition table in `sim/types.py`.
- `World.phase` + `World.transition(to)` returning True/False on legal/
  illegal attempts (no raise; server converts illegal to a WebSocket
  error frame).
- `Scenario.step` is phase-gated (no-op in SETUP / PAUSED / FINISHED)
  so `world.t` — and every sim-time timer reading against it — freezes
  automatically during pause / setup.
- `build_default_scenario(auto_start=True)` keeps headless tests on
  the old behaviour; server passes `auto_start=False` to land in SETUP.
- WebSocket protocol: `start`, `pause`, `resume`, `reset` commands with
  `{type: "phase_change", phase}` sender-only acks and
  `{type: "error", reason: "illegal_transition", from, to}` on refused
  transitions. Every snapshot carries a top-level `phase` field.
- Frontend: top-HUD phase chip, phase-specific centre-screen overlay
  (MATCH SETUP → Start / PAUSED → Resume / FINISHED → Restart), Pause
  button in the bottom bar gated to RUNNING. Restart = reset + start
  back-to-back so the demo stays one-click.

Test coverage: 19 unit tests (`test_match_phase.py`) + 5 integration
tests (`test_match_phase_integration.py`); `test_full_scenario`,
`test_pn`, `test_ballistic`, `test_threat_impact`, `test_damage_debug`,
`test_hgv_impact`, `test_ballistic_cep` all still pass.

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

Landed seams available to Oskar / Boyu:

- `Threat.override_maneuver(turn_dir, g_load)` — per-tick external
  lateral-accel command for HGV real-time control (Milestone I3).
- `Launcher.fire(t_now, engagement_mode=None)` →
  `World.spawn_interceptor(..., engagement_mode=...)` — per-shot
  engagement mode (`'prox'` | `'htk'`) threaded into the Interceptor
  instance and consumed by `world.resolve_damage`. Default preserves
  pre-M-TIER2.5 behaviour. Full contract in
  `./ENGAGEMENT_MODE_DESIGN.md` (landed M-TIER2.5, 2026-04-19).

Cross-subsystem reference doc (Phase + WS command table, spawn
contracts, event schema, snapshot additive rule, silent-no-op risk
register): `./CONTRACT_SEAMS.md` (landed M-TIER2.6-AUDIT,
2026-04-19). Audit findings driving the current seam state:
`./AUDIT_2026-04-19.md`.

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
