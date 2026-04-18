# AI Interfaces and Contracts

This folder is for shared AI-facing contracts. Oskar and Boyu should
use it as the place to define common inputs, outputs, and adapter
rules before any runtime extraction begins.

## Stable Seams Today

### Scenario seam

Live file:
`team-missile-intercept/backend/sim/scenarios.py`

Current responsibilities:

- constructs `World`, `RedAI`, and `BlueAI`
- owns tick order
- resolves winner state
- publishes the snapshot consumed by the frontend

Treat these as stable unless Chen explicitly approves an integration
change:

- `Scenario.step(dt)`
- `Scenario.winner`
- `Scenario.snapshot()`
- `build_default_scenario()`

### World seam

Live file:
`team-missile-intercept/backend/sim/world.py`

Current responsibilities:

- authoritative threat and interceptor stores
- spawn APIs
- collision and damage resolution
- leak detection and site HP updates
- event emission
- budget state
- world snapshot base payload

AI can read from `World`, but `World` remains game-core owned.

### Snapshot seam

`Scenario.snapshot()` currently publishes:

- base world payload:
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

These keys are integration contracts, not AI-private data.

### Entity seam

Live files:

- `team-missile-intercept/backend/sim/entities.py`
- `team-missile-intercept/backend/sim/types.py`

Stable AI-facing pieces:

- `Threat.override_maneuver(turn_direction, g_load)`
- `EntityState.to_dict()`
- `ThreatType`
- `InterceptorType`
- threat and interceptor spec tables

## Shared Ownership Rules

- Oskar and Boyu jointly own AI-facing contract docs in this folder.
- Chen owns approval for runtime contract changes.
- Emil must review changes that alter math meaning, not just AI policy.

## Safe First-Pass Work Here

- Define read-only world-view docs
- Define policy input and output shapes
- Describe adapter boundaries between `backend/sim/*_ai.py` and future
  `ai/*` modules
- Record snapshot dependencies and schema assumptions

## Unsafe First-Pass Work Here

- Inventing new runtime keys without frontend coordination
- Replacing `World` or `Scenario` ownership with AI-owned code
- Moving live runtime files into `ai/` before wrappers exist

## Recommended Future Files

- `ai/interfaces/world_view.md`
- `ai/interfaces/policy_contracts.md`
- `ai/interfaces/snapshot_contract.md`
- `ai/interfaces/change_rules.md`
