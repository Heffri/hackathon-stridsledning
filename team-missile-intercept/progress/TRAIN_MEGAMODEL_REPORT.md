# Megamodel curriculum — training report (cap 72/32/128)

**Branch**: `train-megamodel-cap72`
**Run window**: 2026-04-26 (EPYC 9554P 64C/128T)
**Scope**: Saab 2026 hackathon arcade-game demo. Single browser-based
demo runs in Chrome on one laptop. Reward shaping numbers are gameplay
balance constants only, not domain claims.

> **Status**: this report is being filled in live as the curriculum
> trains. Final numbers are inserted at end-of-run. See "FILL ON
> COMPLETION" markers.

---

## 1. Hardware reality

- Box: AMD EPYC 9554P, 64 physical cores / 128 SMT threads, 3.1 GHz
  base / 3.75 GHz boost, 377 GB RAM, 814 GB free SSD, Ubuntu 24.04.
- No GPU. `--device cpu` throughout.
- `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`
  exported in tmux launcher to keep PyTorch BLAS from contending with
  the 48 SubprocVecEnv workers.
- **n_envs settled on**: 48. fps probe at 32-thread parent BLAS gave
  fps≈900 with workers under-saturated; clamping BLAS to 1 thread
  brought parent CPU down without hurting fps.
- **Steady-state fps** (FILL ON COMPLETION): ~__fps__ across S1-S4.

## 2. Reward changes summary (versus prior cap-120 V4 reward)

The full reward function is in `team-missile-intercept/backend/rl/env.py`
`_reward_from_events`. Key deltas:

| Change | What | Why (gameplay) |
|---|---|---|
| Caps 120/60/160 → **72/32/128** | smaller obs/action shapes | enough for 3-base layouts; faster training, smaller policy net |
| **Doctrine multiplier** on intercept | 8 (interceptor, threat) pairs scaled 0.7x..2.0x | reward gambling cheap interceptor on hard target (CIWS->ballistic, CIWS->HGV: 2.0x); discourage SAM tier on drone (0.7x) |
| **Head-on bonus** | +50% × cos(geometry) for PAC-2/PAC-3 vs ballistic/HGV | favor head-on engage (lower miss rate at speed) over tail chase |
| **Base-weight scaling on leak** | leak penalty × (n_initial / n_alive) | last-alive bases hurt 3× — preserves the demo's "hold to last base" tension |
| **Dead-base zero-out** | intercepting a threat targeted at dead base = 0 reward | avoid policy farming dead-base traffic |
| **Budget-aware spend penalty** | `spent / 1e6 * 0.5 * spend_modifier`, modifier in [0.5, 2.0] inversely with budget ratio | when Blue richer than Red, spending becomes cheap (afford expensive defense); when poorer, conserve |

## 3. Per-stage trajectory (FILL ON COMPLETION)

Increment = 200 000 PPO transitions.
Convergence rule = last-3 ep_rew_mean span < 5.0 AND latest is not new global max.

### S1 — Layout C, ScriptedRed only, cold start
- **HARD_CAP**: 2 000 000 — converged at __steps__
- **ep_rew_mean trajectory** (per increment): __values__
- **Wall**: __min__
- **fps observed**: __fps__

### S2 — Add Layout D (warmstart from S1)
- **HARD_CAP**: 2 000 000 — converged at __steps__
- **ep_rew_mean trajectory**: __values__
- **Wall**: __min__

### S3 — Add multi-Red opponents (warmstart from S2)
- **HARD_CAP**: 2 000 000 — converged at __steps__
- **Red-mode pool**: `('scripted', 'scripted', 'rule')` — see §4 below for
  why no learned-Red opponent.
- **ep_rew_mean trajectory**: __values__
- **Wall**: __min__

### S4 — Broader layout pool (warmstart from S3)
- **HARD_CAP**: 1 000 000 — converged at __steps__ / **skipped** with
  reason: __wall budget__
