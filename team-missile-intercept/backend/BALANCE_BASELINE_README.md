# Balance Regression Baseline

Tripwire for future refactors (RK4, unified threat-control contract,
Blue-AI learned policy, etc.). Captures today's threat-vs-defense
numbers in a structured JSON blob so future workers can diff against
them and flag silent balance drift.

## What's here

- `test_balance_baseline.py` — the runner.
- `balance_baseline_2026-04-19.json` — the M-TIER1.5 (Worker 3)
  baseline. Kept intact for historical diffing.
- `balance_baseline_2026-04-20.json` — the M-TIER2.5 (Worker 5) post-
  broad-flyover-fix + engagement_mode infrastructure baseline. This
  is the current reference.

## How to rerun

```bash
cd team-missile-intercept/backend
python test_balance_baseline.py                            # full 1800 s scenarios
python test_balance_baseline.py --quick                    # 600 s scenarios
python test_balance_baseline.py --out my_new_baseline.json # write elsewhere
```

Full run takes ~2 minutes of wall-clock.

## What's in the JSON

Three scenarios:

- **`full_match`**: default `BLUE_LAUNCHER_POSITIONS`, default waves,
  Blue AI on, single match, 1800 s cap. Captures `winner`, per-kind
  `{spawned, intercepted, leaked, ground_impacted, still_alive_at_end}`,
  site HP, and Blue budget remaining.

- **`no_blue`**: same 1800 s match but Blue AI disabled. Threats fly
  unopposed to ground / leak. Useful to isolate intrinsic threat
  effectiveness from defense performance.

- **`per_kind_cep`**: 30 single-threat trials per kind (drone, cruise,
  ballistic, HGV) via `RedAI._spawn_point` + `red_ai._pick_target`,
  no Blue. Emits `miss_{mean,median,p95,max}_m` against the pre-selected
  target site position. Per-kind sim caps so slow kinds (drone at 120 m/s,
  cruise at 260 m/s) reach target before cutoff.

## How to diff

```bash
python - <<'EOF'
import json
old = json.load(open("balance_baseline_2026-04-19.json"))
new = json.load(open("my_new_baseline.json"))
def diff(old, new, path=""):
    if isinstance(old, dict):
        for k in old:
            if k in new:
                diff(old[k], new[k], f"{path}.{k}")
    else:
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            if abs(new - old) > 0.01 * max(abs(old), 1):
                print(f"{path}: {old} -> {new}")
diff(old, new)
EOF
```

## What should be stable vs vary

- **Stable across runs (any RK4 / Blue-AI refactor should preserve these)**:
  - `total_spawned` — 26 per match with current wave spec. Red AI is
    deterministic in *which* threats spawn; only *where* and *which site*
    vary.
  - `per_kind.*.spawned` — wave composition is fixed.
  - `no_blue.per_kind.*.leaked` — without Blue, every threat should
    reach its target. Drift here means targeting broke.
  - `per_kind_cep.hgv.miss_median_m` — 174–230 m (glide-path CEP). If
    this grows, HGV targeting broke.
  - `per_kind_cep.ballistic.miss_median_m` — 1386–1414 m (ballistic
    in-air leak-disc trigger). If this grows or mean blows up without
    the flyover explanation, ballistic targeting broke.

- **Expected to vary (single-match stochasticity in Red AI RNG +
  weighted-random target picks)**:
  - `full_match.winner` — Blue wins most matches today but variance
    spans {blue, draw} on a single run. Running 20 matches like
    `test_balance.py` smooths this out.
  - `full_match.total_intercepts` — ±5 across runs.
  - `per_kind_cep.ballistic.miss_mean_m` — the 2/30 flyover
    artifact trials push mean 2–5× above median. Expect
    4–10 km mean depending on which sites Red targets.
  - `site_hp` — entirely run-specific.

## Known-sensible value ranges (M-TIER1.5)

From the historical `balance_baseline_2026-04-19.json` (W3):

| field | baseline | OK range |
|---|---|---|
| `full_match.total_spawned` | 26 | 26 (fixed wave) |
| `full_match.total_intercepts` | 19 | 15–23 |
| `full_match.total_leaked` | 7 | 5–12 |
| `no_blue.total_leaked` | 24 | 22–26 (∝ spawned) |
| `per_kind_cep.drone.miss_median_m` | 1499 | 1450–1500 (leak disc edge) |
| `per_kind_cep.cruise_sub.miss_median_m` | 1494 | 1450–1500 |
| `per_kind_cep.ballistic.miss_median_m` | 1392 | 1350–1450 |
| `per_kind_cep.hgv.miss_median_m` | 205 | 100–400 (glide-path) |

Drift outside these ranges warrants investigation, not automatic
acceptance of the new numbers.

## 2026-04-20 entry (M-TIER2.5)

Changes since W3:

