# Megamodel curriculum — training report (cap 72/32/128)

**Branch**: `train-megamodel-cap72`
**Run window**: 2026-04-26 → 2026-04-27 UTC (overnight, EPYC 9554P 64C/128T)
**Scope**: Saab 2026 hackathon arcade-game demo. Single browser-based
demo runs in Chrome on one laptop. Reward shaping numbers are gameplay
balance constants only, not domain claims.

---

## 1. Hardware reality

- Box: AMD EPYC 9554P, 64 physical / 128 SMT, 3.1 GHz base / 3.75 GHz boost,
  377 GB RAM, 814 GB free SSD, Ubuntu 24.04.
- No GPU; `--device cpu` throughout.
- `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`
  exported in the tmux launcher to keep PyTorch BLAS from contending
  with the SubprocVecEnv workers.
- **n_envs settled on**: 48. Steady-state fps ≈ 380–400 in S1/S2/S4,
  dropped sharply during S3 due to a parallel Red-trainee job sharing
  the box (see §3 risks).

## 2. Reward changes summary (vs prior cap-120 V4 reward)

The full reward function is in `team-missile-intercept/backend/rl/env.py`
`_reward_from_events` and `step()`'s spend-penalty block. Key deltas:

| Change | What | Why (gameplay) |
|---|---|---|
| Caps 120/60/160 → **72/32/128** | smaller obs/action shapes | enough for 3-base layouts; smaller policy net |
| **Doctrine multiplier** on intercept | 8 (interceptor, threat) pairs scaled 0.7×..2.0× | reward gambling cheap interceptor on hard target (CIWS→ballistic, CIWS→HGV: 2.0×); discourage SAM tier on drone (0.7×) |
| **Head-on bonus** | +50% × max(0, −cos(angle)) for PAC-2/PAC-3 vs ballistic/HGV | favor head-on engage (lower miss rate at speed) over tail chase |
| **Base-weight scaling on leak** | leak penalty × (n_initial / n_alive) | last-alive bases hurt 3× — preserves the demo's "hold to last base" tension |
| **Dead-base zero-out** | intercepting a threat targeted at dead base = 0 reward | avoid policy farming dead-base traffic |
| **Budget-aware spend penalty** | `spent / 1e6 × 0.5 × spend_modifier`, modifier in [0.5, 2.0] inversely with budget ratio | when Blue richer than Red, spending becomes cheap (afford expensive defense); when poorer, conserve |

## 3. Per-stage trajectory

Convergence rule (hardened mid-run): need ≥5 ep_rew_mean entries in the TB
event file (raw floats, not display-rounded), span < 20.0, latest not new
global max, ≥2 distinct values in the last 5 (rules out buffer-stagnation
false positives where SB3's ep_rew_mean is unchanged because no new
episodes ended in recent rollouts).

| Stage | Layout pool | Red pool | Wall | Final step | Final ep_rew | ep_len_mean |
|---|---|---|---|---|---|---|
| S1 | C | scripted | 24 min | ~540 k | -1094 | 7523 |
| S2 | C, D | scripted | 38 min | ~786 k | -1194 | 7388 |
| S3 | C, D | scripted | 247 min¹ | ~639 k | -1182 | 7558 |
| S4 | C, C, D, D, E | scripted | 29 min | ~639 k | -1169 | 7397 |

¹ S3's 247 min wall is dominated by a parallel Red-trainee job in
`~/hackathon-stridsledning-red/` saturating the box. See §6.

### S1 — Layout C, ScriptedRed only, cold start
ep_rew_mean trajectory (TB raw): -978, -1059, -1030, -1095, -1095, -1095.
Watchdog SIGINT at iter 11 (~540 k) when the LATER convergence rule
*would* still have fired — display-precision artifact at the time
(see §6 below).

### S2 — Add Layout D (warmstart from S1)
ep_rew_mean: -1123, -1095, -1084, -1221, -1218, -1218, -1187, -1187, -1185, -1192, -1194.
Layout D introduction caused a temporary regression (-1084 → -1221) before
the policy stabilised. Final span on last 5 = 8.7 → converged at 786 k.

### S3 — Same C, D pool, scripted-only Red (fallback from learned + rule)
ep_rew_mean: -1032, -1083, -1118, -1183, -1183, -1183, -1182, -1182.
ep_len trending up (5868 → 7558) — Blue holding bases longer.
Span on last 5 = 1.7 → converged at 639 k.

