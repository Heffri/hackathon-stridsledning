# Perf Notes — 2026-04-21 (W13 Phase 6)

Investigative pass in response to Chen's "demo feels sluggish" report.
Scope: measure where time is actually spent on both sides, apply **only
low-risk easy wins**, document hotspots that need dedicated sessions.

## TL;DR

- Backend is the faster side. A 600 s headless match costs ~25 s wall-
  clock on Chen's machine (~24× real-time); the 50× demo speed slider
  sits close to the cache-line edge but there is no runaway leak.
- Frontend over-rendered the HUD / launcher / status-panel DOM paths by
  3-4× because every RAF frame (60 Hz) re-ran the full snapshot
  rendering pipeline against the same snapshot (snapshots arrive at
  ~15 Hz). One easy fix landed in this session — gate the non-animating
  paths on snapshot-reference change. Selection-change invalidation
  wired so Magazine HUD latency stays inside 1 RAF tick.
- No easy Three.js / mesh-pool wins found without scope that exceeds
  the Phase 6 brief. Those are flagged below.

## Backend — cProfile top-N

`python backend/tools/perf_probe.py --sim-s 600 --top 20`
(git_head 3f9e64f, cap 600 s, Blue AI + default Red waves, headless.)

Total: 24.3 M function calls, 25.29 s wall-clock. 12,000 ticks at
`dt=0.05 s`. Per-tick cost ~2.1 ms.

Top 5 hotspots (by cumulative time):

| Rank | Function | ncalls | tottime | cumtime | % cum | Notes |
|---|---|---|---|---|---|---|
| 1 | `world.py:260(step)` | 12,000 | 1.02 s | 14.12 s | 55.8 % | Full world tick — entities + collisions + prune |
| 2 | `entities.py:449(step)` | 204,075 | 3.10 s | 11.07 s | 43.8 % | Per-entity-per-tick update (guidance, integrate, coast logic) |
| 3 | `blue_ai.py:288(step)` | 12,000 | 2.10 s | 10.82 s | 42.8 % | Saturation + per-threat assignment loop + firing decisions |
| 4 | `linalg.py:2383(norm)` | 1,648,617 | 4.52 s | 8.03 s | 31.7 % | np.linalg.norm called in every distance calc |
| 5 | `blue_ai.py:189(_primary_available_in_time)` | 201,827 | 0.53 s | 3.15 s | 12.5 % | Calls norm() several times per candidate |

Observations:
- `np.linalg.norm` is the single hottest leaf (4.5 s self time, 1.6 M
  calls). For `(3,)` arrays, `np.linalg.norm(v)` is ~5× slower than
  `(v[0]**2 + v[1]**2 + v[2]**2)**0.5`. Substitution is numerically
  identical — game-behaviour-safe — but the call sites are spread
  across `blue_ai.py`, `entities.py`, `physics.py`. Multi-file refactor;
  flagged for a dedicated session.
- `entities.py::Threat.step` plus `_maybe_retarget_on_flyover` together
  cost ~12.7 s. The flyover fallback (M-TIER3) runs every tick for
  every threat; most ticks it short-circuits cheaply. No low-hanging
  fruit in its current shape.
- `blue_ai.py::step` makes ~17 candidate-interceptor decisions per
  threat per tick. Each decision calls `_time_to_enter_range`,
  `_time_to_impact`, `_primary_available_in_time` — each of which does
  multiple `norm()` calls. A single engagement-time cache per
  (launcher, threat) per tick could reuse those results; also flagged.

**No low-risk backend fix applied this session.** All the candidates
touch 3+ files each. `backend/tools/perf_probe.py` is committed so
future workers can re-profile without re-writing the harness.

## Frontend — audit + easy-win applied

### Static audit

Read `main.js`, `scene.js`, `entities.js`, `launchers.js`,
`sites.js`, `hud.js`, `status_panel.js`. Patterns found:

1. **Snapshot-driven DOM paths run every RAF frame.** `animate()` in
   `main.js` called `updateHud`, `launchers.updateFromSnapshot`,
   `redLaunchers.updateFromSnapshot`, `updateStatusPanel` on every
   RAF tick (~60 Hz). Snapshots arrive at ~15 Hz. 3-4× redundant DOM
   rewrite per real snapshot. Worst offender: `renderLog` rebuilds the
   `#log-red` / `#log-blue` innerHTML each call.
2. **Repeated `document.getElementById` in hot path.** `hud.js` looks
   up ~20 distinct element ids per `updateHud` call. Modern browsers
   make this O(1) and cheap (~0.5-2 µs), but at 60 Hz × 20 ids =
   1,200 lookups/s. Non-trivial only if the frame budget is already
   tight; not the dominant cost.
3. **`EntityRegistry.updateFromSnapshot` allocates a fresh
   `aliveById` Map per call.** Per-RAF-tick GC churn.
4. **Trail geometry updated in-place.** `BufferAttribute.needsUpdate
   = true` on every tick per entity — unavoidable for the trail effect
   but means entities DO need per-frame updates.

### Animation-sensitive paths (MUST run per-frame)

