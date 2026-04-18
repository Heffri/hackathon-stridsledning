# Balance Checklist

This checklist assumes the hard rule for this session: do not change weapon unit prices. Emil's job here is to judge whether the current HP, budget, magazines, engagement logic, and spawn assumptions create a fair and explainable game.

## 1. Blue Budget And Site HP Calibration

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/config.py` | `BLUE_BUDGET_START = 120_000_000` | Starting Blue spending budget in USD | Compare budget to expected shots in an average and bad match. | Budget never matters, or one bad wave reliably bankrupts Blue regardless of good play. |
| `backend/sim/config.py` | `SITE_HP_START = 100` | Starting HP for each active site | Compare against `progress/STATUS.md`, which still talks about `60 HP`. | Team members are discussing a 60 HP game while runtime is actually running a 100 HP game. |
| `backend/sim/config.py` | `SITE_LEAK_DAMAGE` | Damage per leak by threat type | Check whether the per-leak stakes fit the intended story. | Threats leak often but site deaths almost never happen, or a single leak type dominates match outcomes too sharply. |
| `backend/sim/scenarios.py` | `winner` | Final red/blue/draw rule | Check that HP and budget thresholds produce the intended win narrative. | The victory rule makes balance look healthy while the actual player experience feels wrong. |

### Hand calculations Emil should do first

With current runtime values:

- Drone leak damage = `5`
- Cruise leak damage = `15`
- Ballistic leak damage = `30`
- HGV leak damage = `40`
- Site HP = `100`

That means one site dies after:

- `20` drones
- `7` cruise missiles
- `4` ballistic missiles
- `3` HGVs
- `1` HGV + `2` ballistic missiles
- `2` HGVs + `1` ballistic missile

Important edge case:

- `2` HGVs + `1` cruise missile = `95`, so the site survives with `5 HP`.

If the team still intends the older `60 HP` narrative from `STATUS.md`, the same thresholds would instead be:

- `12` drones
- `4` cruise missiles
- `2` ballistic missiles
- `2` HGVs

That is a major gameplay difference and should be signed off explicitly.

## 2. Current Loaded Blue Inventory Value

Use `backend/sim/launcher.py`, `backend/sim/types.py`, and `backend/sim/config.py` together.

### Runtime loadout implied by current launcher positions and magazine templates

```text
1 x CIWS launcher   with 144 rounds at $2,000 each   = $0.288M
2 x RBS 70 launchers with 1 missile each at $0.175M  = $0.350M
2 x IRIS-T SLS       with 4 missiles each at $0.5M   = $4.000M
2 x IRIS-T SLM       with 8 missiles each at $1.0M   = $16.000M
1 x PAC-2            with 4 missiles at $3.0M        = $12.000M
1 x PAC-3            with 4 missiles at $4.0M        = $16.000M

Total loaded value                                   = about $48.638M
```

### Why this matters

- `BLUE_BUDGET_START` is currently about `2.47x` the currently loaded inventory value.
- If the team still thinks PAC-3 carries `12` missiles, they may be mentally budgeting against a very different game.
- Budget fairness should be judged against the active runtime loadout, not the older reference example.

### Suspicious results

- Blue almost never spends enough to make budget meaningful.
- Blue must spend well above loaded inventory value every ordinary match.
- Budget outcomes depend more on PAC-3 magazine ambiguity than on player or AI quality.

## 3. Launcher, Reload, And Magazine Assumptions

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/launcher.py` | `LAUNCHER_TEMPLATES` | Active per-launcher capacities and reload times | Compare to `WEAPON_SPECS.md` and recent balance discussion. | Magazines in runtime do not match the values people are tuning around in conversation. |
| `backend/sim/launcher.py` | `HIT_TO_KILL` template uses `magazine_capacity = 4` | Active PAC-3 ammo assumption | Decide whether `4` is intentional or drift from the reference `12`. | Balance conclusions depend on PAC-3 scarcity that the docs never mention. |
| `backend/sim/blue_ai.py` | `MAX_SIMULTANEOUS_PER_THREAT = 3` | Saturation cap excluding CIWS | Check whether 3 layered shots is enough for current HP and damage assumptions. | Hard targets routinely need more than 3 credible shots, but the AI is blocked from firing them. |
| `backend/sim/blue_ai.py` | `_expected_damage` | Sums current in-flight `damage_prox` only | Check whether prox-only accounting is fair for weapons whose design intent depends on direct hits. | The AI stops shooting because paper prox damage looks sufficient, even when direct-hit probability is the real issue. |
| `backend/sim/blue_ai.py` | `LAUNCH_RANGE_MARGIN = 1.1` through `_try_fire` and `_time_to_enter_range` | AI may shoot once a target is inside 110 percent of max range | Check whether the extra 10 percent range margin is a good tactical approximation. | Launches happen outside any believable kinematic envelope and balance depends on that slack. |

