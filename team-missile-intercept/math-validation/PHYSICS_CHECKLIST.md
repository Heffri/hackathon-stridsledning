# Physics Checklist

This checklist is written for hand audit. For every line item, Emil should record:

- keep as-is
- acceptable approximation
- suspicious and needs team decision

## 1. Proportional Navigation And Closest Approach

### Core formulas to verify

```text
r      = target_pos - shooter_pos
v_rel  = target_vel - shooter_vel
r_hat  = r / |r|
omega  = (r x v_rel) / |r|^2
v_c    = -(r . v_rel) / |r|
a_cmd  = N * v_c * (omega x r_hat)

t*     = clamp(-((p1 - p2) . (v1 - v2)) / |v1 - v2|^2, 0, dt)
d_min  = |(p1 - p2) + (v1 - v2) * t*|
```

### Audit table

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/physics.py` | `pn_guidance_accel` | Active True PN command for interceptors | Re-derive the sign convention for `omega`, `v_c`, and `omega x r_hat`. Check that the output is lateral acceleration in `m/s^2`. | Acceleration points the wrong way in a simple crossing case, or the command grows when closure is negative. |
| `backend/sim/config.py` | `PN_GAIN = 4.0` | Global PN gain | Check whether `N = 4` is reasonable with the current target speeds and `DT = 0.05 s`. | Hand estimates say the chosen `N` should wildly overshoot or understeer, yet the code relies on it everywhere. |
| `backend/sim/config.py` | `DT = 0.05` | Physics timestep | Compare one-tick travel distances against direct-hit scales. | Relative travel per tick is much larger than the hit radii the game claims to care about. |
| `backend/sim/physics.py` | `closest_approach` | Closed-form CPA over one tick under constant velocity | Recompute `t*` and `d_min` for 1-2 simple examples. | CPA is very sensitive to tiny numeric changes, or endpoint distance and CPA distance disagree by an impossible amount. |
| `backend/sim/world.py` | CPA gate using `kr = max(inter.kill_radius, target.kill_radius)` | First gate before damage is resolved | Check whether using the max of the two kill radii makes sense physically and for gameplay. | A target can take damage at separations that are far outside the weapon's own stated lethal geometry. |

### Useful hand numbers

- In the current `test_pn.py` smoke test, minimum distance reaches about `16.6 m`.
- Against a ballistic target, PAC-3 speed `1700 m/s` plus ballistic speed `4459 m/s` gives about `6159 m/s` closure.
- At `DT = 0.05 s`, that is about `308 m` of relative travel in one tick.

That single comparison is one of the most important manual sanity checks in the whole package.

## 2. Drag, Acceleration, Speed Caps, And Integration

### Core formulas to verify

```text
a_drag = -drag_k * |v| * v
rho_ratio(h) = exp(-h / 8500), clamped to [1e-4, 1]
a_drag_at_alt = rho_ratio(h) * a_drag
|a_cmd| <= max_g * g
|v| <= max_speed
v_new = v + a * dt
p_new = p + v_new * dt
```

### Audit table

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/physics.py` | `drag_accel` | Sea-level quadratic drag | Check units and order of magnitude using `|a| = drag_k * v^2`. | Drag is too weak to matter at high speed, or so strong that it dominates gravity and guidance instantly. |
| `backend/sim/physics.py` | `air_density_ratio` | Exponential atmosphere model | Compute `exp(-h / 8500)` at representative altitudes such as `5 km`, `20 km`, and `30 km`. | High-altitude drag stays unrealistically large, or the floor `1e-4` creates non-physical behavior at altitude. |
| `backend/sim/physics.py` | `drag_accel_at` | Altitude-scaled drag for post-burnout interceptor glide | Compare coast drag at low altitude and high altitude. | A missile coasting at `25 km` loses speed almost as fast as one at `2 km`. |
| `backend/sim/physics.py` | `cap_accel` and `cap_speed` | Stability and performance caps | Check whether the caps are physically plausible or merely numerical safety rails. | Active motion spends most of its time clipped by caps instead of governed by the underlying model. |
| `backend/sim/physics.py` | `integrate` | Semi-implicit Euler step | Check whether Euler at `0.05 s` is acceptable for the current closure rates. | Hand estimates suggest integration error is on the same scale as the kill geometry. |
| `backend/sim/entities.py` | `fuel_elapsed`, `powered`, `_COAST_G_FRACTION = 0.5`, `_STALL_SPEED = 200.0` | Interceptor boost/coast/stall assumptions | Check whether burnout, half-authority coast, and 200 m/s stall are internally consistent. | Burnout causes an abrupt non-physical flight mode change that dominates outcomes more than guidance quality does. |

