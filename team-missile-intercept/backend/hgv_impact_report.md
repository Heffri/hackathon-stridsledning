# HGV Glide-Path Impact — Empirical Baseline

> Worker 3 — M-TIER1.5 Subtask B (Issue #10 subtask)
> Date: 2026-04-19
> Branch: `new-teamwork-split-V1`
> Run: `cd backend && python test_hgv_impact.py`

## Pre-change state

HGV default (Milestone I Task 3) was: fly horizontally at `cruise_alt
= 35_000 m` until the horizontal distance to target drops below 30 km
(`entities.py:266`). Only then does it aim its 3D velocity at the
waypoint and begin descending. Post-Issue-#2 leak detection requires
`z <= GROUND_Z + 50 m` for HGV kinds (`requires_ground_impact=True`).

Consequence: at Mach 17 (5831 m/s), descending 35 km vertically under
`max_g = 10` needs ~27 s × 5831 m/s ≈ 157 km of horizontal runway at
the steepest sustainable dive. With only 30 km available inside the
terminal-dive gate, the HGV flew over the target in-air and exited the
leak window without ground-impact. Worker 2's 1800 s balance run
measured **0 HGV ground-impacts / 0 HGV leaks** — effectively harmless.

## Change

Constant glide-path dive from spawn. At HGV spawn:

```python
self._glide_initial_dh = max(1.0, norm_h)
tan_pitch = spawn_z / self._glide_initial_dh
vel = horiz_unit * (cruise_speed / sqrt(1 + tan_pitch²))
vel[2] = -cruise_speed * tan_pitch / sqrt(1 + tan_pitch²)
```

For the Milestone I spawn strip (z = 30–40 km, dh = 150–240 km), pitch
is roughly 7–15° shallow dive.

Per-tick update, default path (`entities.py` cruise-branch):

```python
tan_pitch = _base_alt / _glide_initial_dh          # constant
glide_ratio = clamp(dh / _glide_initial_dh, 0, 1)
target_alt = _base_alt * glide_ratio                # linear descent
target_vz = -tan_pitch * cur_h_speed                # feed-forward
alt_accel = 0.3 * (target_alt - pos_z) + 0.5 * (target_vz - vel_z)
```

The spawn velocity already sits on the glide line, so the PD has
essentially no transient to reject and only corrects small integration
drift. `override_maneuver(dir, g)` still wins over the default command
on every tick it fires (existing one-tick plumbing at
`entities.py:298–306` left untouched).

Terminal-dive gate reduced from `dh < 30 km` to `dh < 3 km OR pos[2] <
2 km`. Sharp 3D aim snaps the final ~second of flight for a clean
impact; optional cosmetic add-on.

## Post-change result (30 trials, no Blue AI, 600 s cap per trial)

```
N spawned=30  ground-impacted=30  still-alive-at-600s=0  nan=0
ground-impact fraction=1.00
horizontal_miss (m): mean=207.5  median=200.2  p95=490.0  max=523.7
altitude oscillation (m, detrended, mid-flight p-p): mean=1004  max=1198

Per-target-site:
  Firewatch Station : n=13  median=201.8  max=502.3
  Main Base         : n=10  median=251.3  max=523.7
  Spear Point Base  : n= 7  median= 59.4  max=134.1

Verdict: impact=PASS (1.00 >= 0.80)   cep=PASS (median 200 m <= 2500)
         nan=PASS   osc=PASS (1198 m <= 5000)
Overall: PASS
```

Impact `z` is 5–50 m — the HGV genuinely reaches the ground before the
leak fires. Every leak fires at the intended site (no flyover
artifact like the ballistic case).

Spear Point (`n=7`, median 59 m) does better than the further sites
because the shallower glide path has less lateral drift. All three
sites well inside the 1500 m leak disc.

## Physics sanity

- No NaN in `pos` or `vel` across 30 trials.
- Altitude oscillation max 1198 m during mid-flight cruise (detrended
  from the monotonic descent). Well below the 5000 m stop threshold.
  The oscillation is the spring-damper natural period settling — starts
  visible because the spawn pitch isn't identical to the ideal steady-
  state pitch under drag, so the PD has a small transient.
- KE bleed, stall check, and `override_maneuver` paths untouched.

## Balance-test impact

See `backend/test_balance.py` output captured in the commit message —
HGV leak count is expected to flip from 0 (pre-change) to non-zero. A
full 20-match run was performed as part of the verification; the
headline HGV leak count is recorded in the Subtask B commit.

## Out of scope (Tier 3+ futures, per ISSUES_2026-04-19)

- `Threat.target_site_id` field (unified threat-control contract).
- `maneuver_schedule` pre-scripted jinks.
- Flyover fallback re-targeting.
- Boyu's real-time Red AI HGV controller using `override_maneuver`.

Those all stay Open under Issue #10 Tier 3. This subtask only closes
the "HGV default behaviour is straight-line in the air" problem.
