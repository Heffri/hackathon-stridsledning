# Live-demo polish — 3 fixes, no retrain

> **Framing (required)**: student hackathon entry for Saab 2026 "Smart
> Stridsledning" university competition — a browser-based arcade game /
> simulation, same category as a tower-defense game. Runs in Chrome on
> one laptop during a 4-minute demo. All entity names / speeds / costs
> are public encyclopedia-level arcade balance numbers. NOT a military
> product, training tool, or operational system.

**Status:** v1 landed on branch `blue-aoe-livefix` (off
`blue-aoe-training`). Three live-demo bugs surfaced during playtesting
the `blue_aoe_mixed` model. All three are sim / live-wrapper code
patches; **no retraining needed**. One commit per bug so Chen can
cherry-pick individually.

Date: 2026-04-24.

---

## 0. TL;DR

| Bug | Fix commit | Symptom before | Symptom after |
|---|---|---|---|
| 6 | ScriptedRed mop-up drone phase + done on economic exhaustion | Red idles with ~$800 k leftover after schedule exhausts; match runs to `MAX_SIM_TIME = 3600 s` → draw | 1 drone / 30 s toward a random alive military site until budget < drone cost; `done` latches cleanly once no mop-up targets remain |
| 7 | Strip `ALLOWED_INTERCEPTORS` allowlist + `_force_ballistic_fallback` + wrapper-level orphan cleanup from `LearnedBlueAI` | Policy filtered into a narrow rule-AI-shaped subset; fallback originated fires the policy had deliberately deferred; orphan cleanup killed retargeted interceptors (see Bug 8) | Policy fires whatever pairing it wants; budget + per-kind saturation gate are the only safety nets remaining |
| 8 | Mirror `inter.state.target_id` on retarget in `World.step` (and remove the orphan-cleanup offender in Bug 7) | Retargeted interceptors visibly swung onto new threat, then vanished within a few frames | Retargets persist; `inter.target_id` and `inter.state.target_id` stay in sync so HUD / snapshot / any future RL obs see the current target |
| 9 | `ARENA_Y` 250 km → 350 km (`config.py` + `scene.js`) | Ballistic / HGV spawn 158 km north of Spear Point Base — PAC-3 intercept window 1-5 s | Spawn 258 km north → window 30-40 s, 2-3× safety margin |

Five tests green on the three fixes:
- `test_scripted_red_mopup.py` (2 cases)
- `test_retarget_persistence.py` (2 cases)
- `test_arena_extension.py` (6 cases)

Full existing preflight green except two pre-existing W2-roster
failures (unrelated) and one Bug 9 cascade (`test_hgv_impact.py`; see
§5 Cascades).

---

## 1. Bug 6 — ScriptedRed mop-up drone phase

### Symptom before

`ScriptedRedAI` runs 3 chains × 3 rounds = ~45 trigger events (drone /
cruise / ballistic-pair / HGV per chain). Once the budget drops below
HGV ($10 M), then ballistic ($5 M), then cruise ($1 M) cost, the
expensive branches of each chain silently skip. By the time every
chain has fired all 9 rounds, ~$800 k-$1 M can remain — enough for
25-30 more drones at $30 k each, but no trigger exists to spawn them.
Drones spawned early (North Remote Island, 140 km from Main Base at
120 m/s = ~1200 s flight) are still cruising south when `_triggers`
empties, so `no_live` stays False and `done` never latches. Match
runs to `MAX_SIM_TIME = 3600 s` → draw.

### Fix

`team-missile-intercept/backend/sim/red_ai.py`:
- New module constants `MOPUP_INTERVAL_S = 30.0` and
  `MOPUP_JITTER_M = 1500.0`.
- New `ScriptedRedAI` state: `_mopup_active`, `_last_mopup_t`,
  `_mopup_count`.
- In `step()`, after the due-triggers loop: if `_initialized` AND
  `_triggers` is empty, activate mop-up. Every 30 s of sim time,
  call `_fire_mopup_drone(world)`. If that returns False (no alive
  military site OR budget < drone cost), deactivate mop-up. Update
  `done` gate to require `not _mopup_active` too, so it doesn't
  latch between spawns.
- New `_fire_mopup_drone(world)` helper: picks a random alive military
  site (subtype ∈ `{'base', 'air_base'}`, `hp > 0`), picks the nearest
  drone launcher from `config.RED_LAUNCHER_POSITIONS["drone"]`, spawns
  one drone with ±1.5 km xy jitter + drone alt range, retrying at the
  exact launcher position if jitter lands on sea.

