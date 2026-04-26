# 120-Cap Blue Training — v4 Reward + Path 2 Loose Mask — Overnight Report

**Date:** 2026-04-26 (overnight 2026-04-25 → 26)
**Branch:** `train-120-v4-path2` (off `final-demo` tip `1485681`)
**Author:** worker session
**Status:** STOPPED EARLY at 2.5 M / 10 M steps — fps far below prompt's projection; full ceiling unattainable in the overnight window. Five checkpoints landed cleanly. ep_rew_mean stayed flat at random-policy baseline; **the model is not expected to play noticeably better than random and Chen should treat this run as a baseline / null result, not a usable Blue policy**. No errors, no NaNs, no entropy collapse.

> **Framing**: hackathon arcade-game / sim training session. Public
> encyclopedia balance numbers, browser demo. Not a military product.

## TL;DR

- Launched 10 M-step PPO from scratch on the 5070 with v2+v3+v4 reward stack and Path 2 loose action mask (`max_range × 3.0`).
- Actual aggregate fps was **74**, not the prompt's projected ~1 000. CPU sim is the bottleneck at 120-cap; GPU sat at 4-9 % util / ~2-3 GB VRAM the whole run.
- Stopped after **5 checkpoints (2.5 M steps, ~9.5 h wall-clock)** — at observed fps the 10 M ceiling would have taken ~37 h, well past Chen's overnight window.
- ep_rew_mean parked at **-1.06 to -1.10 e+03** for the entire run with no clear learning signal. Best snapshot was the 1 M checkpoint; latest (2.5 M) is essentially indistinguishable.
- Final `model.zip` = 2.5 M-step checkpoint. Promoted into both the worktree run dir and Chen's main tree at the canonical path.

## What ran

```
python rl/train.py \
    --red-mode scripted \
    --blue-budget 200000000 \
    --red-budget 150000000 \
    --layouts-pool rl/top3_layouts_CD.json \
    --layouts-pool-slots C D \
    --total-steps 10000000 \
    --run-name blue_local/blue_120_v4_path2_scratch \
    --checkpoint-every 500000 \
    --episode-time-limit 3000 \
    --n-envs 24 \
    --device cuda
```

