# Ballistic Targeting CEP — Empirical Baseline

> Worker 3 — M-TIER1.5 Subtask A (Issue #11 verify)
> Date: 2026-04-19
> Branch: `new-teamwork-split-V1`
> Run: `cd backend && python test_ballistic_cep.py`

## Claim (pre-work)

`entities.py:134–171` solves projectile motion at spawn so the ballistic
lands at its pre-selected target `(x, y)` at `z = 0`. `entities.py:337–354`
re-steers horizontal velocity toward the target each tick, capped at
`spec.max_g`. `red_ai._pick_target` returns `(x, y)` from a weighted
pick over `sites.SOUTH_SITES`.

## Operator observation (2026-04-19)

Ballistics visually appeared not to fly toward a Blue site.

## Method

`backend/test_ballistic_cep.py`. N = 30 trials. Each trial spawns one
ballistic via `RedAI._spawn_point(BALLISTIC, ...)` + `red_ai._pick_target(rng)`,
no Blue AI, runs to death or 600 s. Measures horizontal miss at death vs
the pre-selected target `(thr.waypoint[:2])`. Tags leak-event site so a
"flew over a different site en route" flyover artifact is visible
separately from true targeting error.

## Result — before fix

```
N spawned=30  ground-impacted=30  still-alive-at-600s=0
horizontal_miss (m): mean=13770.7  median=17360.1  p95=21604.0  max=22058.2
Verdict: FAIL  (median 17360 m vs threshold 1500 m)
```

All impacts landed consistently SHORT of the target (y_impact > y_target,
still north). The Main-Base and Firewatch-Station distant targets missed
by ~17–22 km; the closer Spear-Point target by ~3–5 km.

## Root cause

`entities.py:359` used **sea-level** `physics.drag_accel(vel, drag_k)` for
the ballistic update. HGV already uses altitude-scaled `drag_accel_at`.

The projectile-motion trajectory solver at `entities.py:134–171` assumes
**no drag** and applies a tiny 2 % aim-past to counter drag. This was
empirically tuned for the pre-Milestone-I setup where ballistic spawned
~30 km north of the base at 20 km altitude. In that regime sea-level
drag loss over a 30 km flight was small enough that 2 % compensated.

Post-Milestone-I the ballistic spawn strip was moved to the far-north
edge of the arena (Y 235–245 km, Z 30–40 km). Flight distances grew to
150–240 km. With sea-level drag applied for the entire 50–60 s cruise,
the ballistic lost ~2 km/s horizontal, landing 15–20 km short. The 2 %
aim-past covered only ~5 km, so the gap dominated.

## Fix

Single-line change, `entities.py:359`:

```python
# was:  accel + physics.drag_accel(vel, self.spec.drag_k)
# now:  accel + physics.drag_accel_at(vel, self.spec.drag_k, float(pos[2]))
```

This matches the HGV drag model. At the 30–40 km spawn altitude `rho` ≈
0.02, so cruise drag is near zero. Dense-air drag kicks in only during
terminal re-entry, and the existing 2 % aim-past remains sufficient for
that narrow band.

## Result — after fix

```
N spawned=30  ground-impacted=30  still-alive-at-600s=0  flyover-artifact=2
horizontal_miss all trials        (m): median= 1413.6  mean= 6177.2  p95=40623.5  max=73312.4
horizontal_miss (flyover-excluded n=28): median= 1409.1  mean= 1406.1  p95= 1487.5  max= 1498.3

Per-target-site:
  Firewatch Station : n= 9  median= 1383.2  max=  1476.4
  Main Base         : n=13  median= 1450.0  max= 73312.4  (2 flyovers counted)
  Spear Point Base  : n= 8  median= 1402.5  max=  1462.1

Verdict: PASS  (median 1413.6 m vs threshold 1500 m)
```

Tight spread on the 28 clean trials: 1313–1498 m. Impact `z` is 800–1200 m
— the ballistic leaks mid-air as the 1500 m horizontal disc fires before
ground-impact, exactly like the current game flow.

## Flyover artifact (not a targeting bug)

2 of 30 trials had Main-Base-targeted ballistics that were counted as
hitting Spear Point at `z` ≈ 13–15 km. Their horizontal miss vs the
Main Base target was 72–73 km (they were still cruising at altitude).

Cause: `world.py` leak detection uses a 1500 m horizontal disc per site,
and ballistic has `requires_ground_impact=False` (per Issue #2 — only
HGV currently requires ground impact). A ballistic cruising from Y=240
over a Main-Base target at Y=5 passes directly over Spear Point
(Y=76.5 km) and can clip its disc at altitude.

This is a game-rule artifact, not a targeting bug. A future unified
threat-control contract (Issue #10 Tier 3) could flip ballistic to
`requires_ground_impact=True` if operator intent is "no mid-air
airbursts", but that is out of scope for this verification task.

## Verdict

Ballistic targeting is working correctly. The `_pick_target` site is
being set as `thr.waypoint`, the trajectory solver aims at it, and
the ballistic lands within the leak disc of its intended site.

The operator's observation ("ballistics don't seem to fly toward Blue
sites") had two reinforcing causes:

1. The sea-level-drag bug made every ballistic land ~17 km north of
   its target, which visually looks like "flying past the sites toward
   the base region but never reaching it."
2. In the rare flyover case, a Main-Base-aimed shot ends its flight
   flashing over Spear Point 73 km short of the visible target.

Both now understood; (1) fixed, (2) documented as a separate rule
consideration.
