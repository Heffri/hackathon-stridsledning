# Contract Seams (game-core)

## Purpose

Cross-subsystem reference for **what the current runtime guarantees**
at the boundaries between `game-core/` and its consumers:

- `ai/` — Boyu's Red AI, Oskar's Blue AI, future placement AI.
- `maps/` / `models/` — Sebastijan's terrain + visual assets.
- Future Milestone J deployment-UI worker.
- `math-validation/` — Emil's numeric acceptance harness.

This doc collects the "stuff an integrating worker should know
before wiring in" that is *not* already covered by
`RUNTIME_MAP.md` (architectural ownership), `ENGAGEMENT_MODE_DESIGN.md`
(single-feature spec), or the runtime source files themselves. It
is companion reading, not a replacement for either.

Landed 2026-04-19 by M-TIER2.6-AUDIT (Worker 6, overnight audit
pass) as a deliverable of the Phase-3 wrap.

## Reading order

1. This document — cross-subsystem contracts + conventions.
2. `RUNTIME_MAP.md` — file-level ownership + stable snapshot surface.
3. `ENGAGEMENT_MODE_DESIGN.md` — per-shot engagement mode plumbing.
4. `AUDIT_2026-04-19.md` — audit findings + deferred items.
5. `ISSUES_2026-04-19.md` — live issue list (includes I1-I5 added
   by this worker).
6. Runtime code under `backend/sim/` + `backend/server.py`.

## 1. Match Phase FSM

Four phases defined in `sim/types.py::MatchPhase`:

| Phase | Meaning | `Scenario.step` behaviour |
|---|---|---|
| `setup` | Pre-match, world frozen, used later by Milestone J deployment UI | no-op (events cleared, sim not advanced) |
| `running` | Live game; Red / Blue AI tick; physics advances | full tick |
| `paused` | Frozen mid-match; entities keep their poses on-screen | no-op |
| `finished` | Winner declared; only legal exit is reset (→ setup) | no-op |

Six legal transitions (`types.LEGAL_PHASE_TRANSITIONS`):

```
setup    → running
running  ↔ paused
running  → finished
paused   → finished
finished → setup
```

Self-transitions and any pair outside that set are illegal.
`World.transition(to)` returns `True`/`False` (no raise) so the
server converts illegal attempts into a WebSocket error frame
without aborting the tick. Self-transitions are treated as
illegal specifically so accidental double-clicks surface as an
error rather than being silently swallowed.

### Phase-gated vs ungated step surfaces

- `Scenario.step(dt)` **is** phase-gated. It no-ops in SETUP /
  PAUSED / FINISHED (events cleared first so stale frames don't
  rebroadcast; world.t does not advance).
- `World.step(dt)` **is not** phase-gated. Tests that construct a
  raw `World()` and drive it directly bypass the FSM.

If you move the phase gate down into `World.step`, update every
pattern-1 test (see `AUDIT_2026-04-19.md` §B2) to walk
SETUP → RUNNING first. Silent-no-op traps from M-TIER2-PHASE are
an exact precedent.

### Auto-finish on winner

Inside `Scenario.step`, if a RUNNING tick produces a non-None
`Scenario.winner`, the scenario auto-transitions RUNNING → FINISHED
at the end of that same tick. Server / client render the
end-of-match overlay off `snap.winner` on the next snapshot.

## 2. WebSocket command ↔ phase table

Per `backend/server.py::SimRunner.handle_command`:

| Cmd | Legal source phases | Transition | Response |
|---|---|---|---|
| `start`  | SETUP only                   | → RUNNING  | `{type: phase_change, phase: running}` |
| `pause`  | RUNNING only                 | → PAUSED   | `{type: phase_change, phase: paused}`  |
| `resume` | PAUSED only                  | → RUNNING  | `{type: phase_change, phase: running}` |
| `reset`  | any (rebuilds World in SETUP)| → SETUP    | `{type: phase_change, phase: setup}`   |
| `speed`  | any (phase-agnostic)         | (none)     | `None` (scalar-only) |

Illegal command for the current phase returns:

```json
{"type":"error","reason":"illegal_transition","from":"<p>","to":"<p>"}
```

Both responses are **sender-only** (not broadcast). Illegal-
transition errors are scoped to the client that sent the bad
command; `phase_change` acks are returned to the sender — the
HUD reflects phase via `snap.phase` on the next broadcast
snapshot, so observer clients get the phase transition
automatically via the normal 15 fps stream.