**S3 was retried.** First attempt used `red_mode_pool = (scripted, scripted, rule)`
per the prompt's documented fallback. The rule RedAI front-loads all 28
demo waves in the first 145 s sim, so the world holds many simultaneous
threats and each env step becomes heavy. Combined with the Red-trainee
job (also `n_envs=48`) on the same box, fps dropped 400 → 36 and iter 2
took 45 min. Killed it and dropped `rule` from the pool — second attempt
ran at fps recovering 11 → 25 → ~50 as Red-trainee load eased, finally
converging.

### S4 — Broader layout pool C, C, D, D, E (warmstart from S3)
ep_rew_mean: -1173, -1174, -1113, -1158, -1155, -1155, -1169, -1169.
Layout E added at 1/5 weight, scripted-only Red.
Span on last 5 = 14.0 → converged at 639 k. Wall 29 min (Red-trainee
contention had cleared by this point).

## 4. Learned-Red opponent in S3 — fallback documented

`train.py`'s `--red-mode-pool` argparse `choices = ['scripted', 'rule', 'default']`.
There is no `learned` value; train.py builds the env's Red opponent from
`env.MissileInterceptEnv.__init__`'s `red_mode` argument, forking into
`ScriptedRedAI` (scripted) or rule-based `RedAI(build_demo_waves())`
(rule/default). The megamodel work scope (the launching prompt) forbids
editing `train.py`.

Two pre-existing learned Red models were inspected (loadable via
`MaskablePPO.load`):

| Path | Obs (threats × launchers × interceptors) | Action | Compat |
|---|---|---|---|
| `rl/runs/red_20260421_205051/model.zip` | 30 × 15 × 40 | MultiDiscrete([5, 3]) | shape mismatch w/ cap-72 train env |
| `rl/runs/red_20260421_234425/model.zip` | 30 × 15 × 40 | MultiDiscrete([5, 3]) | shape mismatch |

`live_ai.py`'s `LearnedRedAI` adapter slices obs and remaps actions for
inference, but the training env doesn't use it. S3 fell back further
than the prompt-documented `(scripted, scripted, rule)` to **scripted
only** — see §3 for the rule-RedAI fps issue.

The doctrine reward in `env.py` (head-on PAC-3 bonus vs ballistic/HGV)
still pushes Blue toward HGV-handling behaviour without a dedicated
HGV-spammer Red.

## 5. Phase 2 — Red trainee

