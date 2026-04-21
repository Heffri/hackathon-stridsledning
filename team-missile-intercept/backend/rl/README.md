# rl — self-play RL envs + training

Two Gymnasium envs over the `backend/sim/` simulator, plus a
MaskablePPO training entry per side. Both envs share a symmetric
observation/action dict and normalization so policies trained on one
side can be cross-evaluated against the other.

| Side  | Env                         | Opponent (rule-based) | Train entry          | Smoke              |
| ----- | --------------------------- | --------------------- | -------------------- | ------------------ |
| Blue  | `env.MissileInterceptEnv`   | `sim.red_ai.RedAI`    | `rl.train`           | `rl.smoke`         |
| Red   | `red_env.RedEnv`            | `sim.blue_ai.BlueAI`  | `rl.red_train`       | `rl.red_smoke`     |

## Blue side (Boyu)

Blue agent picks a fire command per Blue launcher per decision
(`MultiDiscrete([MAX_THREATS + 1] * MAX_LAUNCHERS)`). Threat spawns
are driven by the scripted `build_demo_waves()`.

```bash
# Smoke (3 policies × 1200 steps, ~20s)
python -m rl.smoke

# Train (CPU/GPU auto-detected; expect hours on GPU for 1M steps)
python -m rl.train --total-steps 1000000 --n-envs 8

# Output → rl/runs/<timestamp>/{model.zip,ckpt/,tb/}
```

## Red side (Chen)

Red agent picks `(kind, target_site)` per decision
(`MultiDiscrete([5, len(SOUTH_SITES)])`). `kind=0` means hold; 1..4
are drone / cruise / ballistic / HGV. Launcher position is auto-
selected per kind (V1 simplification — agent doesn't choose launcher
or maneuver_schedule). Opponent is rule-based `BlueAI`.

```bash
# Smoke (3 policies × 100 steps, ~5s)
python -m rl.red_smoke

# Train (runs in parallel with Blue training on a second machine)
python -m rl.red_train --total-steps 1000000 --n-envs 8

# Output → rl/runs/red_<timestamp>/{model.zip,ckpt/,tb/}
```

Red reward is sign-flipped vs Blue: `+2*dmg` per `leak`, spawn cost
subtracted at decision time, `-cost/1e6` per `intercept` (lost threat),
`-0.2` per `ground_crash`, terminal `±100` on site HP=0 / Red priced
out + no live threats.

See `red_env.py` module docstring for the full reward and action-space
contract.

## Parallel self-play training

Boyu trains Blue on his machine, Chen trains Red on a second machine.
Both sides see the same sim — the symmetric env shape means policies
from either side can be loaded into a shared eval harness.

## Cross-eval (deferred)

`rl.eval` currently loads a Blue MaskablePPO policy and runs it
against rule-based Red. Loading a Red policy + running it against
rule-based Blue (or against a trained Blue policy for full self-play
eval) is a future extension — a follow-up worker should generalise
`eval.py` to switch env class + mask_fn based on a `--side red|blue`
flag.

## Non-goals (V1)

* Red agent does NOT pick launcher position (auto round-robin via
  `RedLauncherFleet.next_pos` for drone/cruise; strategic north-strip
  sampler for ballistic/HGV).
* Red agent does NOT set `maneuver_schedule` — HGV uses its default
  glide-dive; cruise_sub uses default S-shape waypoints.
* No partial-observation / radar model — both envs are omniscient.

If Red training plateaus, the follow-up expansion is to widen the
action space to include launcher-id and a small maneuver-schedule
menu (e.g. jink patterns for cruise / ballistic). The reward signal
and sim coupling don't need to change.
