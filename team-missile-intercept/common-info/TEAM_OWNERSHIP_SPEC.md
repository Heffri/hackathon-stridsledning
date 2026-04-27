# Team Ownership Specification

## Purpose

This document defines the modular ownership boundaries used during
the hackathon. It is preserved as a historical record of who owned
what.

> Note: the per-module folders (`ai/`, `game-core/`, `maps/`,
> `models/`, `math-validation/`) were docs-first ownership packages
> during development. On this post-Finale branch the runtime sits in
> `backend/` + `frontend/` only; the docs-first packages have been
> removed. The references below describe what each owner was
> responsible for, not directories that exist in this branch.

Ownership here means:

- Primary responsibility for direction and acceptance
- Default first reviewer for changes in that domain
- Authority over domain boundaries, not unilateral authority over all cross-cutting changes

## Ownership Model

### Emil

Primary domain:

- `math-validation/`

Owns:

- Intercept math validation criteria
- Numerical correctness sign-off
- Guidance validation cases
- Reference trajectories, tolerance bands, and precision debt tracking
- Validation-side interpretation of changes to PN, intercept timing, and guidance accuracy

Does not solely own:

- Frontend visuals
- Scenario pacing
- AI target selection behavior

Required review when:

- A change alters physics assumptions, guidance equations, or numeric tolerances

### Oskar

Primary domain:

- `ai/` on the Blue side

Owns:

- Blue AI engagement logic
- Blue-side prioritization and assignment policy
- Blue-side evaluation heuristics
- Defender-side AI interface expectations

Joint responsibility with Boyu:

- Shared AI infrastructure
- AI module boundaries
- Evaluation of overall AI behavior

### Boyu

Primary domain:

- `ai/` on the Red side

Owns:

- Red AI behavior
- Threat-side control logic
- Adaptive attack behavior
- HGV and wave-control AI paths

Joint responsibility with Oskar:

- Shared AI infrastructure
- AI module boundaries
- Evaluation of overall AI behavior

### Sebastijan

Primary domains:

- `maps/`
- `models/`

Owns:

- Boreal Passage map presentation and terrain-facing assets
- Geographic references and visual map layout
- 3D structures, launcher visuals, landmark models, and scene asset quality
- Visual identity and asset packaging

Does not solely own:

- Runtime tuning of damage, budgets, or win conditions
- AI decision policy

Required review when:

- A map or model change affects visible geography, terrain interpretation, or model placement

### Chen

Primary domains:

- `game-core/`
- Runtime tuning and integration
- `common-info/` stewardship

Owns:

- Core game loop
- Scenario flow
- Entity lifecycle
- Launchers, sites, budget, HP, win conditions
- Runtime tuning and playable-state integration
- Final integration acceptance across modules
- Maintenance of restructuring documentation in `common-info/`

Does not solely own:

- AI behavior details that stay within AI boundaries
- Visual asset direction
- Math validation sign-off

Required review when:

- A change touches runtime contracts, snapshot shape, scenario flow, or integration behavior

## Module-to-Owner Map

| Target module | Primary owner | Secondary / required collaborators |
|---|---|---|
| `ai/` | Oskar + Boyu | Chen for interface changes; Emil if math assumptions change |
| `game-core/` | Chen | Oskar/Boyu for AI-facing contract changes; Sebastijan for map/model coupling |
| `maps/` | Sebastijan | Chen when geography changes affect gameplay or runtime assumptions |
| `models/` | Sebastijan | Chen when visual changes require runtime contract changes |
| `math-validation/` | Emil | Chen for runtime adoption; Oskar/Boyu when AI depends on the result |
| `common-info/` | Chen as steward | All domain owners for changes affecting their boundaries |
| `archive/` | Chen as steward | Relevant domain owner when archived material still informs a live module |

## Cross-Boundary Approval Rules

1. Physics or guidance changes require Emil review and Chen review.
2. Blue or Red AI behavior changes require Oskar or Boyu review respectively, plus Chen review if the runtime contract changes.
3. Shared AI infrastructure changes should be reviewed by both Oskar and Boyu.
4. Terrain, launcher geography, or map-source changes require Sebastijan review and Chen review when gameplay consequences exist.
5. Snapshot shape, server/frontend wiring, or core scenario flow changes require Chen review.
6. Structural or archive decisions in `common-info/` require the affected domain owner to sign off.

## Practical Working Split

To reduce overlap in later parallel sessions:

- Oskar should default to Blue AI and defender policy work.
- Boyu should default to Red AI and attacker policy work.
- Sebastijan should default to map, terrain, model, and visual-asset tasks.
- Emil should default to validation harnesses, math checks, and numeric acceptance criteria.
- Chen should default to game-loop integration, runtime tuning, and cross-module coordination.

## What Ownership Does Not Mean

- Ownership does not allow silent cross-domain changes.
- Ownership does not allow one person to redefine another module's contract without review.
- Ownership does not remove the need to keep the game runnable.

## Rules for Later Sessions

- Assign work by target module first, not by current file location.
- If one change touches two modules, call out the primary owner and the required reviewer before editing.
- Keep Oskar and Boyu split by Blue-side vs Red-side AI unless a task truly needs shared AI infrastructure.
- Treat Chen as integration sign-off for anything that could affect whether the demo still runs.
