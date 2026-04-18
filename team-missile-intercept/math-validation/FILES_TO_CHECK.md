# Files To Check

Use this as the quick map before opening code. The files are ordered by how quickly they answer "what math is active right now?"

| Order | File | Why Emil should read it | Main things to extract |
| --- | --- | --- | --- |
| 1 | `backend/sim/types.py` | This is the active numeric table for threat and interceptor specs. | Speeds, `max_g`, `drag_k`, HP, damage, radii, USD costs |
| 2 | `backend/sim/config.py` | Global constants and top-level tuning assumptions. | `DT`, `PN_GAIN`, `LAUNCH_RANGE_MARGIN`, `BASE_HIT_RADIUS`, site HP, budget, spawn anchors |
| 3 | `backend/sim/physics.py` | Core math helpers. | PN command, drag, altitude scaling, acceleration caps, speed caps, integrator, closest approach |
| 4 | `backend/sim/entities.py` | Where ballistic, HGV, cruise, drone, and interceptor motion is actually stepped. | Ballistic launch-angle math, HGV bleed/stall, altitude hold, boost/coast rules |
| 5 | `backend/sim/world.py` | Where hits, damage, leaks, and site HP changes are resolved. | CPA gate, direct vs prox damage, leak detection, site damage application |
| 6 | `backend/sim/blue_ai.py` | Balance-critical engagement assumptions live here. | Range gating, time-to-impact approximations, saturation cap, expected damage, budget spend |
| 7 | `backend/sim/red_ai.py` | Spawn geometry and route-shaping assumptions. | Strategic spawn strip, altitude bands, target weights, cruise waypoint offsets |
| 8 | `backend/sim/launcher.py` | Real launcher loadout and magazine assumptions. | Per-launcher counts, PAC-3 current magazine, reload times, inter-shot cooldowns |
| 9 | `backend/sim/sites.py` | Map-to-world transform and target-site filtering. | Active site count, affine transform, out-of-arena filter |
| 10 | `backend/sim/scenarios.py` | Final win-condition wiring. | What actually counts as Red win, Blue win, or draw |
| 11 | `backend/test_pn.py` | Smallest possible PN sanity check. | Current cruise intercept baseline |
| 12 | `backend/test_ballistic.py` | Ballistic smoke test for eyeballing geometry. | Current ballistic trajectory baseline and test limitations |
| 13 | `backend/test_balance.py` | Current balance classifier. | What the project currently calls blue/draw/red in sweeps |
| 14 | `WEAPON_SPECS.md` | Reference intent, not always active runtime truth. | Intended values, documented damage formula, expected magazine sizes |
| 15 | `progress/STATUS.md` | Historical and recent calibration claims. | Reported HP/budget values, narrative claims, known limitations |
| 16 | `progress/ROADMAP.md` | Shows which current approximations are already acknowledged debt. | Planned fixes, especially PN precision and AI follow-up work |

## Fastest Path If Time Is Short

If Emil only has one focused pass, read these first:

1. `backend/sim/types.py`
2. `backend/sim/physics.py`
3. `backend/sim/entities.py`
4. `backend/sim/world.py`
5. `WEAPON_SPECS.md`

That sequence exposes almost every active math-vs-doc mismatch.

## Cross-Checks That Matter Most

Open these pairs side by side:

- `backend/sim/types.py` vs `WEAPON_SPECS.md`
- `backend/sim/world.py` vs the damage formula section in `WEAPON_SPECS.md`
- `backend/sim/config.py` vs `progress/STATUS.md`
- `backend/sim/launcher.py` vs the launcher/magazine tables in `WEAPON_SPECS.md`
- `backend/test_ballistic.py` vs `backend/sim/world.py`

## Practical Note

Do not assume comments and docs agree with runtime values. In this repo, the fastest way to lose time is to audit the comments only.