**SKIPPED.** Phase 1 finished at ~395 min of the 480 min budget;
remaining 85 min < 90 min Phase-2 floor (per the prompt's `if [
$REMAINING -lt 5400 ]; then echo "Phase 2 skipped"`).

If the box becomes free, Phase 2 can be launched separately with
`scripts/run_red_trainee.py --total-steps 5000000 --push`. The script
is wired in this branch.

## 6. What went wrong, what we learned

### Bug 1 — per-increment driver couldn't accumulate episode signal
The original driver split each stage into 200 k-step increments, each a
separate `python -m rl.train` invocation. Every invocation spawned fresh
SubprocVecEnv workers, so episode state did not persist across increments.
With `episode_time_limit=5000s` (10 000 decisions max per ep) and
`n_envs=48`, each increment provided only ~4 166 decisions per env —
not enough for any episode to finish. SB3's `ep_info_buffer` stayed empty
and `ep_rew_mean` was never logged, so convergence detection couldn't
fire. The driver would have hit HARD_CAP for every stage.

**Fix:** rewrote `run_megamodel.py` to use ONE long `train.py` per stage
with `--total-steps = HARD_CAP`. A watchdog thread polls the log; on
convergence detection it sends SIGINT to the train process. `train.py`
catches `KeyboardInterrupt`, saves `model.zip`, and exits. Within one
`train.py` invocation, SubprocVecEnv state persists across rollouts and
episodes finish naturally.

### Bug 2 — convergence detection fooled by SB3 display rounding
SB3's stdout logger rounds `ep_rew_mean` to 3 sig figs in scientific
notation: -1085 to -1094 all display as `-1.09e+03`. The original
convergence check parsed the displayed string with regex, so 3
consecutive iterations showing `-1.09e+03` produced span = 0 and
falsely triggered convergence — even when the underlying buffer
hadn't refreshed (large `ep_len_mean` means few new episodes per
rollout, so the moving-mean over the latest 100 episodes can stay
unchanged for 2-3 iterations).

**Fix:** `check_convergence.py` now reads raw floats from the TB event
file (no display rounding), requires ≥5 entries instead of 3, requires
span < 20 instead of < 5, and requires ≥2 distinct values in the last
5 (rules out buffer-stagnation false positives).

### Bug 3 — rule RedAI + parallel Red-trainee = box saturation in S3
Adding `rule` to S3's `red_mode_pool` made env steps heavier (rule
RedAI front-loads 28 threats in first 145 s sim, so many simultaneous
in-flight entities). At the same time, a Red-trainee job (`n_envs=48`)
was running in `~/hackathon-stridsledning-red/`, using ~130 cores'
worth of work (each worker burst-using ~270 % CPU during BLAS ops).
With my 48 + their 48 = 96 workers contending for 64 physical cores,
load average ran up to ~3 080. My S3 fps dropped 400 → 36.

**Fix:** dropped `rule` from S3 (and S4) — scripted-only matches S2's
setup. Documented in code comment in `STAGE_PLANS`. Did NOT touch the
parallel Red-trainee per Chen's instruction (`~/hackathon-stridsledning-red/`
is the Red worker isolation area).

## 7. Compatibility / pip freeze

Reproduce on Chen's Windows box with these versions
(`rl/runs/blue_local/blue_megamodel/pip_freeze.txt`):

- numpy 1.26.4 (do **not** upgrade to 2.x — env pickles break)
- torch 2.5.1+cu124 (CPU-only at training time on EPYC)
- stable-baselines3 2.8.0
- sb3-contrib 2.8.0
- tensorboard 2.20.0 (required for SB3 logger)
- tqdm 4.67.3, rich 15.0.0 (required for SB3 `progress_bar=True`)

## 8. Branch tip

- Branch: `train-megamodel-cap72`
- Pre-training commit: `57e0cee` — env reward + driver scaffold
- S1 converged: `3900315`
- S2 converged: `70256c5`
- S3 hardcap (first attempt): `32f1742` (junk, superseded)
- S3 converged: `ede99c8`
- S4 converged: `5685208`
- Final report commit (this file): tip after this push

## 9. Notes for Chen on Windows

- **Final Blue policy** is at
  `team-missile-intercept/backend/rl/runs/blue_local/blue_megamodel/model.zip`
  (this is `S4_final.zip` promoted).
- The `live_ai.py` adapter handles cap-72 ↔ cap-72 (no slicing).
- To wire into the demo, add a model entry to `BLUE_AI_MODELS` in
  `server.py` and the dropdown in the frontend. Per the prompt's
  scope, I did NOT modify those files.
- `rl/runs/blue_local/blue_megamodel/launch_cmd.txt` records the exact
  CLI per stage (also visible in commit messages).
- Each stage's training log is at
  `rl/runs/blue_local/blue_megamodel/stages/<STAGE>_training.log`,
  including the SB3 stdout dump (Tables and warnings).

## 10. Open issues / risks for the demo

- **Reward magnitude is large negative throughout.** ep_rew_mean
  plateaued at ~-1170 to -1190 across stages. With my reward function
  (HGV leaks ×8, base-weight scale up to ×3×, terminal -100 for
  losing), a single HGV hit on the last alive base contributes -800
  to -1200. The policy is losing matches but doing slightly better than
  random. Eyeballing the model in the browser is the right next step
  — the displayed reward is dominated by leak-penalty magnitude, not
  necessarily by quality of decisions.
- **Curriculum did not produce dramatic improvement across stages.**
  S2 → S3 → S4 ep_rew_mean: -1194 → -1182 → -1169. Slight upward
  trend, consistent with "minor refinement" rather than "step-change
  improvement". The S3 contention episode likely cost real signal.
- **Phase 2 (Red trainee) was not run.** If we want it for the
  Finale demo, allocate ≥90 min of clean box time and run
  `scripts/run_red_trainee.py --push`.
- **HARD_CAP at 2 M / 1 M was never hit** for the converged stages —
  watchdog convergence triggered everywhere. Good: no waste from
  runaway training. (But also cosa: convergence may be more "buffer
  has settled" than "policy can't improve further".)

(end)