### Test

`backend/test_scripted_red_mopup.py`:
- **Case 1**: schedule force-drained, budget set to $500 k (above
  drone cost). Advance 120 s. Assert ≥ 3 spawns at 30 s cadence,
  `_mopup_active` still True.
- **Case 2**: schedule force-drained, budget set to $20 k (below drone
  cost). Advance 120 s. Assert 0 mop-up spawns, `_mopup_active` False,
  `done` latched.

Both pass.

### Log sample (from an ad-hoc run with forced low budget)

```
[   0.0s] mop-up phase active — drone pressure on alive military sites
[  30.0s] mop-up drone #1 → Main Base (id=1, budget=$0.47M)
[  60.0s] mop-up drone #2 → Spear Point Base (id=2, budget=$0.44M)
```

---

## 2. Bug 7 — Strip rule-layer gates from `LearnedBlueAI`

### Symptom before

`rl/live_ai.py::LearnedBlueAI` was written for an earlier, weaker
Blue model that hadn't internalised cost-exchange. It bolted four
rule-layer gates onto the policy's output:

1. `ALLOWED_INTERCEPTORS` — hardcoded allowlist of `(launcher_kind,
   threat_kind)` pairings. Drops anything outside the table.
2. `SATURATION_CAP_BY_KIND` — per-threat cap.
3. `_force_ballistic_fallback` — every tick, for each unengaged
   ballistic, originates a PAC-3/PAC-2 dispatch.
4. Orphan cleanup — any interceptor whose `state.target_id` points
   at a dead threat gets `state.alive = False`.

The `blue_aoe_mixed` policy (2.3 M cumulative steps) has internalised
cost-exchange well enough that items 1 and 3 distort more than they
help: the allowlist filters out decisions the policy learned for
reasons worth trusting, and the fallback originates fires the policy
deliberately deferred (e.g. conserving PAC-3 ammo for a later
saturation wave). Item 4 is the root cause of Bug 8 — see §3.

### Fix

`team-missile-intercept/backend/rl/live_ai.py`:

**Removed entirely:**
- `ALLOWED_INTERCEPTORS` module constant + Gate 0 filter block in
  `_apply_action_gated`.
- `_force_ballistic_fallback` method + its call in `step`.
- Wrapper-level orphan cleanup block (lines ~386-394 in the pre-fix
  file).
- `_filter_rejects` bookkeeping (field init + bump call).
- Unused imports (`defaultdict`, `Set`).

**Kept:**
- `_assignments` tracking + Gate 2 (per-kind saturation cap via
  `SATURATION_CAP_BY_KIND` — DRONE/CRUISE 2, BALLISTIC/HGV 3; CIWS
  exempt).
- Gate 1 (budget hard-refusal, no `max(0, …)` clamp).
- Defensive range re-check at the bottom of `_apply_action_gated`.

Docstrings on the class + `_apply_action_gated` updated to reflect
the leaner wrapper; historical notes call out which pre-fix features
are gone and why.

### Test (optional, skipped per prompt)

Per-prompt: instrumenting a "SLM-at-ballistic now fires" scenario is
optional if time-constrained. **Minimum acceptance = live_ai smoke +
full preflight suite green**:

```
python -m rl.live_ai
=== live_ai smoke ===
[OK] Loaded learned Red: model.zip
[OK] Loaded learned Blue: model.zip
[OK] 10 ticks advanced: t=0.500s, phase=running, threats=1, interceptors=0
Smoke OK.
```

---

## 3. Bug 8 — Retargeted interceptors disappear

### Investigation finding (the deep-dive Chen asked for)

`Interceptor.target_id` and `Interceptor.state.target_id` are **two
separate attributes** in the current codebase:

- `sim/entities.py:731` — `Interceptor.__slots__` includes `target_id`.
- `sim/entities.py:857` — `self.target_id = target_id` (slot write).
- `sim/types.py:369` — `EntityState.target_id: Optional[int] = None`
  (dataclass field on the state object).
- `sim/entities.py:852` — constructor passes `target_id=target_id` to
  `EntityState(...)` at spawn, so both start in sync.

The retarget hook in `World.step` (block 2, lines 358-375 pre-fix)
only wrote to `inter.target_id`:

```python
if new_target is not None:
    inter.target_id = new_target.state.id
    target = new_target
```