- Broad flyover rule — every non-nuclear threat kind now sets
  `requires_ground_impact=True`. Pre-W3 only HGV had the flag. The
  effect: a ballistic / cruise / drone crossing a site's 1500 m
  horizontal disc at altitude no longer triggers leak damage. Only
  physical ground-level crossings count.
- `engagement_mode` infrastructure landed (pac_3 defaults to htk;
  every other interceptor defaults to prox — bit-for-bit identical
  to pre-W5 prox behaviour). See `../game-core/ENGAGEMENT_MODE_DESIGN.md`.

Direct consequences for the baseline numbers:

- `per_kind_cep.*.miss_median_m` now measures true ground-impact
  position, not the 1500 m disc-edge trigger position. drone drops
  from 1499 → ~237 m (drones dive to z=0 on final approach), ballistic
  climbs from 1392 → ~3313 m (real projectile CEP, the pre-W3 value
  was measuring the leak-disc radius), hgv stays ~200 m (unchanged
  — HGV already had the flag).
- `per_kind_cep.cruise_sub` goes to `None` because cruise_sub's
  terminal pop-up profile holds it at 300 m altitude rather than
  diving to 0 m — the ground-impact requirement is never met within
  the 2000 s cap. This is a known behaviour gap: cruise_sub needs a
  drone-style terminal dive (`_cruise_alt_override → 0.0` at
  `horiz_to_wp < 500`). Flagged as future work, NOT a bug in
  M-TIER2.5 scope.
- `full_match.total_leaked` drops 7 → 3 (flyover leaks removed).
- `no_blue.per_kind.cruise_sub.leaked` / `.ballistic.leaked` drop
  to 0 for the same reason as the CEP shift — cruise doesn't dive,
  ballistic's CEP exceeds the 1500 m disc.
- `full_match.winner` is `None` at the 1800 s cap because both
  Blue-win (Red.done + no threats alive) and Red-win (site HP 0 or
  budget 0) take longer to fire when fewer leaks happen. Not a bug;
  the 1800 s cap just isn't generous enough for the new pacing.
  The 20-match `test_balance.py` sweep uses a 2000 s cap and catches
  the natural end-states at 18/20 Blue wins, 2/20 draws.

20-match sweep (`test_balance.py`, 2000 s cap, hybrid classifier):

```
Pre-W5 (baseline):  Blue  1/20  Draw 19/20  Red 0/20   avg leaks 7.8
                     leaks by kind: ballistic 62, hgv 40, drone 51, cruise_sub 2
Post-A (flyover):    Blue 18/20  Draw  2/20  Red 0/20   avg leaks 3.9
                     leaks by kind: hgv 41, drone 37
Post-B (mode infra): Blue 14/20  Draw  6/20  Red 0/20   avg leaks 4.8
                     leaks by kind: hgv 45, drone 51
```

Blue at 70 % (post-B) is above the spec's 30–55 % target band. No
budget tune applied — per operator rule (2026-04-19): "Blue stronger
is a good problem; leave it." Post-B is slightly softer than post-A
because pac_3's prox-band fallback (CPA 60-80 m → 2-6 dmg) is now a
clean miss in htk mode; HGV leaks pick up 4 (41 → 45), drone leaks
pick up 14 (37 → 51). Follow-up balance work (cruise dive fix,
ballistic CEP tightening, or anti-ground-crash HGV re-routing) will
bring the numbers back into the band without tuning the budget.

Updated known-sensible ranges (W5):

| field | W5 baseline | OK range |
|---|---|---|
| `full_match.total_spawned` | 26 | 26 (fixed wave) |
| `full_match.total_intercepts` | 17 | 12–22 |
| `full_match.total_leaked` | 3 | 1–6 |
| `no_blue.per_kind.drone.leaked` | 9 | 7–11 |
| `no_blue.per_kind.hgv.leaked` | 3 | 2–4 |
| `no_blue.per_kind.cruise_sub.leaked` | 0 | 0 (until cruise dive lands) |
| `no_blue.per_kind.ballistic.leaked` | 0 | 0–1 (until ballistic CEP < 1500 m) |
| `per_kind_cep.drone.miss_median_m` | 237 | 100–400 (terminal dive) |
| `per_kind_cep.ballistic.miss_median_m` | 3313 | 2500–4500 |
| `per_kind_cep.hgv.miss_median_m` | 161 | 100–400 |
| `per_kind_cep.cruise_sub.miss_median_m` | None | None until cruise dives |

## Caveats

- Random sampling: `RedAI.rng` takes fresh entropy each run, so
  individual-match numbers jitter. To reduce noise without running
  twenty matches, compare medians and interpret a single run's numbers
  as "one sample".
- The `full_match` winner can flip between blue and draw on a single run
  because post-M-TIER1.5 ballistic + HGV are both effective and bust
  Blue's budget frequently. Use `test_balance.py` (20 matches) for the
  true distribution.
- Flyover artifact (ballistic firing leak at altitude on a
  non-targeted site) is real and documented in
  `ballistic_cep_report.md` — expect ~2/30 CEP trials to show 50+ km
  miss.
