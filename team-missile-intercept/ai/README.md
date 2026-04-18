# AI Ownership Package

This folder is the documentation home for the AI team while the live
runtime still executes from `team-missile-intercept/backend/sim/`.
Ownership is logical first and physical later: Oskar and Boyu own AI
behavior direction, while Chen keeps ownership of game-core runtime
contracts and integration acceptance.

## Current Runtime Reality

- Live Blue AI runtime entry: `team-missile-intercept/backend/sim/blue_ai.py`
- Live Red AI runtime entry: `team-missile-intercept/backend/sim/red_ai.py`
- Stable scenario/runtime shell: `scenarios.py`, `world.py`, `entities.py`,
  `launcher.py`, `sites.py`, `types.py`, `config.py`
- This folder is the AI team's planning, contract, and future extraction
  home. It is not the live runtime import root yet.

## Recommended Ownership Split

| Area | Default owner | Notes |
|---|---|---|
| Blue-side decision logic | Oskar | Engagement priorities, saturation policy, wait vs fire policy, target ranking, launcher assignment heuristics |
| Red-side decision logic | Boyu | Wave composition, target selection, cruise route logic, HGV control policy |
| Shared AI interfaces and contracts | Oskar + Boyu | AI-facing world views, policy inputs/outputs, adapter plans, behavior evaluation notes |
| Runtime contracts and integration acceptance | Chen | `Scenario`, `World`, snapshot shape, launcher/site/config ownership |
| Math assumption changes | Emil + Chen | Physics, guidance, kill-radius meaning, acceptance thresholds |

## What Belongs Under `ai/`

- `blue-team/`: Blue-side behavior notes, extracted decision policy, Blue
  evaluation plans, future Blue-side modules
- `red-team/`: Red-side behavior notes, HGV-control plans, wave and target
  policy docs, future Red-side modules
- `interfaces/`: shared contracts, adapter plans, stable seam docs, and
  future AI-facing interface definitions
- `TASKS_FOR_OSKAR_AND_BOYU.md`: concrete handoff tasks
- `INTEGRATION_POINTS.md`: stable seams and replacement safety rules

## What Should Stay Game-Core Owned

These files remain game-core owned even when AI logic is gradually
extracted:

- `team-missile-intercept/backend/sim/scenarios.py`
- `team-missile-intercept/backend/sim/world.py`
- `team-missile-intercept/backend/sim/entities.py`
- `team-missile-intercept/backend/sim/launcher.py`
- `team-missile-intercept/backend/sim/sites.py`
- `team-missile-intercept/backend/sim/types.py`
- `team-missile-intercept/backend/sim/config.py`

Reason: they own tick order, state mutation, leak and budget rules,
entity physics, launcher and site data models, and the snapshot contract
consumed by the frontend.

## Safe Near-Term AI Work

- Document current behavior
- Define AI-facing interfaces under `ai/interfaces/`
- Add evaluation notes and scenario-specific behavior plans
- Prepare thin adapter modules that can later be called from
  `backend/sim/blue_ai.py` and `backend/sim/red_ai.py`
- Replace Blue and Red decision heuristics behind existing runtime
  contracts

## Unsafe Without Coordinated Integration

- Renaming snapshot keys
- Changing `Scenario.step()` order
- Moving or renaming files under `backend/sim/`
- Changing `World` leak, budget, damage, or event semantics without
  Chen review
- Rewriting threat or interceptor physics inside `entities.py` as part
  of an AI task

## Recommended Future Files

When runtime extraction starts, these are good first additions under
`ai/`:

- `ai/blue-team/engagement_policy.py`
- `ai/blue-team/target_priority.py`
- `ai/blue-team/evaluation_notes.md`
- `ai/red-team/wave_policy.py`
- `ai/red-team/target_selection.py`
- `ai/red-team/hgv_controller.py`
- `ai/red-team/cruise_route_policy.py`
- `ai/interfaces/world_view.md`
- `ai/interfaces/policy_contracts.md`
- `ai/interfaces/snapshot_contract.md`

## Read Next

- `team-missile-intercept/ai/blue-team/README.md`
- `team-missile-intercept/ai/red-team/README.md`
- `team-missile-intercept/ai/interfaces/README.md`
- `team-missile-intercept/ai/INTEGRATION_POINTS.md`
- `team-missile-intercept/ai/TASKS_FOR_OSKAR_AND_BOYU.md`
