# Blue Team Ownership

This document defines what Oskar can safely own on the Blue side today,
what the current Blue AI actually does, and which surfaces still belong
to game-core.

## Current Blue AI Behavior

Live runtime file:
`team-missile-intercept/backend/sim/blue_ai.py`

Current behavior is rule-based and per-tick:

1. Blue ticks `LauncherFleet` reload and cooldown state.
2. Blue purges dead interceptor assignments so saturation accounting
   stays current.
3. Blue scans every live threat directly from `world.threats`.
4. CIWS is a separate point-defense layer:
   - any CIWS launcher fires at any threat inside its own envelope
   - CIWS ignores the main non-CIWS saturation cap
5. Non-CIWS saturation is capped at `3` simultaneous interceptors per
   threat.
6. Blue stops shooting if the expected in-flight prox damage already
   covers the threat's remaining HP.
7. Blue tries primary weapons first, in fixed preference order:
   - `drone`: `ciws`, then `rbs_70`
   - `cruise_sub`: `rbs_70`, then `iris_t_sls`, then `iris_t_slm`
   - `ballistic`: `pac_3`, then `pac_2`
   - `hgv`: `pac_3`, then `pac_2`
8. If no primary shot is ready now, Blue waits if any primary
   `(kind, launcher)` pair will become both ready and in range before
   impact minus a small margin.
9. If waiting is no longer acceptable, Blue tries fallback weapons:
   - `drone`: `iris_t_sls`
   - `ballistic`: `iris_t_slm`, then `iris_t_sls`
   - `hgv`: `iris_t_slm`, then `iris_t_sls`, then `rbs_70`, then `ciws`
10. If primary and fallback both fail and time-to-impact is under
    `15 s`, Blue enters a last-resort tier and fires any remaining
    weapon in cheap-to-expensive order.
11. Every shot launches from the actual firing launcher's position, not
    from the base center.
12. Every shot deducts `INTERCEPTOR_SPECS[kind].usd_cost` from
    `world.blue_budget`.

## Important Current Limitations

- Urgency still uses time-to-impact relative to `BLUE_BASE_POS`, not
  the nearest threatened site.
- Blue has omniscient threat awareness. No radar or sensor gating is
  applied yet.
- The ballistic fallback rule table includes `iris_t_slm`, but the
  current ordering makes SLM effectively hard to reach in practice.
- Blue decision logic is tightly coupled to runtime objects today:
  `World`, `LauncherFleet`, `config`, and spec tables are all read
  directly inside `blue_ai.py`.

## What Oskar Should Own

- Weapon preference strategy
- Threat prioritization policy
- Wait vs fire heuristics
- Saturation policy
- Last-resort escalation policy
- Future Blue-side adapter design under `ai/interfaces/`
- Blue-side evaluation notes and test scenarios

These are AI decisions, not game-core decisions.

## What Should Stay Game-Core Owned

- Launcher magazine, cooldown, reload, and position data models in
  `team-missile-intercept/backend/sim/launcher.py`
- Spawn path `World.spawn_interceptor(...)`
- Budget state and Red-win condition in `world.py` and `scenarios.py`
- Interceptor physics, PN guidance, burnout, and stall behavior in
  `entities.py` and `physics.py`
- Enums and spec tables in `types.py`
- Snapshot keys consumed by the frontend

## Safe Replacements for the Blue Side

Safe to replace behind the current contracts:

- `PRIMARY_RULES`
- `FALLBACK_RULES`
- target-order logic
- assignment heuristics
- urgency heuristics
- logging content

Not safe to replace casually:

- `LauncherFleet` schema
- `World.spawn_interceptor(...)`
- `Scenario.snapshot()` keys
- budget deduction semantics
- threat and interceptor data shapes in `types.py`

## Recommended Future Files

- `ai/blue-team/engagement_policy.py`
- `ai/blue-team/target_priority.py`
- `ai/blue-team/launcher_assignment.py`
- `ai/blue-team/decision_trace.md`
- `ai/blue-team/evaluation_notes.md`

## First Blue-Side Takeover Tasks

- Mirror the current rule ladder in a pure-policy document before
  changing behavior.
- Define a Blue-facing input contract that reads world state without
  mutating it.
- Separate "policy choice" from "fire this launcher now" so runtime
  wiring can stay stable while Blue logic evolves.
- Decide whether site-aware urgency replaces base-only urgency, and
  coordinate any new required data with Chen before changing contracts.