### Useful hand numbers

- For PAC-3 and PAC-2, `drag_k = 4e-6`. At `1700 m/s`, sea-level drag magnitude is about `4e-6 * 1700^2 = 11.6 m/s^2`.
- At `25 km`, `exp(-25000 / 8500) ~= 0.053`, so the same coast drag drops to roughly `0.6 m/s^2`.
- In the current code, powered flight uses sea-level drag and coast flight uses altitude-scaled drag. Emil should explicitly decide whether that split is intended.

## 3. HGV Maneuver And Energy-Bleed Assumptions

### Core formulas to verify

```text
speed_loss = 120 * (commanded_accel / max_accel)^2 * dt
stall if |v| < 500 m/s
turn_radius R = v^2 / a
```

### Audit table

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/types.py` | `THREAT_SPECS[ThreatType.HGV]` | Active HGV speed, `max_g`, drag, HP | Check whether the active values match current team intent. | Runtime values differ materially from `WEAPON_SPECS.md` and nobody can say which set is canonical. |
| `backend/sim/entities.py` | `_HGV_BLEED_RATE = 120.0` | Speed loss at max command load | Compare to the documented expectation in `WEAPON_SPECS.md` of about `50 m/s/s`. | The runtime HGV sheds speed much faster than the team thinks, or the docs understate how punitive turns are. |
| `backend/sim/entities.py` | `_HGV_STALL_SPEED = 500.0` | Glide failure threshold | Check whether lift collapse near `500 m/s` is a defensible simplification. | The HGV is allowed to glide unrealistically slowly, or crashes far too early for its altitude. |
| `backend/sim/entities.py` | `override_maneuver` | One-tick external control hook | Check whether "call every tick to sustain a turn" is the intended contract. | Red AI assumptions later on silently rely on persistent control even though the hook is one-tick only. |
| `backend/sim/entities.py` | `terminal_dive` at `dh < 30000` | HGV switches from glide-like hold to direct terminal aim | Check whether `30 km` is the right threshold for current arena scale and speeds. | The HGV dives so early that it stops acting like a glide vehicle, or so late that it skips over the site. |

### Useful hand numbers

- With current runtime values, HGV speed is `5831 m/s` and `max_g` is `10`.
- At `10 G`, turn radius is about `5831^2 / (10 * 9.81) ~= 346,000 m`, or about `346 km`.
- That is larger than the current arena width, so any claim that the HGV can freely zig-zag inside the map should be treated skeptically unless speed bleed is doing the real work.
- Under the current bleed formula, `5 seconds` at max command costs about `600 m/s`.

### Important doc mismatch to flag

- Runtime currently says `10 G` and `120 m/s/s` bleed.
- Reference docs and comments elsewhere describe `8 G` and about `50 m/s/s`.

Emil should not sign off on HGV realism until that discrepancy is resolved.

## 4. Ballistic And HGV Spawn Geometry Assumptions

### Audit table

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/red_ai.py` | `STRATEGIC_Y_BAND = (ARENA_Y - 15000, ARENA_Y - 5000)` | Ballistic and HGV spawn in the far-north strip | Compute actual start distance to each active site. | Strategic threats spawn so close that Blue has too much time, or so far that fuel and closure assumptions stop matching the design story. |
| `backend/sim/red_ai.py` | `BALLISTIC_MIN_Z = 20000`, `HGV_MIN_Z = 30000` | Re-entry/glide altitude floors | Check whether these floors match the intended cinematic and physical story. | A strategic threat can appear unreasonably low, or the floor is so high that the arena ceases to matter. |
| `backend/sim/red_ai.py` | `DRONE_ALT_RANGE`, `CRUISE_ALT_RANGE`, `BALLISTIC_ALT_RANGE`, `HGV_ALT_RANGE` | Per-kind altitude bands | Check whether the bands are distinct and intentional. | The visual tiers look separated in docs but overlap in active runtime. |
| `backend/sim/entities.py` | Ballistic launch-angle solve in `Threat.__init__` | Solve angle below horizontal so a ballistic threat lands near target under gravity | Re-derive the quadratic in `tan(theta)` and the chosen shallow-angle root. | The algebra does not match projectile motion, or the 2 percent overshoot hides a deeper math bug. |
| `backend/sim/entities.py` | `dh_aim = dh * 1.02` | Ballistic range compensation for drag | Convert the 2 percent overshoot into actual kilometers. | The compensation is large enough to dominate the actual ballistic solve. |
| `backend/sim/sites.py` | `_saab_to_world` and `_in_arena` | Active target-site geometry after map transform | Check whether only 3 in-arena sites is acceptable for balance and narrative. | Key Saab sites are silently removed and the balance model still assumes they exist. |