Env: 24 SubprocVecEnv workers, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`. `Using cuda device` confirmed in log; only the RTX 5070 is enumerated (CUDA capability 12.0). No 1080 sm_61 warning observed (PyTorch 2.11 cu128 only sees the 5070).

## Code state going in

Branch already had the four required commits sitting on top of `final-demo`:

```
bb8b4eb feat(rl): Path 2 loose action mask (max_range x 3.0) for pre-emptive RV intercept
4a4407a feat(rl): reward v4 — drone leak penalty 2.0 → 4.0 for CIWS willingness
833d02a feat(rl): reward v3 — weighted sites (defend-the-living signal)
9d884c2 feat(rl): reward v2 — spend×10, time penalty, terminal HP/budget split
1485681 feat(rl): Path 1 — predictive strategic dispatch in live_ai.py   (final-demo)
```

`env.py` smoke verified (cwd `team-missile-intercept/backend`):

```
threats shape:     (120, 12)  — match
launchers shape:   (60, 12)   — match
action_mask shape: (60, 121)  — match
```

## Throughput

| Phase | fps |
|---|---|
| First iteration | 95 |
| Settled | 74-77 |
| Final 50 iter | 74 |

Aggregate throughput stayed near 74 fps the entire run. The prompt's §5 estimate ("24 envs × 50 ticks/sec/env ≈ ~1 000 fps") did not hold — at 120-cap obs (120 threats × 12 features + per-tick action mask rebuild over (60, 121)) sim cost dominates the policy forward pass. GPU sat at:

```
nvidia-smi (mid-run): 4-9 % util, ~2.5-3.1 GB VRAM, 38-48 W
```

— consistent with a CPU-bound rollout, GPU only doing the periodic forward+backward.

## Wall-clock

- Started: 2026-04-26 00:18 (local)
- Stopped: 2026-04-26 ~09:47 (worker, after the 2.5 M checkpoint at 09:45:52)
- Total wall-clock: ~9 h 30 m
- PPO `time_elapsed` at last log line: **33 994 s** (~9 h 26 m)
- Iterations completed: **204**
- Total timesteps: **2 506 752** (next checkpoint would have been 2 999 952)

## ep_rew_mean trajectory

Sampled every ~30 iterations (~370 k steps):

| total_timesteps | ep_rew_mean |
|---:|---:|
| 135 168 | -1 110 |
| 491 520 | -1 100 |
| 860 160 | -1 060 |
| 1 228 800 | -1 060 |
| 1 597 440 | -1 070 |
| 1 966 080 | -1 080 |
| 2 334 720 | -1 070 |

`ep_len_mean` parked at ~5.93-5.95 e+03 → episodes are running to the 3 000 s time-limit (≈6 000 ticks at 0.5 s/tick) almost universally. The policy is not ending matches earlier through decisive wins or losses; it's drifting to the cap.

**Reward did not go positive.** It crept from -1.11 e+03 (135 k) to -1.06 e+03 (1 M) — a small ~50-pt improvement out of the random-policy baseline — then oscillated within ±20 of -1.07 e+03 for the next 1.5 M steps. No upward trend after 1 M. The 1 M checkpoint and the 2.5 M checkpoint are functionally indistinguishable on this metric.

## Other metrics (final iterations)

```
approx_kl       ≈ 0.001-0.003     (very conservative updates)
clip_fraction   ≈ 0.008-0.03      (most updates uncliped)
entropy_loss    ≈ -0.16 to -0.18  (entropy still high, no collapse)
value_loss      ≈ 1-23 (oscillating; spikes of 12.6 and 23.0 in the very last two iter)
```

The late `value_loss` spikes (1.4 → 12.6 → 23) are worth flagging. Could be the start of value drift as the policy starts mixing in non-baseline behaviours; could equally be a rollout-batch outlier. Not enough subsequent data to tell.

## Likely reasons for stalled learning

Speculation, not diagnosis:

1. **Strong terminal penalty + tiered leak penalties dominate the early gradient.** Random-policy baseline reward is ~-1100 (terminal-100 for Red wins + ~1000 worth of HGV/ballistic ×8/×6 leak penalties scaled by alive-site weighting). Until the policy learns to intercept fast enough to flip a single match, the gradient is just "spend less" — and the spend×10 (v2) makes any over-shoot net-negative even if it eventually intercepts.
2. **Path 2 loose mask (3 × max_range) widens the action space dramatically.** The policy can now fire at threats it cannot reach, and the mask doesn't filter them out. Combined with spend×10 this is a steep exploration tax.
3. **120-cap obs is 4 × the 30-cap network the prompt's fps figure was calibrated against.** Bigger MLP input + larger sim arrays = more CPU per tick, less reward signal per wall-clock-second.
4. **No warmstart.** `--warmstart` was correctly omitted (architecture mismatch), but the 30-cap B_shaped policy had ~5 M shaped-from-CIWS-pretrain steps under it. Starting fresh at 120-cap effectively reset that prior.

These are hypotheses for Chen to consider when designing v5 — not action items for this run.

## Final model artifacts

Worktree (gitignored, 99 MB each):

```
rl/runs/blue_local/blue_120_v4_path2_scratch/
├── ckpt/
│   ├── blue_ppo_499992_steps.zip
│   ├── blue_ppo_999984_steps.zip       ← arguable local best on ep_rew_mean (-1.05e+03)
│   ├── blue_ppo_1499976_steps.zip
│   ├── blue_ppo_1999968_steps.zip
│   └── blue_ppo_2499960_steps.zip      ← promoted to model.zip (latest)
├── model.zip                           ← copy of blue_ppo_2499960_steps.zip
├── tb/ppo_1/                           ← tensorboard (skipped writing analysis)
└── training.log
```

Chen's main tree:

```
C:/Users/xingy/Documents/github/hackathon-stridsledning/team-missile-intercept/backend/rl/runs/blue_local/blue_120_v4_path2_scratch/model.zip
```

The latest (2.5 M) was chosen over the marginally-better-on-paper 1 M checkpoint because the 0.05 e+03 difference in `ep_rew_mean` is within the noise band shown across iterations, and the latest snapshot is more typically what eyeball-eval expects. If the browser eyeball comes out indistinguishable from random, swapping `model.zip` to `ckpt/blue_ppo_999984_steps.zip` is a one-line copy.

## Deviations from the prompt

- **Step ceiling not reached (2.5 M / 10 M).** Prompt anticipated 2-4 h on GPU at ~1 000 fps; actual was 74 fps. The fallback "drop ceiling to 3 M for CPU" applied in spirit (CUDA available but CPU-bound), so the run was stopped short of 10 M when wall-clock left the overnight window.
- **No `--device auto` fallback executed.** CUDA was available; the prompt's CPU fallback was not triggered at launch time, only retroactively in interpreting the slow fps.
- **No final `model.save` from `model.learn()` return.** Training was killed, not allowed to exit cleanly; `model.zip` was promoted from the latest checkpoint manually. Identical bytes to the 2.5 M checkpoint.
- **No eval.** Per prompt — Chen will eyeball in the browser.

## Next steps (for Chen, not this worker)

- Eyeball `model.zip` in the browser. Expectation: ~random behaviour with a small bias (maybe slightly fewer wild PAC-3 launches at out-of-range threats than full random, but the spend×10 may have only learned "fire less" rather than "fire smart").
- If the eyeball confirms null result, candidates for v5:
  - Tighten the action mask back toward 1.5-2.0× max_range (Path 2 may be too loose for from-scratch).
  - Or keep Path 2 loose but warmstart from a 120-cap **structural** copy of the 30-cap B_shaped policy (an obs-padding migration script) instead of from-scratch init.
  - Or scale the spend penalty back toward 0.1-0.2 (between v1's 0.05 and v2's 0.5) so the policy isn't punished hard for early exploration.
- Independent question: **can fps be improved at 120-cap?** The action-mask rebuild on each step (loop over (60, 121) launcher×threat pairs) is a likely sim-cost contributor — vectorising or caching that is probably worth >2× wall-clock improvement, regardless of which reward variant runs next.