- **Layouts**: `('C', 'C', 'D', 'D', 'E')` (so 2/5 each for C and D, 1/5
  for E)
- **Red-mode pool**: same as S3
- **ep_rew_mean trajectory**: __values__
- **Wall**: __min__

## 4. Learned-Red opponent (S3 fallback note)

`train.py`'s `--red-mode-pool` argparse has `choices=['scripted', 'rule', 'default']`.
There is no `learned` value; train.py builds the env's Red opponent from
`env.MissileInterceptEnv.__init__`'s `red_mode` argument, which forks
into `ScriptedRedAI` (scripted) or rule-based `RedAI(build_demo_waves())`
(rule/default). The megamodel work scope (per the launching prompt)
forbids editing `train.py`.

Two pre-existing learned Red models were inspected:

| Path | Obs (threats × launchers × interceptors) | Action | Compat |
|---|---|---|---|
| `rl/runs/red_20260421_205051/model.zip` | 30 × 15 × 40 | MultiDiscrete([5, 3]) | ❌ shape mismatch w/ cap-72 train env |
| `rl/runs/red_20260421_234425/model.zip` | 30 × 15 × 40 | MultiDiscrete([5, 3]) | ❌ shape mismatch |

`live_ai.py`'s `LearnedRedAI` adapter slices obs and remaps actions for
inference, but the training env doesn't use it (and modifying the env
to inject a learned-Red opponent would have required editing `train.py`).
Per the prompt's documented fallback rule, S3 was launched with
`('scripted', 'scripted', 'rule')`. The doctrine reward already biases
Blue toward head-on PAC-3 vs HGV, so the curriculum still converges on
HGV-handling behavior without a dedicated HGV-spammer Red.

## 5. Phase 2 — Red trainee (FILL ON COMPLETION)

- **Decision**: __ran __ steps / skipped (reason: ≤ 1.5h remaining in
  8 h budget)__
- **Output**: `rl/runs/red_local/red_trainee_megamodel/model.zip`
- **Trajectory**: __values__

## 6. Compatibility / pip freeze

Reproduce on Chen's Windows box with these versions
(`rl/runs/blue_local/blue_megamodel/pip_freeze.txt`):

- numpy 1.26.4 (do **not** upgrade to 2.x — env pickles break)
- torch 2.5.1+cu124 (CPU-only at training time on EPYC; Windows can use CUDA for inference)
- stable-baselines3 2.8.0
- sb3-contrib 2.8.0
- tensorboard 2.20.0 (required for SB3 logger)
- tqdm 4.67.3, rich 15.0.0 (required for SB3 progress_bar=True)
- gymnasium (in requirements.txt)

## 7. Branch tip

- Branch: `train-megamodel-cap72`
- Pre-training commit: `57e0cee` — env reward + driver
- Final commit (FILL ON COMPLETION): __hash__

## 8. Notes for Chen on Windows

- The model's at `rl/runs/blue_local/blue_megamodel/model.zip`.
- `live_ai.py`'s adapter handles cap-72 ↔ cap-72 (no slicing).
- Add to `BLUE_AI_MODELS` in `server.py` and the dropdown in
  `frontend/index.html` to wire it in. (Per the prompt I did not touch
  these files.)
- `rl/runs/blue_local/blue_megamodel/launch_cmd.txt` records the exact
  CLI used per stage.

## 9. Open issues / risks

- Episode duration vs rollout granularity: with `--episode-time-limit
  5000.0` and `n_envs=48`, `n_steps=1024`, early increments may collect
  zero finished episodes (so no ep_rew_mean logged). Convergence check
  tolerates this — it returns "not enough data" and the driver
  continues. ep_rew_mean entries start landing once cumulative
  per-env steps cross the typical match length (~2k decisions ≈ 2 rollouts).
- HARD_CAP guard: every stage caps at 2M (S1-S3) / 1M (S4) regardless
  of convergence, so stages can't run away.

(end)
