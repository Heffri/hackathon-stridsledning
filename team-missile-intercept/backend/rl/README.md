# rl — RL envs + training + live inference

Two Gymnasium envs over the `backend/sim/` simulator, plus
training entries and live inference wrappers. Both envs share a
symmetric observation/action shape with action masking, so
policies trained on one side can be cross-evaluated against the
other.

| Side  | Env                       | Opponent (rule baseline) | Train entry      | Live inference        |
| ----- | ------------------------- | ------------------------ | ---------------- | --------------------- |
| Blue  | `env.MissileInterceptEnv` | `sim.red_ai.RedAI`       | `rl.train`       | `rl.live_ai.LearnedBlueAI` |
| Red   | `red_env.RedEnv`          | `sim.blue_ai.BlueAI`     | `rl.red_train`   | `rl.live_ai.LearnedRedAI`  |

## Action / observation cap

Both envs are sized at `MAX_THREATS=120`, `MAX_LAUNCHERS=60`,
`MAX_INTERCEPTORS=160`, `MAX_SITES=4` (see `env.py`). This
matches what the live demo uses. `live_ai.py` adapts smaller-cap
checkpoints (e.g. cap 72 / cap 30) by slicing the obs vector
and remapping the action.

## Blue side

Blue agent picks a fire command per Blue launcher per decision
(`MultiDiscrete([MAX_THREATS + 1] * MAX_LAUNCHERS)`) with action
masking gating which `(launcher, threat)` pairs are legal.
Threat spawns are driven either by the scripted `RedAI` or by
the `Red Trainee v2` policy when `--red-policy-path` is passed.

```bash
# Smoke
python -m rl.smoke

# Train (CPU; expect hours per million steps depending on n_envs)
python -m rl.train --total-steps 1500000 --n-envs 30 \
  --layouts-pool-slots C \
  --red-mode-pool scripted \
  --blue-budget 200000000 --red-budget 150000000 \
  --run-name my_blue_run

# Output → rl/runs/blue_local/<run-name>/{model.zip, ckpt/, tb/}
```

The shipping Blue is in
`rl/runs/blue_local/blue_reward_v4_finetune/` (the validated V4 +
CIWS Active configuration). Path 1 predictive-dispatch rule
layer in `live_ai.py` runs alongside it.

## Red side

Red agent picks `(kind, target_site)` per decision
(`MultiDiscrete([5, len(SOUTH_SITES)])`). `kind=0` is hold;
1..4 are drone / cruise / ballistic / HGV. Launcher position
is auto-selected per kind (V1 simplification — agent doesn't
choose launcher or `maneuver_schedule`).

```bash
python -m rl.red_smoke

python -m rl.red_train --total-steps 1500000 --n-envs 30 \
  --run-name my_red_run

# Output → rl/runs/red_local/<run-name>/{model.zip, ckpt/, tb/}
```

The shipping Red Trainee v2 is in
`rl/runs/red_local/red_trainee_parallel/`. Reward shaping
includes spend cost, leak reward (sign-flipped from Blue),
HGV-evasion bonus, and a small ground-crash penalty.

## Models bundled in this branch

Loadable from the SETUP dropdown:

- Blue: heuristic, RL v3 / v4 / V4 (CIWS Active), Boyu V2 / V2a,
  Cap120, Megamodel + S1–S4, S1 retrain (final + peak)
- Red: scripted 3-chain, attrition, RL Trainee v2

See `team-missile-intercept/backend/server.py` `BLUE_AI_MODELS`
and `RED_AI_MODELS` for the registration table.

## Postmortems

For why several of the bigger Blue checkpoints regressed into
PAC-spam (and why V4 + the rule layer is the validated demo
configuration), see:

- `team-missile-intercept/progress/BIG_MODELS_POSTMORTEM_en.md` / `_zh.md`
- `team-missile-intercept/progress/V4_DISTRIBUTION_SHIFT_UPDATE_zh.md`

## Known limitations

- No partial-observation / radar model — both envs are
  omniscient.
- Red agent does not pick launcher position or
  `maneuver_schedule` (auto round-robin via
  `RedLauncherFleet.next_pos` for drone/cruise; strategic
  north-strip sampler for ballistic/HGV).
- `LearnedBlueAI` carries cross-match state in `_assignments` /
  `_tick_counter`; first match clean, second match degrades.
  Fix would be ~10 lines.
- `EvalCallback` with periodic deterministic rollouts wasn't
  wired during training, so checkpoint selection used
  `ep_rew_mean` rather than win rate.
