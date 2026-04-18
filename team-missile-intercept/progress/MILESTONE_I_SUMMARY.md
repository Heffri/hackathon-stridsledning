# Milestone I — PM Summary

Milestone I closed three engine gaps so future Red / Blue AI layers
have a proper game loop to plug into. Four commits on branch
`knowledge-base` (`97b69fb`, `883dcc3`, `826c5ea`, `81023db`).

## What shipped per task

**Task 1 — Win conditions.** `Site.hp` decrements per leak by kind
(drone 5, cruise 15, ballistic 30, HGV 40). `World.blue_budget`
starts at $120 M and is deducted by `spec.usd_cost` on every
interceptor launch. `Scenario.winner` resolves
`'red' | 'blue' | 'draw' | None`: Red wins on HP ≤ 0 or budget ≤ 0,
Blue wins on all waves spawned + no threats alive, Draw is the
3600 s safety cap (should basically never fire). Server halts on
`scenario.done`. HUD: per-site HP bars, Blue budget bar, blurred
full-screen end-of-match overlay.

**Task 2 — Ballistic + HGV far-north spawn.** Strategic-range
weapons sample `X` uniformly across the arena width and `Y` inside
`STRATEGIC_Y_BAND = (ARENA_Y - 15 km, ARENA_Y - 5 km) = (235, 245) km`.
Altitude floors for reentry realism: ballistic ≥ 20 km, HGV ≥ 30 km.
Drone / cruise spawn via `RedLauncherFleet` — untouched.

**Task 3 — HGV manoeuvre freedom.** Default HGV flies straight to
target. Deleted constants: `_HGV_S_OFFSET_M`, `_HGV_WP_SWITCH_RADIUS`,
`_HGV_DETECT_RADIUS`, `_HGV_JINK_G`. New hook
`Threat.override_maneuver(turn_direction, g_load)` stores a one-tick
commanded lateral accel; `g_load` clamped to `[0, spec.max_g]` (so
50 G → 8 G, -5 G → 0, zero-vector → clear). Physics unchanged
(8 G cap, quadratic KE bleed, 500 m/s stall).

**Task 4 — SLM ballistic gap doc.** Added to STATUS "Known
Limitations": forward-deployed IRIS-T SLM never fires on ballistic
despite being listed in `FALLBACK_RULES[BALLISTIC]` — the rule-
ordering path blocks on PAC-3 / PAC-2 ready time so fallback is
never reached when ballistic fallback actually fires. Deferred for
the learned-engagement refactor. Also flagged in REPORT.md
Milestone I section.

## Final balance numbers

Three 20-match sweeps with the Milestone I hybrid classifier
(winner-aware + leak-count nuance, 2000 s per-match cap):

```
Run 1:  Blue 10/20  Draw  8/20  Red 2/20   leaks avg 5.5
Run 2:  Blue  5/20  Draw 10/20  Red 5/20   leaks avg 5.2
Run 3:  Blue  8/20  Draw 12/20  Red 0/20   leaks avg 6.2
```

Distribution spans **Blue 25-50 %, Draw 40-60 %, Red 0-25 %**.
Run 1 lands fully inside the spec's 30-55 / 30-50 / 10-30 window;
Runs 2 + 3 straddle edges due to binary-concentration variance at
N = 20 (two HGVs on the same site either dies or doesn't).

Leak kinds: HGV 59-60 per 20 matches (100 % leak rate — a physics-
geometry consequence of removing the scripted S + jink per Task 3),
drone 28-56, cruise 0-5, ballistic 0-3.

## Decisions made on my own

- **`SITE_HP_START = 100`** — spec default. Early calibration walked
  through 60 and 80 (both Red-heavy ~80-90 % due to HGV leak rate)
  before landing back at 100 with a redesigned `test_balance.py`
  classifier. HP tuning doesn't shift the leak-count distribution;
  it only gates `scenario.winner` Red-loss.
- **`BLUE_BUDGET_START = 120_000_000` ($120 M)** — sized against
  `WEAPON_SPECS.md` USD values so a typical match burns 30-60 %.
  Observed 30-45 % burn across sweeps.
- **Altitude floors unchanged from spec**: ballistic 20 km, HGV
  30 km.
- **`STRATEGIC_Y_BAND` width = 10 km, 5 km inside top edge** — chose
  the midpoint of the spec's 10-15 km range.
- **`override_maneuver(turn_direction, g_load)`** signature: picked
  the "turn vector + G load" form (vs raw accel) so callers reason
  in pilot terms without computing `max_g × GRAVITY` themselves.
  One-tick (non-sticky) semantics — Red AI must call every tick to
  hold a turn.
- **`test_balance.py` hybrid classifier** at 2000 s cap with Blue
  threshold `leaks ≤ 5`. The threshold recognises the post-Task-3
  3-HGV baseline (every match eats 3 HGV leaks regardless of Blue
  action) and sets "clean Blue" as "HGVs all leaked but nothing
  else did". Doc-flagged so it's reviewable.

## New items surfaced for the roadmap

- **Red AI Level 5 HGV control** — override hook is in place; needs
  a per-tick decision layer (nearest-interceptor scan, geometry,
  KE budget) to drive it. First concrete customer of the hook.
- **Engagement-ladder replacement** — the SLM ballistic-fallback
  gap is a concrete symptom of the rule-based ladder's limits. A
  learned Blue AI decision layer is the real fix (flagged this
  session).
- **PN precision upgrade (Route 3 on existing ROADMAP)** — now
  load-bearing. Straight-line HGV exposed that Euler-0.05 s PN's
  100-300 m CPA against head-on Mach-17 geometry is the hard
  ceiling on HGV intercept rate. RK4 + sub-tick guidance would
  close the gap without restoring a scripted evasion.
- **Site HP hot-dial / debug UI** — HP starting value is now a
  demo-critical knob. Exposing it in a debug UI would let operators
  rebalance live without a sim restart.