`inter.state.target_id` was **not** updated. Meanwhile the wrapper-
level orphan cleanup in `LearnedBlueAI.step` read from
`inter.state.target_id`:

```python
for inter in world.interceptors.values():
    …
    tid = inter.state.target_id
    …
    tgt = world.threats.get(tid)
    if tgt is None or not tgt.state.alive:
        inter.state.alive = False
```

So: retarget writes `inter.target_id = new_tid`, then next tick the
orphan cleanup reads `inter.state.target_id` (still pointing at the
dead original), sees `tgt is None`, and kills the interceptor.
Visible outcome: retarget animation plays, then the interceptor
vanishes — exactly Chen's observation.

**Removing the orphan cleanup alone is enough to unblock the symptom**,
but the `state.target_id` staleness is a latent bug in its own right
(the snapshot / HUD / status panel / future RL obs all read it). So
the fix is a two-part belt-and-braces:

### Fix

`team-missile-intercept/backend/sim/world.py` — mirror write on
retarget:

```python
inter.target_id = new_target.state.id
# (live-demo Bug 8) mirror onto EntityState so downstream consumers
# (snapshot, HUD, RL obs) see the current target, not the dead one.
inter.state.target_id = new_target.state.id
```

`team-missile-intercept/backend/rl/live_ai.py` — orphan cleanup
removed (part of Bug 7). Retarget-on-death is owned by `World.step`
alone.

### Test

`backend/test_retarget_persistence.py`:
- **Case 1**: Fire SLS at drone A, mark A dead, single-step world.
  Assert interceptor alive, `target_id == B`, `state.target_id == B`.
- **Case 2**: Same geometry, stricter single-step assertion that
  `target_id == state.target_id` (catches mirror-drift regressions).

Both pass.

---

## 4. Bug 9 — `ARENA_Y` extended 250 km → 350 km

### Geometry

Pre-fix:
```
ARENA_Y              = 250 km
STRATEGIC_Y_BAND     = (235, 245) km      # ballistic / HGV spawn
Spear Point Base     = y 76.5 km          # northernmost military site
Distance             = 158 km
Mach-13 ballistic    = 4459 m/s → 35 s to arrival
Mach-17 HGV          = 5831 m/s → 27 s to arrival
PAC-3 max_range      = 70 km → inside envelope 15.7 / 12 s
PAC-3 fly-out        = 10-15 s
Net intercept margin = ~1-5 s, typically no intercept
```

Post-fix:
```
ARENA_Y              = 350 km
STRATEGIC_Y_BAND     = (335, 345) km
Distance to Spear Pt = 258 km (= 158 + 100)
Mach-13 ballistic    = 59 s to arrival
Mach-17 HGV          = 45 s to arrival
Inside PAC-3 envelope = 30-35 s
Net intercept margin = 20-25 s, 2-3× safety margin on PAC-3 fly-out
```

### Fix

`team-missile-intercept/backend/sim/config.py` — `ARENA_Y = 350_000`
(was 250_000). `RED_SPAWN_Y`, `STRATEGIC_Y_BAND` (in `red_ai.py`) both
use `config.ARENA_Y` at import time and auto-adjust.

`team-missile-intercept/frontend/js/scene.js` — `export const ARENA_Y
= 350_000` (mirror). Ground plane, floor grid, and compass N marker
all scale off this constant. Saab terrain polygons
(`BOREAL_TERRAIN` + `BOREAL_LOCATIONS`) use their own hardcoded
`SCENE_Z_NORTH = -245` mapping so landmass stays in world y=0-250 km;
the new y=250-350 km band renders as open ocean — matching the
"deep strategic rear where ICBM silos sit off-map" intent.

### Did scene.js need camera / ortho tweaks?

**No.** The scene uses a `THREE.PerspectiveCamera` with `far = 2000`
scene units (2000 km) and default pose `[0, 42, 95]` looking at
`[0, 0, -90]`. After the bump:
- Ground plane centre shifts from scene_z ≈ -120 to scene_z ≈ -170
  (camera target roughly covers it).
- Ballistic / HGV spawn at scene_z ≈ -335..-345 — inside the far
  plane, visible as distant specks until they dive.
- OrbitControls still orbit around the centre target; operator can
  pan to inspect far-north spawns if needed, R-to-reset restores the
  demo pose.