- `EntityRegistry`: thrust flame sin-modulation, propeller spin
  (`+= 0.6 / frame`), seeker cone colour/opacity, trail geometry,
  explosion scale/opacity animation.
- `SiteRegistry`: `mesh.pulse(dt)` reads `performance.now()` and
  animates ring pulsing.

These cannot be gated on snapshot-change without visible stutter.

### Easy win applied (main.js)

Gated the following paths on snapshot-reference change:
- `launchers.updateFromSnapshot(latestSnap)`
- `redLaunchers.updateFromSnapshot(latestSnap)`
- `updateHud(latestSnap)` — the biggest saving; includes renderLog.
- `updateStatusPanel(latestSnap)`

Animation-sensitive registries (`EntityRegistry`, `SiteRegistry`)
remain per-RAF so visual animations stay smooth.

Cache invalidation hook: `onSelectionChange` clears
`_lastSnapProcessed` so the next RAF frame re-runs the gated paths
even without a new snapshot. Click-to-select Magazine HUD updates
within 1-2 RAF ticks (verified via `preview_eval`).

Expected saving: HUD / launcher / status-panel DOM work drops from
60 Hz to ~15 Hz — roughly 4× less work on those paths. Most visible
at 50× speed where the backend produces fuller snapshots (more
threats live, larger launcher states).

Zero visible behaviour change — Magazine, Site HP bars, budget,
launch banner, phase chip, setup ribbon all still update at
snapshot cadence (15 Hz), which matches the rate the data actually
arrives.

### Easy wins NOT applied (too many lines / too much risk)

- **Cache `getElementById` results in `hud.js`** — would touch ~20
  distinct call sites across 10+ functions; potential for stale refs
  if ever the DOM is re-created; low absolute savings. Skipped.
- **Reuse `aliveById` map in `EntityRegistry.updateFromSnapshot`** —
  would need to clear+reuse a module-level Map; edge cases with
  first-call. Skipped.
- **Dispose unused meshes on FINISHED reset** — `EntityRegistry` does
  dispose via `em.dispose(scene)` when an entity drops out of the
  snapshot, so this is already handled. Verified by reading
  `entities.js:697`.

## Candidate future investigations (dedicated session required)

Ordered by expected impact × risk:

1. **Backend `np.linalg.norm` → inline sqrt in hot loops.** Save 2-3 s
   per 600 s match (~10 % of sim time). Files: `blue_ai.py`,
   `entities.py`, `physics.py`. Must be paired with the existing
   regression baseline (compare medians on 20-match sweep) — any
   numerical drift would invalidate the "identical behaviour"
   claim, but an honest sqrt/dot substitution produces bitwise
   identical results on numpy's float64.
2. **Cache `_time_to_enter_range` / `_time_to_impact` per tick in
   `blue_ai.step`.** Each saturation pass recomputes these from
   scratch for every (launcher, threat) pair; a per-tick memoization
   Dict would cut repeat calls. Save ~3-5 s per 600 s match.
3. **Three.js BufferGeometry pooling for trails.** Entities each
   allocate a 60-point position buffer at construction; on disposal
   the buffer is released. At 50× speed with high threat throughput
   this is steady GC pressure. A pre-allocated pool of 40-50 trail
   buffers would cap the allocation rate. Moderate frontend refactor.
4. **Snapshot delta protocol** — server sends only `{entities_added,
   entities_removed, pos_updates}` instead of a full snapshot each
   tick. Large payload reduction + smaller JSON parse. Large backend
   change. Not justified until the single-laptop demo actually runs
   into WebSocket framing bottlenecks.
5. **Level-of-detail (LOD) on entity meshes** — drone / cruise have
   multi-piece bodies + props; at arena-far distances a single box
   mesh would suffice. Mostly a GPU saving; worth trying only if the
   GPU is the actual bottleneck, which we have no evidence of yet.

## Honest assessment

**Is the sluggishness real or machine-dependent?**

The static audit + profile points to real per-RAF overhead (HUD over-
render) plus backend `norm()` cost at high speed multipliers. The
`performance.memory.usedJSHeapSize` stays at 7-10 MB across a full
match at 50×; no heap leak. DOM node count stabilises at ~130 (light
fluctuation as log entries come/go). Frame budget is tight at 50× but
fine at 1× / 10× / 20× — the typical demo pace.

If Chen's laptop is integrated-graphics + battery-saver Chrome,
GPU-side render cost (shadow-free standard materials, ~60 active
entity meshes at peak, trail line segments) could push into the
frame budget. That is machine-dependent and not something this
investigation can fix without dedicated hardware testing.

The easy win landed this session should be visible at 50× speed
during the demo — fewer dropped RAF frames, smoother snapshot
cadence on the HUD side.

## Artifacts

- `backend/tools/perf_probe.py` — reusable cProfile harness.
  Committed in this session; future workers can re-profile with
  `python tools/perf_probe.py --sim-s 600 --top 20`.
- `team-missile-intercept/frontend/js/main.js` — animate() gating
  change (+10 lines).
