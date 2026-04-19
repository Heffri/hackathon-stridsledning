# Worker 6 — Code-quality audit + safe fixes (overnight, ~4–5 h unsupervised)

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingy\Documents\github\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Chen runs this under bypass permissions overnight. The worker runs unsupervised; safety depends on the hard constraints below.

**Prerequisite:** Worker 5 (M-TIER2.5) must have landed. Confirm `git log --oneline -8` shows `0348640 docs: W5 engagement_mode design + ISSUES / STATUS / backlog update` at (or near) the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task. All prose in commits, comments, and docs uses game-dev framing ("threat", "intercept", "game", "arcade", "simulation") and avoids operational/tactical language.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). Push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `0348640` (Worker 5's docs commit, or newer).

Start by reading these files:

- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/progress/ROADMAP.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — **primary task tracker**, full read
- `team-missile-intercept/game-core/CHEN_BACKLOG.md`
- `team-missile-intercept/game-core/ENGAGEMENT_MODE_DESIGN.md` (W5 — new contract doc for Oskar)
- `team-missile-intercept/common-info/MODULARIZATION_SPEC.md`
- `team-missile-intercept/common-info/TEAM_OWNERSHIP_SPEC.md`
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`
- `team-missile-intercept/common-info/KNOWN_DOC_RUNTIME_DRIFT.md`
- `team-missile-intercept/backend/balance_baseline_2026-04-20.json` (latest W5 baseline)

Then scan all `team-missile-intercept/backend/sim/*.py` and `team-missile-intercept/backend/test_*.py` (directory listing first, then per file as needed).

# Why this worker exists

W3–W5 landed 14 commits across Tier 1 / 1.5 / 2 / 2.5 in rapid succession. Multiple surprises surfaced along the way:

- W5 found a pre-existing M-TIER2-PHASE silent-no-op bug (`test_balance_baseline.py::_run_full_match` constructed a fresh `Scenario()` which stayed in SETUP, making `step()` a no-op, producing silently-invalid data). That bug existed for days between W4 and W5 and was not caught by tests because the test produced output that *looked* plausible.
- W5 flipped `pac_3` default engagement mode from prox to htk, which shifted 20-match balance by +4 HGV / +14 drone leaks — a real balance drift emerging from an "infrastructure-only" change.
- W5 noted `cruise_sub` terminal profile never dives to z=0 (so with the new `requires_ground_impact=True` rule, cruise_sub can never leak damage — effectively disabled).
- W5 noted ballistic median CEP is 3300–3500 m post-flyover-fix vs a 1500 m leak disc, so ballistic rarely lands close enough to leak damage under Euler-0.05 s drift.

The pattern: **rapid feature work leaves silent-no-op bugs and semantic drift that existing tests don't catch.** Boyu (Red AI) and Oskar (Blue AI) are about to plug into the game-core's contract seams. Before they do, the operator wants an audit pass to find and fix latent bugs, document contracts clearly, and make the code easy for AI integration rather than a reverse-engineering exercise.

Operator's exact mandate (translated): "make the game foundation solid, write clean code, don't leave shit-code / instability / embedded problems that'll make later AI work hard."

# What this worker MUST NOT do (hard constraints)

- **No refactoring.** Do not extract helpers, rename variables, reorganize imports, split files, or merge modules.
- **No file moves or renames.**
- **No physics changes** (integrator, drag, PN gain, MAX_ACCEL, dt, gravity, spec `damage_*` / `radius_*` / `kill_radius` / `max_g` / `cruise_speed` / `cruise_alt`).
- **No balance changes** (spec values, `blue_budget`, `red_budget`, wave counts, spawn rates, site HP, leak radii).
- **No frontend changes** (`frontend/*.js`, `frontend/*.html`, `frontend/*.css`). Pause-overlay UX and 50× slider are explicitly deferred to a future Milestone J worker.
- **No changes to `Scenario.winner` rules** or `requires_ground_impact` gate logic.
- **No changes to Blue AI / Red AI logic** (`blue_ai.py`, `red_ai.py` — those are Oskar / Boyu territory).
- **No new tests just because coverage is low.** Only: fix existing tests that are broken or silently asserting nothing.
- **No `--no-verify`, no `git amend`, no force-push.**
- **No API keys committed.**

If you find something that looks refactor-worthy or balance-adjacent, **record it in the audit doc for a future worker under operator supervision**; do not touch it.

# What this worker IS allowed to do

1. **Fix latent bugs** that cause silent wrong behavior (e.g. no-op paths, unreachable code, broken test assertions, skipped code due to phase gating, swallowed exceptions). Must be provable by an existing test or new assertion that captures the bug without inventing new test surfaces.
2. **Add docstrings** to public contract boundaries (`launcher.fire`, `World.spawn_*`, `World.transition`, `Scenario.step`, `Interceptor.__init__`, `Threat.__init__`, damage resolution helpers, phase transition table).
3. **Audit and fix `__slots__` hygiene** on classes that use slots. W3/W4/W5 added fields (`glide_path_pitch`, `_base_alt`, `engagement_mode`, `phase`, etc.) — verify each slot-using class lists all its attributes in `__slots__`. A class with a missing slot entry silently falls back to `__dict__`, defeating the memory / typo-guard benefit.
4. **Audit event-string stability.** `hit_kind`, `type`, `phase_change`, `error`, `damage`, etc. strings in event dicts. W5 added `htk_direct` and `htk_miss`. Grep all consumers (backend + tests + frontend `main.js` / `hud.js` if necessary **read-only** to verify). If a consumer has an incomplete switch/if-chain that would silently drop a new string, either (a) fix the consumer with a minimal change if it's pure backend, or (b) document the gap in the audit doc for a Milestone J / frontend worker to address. Do not edit frontend files.
5. **Move magic numbers to config** — but ONLY when: (a) the literal appears in 2+ places in backend/sim or backend/test, (b) the literal has a clear semantic name, and (c) the move is a pure reference rename (no logic change). Skip if in doubt.
6. **Add contract-seam design docs** under `team-missile-intercept/game-core/` or `team-missile-intercept/common-info/` for cross-subsystem APIs that Boyu / Oskar / Milestone J worker will depend on. Example candidates: phase transition table + allowed commands per phase, `World.spawn_interceptor` / `spawn_threat` contracts, `Scenario.step` invariants, the Red AI `_pick_target` → `target_xy` pipeline that will become `target_site_id` later.
7. **Fix existing broken / silent-no-op tests.** W5 found `test_balance_baseline.py::_run_full_match`. Sweep for similar patterns: tests that construct `World()` or `Scenario()` directly without calling `transition(RUNNING)` or passing `auto_start=True`, making their `step()` calls silent no-ops.

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker6-preflight"` and pop at the end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -8` — confirm `0348640` or newer is at top. If older, STOP and report.
6. Run all existing tests as a baseline:
   - `python team-missile-intercept/backend/test_match_phase.py`
   - `python team-missile-intercept/backend/test_match_phase_integration.py`
   - `python team-missile-intercept/backend/test_engagement_mode.py`
   - `python team-missile-intercept/backend/test_threat_impact.py`
   - `python team-missile-intercept/backend/test_ballistic.py`
   - `python team-missile-intercept/backend/test_ballistic_cep.py`
   - `python team-missile-intercept/backend/test_hgv_impact.py`
   - `python team-missile-intercept/backend/test_damage_debug.py`
   - `python team-missile-intercept/backend/test_pn.py`
   - `python team-missile-intercept/backend/test_full_scenario.py`
   - Record each as baseline-pass or baseline-fail in a scratch note. `test_balance.py` and `test_balance_baseline.py` are long; skip them for preflight (run selectively in Phase 1/2 if you actually touch code they exercise).

If ANY baseline test fails before you make any changes, STOP and report — something is wrong with the starting state.

# Task structure — three phases, commits as described

## Phase 1 — Audit pass (~1.5 h, exactly one commit at the end)

Produce `team-missile-intercept/game-core/AUDIT_2026-04-19.md`, structured as:

```
# Code-Quality Audit — 2026-04-19

## Summary
- Worker: Worker 6 (overnight audit)
- Branch / starting HEAD: <branch> @ <hash>
- Files scanned: <count of .py files under backend/sim + backend/test_*.py>
- Findings total: <N>
  - Will fix this session (Phase 2): <K>
  - Deferred (design decision needed from operator): <D>
  - Deferred (other-team ownership, e.g. Oskar / Boyu / Sebastijan): <T>
  - Document-only (no fix): <M>

## Section A — Latent bugs (silent wrong behavior)
A1. <file:line> — <one-line description>
    Severity: critical / high / medium / low
    Effort: S / M / L
    Action: Fix in Phase 2 / Defer (design) / Defer (cross-team) / Document-only
    Notes: <why this is a bug, reproduction, how safe a fix is>
A2. ...

## Section B — Silent-no-op test audit (M-TIER2-PHASE sweep)
B1. <test file:function> — <pattern: constructs Scenario()/World() without phase transition>
    <Fix in Phase 2 | Already correct | Other>
B2. ...

## Section C — __slots__ hygiene
C1. <class> in <file> — missing slots: <list>
    Impact: <silent __dict__ fallback on these attributes — confirms by running `hasattr(instance, '__dict__')` on a fresh instance>
    Action: <Fix / Document>
C2. ...

## Section D — Contract-seam documentation gaps
D1. <function or class in file:line> — missing docstring
    Called by: <list of files>
    Pre-conditions / side-effects / invariants operator should document: <brief>
    Action: Add docstring in Phase 2
D2. ...

## Section E — Event string stability
E1. `hit_kind` strings currently emitted: <list of literals grepped across backend>
    Consumers (grepped): <list of files + line numbers that switch/if on hit_kind>
    Gap analysis: <any consumer that would silently drop a new string?>
    Action: <Fix backend consumer / Document for frontend worker / None>
E2. Similar audit for `type` field, `phase_change`, `error`, `damage`, `intercept` event strings.

## Section F — Magic numbers → config candidates
F1. <literal in file:line> — <semantic name> — used in <count> places
    Justification for move: <semantic clarity, dedup, future AI tune point>
    Action: Move in Phase 2 / Document only (insufficient reuse)

## Section G — Dead code candidates
G1. <symbol or block in file:line> — <evidence of unused: grep shows zero callers>
    Action: Remove in Phase 2 (only if confident; otherwise document)

## Section H — Cross-subsystem assumptions
Short design-note items — things Boyu (Red AI), Oskar (Blue AI), and Milestone J worker will need to know. Candidates:
- Phase transition table + allowed WS commands per phase
- World.spawn_interceptor / spawn_threat contract (preconditions, what fields are populated, which are caller-owned)
- Scenario.step invariants (what can safely be read / mutated during step vs between steps)
- Red AI _pick_target → Threat.waypoint pipeline (how `target_site_id` will slot in later)
- Launcher.fire contract (engagement_mode plumbing documented in ENGAGEMENT_MODE_DESIGN.md, verify alignment)

## Section I — Deferred for operator decision
Items surfaced during audit that require Chen's design judgment, not mechanical fixes. Each goes into ISSUES_2026-04-19.md by this worker in Phase 3.
I1. cruise_sub terminal dive — pops to 300 m, never descends to 0 m, so requires_ground_impact=True makes cruise_sub effectively non-threat. W5 flagged. Options: (a) drone-style terminal dive, (b) exempt cruise from ground-impact rule, (c) leave (cruise obsolete by AI era anyway). Operator decides.
I2. Ballistic CEP (3300–3500 m) vs site leak disc (1500 m) — ballistic rarely lands close enough to leak. Fix requires Route 3 RK4 integrator (ROADMAP). Document only; no fix this session.
I3. pac_3 default flip (prox → htk) balance shift (+4 HGV / +14 drone leaks per 20-match) — do we revert or accept? Record in audit.
I4 … I<n> as discovered.
```

**Important:** the audit doc must be **honest about uncertainty**. If a finding might not be a real bug, say so. The operator will use this doc tomorrow morning — clarity matters more than claim count.

**Commit:** `audit(game-core): code-quality + contract-seam audit 2026-04-19`

The commit message body should list Sections A–I headline counts (e.g. "A: 5 latent bugs found (2 fixable, 3 deferred); B: 2 silent-no-op tests found (both fixable); ..."). Push to origin.

## Phase 2 — Safe fixes (~2 h, one commit per class of fix)

Apply ONLY findings that the audit self-rated "Fix in Phase 2" AND that comply with the hard constraints above. For each class of fix, one commit:

- **`fix(game-core): latent bug fixes from audit`** — Section A "Fix in Phase 2" items. Per-finding diff should be surgical (≤ 10 lines typically). Commit body lists each finding ID, file:line, and a one-line "before → after" summary.
- **`test(game-core): repair silent-no-op tests (M-TIER2-PHASE sweep)`** — Section B items. Each repaired test must now exercise its code path for real (verified by adding a minimal assert that fails if the path is still no-op).
- **`fix(game-core): __slots__ hygiene on <class list>`** — Section C items. Verify with a test that tries to set an unknown attribute and confirms `AttributeError` is raised. Skip if the class doesn't use slots.
- **`docs(game-core): docstrings on contract seams`** — Section D items. Each docstring is short, imperative, and covers: purpose, pre-conditions, side effects, invariants the caller must respect. No prose > 10 lines per function.
- **`refactor(game-core): move duplicated literals to config`** — ONLY Section F items that passed the "2+ call sites + clear semantic name + pure reference rename" filter. If uncertain, skip — better to defer than corrupt.
- **`fix(game-core): remove dead code`** — ONLY Section G items with zero grep hits. If any doubt, skip.

**Every commit must pass ALL preflight tests** (from the list in "Pre-flight" step 6) before pushing. If a commit breaks a test, revert and re-enter the audit doc as "attempted fix regressed X test; deferred for supervised worker."

**Push each commit immediately after it lands.**

If a fix requires frontend coordination (Section E finding that a frontend consumer would silently drop a new string), **do not fix it** — document it for the Milestone J worker.

## Phase 3 — Wrap + doc close (~30 min, exactly one commit)

1. **Update `team-missile-intercept/game-core/ISSUES_2026-04-19.md`**: for each Section I deferred item, add a new numbered issue. Renumber downstream entries if needed. Each new issue:
   - State: Open
   - Category: <Bug / Design decision / Rule refinement>
   - Owner: <likely Chen>
   - Tier: <from context, conservative>
   - Description, current behavior, options, touchpoints
2. **Append new Tier item** under "Tier execution order": `M-TIER2.6-AUDIT: overnight code-quality audit + safe fixes. Landed 2026-04-19.` Renumber following items accordingly.
3. **Update `team-missile-intercept/progress/STATUS.md`** with a short "M-TIER2.6-AUDIT landed" note + a 2-line summary of Phase 2 fix classes.
4. **Update `team-missile-intercept/game-core/CHEN_BACKLOG.md`** if any backlog items map to audit findings — minimal edits.
5. **If you produced any contract-seam design doc** (Section H): commit it under `team-missile-intercept/game-core/` with a clear name like `CONTRACT_SEAMS.md` or `PHASE_TRANSITION_SPEC.md` — one doc for one seam, not mega-docs.

**Commit:** `docs(game-core): audit close — deferred items into ISSUES, contract seams documented`

Push to origin.

# STOP conditions (hard — if any triggers, stop the whole session cleanly)

- Any preflight test fails before any change lands → STOP, report starting state is broken.
- Any Phase 2 commit breaks a test that passed in preflight → revert that commit locally (don't push), move the finding to "deferred for supervised worker" in the audit doc, continue to next class.
- Two consecutive Phase 2 commits fail in a row → STOP, the audit might be wrong about safety; write final summary.
- A finding you thought was safe turns out to need design input mid-fix → revert, reclassify as deferred, continue.
- Context window or time budget running out → stop gracefully, push whatever did land, write the final summary.
- Unexpected framing / content-policy concerns in any file you read → STOP, report.

# Post-flight

1. `git status` — clean.
2. `git log --oneline -15` — confirm audit + Phase 2 commits + Phase 3 commit above `0348640`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity push.
4. If preflight stashed: `git stash pop`.
5. Re-run the full preflight test list. All must still pass.

# Deliverable — final summary (≤ 500 words, relayed back to Chen who will be asleep)

Write a structured report, not prose:

1. **Commits landed** — N hashes + one-line each. Expected shape: 1 audit + up to 6 Phase 2 + 1 Phase 3 = up to 8 commits.
2. **Audit doc path** — `team-missile-intercept/game-core/AUDIT_2026-04-19.md`.
3. **Findings totals** — A/B/C/D/E/F/G section counts, split into "fixed" vs "deferred."
4. **Fixes landed** — for each Phase 2 commit, the finding IDs it addressed.
5. **Deferred for operator** — list the Section I items added to ISSUES.md with their new issue numbers. Flag any that Chen should probably look at first thing tomorrow.
6. **New design docs** — any Section H docs produced, with paths.
7. **Preflight → postflight test delta** — confirm all preflight tests still pass post-work. If a test moved from pass to fail AND wasn't reverted, explain why and flag loud.
8. **Anything surprising** — things the audit surfaced that the operator (Chen) probably doesn't know, without editorializing. Just: "here's what I saw, here's where."
9. **Budget used** — rough hours spent per phase.

Be concise and structured — Chen wakes up, reads this, decides what to do. The audit doc itself has the long form; the summary is the entrypoint.