### Useful hand numbers

- The strategic spawn strip is `235 km` to `245 km` north in world Y.
- Main Base sits at `y = 5 km`, so a far-north strategic threat is usually more than `230 km` away in Y before any X offset is counted.
- A `2 percent` overshoot means:
  - `200 km` horizontal distance becomes an aim distance of `204 km`
  - `240 km` horizontal distance becomes an aim distance of `244.8 km`

## 5. Direct-Hit, Proximity-Damage, And Leak Model

### Audit table

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/types.py` | `INTERCEPTOR_SPECS[*].damage_direct`, `damage_prox`, `radius_direct`, `radius_prox`, `kill_radius` | Active weapon lethality tables | Compare runtime values with `WEAPON_SPECS.md`. | Runtime values are much larger than the documented spec and nobody knows whether that is debt or intent. |
| `backend/sim/world.py` | Direct vs proximity damage block | Convert CPA into damage | Check the exact piecewise logic. | The world applies linear falloff even though the spec says quadratic, and this was not a conscious decision with sign-off. |
| `backend/sim/world.py` | `damage = max(1, round(damage_prox * fall))` | Minimum non-zero prox damage once inside prox radius | Check whether guaranteed chip damage is intended. | A fringe contact always deals at least 1 damage even when the continuous formula would be tiny. |
| `backend/sim/config.py` | `BASE_HIT_RADIUS = 1500.0` | Horizontal defended-area radius for leak detection | Check whether `1500 m` matches the intended "site hit" definition. | A threat counts as a leak even when it only overflies the site at altitude and never actually impacts it. |
| `backend/sim/world.py` | Leak detection before ground impact | Site hit if horizontal range is within `BASE_HIT_RADIUS` at any altitude | Decide whether overflight should count as a leak or whether only terminal impact should. | High-altitude overflight is being counted as a successful strike when Emil would classify it as a miss. |
| `backend/sim/config.py` | `SITE_LEAK_DAMAGE` | Threat-type damage to site HP | Check whether damage increments match intended stakes per leak. | Site HP falls too slowly or too quickly relative to the threat mix and the claimed game loop. |

### Current runtime-vs-reference examples worth checking first

- PAC-3 in runtime:
  - `radius_direct = 60 m`
  - `damage_prox = 25`
  - `radius_prox = 80 m`
- PAC-3 in `WEAPON_SPECS.md`:
  - `radius_direct = 0.3 m`
  - `damage_prox = 5`
  - very small proximity effect by design

- CIWS in runtime:
  - `radius_prox = 80 m`
- CIWS in `WEAPON_SPECS.md`:
  - `radius_prox = 5 m`

Emil should explicitly decide whether these are accepted gameplay compensations for current PN precision or unacceptable drift from the stated weapon story.

## 6. Smoke-Test Baselines To Keep In Mind

- `backend/test_pn.py` currently reports an intercept at about `27.25 s` with minimum distance about `16.6 m`.
- `backend/test_ballistic.py` currently reports an "intercept" at about `9.45 s` and `68 m` range, but the threat remains alive because that test does not use the live world's CPA-plus-damage logic.

These are good sanity anchors, not final proof of correctness.
