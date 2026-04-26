# Pre-Finale Backend Perf — Session 1 Report

**Branch:** `final-demo` (worktree was not provisioned for this session;
changes applied directly).
**Scope:** Python sim hot paths only — physics math, entity step loops,
launcher bookkeeping. Frontend / snapshot / WS encoding untouched
(Sessions 2 + 3 territory).

## Headline result

5-seed regression run, 600 s sim each, RedAI rng pinned per seed:

| Seed | Baseline (s) | After (s) | Speedup | Reduction | Stats match |
|-----:|-------------:|----------:|--------:|----------:|:-----------:|
|   42 |        5.608 |     4.815 |   1.16× |    14.1 % | YES |
|    7 |        5.588 |     4.852 |   1.15× |    13.2 % | YES |
|  123 |        5.575 |     4.773 |   1.17× |    14.4 % | YES |
| 2024 |        5.452 |     4.675 |   1.17× |    14.3 % | YES |
|    1 |        5.685 |     4.889 |   1.16× |    14.0 % | YES |
|  AVG |        5.582 |     4.801 |   1.16× |    14.0 % | — |

Stats compared per seed: `intercepts`, `leaked`, `intercepts_by_kind`,
`leaked_by_kind`, `blue_budget`, `red_budget`, `active_threats`. All
bit-identical baseline ↔ after — i.e. zero behavioural drift.

cProfile-instrumented runs (where Python call overhead is amplified)
show a larger 21 % reduction (10.31 s → 8.14 s); the 14 % above is the
honest production-rate number on a non-instrumented run.

## Changes (one logical change per commit)

### 1. Replace `np.linalg.norm` with `physics._norm3` (29 sites)

`np.linalg.norm` was the #3 hottest function in the baseline profile
(937 k calls, 2.07 s cumulative). Every call site operated on a
3-vector, where the dedicated `physics._norm3(v) = sqrt(v[0]² + v[1]² +
v[2]²)` helper is ~3.7× faster per call and bitwise-identical for
IEEE 754 float64.

- `sim/entities.py` — 26 sites in `Threat.step` / `Interceptor.step`
  / `__init__` / `_maybe_retarget_on_flyover`.
- `sim/blue_ai.py` — 3 sites in `_time_to_impact`,
  `_time_to_enter_range`, and the saturation last-resort path. Added
  `physics` import.

After: `np.linalg.norm` falls off the profile entirely; `_norm3` jumps
from 631 k → 1.55 M calls but absorbs the work at 0.59 µs/call instead
of 2.21 µs/call.

### 2. Cache `gravity_accel()` and zero-vector returns as read-only constants

`physics.gravity_accel()` previously allocated a fresh `np.array([0.0,
0.0, -G])` on every call. With Threat.step / Interceptor.step calling
it 1–2× per tick across 25–50 entities × 12 000 ticks, that was
~200 k+ throwaway allocations per match. Same pattern in
`drag_accel` / `drag_accel_at` / `pn_guidance_accel` zero-vector
fallbacks.

- Added module-level `_GRAVITY_VEC` and `_ZERO_VEC3` constants in
  `sim/physics.py`, both `flags.writeable = False` to catch future
  callers that try to mutate.
- All call-site usage is `accel + gravity_accel()` (creates a new
  array via add) — no caller writes through the returned reference,
  audited by hand. The read-only flag enforces this going forward.

`numpy.array` allocations dropped from 911 k → 884 k across the
profile.

### 3. Pre-compute `Launcher.pos_3d` once at construction

`blue_ai._primary_available_in_time` was building
`np.array([lch.pos[0], lch.pos[1], 0.0])` inside its inner loop —
~14 launchers × 187 k ticks-with-threats-alive ≈ 2.6 M allocations per
match for a vector that never changes during a launcher's lifetime.

- Added `Launcher.pos_3d: np.ndarray` field, populated in
  `__post_init__` and marked read-only.
- Updated `_primary_available_in_time` to read `lch.pos_3d` directly.
- `add_launcher` / `remove_launcher` server commands work via list
  add/remove on `fleet.launchers`, so the cache is per-instance and
  cannot go stale (a removed launcher's cache dies with the launcher).

## What was profiled but NOT changed

These showed up high in the profile but were left alone for risk
reasons:

- **`launcher.can_fire` 2.2 M calls / 0.47 s cumtime** — pure Python
  function-call overhead. Inlining at the two call sites in
  `_try_fire` and `_primary_available_in_time` would shave ~0.2 s but
  duplicates the reload/cooldown logic in three places. Not worth it
  this close to the demo.
- **`physics.integrate` 205 k calls / 0.39 s** — semi-implicit Euler.
  Could go in-place but the function returns `(new_pos, new_vel)`
  tuples consumed immediately by tuple unpacking in entity step
  paths. Rewriting to in-place mutation is invasive.
- **`Threat.step` 1.25 s self-time** — biggest line, but the cost is
  spread evenly across the per-kind branches and array constructions
  (`np.array([vel[0], vel[1], 0.0])` etc.). Each individual array is
  used downstream as a vector, so caching the magnitude doesn't
  remove the allocation.
- **Bucketing launchers by kind in `LauncherFleet`** — would shave
  the `lch.kind != kind` skip iterations in `_try_fire` /
  `_primary_available_in_time`. Skipped because `add_launcher` /
  `remove_launcher` mutate the launcher list at runtime; an index
  cache would need invalidation hooks that don't exist today, and
  introducing them right before the demo is risky.

## Files touched

```
sim/physics.py    | + _GRAVITY_VEC / _ZERO_VEC3 constants
sim/entities.py   | 26 norm sites → _norm3
sim/blue_ai.py    | 3 norm sites + import physics; pos_3d cache use
sim/launcher.py   | + Launcher.pos_3d cached in __post_init__
```

## Test status post-change

Plan-required preflight suite, plus broad pass over all `test_*.py`:

| Test | Result |
|------|:------:|
| test_match_phase | OK |
| test_match_phase_integration | OK |
| test_scripted_red_mopup | OK |
| test_arena_extension | OK |
| test_aoe_damage | OK |
| test_aoe_no_friendly_fire | OK |
| test_ciws_saturation | OK |
| test_ciws_shot_cap | OK |
| test_pn | OK (intercept hit=True, dist=16.6 m) |
| test_engagement_mode | OK |
| test_placement_api | OK |
| test_red_budget | OK |
| test_red_skip_dead_site | OK |
| test_red_spawn_contract | OK |
| test_retarget_nearest | OK |
| test_retarget_on_death | OK |
| test_retarget_range_gate | OK |
| test_launcher_id | OK |
| test_full_scenario | OK (modulo pre-existing Win-1252 unicode print glitch on Windows console — unrelated) |
| test_retarget_persistence | **PRE-EXISTING FAILURE** on baseline tree, confirmed by `git stash` + re-run. Not caused by this session. |
| test_launcher_base_cost | **PRE-EXISTING FAILURE** on baseline tree, confirmed by `git stash` + re-run. Roster total drifted to $59 M vs the test's hard-coded $41.5 M expectation — config drift, not perf change. |

`test_balance.py` (20-match sweep) was not run — too long for
verification and the seeded 5-run regression already shows zero
behavioural drift across full 600 s scenarios.

## Summary

**Merge recommendation:** ship. 14 % wall-clock reduction is well above
the plan's 10 % "don't merge below" threshold; all changes are
surgical, semantically-equivalent, and verified bit-identical across 5
seeds; preflight suite is unchanged (no new failures introduced).