## 3. Snapshot shape (additive rule)

`Scenario.snapshot()` publishes the keys listed in
`RUNTIME_MAP.md` § "Stable Snapshot Surface". This set is
**backward-compatibility-protected**: per
`common-info/RUNTIME_STABILITY_RULES.md`, snapshot keys should
only be renamed via a dedicated integration change that updates
every consumer in the same commit.

Adding new keys is safe; renaming or removing keys is not.

Current shape (post-M-TIER2.5):

```
t                str  sim seconds since match start
entities         list of EntityState dicts
explosions       list of Explosion dicts
events           list of event dicts emitted this tick
stats            {spawned, intercepts, leaked, active_threats,
                  active_interceptors, blue_budget, blue_budget_max}
wave             next wave index (1-based in the HUD)
total_waves      total wave count
red_log          tail of RedAI log lines (list[str])
blue_log         tail of BlueAI log lines (list[str])
ammo             per-kind aggregated launcher status
launchers        per-launcher (kind, pos, ammo, reload) list
red_launchers    per-RedLauncher (kind, pos, team='red') list
sites            per-site {name, subtype, pos, hp, hp_max, leaks}
winner           'red' | 'blue' | 'draw' | null
max_sim_time     float, draw-safety cap
phase            'setup' | 'running' | 'paused' | 'finished'
running          legacy bool = (phase == 'running')
speed            client-side UI echo
```

## 4. Event dict schema

Emitted by `world.py`; accessed by tests + (narrowly) by the HUD.
`world.events` is cleared at the top of each `Scenario.step` call
and rebuilt during the tick.

| type | extra fields | emitted when |
|---|---|---|
| `threat_spawn`  | `id`, `kind` | `World.spawn_threat` |
| `launch`        | `id`, `kind`, `target` | `World.spawn_interceptor` |
| `timeout`       | `id` | interceptor age > `config.INTERCEPT_TIMEOUT` |
| `intercept`     | `interceptor`, `threat`, `pos`, `miss_distance`, `damage`, `hit_kind` | CPA hit lethal |
| `damage`        | `interceptor`, `threat`, `pos`, `miss_distance`, `damage`, `hit_kind`, `hp_remaining` | CPA hit non-lethal |
| `leak`          | `threat`, `kind`, `site`, `damage`, `site_hp` | site-disc crossing + ground epsilon |
| `ground_crash`  | `threat`/`interceptor`, `kind` | z ≤ `GROUND_Z` outside any site disc |

`hit_kind` is one of: `"direct"`, `"prox"`, `"miss"` (prox mode);
`"htk_direct"`, `"htk_miss"` (htk mode). See
`ENGAGEMENT_MODE_DESIGN.md`.

### Event-type additivity

Current consumers:

- `frontend/js/hud.js:88` reads `"launch"` only; everything else
  is silently dropped at the frontend today.
- `frontend/js/main.js:39` guards the snapshot parser against
  typed frames (`msg.type === 'string'`) but does not route
  them — `phase_change` and `error` typed frames are dropped.
- Backend tests read specific types they care about.

**No consumer performs an exhaustive switch on `type` or
`hit_kind`.** Adding a new event type / hit_kind string is safe
— it won't crash any consumer, though the frontend still needs
per-type wire-up before the event is visible to the user.

## 5. Typed WebSocket frames (phase_change / error)

`server.py` sends two non-snapshot frame shapes directly over the
socket (not via `world.events`):

- `{type: phase_change, phase: <new>}` — sender-only ack on a
  successful transition from the five phase commands above.
- `{type: error, reason: illegal_transition, from: <p>, to: <p>}`
  — sender-only response to a rejected transition.

The frontend's current main.js guard discards these via the
`msg.type === 'string'` early-return. Phase state stays correct
because the HUD reads `snap.phase` on every snapshot; but `error`
frames are silently swallowed (no toast). Milestone J / frontend
worker should wire explicit handlers before shipping the
deployment UI, so an illegal deploy attempt shows a human message.

## 6. Cross-subsystem runtime surfaces

### `World.spawn_threat` — Red AI / tests

See docstring in `sim/world.py`. Key contract points:

- Length-2 or length-3 `start_xy`. Length-3 overrides spec
  altitude.
- `target_xy` must be length-2 (z=0 is added internally).
- No post-spawn mutation of trajectory initial conditions —
  spawn a new Threat if target needs to change.
- HGV real-time control: use `Threat.override_maneuver(dir, g)`,
  one-tick persistence. Clamped to `spec.max_g`. Zero-vector
  clears.