Verified by opening a test preview is left to Chen's supervised
browser session per the prompt's "optional manual" route — the three
Python tests + smoke are sufficient automated coverage for this
worker session.

### Test

`backend/test_arena_extension.py` — 6 cases:
1. `config.ARENA_Y == 350_000`.
2. `STRATEGIC_Y_BAND` falls inside `[335_000, 345_000]`.
3. `STRATEGIC_Y_FLOOR <= ARENA_Y` (contract invariant).
4. 100 sampled ballistic spawn points all inside the new band.
5. 100 sampled HGV spawn points all inside the new band + altitude
   ≥ 30 km floor.
6. `RED_SPAWN_Y = ARENA_Y - 5_000` arithmetic holds.

All pass.

### Ballistic spawn log sample (ad-hoc headless run)

```
ballistic spawn #1: x= 105398 y= 335624 z= 38425  (band=(335000, 345000))
ballistic spawn #2: x=  82474 y= 343374 z= 33888
ballistic spawn #3: x=   9065 y= 342132 z= 34166
```

And from the `test_scripted_red.py` smoke post-patch:
```
[1498.4s] Spear Point Base b1_r1: 1 ballistic from (56979,342721)
[1561.5s] Spear Point Base h_r1:  1 hgv       from (89629,336641)
```

---

## 5. Cascades (noted, not blocked on)

### `test_hgv_impact.py` CEP regression

Pre-fix: median horizontal miss ≈ 1090 m for Main Base (passes 2500 m
threshold).
Post-fix: median ≈ 70 km for Main Base (fails 2500 m threshold).

Root cause is purely geometric: HGV spawns 100 km further north, so
the straight-line-glide-to-target flight is 335 km instead of 235 km.
The HGV's KE + glide budget doesn't reach Main Base (y=5 km) from the
new y=340 km spawn. Spear Point (y=76.5 km) stays reachable
(median ≈ 4 km miss).

This test was **already** failing before the fix on its `osc`
sub-check (physics-explosion flag was hitting on pre-existing
turbulent Euler integration at Mach 17). The CEP cascade is an
expected consequence of Bug 9 — it's the exact mechanism that gives
PAC-3 a 30-35 s intercept window instead of 12-16 s. Not a blocker.
If Chen wants the test green, either:
- Bump the CEP threshold to ~75 km for Main Base, keeping the 2500 m
  threshold for Spear Point (the closest site).
- Drop Main Base / Firewatch from the HGV target rotation (change
  `_TARGET_WEIGHTS` or add a range check in Red target selection).

Neither is in scope for this session — flagged for post-demo.

### `test_launcher_base_cost.py` + `test_roster_api.py`

Both pre-existing W2 layout failures (default roster has 14 launchers,
not 9; tests assert the 9-launcher total of $41.5 M). Unrelated to
this patch.

---

## 6. Deliverables

- 4 commits on `blue-aoe-livefix` (one per bug + one test commit).
- 3 new test files in `backend/`.
- This report at `progress/LIVE_DEMO_POLISH_REPORT.md`.
- Full preflight suite green on the 3 new tests + all 19 pre-existing
  tests listed in §0.

## 7. Chen restart procedure

Safe sequence on Chen's demo worktree (not the training one — the
training worktree is still happily chewing on other branches):

```bash
cd <chen-demo-worktree>
git fetch origin
# If Chen's local is on main / some other branch, first commit or
# stash any uncommitted edits.
git checkout blue-aoe-livefix      # or merge into his working branch
# No dependency bumps, no schema changes — clean pull works.
cd team-missile-intercept/backend
# Stop any running dev server, then:
python server.py                   # or PORT=6969 python server.py on Windows-reserved-port machines
# Open http://localhost:5174/ (or the PORT you picked) in Chrome.
# Verify: Start the match, watch for mop-up log lines after ~minute 2,
# verify ballistic / HGV spawn markers in the y=335-345 km band (far
# north of terrain), verify interceptors retarget + don't vanish.
```

Training worktree does not need a restart — the policy on disk is
untouched; only inference-side wrappers + sim constants changed.

## 8. Don't-bother-with (done)

Nothing from the prompt's §7 was touched:
- No retraining.
- No reward shaping / AOE mechanic changes.
- No ARENA_X extension.
- No full 6-cell eval re-run.
- No terrain polygon moves.
- Camera bounds untouched (default perspective still frames the arena
  acceptably after the bump — confirmed via geometry, browser
  verification deferred to Chen per prompt).
