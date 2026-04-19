# Balance Regression Baseline

Tripwire for future refactors (RK4, unified threat-control contract,
Blue-AI learned policy, etc.). Captures today's threat-vs-defense
numbers in a structured JSON blob so future workers can diff against
them and flag silent balance drift.

## What's here

- `test_balance_baseline.py` — the runner.
- `balance_baseline_2026-04-19.json` — the committed baseline.

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

From the committed `balance_baseline_2026-04-19.json`:

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