### `World.spawn_interceptor` — Blue AI

See docstring in `sim/world.py`. Key contract points:

- `engagement_mode=None` → spec default; explicit must be in
  `spec.engagement_mode_choices` or the constructor raises.
- Legal pattern: `Launcher.fire(t_now, engagement_mode=M)` →
  pass the returned mode into `spawn_interceptor` so launch
  bookkeeping and Interceptor state agree.
- `initial_dir` — full 3-vector used only by CIWS; SAMs use
  only the horizontal component for boost lean.

### `Threat.override_maneuver(dir, g)` — Red AI HGV control

- Applies to HGV kind only in the current code; a no-op on other
  threat kinds is allowed by design (field exists on every
  Threat, only the HGV step path consumes it).
- **One-tick persistence.** Red AI must call every tick to
  maintain a sustained manoeuvre.
- `g` clamped to `[0, spec.max_g]`. Negative → 0.
- `dir` is a 3-vector; internally normalised. Zero-vector
  clears the override for this tick.

### `Scenario.winner` — read-only outcome resolver

Returns `'red' | 'blue' | 'draw' | None`. Order of checks:

1. `world.blue_budget <= 0` → `'red'`.
2. every `air_base` + `base` subtype site has `hp <= 0` → `'red'`
   (Issue #9 interim rule; capital short-circuit deferred to
   Tier 4 arena rescale).
3. `red.done` AND every threat dead → `'blue'`.
4. `world.t >= config.MAX_SIM_TIME` → `'draw'`.
5. None of the above → `None` (match ongoing).

Blue AI / Red AI can poll `Scenario.winner` for outcome feedback.
Do not short-circuit `winner` logic from AI code — `Scenario.step`
auto-transitions RUNNING → FINISHED once `winner` fires.

## 7. Runtime invariants worth preserving

- `world.t` is monotonically non-decreasing; only advances in
  RUNNING phase.
- `world.events` is empty immediately after `Scenario.step`
  returns in any non-RUNNING phase (cleared at the top, then
  early-return).
- After a full RUNNING tick, `world.threats` / `world.interceptors`
  contain only live entities (prune_dead called at end of
  Scenario.step).
- `sites.SOUTH_SITES` is a module-level singleton. `Scenario()`
  resets leaks + HP via `sites.reset_leaks()`; tests that
  construct raw `World()` are responsible for calling
  `sites.reset_leaks()` themselves (see
  `test_balance_baseline.py` for the canonical pattern).
- `config.BLUE_LAUNCHER_POSITIONS` is validated at module load
  against `terrain.point_on_south_land`. The assert path is
  intentional — any placement AI or deployment UI must re-run
  the same check before publishing a new layout, or
  construction will fail.
- `INTERCEPTOR_SPECS` / `THREAT_SPECS` are treated as read-only
  at runtime. Per-shot engagement variation lives in
  `engagement_mode` on the Interceptor instance, not on the
  spec. Future threat-side mode variation should follow the
  same pattern per `ENGAGEMENT_MODE_DESIGN.md` §Forward
  compatibility.

## 8. Planned contract evolutions

Active issues that will extend these seams. Not yet landed; track
in `ISSUES_2026-04-19.md`.

- **Issue 7** — `place_launcher` WS command. **Landed** 2026-04-20
  (M-TIER2-J Part 1). See §2 command table.
- **Issue 8** — `world.red_budget` + per-threat `usd_cost` deducted
  at spawn. **Landed** 2026-04-20 (M-TIER3-RED-BUDGET). Snapshot
  `stats.red_budget` / `red_budget_max` added; `Scenario.winner`
  extends the Blue-victory path to `(red.done OR red_budget<=0)
  AND no_threats_alive`.
- **Issue 10-12** — unified `target_site_id` + `maneuver_schedule`
  fields on `Threat`. **Landed** 2026-04-20 (M-TIER3-THREAT-CONTRACT).
  See §8.1 below for the publication-ready contract.

When any of these lands, update this doc in the same commit.

### 8.1 Unified Threat control contract (M-TIER3-THREAT-CONTRACT, 2026-04-20)

`Threat` instances expose three plumbed-through fields and one
in-place helper. Site identification is now by stable `Site.id: int`
(added to the `Site` dataclass, auto-assigned in insertion order by
`_build_south_sites`); `sites.find_site_by_id(id) -> Site | None` is
the canonical lookup.

