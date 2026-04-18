# Tasks for Oskar and Boyu

This is the recommended handoff package for the AI team after Session 0.
The goal is clean ownership without touching the live runtime shell
until adapters are ready.

## Recommended Split

- Oskar owns Blue-side decision logic.
- Boyu owns Red-side decision logic.
- Oskar and Boyu jointly own shared AI interfaces, policy contracts,
  and evaluation notes under `ai/interfaces/`.
- Chen remains required reviewer for any change that affects
  `Scenario`, `World`, snapshot shape, launcher/site/config schemas, or
  runtime wiring.

## Phase 1: Freeze the Current Behavior in AI Terms

1. Oskar: turn the current Blue rule ladder into a pure policy spec.
   Success means Blue behavior is describable without talking about UI
   or frontend concerns.
2. Boyu: turn the current Red wave, target, cruise-route, and HGV-hook
   behavior into a pure policy spec.
   Success means Red behavior is describable as policy choices plus
   game-core hooks.
3. Shared: agree on a minimal AI-facing world view.
   Success means both sides can describe what inputs they need without
   proposing a `World` rewrite.

## Phase 2: Define Stable Interfaces Before Extraction

1. Shared: write a contract for read-only AI inputs.
   Suggested shape:
   - current time
   - live threat states
   - live interceptor states
   - launcher states
   - site states
   - winner and budget context when relevant
2. Shared: write a contract for AI outputs.
   Suggested shape:
   - Blue: fire decision, selected launcher, selected target, log tag
   - Red spawn-time: wave schedule, target choice, waypoint plan
   - Red per-tick: HGV maneuver command
3. Shared with Chen: decide which snapshot fields are frontend-only and
   which should become explicit AI inputs.

## Phase 3: First Runtime Extraction Targets

1. Oskar: extract Blue choice logic first, not launcher mechanics.
2. Boyu: extract HGV controller first, not threat physics.
3. Shared: keep `backend/sim/blue_ai.py` and `backend/sim/red_ai.py`
   as thin adapters until the rest of the runtime can safely follow.

## Immediate Next Tasks by Owner

### Oskar

- Review `team-missile-intercept/backend/sim/blue_ai.py`
- Decide whether site-aware urgency should replace base-only urgency
- Document a cleaner Blue decision pipeline:
  - observe
  - rank
  - choose weapon layer
  - choose launcher
  - fire or wait

### Boyu

- Review `team-missile-intercept/backend/sim/red_ai.py`
- Review `team-missile-intercept/backend/sim/entities.py`
- Design the first HGV controller loop around
  `Threat.override_maneuver(...)`
- Decide whether target choice stays weighted random or becomes
  wave-aware and scenario-aware

### Shared

- Write interface notes under `ai/interfaces/`
- Keep a single list of game-core-owned contracts that AI must not
  silently break
- Agree on naming for future extracted AI modules before adding them

## Things the AI Team Should Not Own

- `World` tick order
- site HP and leak bookkeeping
- launcher reload semantics
- threat or interceptor physics
- snapshot schema changes without integration review

## Fastest Safe Win

The fastest clean takeover path is:

1. Boyu owns HGV decision commands through `override_maneuver(...)`
2. Oskar owns Blue engagement policy behind the existing launcher and
   world APIs
3. Shared contracts are documented before any runtime moves happen