## 4. Engagement Logic And Cost-Exchange Assumptions

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/blue_ai.py` | `PRIMARY_RULES` | Cheapest or most appropriate first-choice weapons | Check that primary choices match the stated cost-exchange logic. | Blue is routinely choosing premium missiles when a cheaper credible option exists. |
| `backend/sim/blue_ai.py` | `FALLBACK_RULES` | Escalation when primary cannot engage in time | Check whether fallback ordering is fair and explainable. | Expensive missiles dominate against cheap threats because the fallback ladder is too eager. |
| `backend/sim/blue_ai.py` | `_time_to_impact` | Urgency estimate against Main Base | Check whether base-centered urgency is still valid now that there are multiple sites. | Blue waits too long or escalates too early for threats aimed at non-base sites. |
| `backend/sim/blue_ai.py` | `LAST_RESORT_T_IMPACT_S = 15.0` | Desperation-fire threshold | Check whether 15 seconds is a reasonable switch from cost discipline to survival mode. | Last-resort fire happens so often that it is really the default policy. |
| `backend/sim/blue_ai.py` | `_fire` budget deduction | Every launch spends `spec.usd_cost` exactly once | Confirm this is the right accounting model for CIWS rounds and missile launches. | Budget modeling silently treats a CIWS burst and a single CIWS round as the same thing, or vice versa. |

### Hand question Emil should answer

For each threat type, what is the current expected shot bill under the live damage model?

Examples to compute with current runtime values:

- Drone under cheap-defense success case
- Cruise under 1-2 medium shots
- Ballistic under PAC-3 direct-hit vs PAC-2 prox-stack case
- HGV under 3-shot saturation cap

That expected per-threat bill is the real input to fair starting budget.

## 5. Red Pressure, Spawn Geometry, And Site Distribution

| File path | Function / constant | Intended meaning | What Emil should verify manually | What result would look suspicious |
| --- | --- | --- | --- | --- |
| `backend/sim/red_ai.py` | `build_demo_waves` | Current attack composition | Check whether the mix is fair relative to Blue's active magazines and ranges. | One threat class dominates outcomes so strongly that balance is really a single-parameter game. |
| `backend/sim/red_ai.py` | `_TARGET_WEIGHTS` | Red target preference | Recompute effective probabilities after the out-of-arena site filter. | Docs discuss capital pressure, but the capital is not currently in the active target list. |
| `backend/sim/sites.py` | `_in_arena` and `SOUTH_SITES` | Only in-arena sites remain targetable | Confirm whether 3 active sites is the intended scenario. | Balance discussion assumes 6 or 7 target sites, but runtime only offers 3. |
| `backend/sim/red_ai.py` | `_build_cruise_waypoints` | Cruise path weaving via 1-2 lateral offsets of `5 km` to `20 km` | Check whether route inflation and shape are reasonable. | Cruise difficulty depends heavily on arbitrary lateral offsets rather than a deliberate tactical model. |
| `backend/sim/red_ai.py` | Strategic spawn strip and altitude floors | Long-range threat pressure | Check whether current spawn geometry already bakes in too much or too little reaction time. | Balance cannot be explained without saying "they spawn from wherever the code happened to put them." |

## 6. Practical Manual Sweep For "Fair Starting Budget"

Keep weapon prices fixed. Emil can still audit budget fairness with a spreadsheet:

1. List the current wave composition from `backend/sim/red_ai.py`.
2. Estimate average shots needed per threat using current live damage logic, not reference-spec damage.
3. Multiply by current unit prices from `backend/sim/types.py`.
4. Add a bad-luck buffer for misses, overkill, and last-resort shots.
5. Compare the total to candidate budgets such as `80M`, `100M`, `120M`, and `140M`.
6. Decide what the team wants:
   - Blue budget should matter in average matches
   - Blue budget should matter only in bad matches
   - Blue budget should almost never matter before HP does

## 7. Immediate Balance Mismatches Worth Escalating

- `progress/STATUS.md` still talks about `60 HP`, but runtime uses `100 HP`.
- `WEAPON_SPECS.md` says PAC-3 launcher capacity `12`; runtime currently uses `4`.
- `WEAPON_SPECS.md` says quadratic proximity damage; runtime currently uses linear falloff.
- Several threat speeds and HGV maneuver assumptions differ between reference docs and active code.

Emil should treat those as balance blockers, not minor documentation polish.