**Spawn-time fields** (`world.spawn_threat(..., target_site_id=None,
maneuver_schedule=None)`):

| Field | Shape | Consumer | Notes |
|---|---|---|---|
| `_target_site_id` | `int \| None` | All kinds; mutable by flyover fallback | Stable id of the Site this threat was spawned against. `red_ai.RedAI.step` stamps this via `_pick_target_site(rng)`. |
| `_maneuver_schedule` | `List[(t_offset_s, turn_dir_3vec, g_load, duration_s)]` | Drone / cruise / ballistic only | Optional pre-scripted jinks. During an active window `[t_offset, t_offset + duration)`, default waypoint steering is REPLACED by `g_load × GRAVITY` along `turn_dir`. Clamped to `spec.max_g`. HGV ignores — uses `override_maneuver` instead. |
| `_final_target` | `np.ndarray[3]` (x, y, 0) | Flyover fallback | Immutable copy of original target for "have I passed it?" detection; `waypoint` mutates through intermediates for cruise / drone, or via fallback retargets. |

**Flyover fallback** (`Threat._maybe_retarget_on_flyover()`, called
at the top of `Threat.step` before per-kind branches):

- **When it fires:** horizontal velocity points AWAY from
  `_final_target` (dot product < 0), AND the threat is NOT in
  terminal phase. Terminal gates: HGV dh < 3 km or alt < 2 km;
  cruise dh < `_CRUISE_TERMINAL_DH = 5 km`; drone dh < 2 km.
- **What it does:** scans `SOUTH_SITES`, picks the nearest one
  AHEAD of the velocity vector (dot product > 0), updates
  `self.waypoint`, `self._final_target`, `self._target_site_id`.
- **No-op kinds:** BALLISTIC — arc is set at spawn and cannot be
  steered mid-flight; retargeting would mislead HUD without
  changing impact.
- **No-op geometry:** cruise / drone still chasing an intermediate
  waypoint (`_wp_queue` non-empty); no site AHEAD of the velocity.

**External-control entry point** (`Threat.override_maneuver(turn_dir, g)`):

Unchanged from Milestone I. Kind-gated by step-path structure:
only HGV reads `_override_accel` (the future stealth-cruise kind
in Issue #12 Tier 4 will add a second consumer). Setting the field
on drone / cruise / ballistic is a safe no-op; use
`maneuver_schedule` for those kinds instead.

**Future extensions (NOT in the 2026-04-20 contract):**

- Boyu's Red AI replaces the wave spawner — schedule entries chosen
  from a tactical policy, `override_maneuver` called per-tick for
  terminal evasion on HGV and stealth-cruise.
- Stealth-cruise threat kind (`ThreatType.STEALTH_CRUISE`, Issue #12
  Tier 4) adds an `allow_terminal_override` flag on `ThreatSpec` so
  `override_maneuver` is consumed during terminal phase.
- `maneuver_schedule` + `target_site_id` exposed in `snap['threats']`
  entries for HUD tooltips (not needed until Blue AI needs to read
  Red's commitment state).

## 9. Silent-no-op risk register

Patterns that have bitten us; keep an eye out:

- **SETUP never transitioned to RUNNING** → `Scenario.step` is
  a no-op. Caught in M-TIER2-PHASE by `test_balance_baseline`
  (W5 fix). Future: any new test that drives `Scenario.step`
  must call `build_default_scenario(auto_start=True)` or
  explicitly walk the transition.
- **Verdict-only tests that never raise** → a regression runner
  calling `python test_foo.py` returns exit 0 regardless. W6 fix
  added `sys.exit(1)` on FAIL to `test_hgv_impact` and
  `test_ballistic_cep`; any new numeric-threshold test should
  follow the same pattern.
- **Raw `World()` tests** — if phase-gating ever moves from
  `Scenario.step` into `World.step`, every test in
  `AUDIT_2026-04-19.md` §B2 Pattern 1 becomes a silent no-op
  overnight. The gate belongs at Scenario level; pushing it down
  is a breaking change.
- **Module-level singletons** — `sites.SOUTH_SITES`,
  `red_ai.RedLauncherFleet` indices. Stale state across runs is
  an observable bug class; tests that bypass `Scenario()` need
  explicit `sites.reset_leaks()` + fresh `RedAI()`.

## Change log

- **2026-04-19** — created by M-TIER2.6-AUDIT (Worker 6). Initial
  cross-subsystem reference; pairs with `AUDIT_2026-04-19.md`
  Section H findings.
