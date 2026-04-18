# Red Team Ownership

This document defines what Boyu can safely own on the Red side today,
what the current Red AI actually does, and where the key HGV hook lives.

## Current Red AI Behavior

Live runtime file:
`team-missile-intercept/backend/sim/red_ai.py`

Current Red behavior is mostly scripted at spawn time:

1. Red builds five fixed demo waves.
2. Waves launch at fixed sim times:
   - `2.0 s`: 3 drones
   - `25.0 s`: 3 drones + 2 cruise missiles
   - `55.0 s`: 4 cruise missiles + 2 ballistic missiles
   - `95.0 s`: 1 HGV + 2 drones
   - `145.0 s`: 2 ballistic + 2 HGV + 3 drones + 2 cruise missiles
3. Every spawned threat picks a target from `sites.SOUTH_SITES` using
   weighted random choice:
   - `capital`: 4.0
   - `base`: 3.0
   - `air_base`: 2.0
   - `major_city`: 1.0
4. Drone and cruise spawns come from `RedLauncherFleet` round-robin
   positions when available.
5. Ballistic and HGV spawns use the strategic far-north strip across
   the top of the arena.
6. Strategic altitude floors are enforced at spawn:
   - ballistic: at least `20 km`
   - HGV: at least `30 km`
7. Cruise missiles receive `1-2` intermediate waypoints that create an
   S-shaped route before terminal approach.
8. Red logs wave launches, but it does not yet run per-tick adaptive
   threat control in `RedAI.step(...)`.

## The HGV Override Hook

The most important Red-side extension point is not inside `red_ai.py`.
It lives in:

`team-missile-intercept/backend/sim/entities.py`

Hook:

`Threat.override_maneuver(turn_direction, g_load)`

Current semantics:

- It stores one tick of commanded lateral acceleration.
- The command is consumed on the next `Threat.step(...)`.
- The command must be issued every tick to sustain a maneuver.
- Passing a zero vector clears the override.
- `g_load` is clamped to `self.spec.max_g`.
- For the current HGV spec in `types.py`, that clamp is `10 G`.
- Physics still stay game-core owned:
  - quadratic kinetic-energy bleed still applies
  - stall still occurs below the HGV stall speed
  - the Red AI is choosing commands, not replacing HGV physics

This is the cleanest current seam for Boyu to own.

## What Boyu Should Own

- Wave composition and timing strategy
- Red target selection policy
- Cruise route policy
- HGV control policy that drives `override_maneuver(...)`
- Threat-side behavior evaluation notes
- Red-side adapter design under `ai/interfaces/`

## What Should Stay Game-Core Owned

- Threat physics in `entities.py`
- Spawn, event, leak, and collision handling in `world.py`
- Site definitions in `sites.py`
- Threat spec tables and enums in `types.py`
- Strategic spawn geometry and launcher-position sources in `config.py`
- `Scenario.step()` order and `Scenario.snapshot()` keys

## Safe Replacements for the Red Side

Safe to replace behind the current contracts:

- `build_demo_waves()`
- `_TARGET_WEIGHTS`
- cruise waypoint generation policy
- per-tick HGV maneuver decisions
- target ranking logic
- threat logging content

Not safe to replace casually:

- `Threat.step(...)` kinematics
- `World.spawn_threat(...)`
- `sites.SOUTH_SITES` schema
- `Scenario.snapshot()` schema
- `RedLauncherFleet` data shape unless frontend integration changes too

## Recommended Future Files

- `ai/red-team/wave_policy.py`
- `ai/red-team/target_selection.py`
- `ai/red-team/hgv_controller.py`
- `ai/red-team/cruise_route_policy.py`
- `ai/red-team/evaluation_notes.md`

## First Red-Side Takeover Tasks

- Freeze the current five-wave behavior in a pure-policy document.
- Design a per-tick HGV controller that reads nearby interceptor state
  and outputs `turn_direction` plus `g_load`.
- Decide which Red behaviors stay spawn-time only and which become
  adaptive mid-flight policies.
- Keep HGV control logic outside `entities.py`; Red should command the
  hook, not own the integrator.
