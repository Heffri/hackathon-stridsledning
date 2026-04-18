# Restructure Sequence

## Purpose

This document defines the safest execution order for later restructuring sessions.

The governing rule is simple:

- Documentation modules first
- Integration second
- Archive and physical moves later
- Keep the current `backend/` and `frontend/` runnable throughout

## Sequence Overview

### Phase 0: Freeze the Blueprint

Before any structural work:

1. Use the documents in `common-info/` as the active blueprint.
2. Confirm the current runtime entry paths still work:
   - `backend/server.py`
   - `frontend/index.html`
   - `frontend/js/main.js`
3. Do not move or rename any active runtime file in this phase.

Exit condition:

- The blueprint is accepted as the working source of truth.

### Phase 1: Documentation Modules First

Goal:

- Make the target structure explicit before any code extraction

Allowed work:

- Module boundary documentation
- Ownership documentation
- Active dependency inventory
- Archive-readiness notes
- Mapping current files to target modules

Not allowed:

- Moving runtime entry points
- Renaming runtime files
- Physical archive moves

Why this comes first:

- It lets later sessions parallelize cleanly
- It avoids conflicting interpretations of where logic belongs

### Phase 2: Integration Second

Goal:

- Introduce safe seams while keeping the current game runnable

Allowed work:

- Thin wrappers
- Adapter functions
- Stable interfaces between current runtime shells and future module locations
- Import shims that preserve the existing entry points
- Small extraction of low-risk helpers only when the old runtime path keeps working

Preferred pattern:

1. Keep `backend/server.py` and `frontend/js/main.js` as stable composition roots.
2. Add or adapt internal module seams one domain at a time.
3. Preserve current snapshot contracts until a dedicated integration session changes them intentionally.

Not allowed yet:

- Broad directory moves
- Simultaneous multi-domain rewrites
- Any change that breaks the current launch path

### Phase 3: Controlled Extraction

Goal:

- Move internal logic toward the target modules only after integration seams exist

Recommended order:

1. `common-info/` remains authoritative
2. `maps/` and `math-validation/` extraction first if they can be isolated safely
3. `ai/` extraction after stable game-core interfaces exist
4. `models/` extraction after scene-facing contracts are stable
5. `game-core/` extraction only when the runtime shell can compose it without path breakage

Rules:

- Move one module family at a time
- Preserve old import paths until the new path is proven
- Re-run smoke verification after each extraction step

### Phase 4: Archive and Physical Moves Later

Goal:

- Only after live dependencies are cut over

Archive work is allowed only when:

- The active runtime no longer imports or reads from the material being archived
- The active documentation points to the new authoritative path
- The team can still locate the historical reference material

This is the phase where physical moves, renames, and archive placement can happen.

## Always-On Stability Gates

After every restructure session that goes beyond documentation:

1. The backend must still start from the current entry path.
2. The frontend must still load and render from the current entry path.
3. The WebSocket loop and snapshot consumption path must remain intact.
4. The game must still support the existing start, pause, reset, and speed controls.

If any gate fails:

- Stop the restructure work
- Fix the runtime path before continuing
- Do not stack more moves on top of a broken intermediate state

## Recommended Session Order

1. Blueprint and ownership confirmation
2. Dependency inventory and archive-readiness work
3. Integration seam creation
4. Low-risk extraction
5. Higher-risk extraction
6. Archive and cleanup

## Rules for Later Sessions

- Start with documentation or dependency mapping before code movement.
- Keep `backend/` and `frontend/` as the active runnable shells until the final move phase.
- Never combine archive work with first-pass integration work in the same session.
- If a proposed move would break the current run path, it is out of order.
