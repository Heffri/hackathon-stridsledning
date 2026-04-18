# AI Integration Points

This document maps the live seams between the current AI logic and the
current game-core runtime. It is the main reference for what is safe to
replace, what must stay stable, and where Oskar and Boyu can extend the
system without breaking the demo.

## Source of Truth

For AI integration details, code is the source of truth over older
status prose.

Two current examples that matter:

- `SITE_HP_START` is `100` in `backend/sim/config.py`
- HGV `g_load` clamping follows `THREAT_SPECS[ThreatType.HGV].max_g`,
  which is currently `10`

If documentation and code disagree, treat the code path as canonical
until Chen updates the docs.

## Live Ownership Boundary

### AI-owned in principle

- Blue engagement decision logic
- Red wave and target policy
- Red HGV maneuver policy
- AI evaluation notes
- AI-facing adapter design

### Game-core-owned in principle

- world tick order
- entity physics and movement integration
- launcher data models
- site data models
- snapshot schema
- runtime win and leak rules
- budget accounting

## Existing Blue AI Hooks

Live file:
`team-missile-intercept/backend/sim/blue_ai.py`

Current replaceable policy surfaces:

- `PRIMARY_RULES`
- `FALLBACK_RULES`
- saturation choice logic
- wait vs fire logic
- last-resort escalation logic
- target iteration and ranking strategy

Current non-replaceable runtime dependencies:

- `LauncherFleet`
- `World.spawn_interceptor(...)`
- `world.blue_budget`
- `INTERCEPTOR_SPECS`
- `Scenario.snapshot()` output shape

## Existing Red AI Hooks

Live file:
`team-missile-intercept/backend/sim/red_ai.py`

Current replaceable policy surfaces:

- `build_demo_waves()`
- target weighting
- cruise waypoint generation
- spawn-time threat composition
- future per-tick HGV control decisions

Current non-replaceable runtime dependencies:

- `World.spawn_threat(...)`
- `sites.SOUTH_SITES`
- `RedLauncherFleet`
- `Threat.step(...)`
- `Scenario.snapshot()` output shape

## HGV Override Hook

Live file:
`team-missile-intercept/backend/sim/entities.py`

API:

`Threat.override_maneuver(turn_direction, g_load)`

What this hook gives the AI team:

- a clean per-tick control input for HGV turning
- no need to rewrite HGV physics to experiment with smarter control
- a natural split where Boyu owns decisions and Chen keeps the
  integrator stable

What must remain stable about this hook:

- one-tick command semantics
- direction plus `g_load` input shape
- physics enforcement after the command is applied

What is safe to change around this hook:

- how Red decides when to maneuver
- how Red picks turn direction
- how Red schedules energy use across the flight

What is not safe to change casually:

- the HGV kinematic model in `Threat.step(...)`
- stall behavior
- drag and bleed behavior
- the meaning of `ThreatType.HGV` state fields

## Snapshot, World, and Scenario Seams

### Scenario seam

`Scenario.step(dt)` currently does this in order:

1. clear `world.events`
2. run `red.step(world.t, world)`
3. run `blue.step(world.t, world)`
4. run `world.step(dt)`
5. run `world.prune_dead()`

This ordering is important. AI decisions currently happen before the
physics tick on the current world state. Treat that ordering as stable
unless Chen deliberately changes the runtime contract.

### World seam

`World` owns:

- entity stores
- spawn functions
- collision and damage resolution
- leak detection
- event emission
- budget state
- snapshot base payload

AI can inspect `World`, but should not absorb `World` responsibilities
into AI-owned code.

### Snapshot seam

`Scenario.snapshot()` is the current frontend and integration contract.
It publishes:

- world payload:
  - `t`
  - `entities`
  - `explosions`
  - `events`
  - `stats`
- scenario payload:
  - `wave`
  - `total_waves`
  - `red_log`
  - `blue_log`
  - `ammo`
  - `launchers`
  - `red_launchers`
  - `sites`
  - `winner`
  - `max_sim_time`

Do not rename or silently reshape these keys during AI extraction.

## Safe to Replace vs Must Remain Stable

| Surface | Safe to replace now | Must remain stable now | Owner |
|---|---|---|---|
| Blue target and weapon choice | Yes | No | Oskar |
| Red wave composition and target choice | Yes | No | Boyu |
| Red HGV maneuver decisions | Yes | No | Boyu |
| `Threat.override_maneuver(...)` command caller | Yes | No | Boyu |
| `Scenario.snapshot()` keys | No | Yes | Chen |
| `World.step(...)` tick semantics | No | Yes | Chen |
| `launcher.py` schemas and reload semantics | No | Yes | Chen |
| `sites.py` target list schema | No | Yes | Chen |
| `types.py` enum names and core data shapes | No | Yes | Chen |
| threat and interceptor physics | No | Yes | Chen + Emil where math meaning changes |

## Recommended Integration Sequence

1. Document the current policy behavior first.
2. Define AI-facing read-only inputs under `ai/interfaces/`.
3. Extract policy decisions into new modules under `ai/`.
4. Keep `backend/sim/blue_ai.py` and `backend/sim/red_ai.py` as thin
   runtime adapters.
5. Only after adapters are stable should deeper file moves be discussed.

## Practical Rule of Thumb

If a change answers "which target should I attack?" or "which weapon
should I fire?", it is usually AI-owned.

If a change answers "what is the world state?", "how does physics
advance?", "how is a leak resolved?", or "what JSON does the frontend
expect?", it is usually game-core-owned.
