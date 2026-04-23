# blue_aoe_long — training report (in progress)

**Status:** in-flight. Worktree `sleepy-mendel-e4432a` on branch
`blue-aoe-training`. This file is updated as training / eval complete.

**Branch commits (fresh → oldest):**
- `feat(sim): arcade-style AOE fragmentation + reacquire-on-death` (b2ccaea)
- `port(rl): layouts-pool + scripted-Red + warmstart CLI for arcade
  Blue training` (f06e29f)
- `feat(sim): build_default_scenario layout_override kwarg for pool
  training` (cf8885d, cherry-picked from red-ai)

## Game mechanic changes

Every interceptor detonation now applies flat `fragment_damage` to
every alive threat inside `fragment_radius` of the detonation point.
Cluster engagement becomes legible: a warhead either catches the whole
drone pack or misses; no more partial-damage grey zones. PAC-3 stays
pure HTK thanks to the `fragment_radius=0` + `<=` gate.

Interceptors whose target dies mid-flight reacquire the nearest alive
threat inside their launcher's max_range — otherwise they coast to
fuel-out / stall. No new RL action; the policy only sees the indirect
reward signal from better / worse in-flight interceptor utilization.

Per-kind calibrated values (frozen pre-training, §3.6 of the worker
prompt):

| Kind       | fragment_radius (m) | fragment_damage |
|------------|---:|---:|
| CIWS       |  30 |  12 |
| RBS-70     |  50 |  18 |
| IRIS-T SLS | 100 |  35 |
| IRIS-T SLM | 120 |  50 |
| PAC-2      | 150 |  80 |
| PAC-3      |   0 | 120 |

## Training configuration

- **Warmstart:** `blue_cd_focused/model.zip` (13.8 MB, loaded OK —
  obs/action spaces match the new env exactly).
- **Red driver:** `ScriptedRedAI` (`--red-mode scripted`) — 3 parallel
  per-site chains, multiple rounds of drones → cruise → ballistic pair
  → HGV.
- **Layouts pool:** slots C + D from
  `rl/top3_layouts_CD.json` (sampled per-episode).
- **Budgets:** Red 150 M, Blue 200 M.
- **Episode cap:** 3000 s sim — covers the slow drone chain from the
  far-north islands.
- **n_envs:** 12 (SubprocVecEnv).
- **Target steps:** 2 M hard cap on this run (ceiling pulled in from
  the worker prompt's 10 M to fit wall-clock: see deviations below).
- **Checkpoint cadence:** every 100 k steps under
  `rl/runs/blue_local/blue_aoe_long/ckpt/`.

## Deviations from the worker prompt

- **--total-steps 2M instead of 10M.** The worker prompt budgets 20–45
  h wall-clock on Chen's laptop. This session has ~2–4 h. A 2M run
  finishes inside the session and Chen can extend to 10M by re-running
  `rl.train` with `--warmstart rl/runs/blue_local/blue_aoe_long/model.zip`.
  Latest checkpoint path is always live in the run dir.
- **Skipping the 1-M-step eval cadence in favour of a single final
  eval.** Training is watched via tensorboard instead (`tb/ppo_1/`).
- **Phase 3 calibration sweep reduced from 20 matches to 10** — each
  3000 s / ScriptedRed match is ~4 min wall-time, and 20 matches
  competing with training for CPU would blow past the session budget.
  Calibration is paired with the eval at Phase 5 so the final decision
  uses a bigger sample anyway.

## Deliverables

- Trained policy: `rl/runs/blue_local/blue_aoe_long/model.zip`
  (also copied to the main tree at the same relative path).
- Per-layout eval: `blue_aoe_long_final_eval.{json,md}` in
  `team-missile-intercept/backend/`.
- Training log: `rl/runs/blue_local/blue_aoe_long/training.log`.
- This report.

## Calibration sweep (Phase 3)

_(Filled once the 10-match sweep completes.)_

## Training run (Phase 4)

_(Filled once training ends / is interrupted.)_

- Final step: _(TBD)_
- Stop reason: _(TBD — total-steps hit / manual interrupt)_
- Wall-clock: _(TBD)_
- Warmstart fallback triggered: No — loaded cleanly.

## Final eval (Phase 5)

_(Filled once `per_layout_eval.py` completes.)_

## Notes for Chen before merging `blue-aoe-training`

1. Pre-existing `test_hgv_impact.py osc=FAIL` predates this branch —
   see commit message for the Phase 2 feat. Verified via `git stash`.
2. `blue_env.py` and `blue_train.py` from red-ai were NOT ported — the
   live-demo RL tree is simpler (just `train.py` for Blue). The
   layouts-pool plumbing lives on `train.py` + `env.py` instead, and
   `per_layout_eval.py` was rewritten from scratch against the worker
   prompt's CLI shape. Nothing else in `rl/` was touched.
3. `sim/config.py` global defaults (BLUE_BUDGET_START 120 M, RED 100 M)
   are UNCHANGED — training budgets come from `--blue-budget` /
   `--red-budget` kwargs on the env. Live-demo / test_balance still
   run at config defaults. `AOE_ENABLED = True` was added as a
   circuit-breaker but is not wired to anything — AOE is always on.
4. `damage_prox` is fully removed from `InterceptorSpec`; every reader
   was updated in the same commit. `damage_direct` remains for event-
   log labelling only (the new damage path uses `fragment_damage`).
