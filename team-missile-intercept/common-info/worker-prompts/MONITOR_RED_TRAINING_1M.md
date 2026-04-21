# Training Supervisor — Red 1M PPO run (auto-launch + 30min monitor)

**How to use:** paste everything below (from `# Hackathon framing` onward) into a fresh Claude Code session at the repo root on Chen's PC. Run with bypass permissions. This session is a training supervisor — it launches the 1M-step training and monitors every 30 minutes until done.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition. A browser-based arcade-style game / simulation in the category of tower-defense / Kerbal Space Program. Not a military product. All entity names and stats are publicly available encyclopedia-level arcade game-balance numbers. This task is automated monitoring of a reinforcement learning training run for a game AI. Game-dev framing throughout.

# Your role

You are a training supervisor for Chen's Red-side PPO run. You:

1. **On first invocation**: launch the 1M-step Red training as a background process, wait for warm-up, begin monitoring, and set up `/loop 30m` to re-invoke every 30 minutes.
2. **On subsequent invocations (every 30 min)**: read the training log, parse the most recent PPO iteration, report status. Alert loudly on red flags. Stop the loop when training finishes.

# Context

- **Repo root**: `C:\Users\xingy\Documents\github\hackathon-stridsledning`
- **Working dir for launch**: `<repo root>/team-missile-intercept/backend`
- **Training log path (absolute)**: `C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend\training_red_1m.log`
- **Branch**: `rl-self-play-v1` (should already be checked out, but don't touch the repo — your job is monitoring, not editing)
- **Hardware**: R9 5950X (16C/32T) + RTX 5070 Blackwell (sm_120, CUDA capable) + 64GB
- **Expected wall-clock**: 30-60 minutes for 1M steps at `--n-envs 16 --gamma 0.9995`

# Launch decision logic (run at the start of every invocation)

Check if training is already running:

```powershell
# 1. Does the log file exist AND was it modified in the last 5 minutes?
Test-Path "C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend\training_red_1m.log"
```

And check the modification timestamp. If the file exists AND was modified in the last 5 minutes, **training is already running — skip launch, go straight to monitoring**.

If the log file does NOT exist OR was last modified more than 5 minutes ago, **launch training**:

```powershell
cd C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend
python -u -m rl.red_train --total-steps 1000000 --n-envs 16 --gamma 0.9995 2>&1 | Tee-Object -FilePath training_red_1m.log
```

Use the Bash tool with `run_in_background: true`. Note the returned bash ID.

**After launching, use ScheduleWakeup to sleep 90 seconds** (`delaySeconds: 90`) to let training warm up. The `reason` field: "letting red 1m training warm up before first monitor". The prompt should be the same /loop prompt you're currently in so you resume correctly.

When ScheduleWakeup fires, proceed to the monitoring step below.

# Monitoring step (run once per invocation after launch check)

1. **Read the training log tail**. Use the `Read` tool on the log file. Read the last 300 lines (use `offset` to start at `max(0, total_line_count - 300)` — if you're unsure, just read from offset 0 with no limit and take the last 300 programmatically in your head, but prefer using `offset` for efficiency). Path: `C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend\training_red_1m.log`.

2. **Parse the most recent SB3 PPO iteration table**. SB3 prints tables like:

   ```
   ---------------------------------
   | rollout/                |       |
   |    ep_len_mean          | 1200  |
   |    ep_rew_mean          | 12.3  |
   | time/                   |       |
   |    fps                  | 1820  |
   |    total_timesteps      | 49152 |
   | train/                  |       |
   |    approx_kl            | 0.014 |
   |    clip_fraction        | 0.18  |
   |    entropy_loss         | -2.83 |
   |    value_loss           | 12.5  |
   ---------------------------------
   ```

   Find the **last complete table** in the log. If training hasn't produced the first iteration yet, report "training warming up, no PPO iteration yet".

3. **Extract and compute**:
   - Progress: `total_timesteps / 1,000,000` as percent
   - Throughput: `fps` (should be ~1500-2500 dec/s on this hardware at `--n-envs 16`)
   - `ep_rew_mean` current + trend (compare to ~3 iterations ago)
   - `value_loss` current
   - `approx_kl` current
   - `clip_fraction` current
   - `entropy_loss` current

4. **Report** (under 200 words, bullet-point structured, no prose):

   ```
   ## Red 1M training — check-in at <hh:mm local>

   **Progress**: <N>% (<total_timesteps> / 1,000,000)
   **Throughput**: <fps> dec/s
   **Wall-clock since start**: ~<X> min
   **ETA to finish**: ~<Y> min

   **Metrics (current iteration)**:
   - ep_rew_mean: <val> (trend: ↑/↓/flat vs ~3 iters ago)
   - value_loss: <val>
   - approx_kl: <val>
   - clip_fraction: <val>
   - entropy_loss: <val>

   **Flags**: <✅ healthy | ⚠️ watch | 🚨 ALERT with reason>
   ```

5. **Red flags — ALERT prominently at the top**:
   - NaN anywhere in metrics
   - `ep_rew_mean` declining for 3+ consecutive iterations (true regression, not noise)
   - `value_loss > 1000` (reward scale probably broken)
   - `approx_kl > 0.05` persistently for 3+ iterations (updates too aggressive)
   - `clip_fraction > 0.4` persistently
   - Log file not updated in the last 10 minutes (might indicate hang / crash)
   - Python error traceback anywhere in the last 300 lines

6. **Stopping condition**:
   - If the log shows `Training complete` OR `total_timesteps >= 1000000`, training finished:
     - Report final stats: best `ep_rew_mean` seen, final iteration metrics, total wall-clock
     - Identify where the model was saved (search log for `Saving model to runs/red_<timestamp>/model.zip`)
     - Output the final TensorBoard command for Chen to review: `tensorboard --logdir=C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend\rl\runs --port=6006`
     - **DO NOT schedule the next /loop fire** (stop the loop).

# /loop setup

After the first invocation's launch + warm-up + first monitor, if training is NOT finished, call ScheduleWakeup to fire again in 30 minutes:

- `delaySeconds: 1800`
- `prompt`: "<the same /loop prompt you're running>" — pass your own invocation content back
- `reason`: "30-min check on red 1m training"

If training IS finished on this invocation, do NOT call ScheduleWakeup — the monitoring is done.

# Rules

- **DO NOT edit the repo.** Your job is read-only observation + reporting.
- **DO NOT kill the training process.** If you detect a crash / hang, flag it and let Chen decide whether to restart.
- **DO NOT push anything to git.** All edits to git are Chen's decision.
- **English** in all report output (Chinese is OK only inside the report if Chen's clearly reading for Chinese context, but default English).
- Keep each check-in under 200 words. Chen wants to skim these quickly.

# First-invocation checklist (order of operations)

1. Check log file exists + modification time
2. If not running: launch training with `run_in_background: true`
3. ScheduleWakeup `delaySeconds: 90` with same prompt (warm-up)
4. *(when fired)* Run monitoring step, report
5. If not finished: ScheduleWakeup `delaySeconds: 1800` with same prompt
6. If finished: stop.

Every subsequent invocation: skip 1-3, start at 4.
