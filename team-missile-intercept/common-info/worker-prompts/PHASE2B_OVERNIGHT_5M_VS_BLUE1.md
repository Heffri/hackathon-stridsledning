# Phase 2b overnight — Red2 vs Blue1 (5M steps, warmstart, worker auto-launches detached training)

**How to use:** paste everything below (from `# Hackathon framing`) into a fresh Claude Code worker session at the repo root on Chen's PC. Bypass permissions. Budget: ~1.5-2 h for coding + ~5.5 h overnight training.

**Chen is going to sleep immediately after handing you this prompt. You must:**
1. Write the opponent-swap + warmstart code (~1-1.5h)
2. Smoke-test (~10 min)
3. Launch the 5M overnight training as a **fully detached process** (via `Start-Process` with redirection to log file, NOT via `run_in_background` — the detached process must survive Claude Code session termination)
4. Verify training started cleanly (wait ~2 min, check log shows first PPO iteration)
5. Write a summary with: launch time, expected completion, log file paths, what Chen checks in the morning
6. Exit session

Do NOT keep the worker session alive all night monitoring. Detached training + morning review is the plan.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition. A small browser-based arcade-style game / simulation in the tower-defense / KSP category. NOT a military product. All entity names and stats are publicly available encyclopedia-level arcade game-balance numbers. This worker trains a game AI overnight. Game-dev framing throughout.

# Your role

Fine-tune Chen's Red1 policy against Boyu's Blue1 policy (single learned opponent, no pool mixing for simplicity). 5M steps overnight. Start detached, Chen sleeps, wakes up to Red2.

Scope decisions (simplified from earlier Phase 2b design):
- **Single opponent**: Red2 trains vs Blue1 ONLY (no rule/Blue1 mixture)
- **Rationale**: Boyu's Blue1 is weaker than simple heuristics per his INFO.md — forcing Red to beat it won't hurt robustness, but the simplicity saves engineering time
- **Warmstart**: start from Red1 model.zip (don't retrain from scratch)

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`.

**Active branch: `rl-self-play-v1`**. Work locally, **do NOT push**.

**Expected starting HEAD:** `a72adc5` or newer.

**Model files:**
- Red1 (warmstart): `team-missile-intercept/backend/rl/runs/red_20260421_205051/model.zip` (local, 9.6 MB)
- Blue1 (opponent): fetch from `origin/blue-ai` via
  ```
  git checkout origin/blue-ai -- team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip
  ```
  Path after fetch: `team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip` (13.8 MB)

Start by reading:
- `team-missile-intercept/backend/rl/red_env.py` — Chen's RedEnv (modify in place)
- `team-missile-intercept/backend/rl/env.py` — Boyu's Blue env (**reference for how Blue actions apply to the sim**; don't modify)
- `team-missile-intercept/backend/rl/red_train.py` — Chen's train script (add warmstart)
- `team-missile-intercept/backend/sim/blue_ai.py` — rule-based Blue (stays as fallback)
- `CLAUDE.md` — project framing

# Pre-flight

1. `git status` — must be clean.
2. `git fetch origin --prune`
3. `git checkout rl-self-play-v1`
4. `git pull --ff-only origin rl-self-play-v1`
5. Fetch Blue1: `git checkout origin/blue-ai -- team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip` — pulls the file only. After this, `git status` shows staged `models/blue_ai_1m_2xpenalty/model.zip`. That's fine; at the end you'll un-stage it.
6. Verify both models on disk:
   ```powershell
   Test-Path "team-missile-intercept\backend\rl\runs\red_20260421_205051\model.zip"
   Test-Path "team-missile-intercept\backend\rl\models\blue_ai_1m_2xpenalty\model.zip"
   ```
   Both must print `True`.
7. Check GPU free: `nvidia-smi` — RTX 5070 should be idle / low usage (no other training or heavy workload occupying it).

If any step fails, STOP and report.

# Design — minimal opponent swap

## Approach

Simple flag-based swap in `RedEnv`. No class hierarchy.

1. Add constructor param: `blue_policy_path: str | None = None`
2. If `None`: use existing `BlueAI()` (default behavior, unchanged)
3. If path given: load `MaskablePPO.load(path)` once at init; in `step()`, call `blue_policy.predict(blue_obs, ...)` and apply Blue action

```python
class RedEnv(gym.Env):
    def __init__(self, ..., blue_policy_path=None):
        ...
        if blue_policy_path:
            from sb3_contrib import MaskablePPO
            self.blue_policy = MaskablePPO.load(blue_policy_path)
            self.blue = None  # rule-based fallback disabled
        else:
            self.blue_policy = None
            self.blue = BlueAI()
    
    def step(self, action):
        # Red's action applies first (as before)
        ...
        
        # Blue's turn — either rule-based or learned
        if self.blue_policy is not None:
            blue_obs = self._encode_obs()  # SAME encoding as Red
            blue_mask = self._compute_blue_action_mask()  # NEW method, see below
            blue_action, _ = self.blue_policy.predict(
                blue_obs, deterministic=False, action_masks=blue_mask
            )
            self._apply_blue_action(self.world, blue_action)  # NEW method
        else:
            self.blue.step(self.world.t, self.world)  # rule-based (existing)
        
        # Advance sim, compute reward, etc. (as before)
        ...
```

## Two new methods to implement

### `_compute_blue_action_mask(self) → np.ndarray`

Blue's action space is `MultiDiscrete([31]*15)` = flat length 465 (15 launchers × 31 actions each). Compute the mask based on `self.world` state:
- For each launcher slot `i ∈ [0, 15)`:
  - Slot 30 (hold): always valid (mask = 1)
  - Slots 0..29 (fire at threat index `j`): valid iff threat `j` exists, is alive, AND launcher `i` can fire (not reloading, has ammo, in range)

**Port from Boyu's env.py** — he has this mask computation in `MissileInterceptEnv.action_masks()` or similar. Copy verbatim (~30 lines), adapt to `RedEnv`'s launcher/threat lookup.

Return shape: `np.ndarray(shape=(15*31,), dtype=np.int8)` — flat 1D array length 465.

### `_apply_blue_action(self, world, action)`

Port from Boyu's `MissileInterceptEnv._apply_action`. Signature: `action: np.ndarray(shape=(15,), dtype=int64)` — each element ∈ [0, 30]. For each launcher `i`:
- If `action[i] == 30`: hold, do nothing
- If `action[i] ∈ [0, 29]`: fire launcher `i` at threat indexed `action[i]` in Boyu's sorted threat list. Call `world.spawn_interceptor(...)` with appropriate args. Skip if invalid (launcher reloading / threat dead / etc.) — don't crash.

**Critical**: Boyu's env maintains a consistent threat-index ordering (sorted by time-to-impact or similar). Your RedEnv's `_encode_obs` mirrors this sort. Use the SAME sort order to resolve `action[i]` → which threat to fire at.

If Boyu's sort order is non-deterministic or state-dependent, extract it into a helper function and call it from both encode_obs and apply_blue_action. Don't re-sort differently.

## Warmstart in red_train.py

Add CLI flag `--warmstart <path_to_model.zip>`:

```python
# In red_train.py, after vec_env is constructed:
if args.warmstart:
    model = MaskablePPO.load(args.warmstart, env=vec_env)
    # Reset learning rate + entropy if desired (usually NOT — keep momentum)
    print(f"Warmstarted from {args.warmstart}")
else:
    model = MaskablePPO(
        "MultiInputPolicy", vec_env, ...
    )
```

Add CLI flag `--blue-opponent <path_to_model.zip>`:

```python
# When constructing envs for vec_env, pass blue_policy_path:
env_fns = [lambda: Monitor(ActionMasker(RedEnv(
    episode_time_limit=args.episode_time_limit,
    blue_policy_path=args.blue_opponent,  # NEW
), action_mask_fn))]
```

## Smoke tests (required before launching overnight training)

Run in this order. All must pass before launching the 5M run.

1. **Regression**: `python -m rl.red_smoke` — 3/3 still pass with rule Blue default.

2. **New Blue-opponent smoke**: Write a short inline script (or add to `red_smoke.py`):
   ```python
   env = RedEnv(
       episode_time_limit=60.0,
       blue_policy_path="models/blue_ai_1m_2xpenalty/model.zip",
   )
   obs, _ = env.reset(seed=42)
   for i in range(50):
       action = env.action_space.sample()  # or masked-random
       obs, r, term, trunc, info = env.step(action)
       if term or trunc:
           obs, _ = env.reset(seed=42 + i)
   # Assert no NaN, no crashes
   ```
   Run it, confirm no errors, no NaN in rewards.

3. **Warmstart + opponent smoke**: 
   ```powershell
   python -u -m rl.red_train --total-steps 10000 --n-envs 2 --gamma 0.9995 --warmstart runs/red_20260421_205051/model.zip --blue-opponent models/blue_ai_1m_2xpenalty/model.zip
   ```
   Must produce at least 1 PPO iteration table without crash. Expect ep_rew_mean in a reasonable range (not exploding, not NaN).

If any smoke fails, fix and re-run. **Do NOT launch overnight training until all 3 smoke tests pass.**

# Launch overnight training (this is the tricky part)

**Key: training must be FULLY DETACHED** from Claude Code. Use `Start-Process` with output redirected to log files, NOT `run_in_background: true`.

## Launch command (you run this via Bash tool)

```powershell
$trainingDir = "C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend"
$logPath = "$trainingDir\training_red_5m_vs_blue1.log"
$errPath = "$trainingDir\training_red_5m_vs_blue1.err"
$pidPath = "$trainingDir\training_red_5m_vs_blue1.pid"

$proc = Start-Process python `
    -ArgumentList "-u","-m","rl.red_train", `
                  "--total-steps","5000000", `
                  "--n-envs","16", `
                  "--gamma","0.9995", `
                  "--save-every","500000", `
                  "--warmstart","runs/red_20260421_205051/model.zip", `
                  "--blue-opponent","models/blue_ai_1m_2xpenalty/model.zip" `
    -WorkingDirectory $trainingDir `
    -RedirectStandardOutput $logPath `
    -RedirectStandardError $errPath `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Out-File $pidPath
Write-Output "Launched training PID=$($proc.Id), logs: $logPath"
```

This launches python directly (not wrapped in cmd/powershell), redirects stdout/stderr to separate files, hides window, returns PID.

## Verify startup

Wait 90 seconds (via ScheduleWakeup delaySeconds=90 to avoid blocking your own session), then:

1. Check PID still alive: `Get-Process -Id (Get-Content $pidPath) -ErrorAction SilentlyContinue` — must return a process object. If null, training crashed.
2. Check log has content: `Get-Content $logPath -Tail 20` — should show env init + at least started rollout collection.
3. Check no errors: `Get-Content $errPath -Tail 10` — should be empty or only warnings.

If training started cleanly, proceed to summary. If not, debug (check stderr), report to Chen, and do NOT leave failing training running.

## Windows sleep prevention (important for 5-6h training)

Before ending the worker session, run:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 10
```

This prevents the laptop from sleeping (even with lid open / idle) while plugged in. Monitor can still turn off after 10 min (saves power, doesn't kill CPU). **Include in your summary that you did this.** Chen can reset after training: `powercfg /change standby-timeout-ac 30`.

# Task

5 subtasks, commits as described.

## Subtask A — RedEnv learned-Blue support (~60-90 min, 1 commit)

Implement `blue_policy_path` constructor param, `_compute_blue_action_mask()`, `_apply_blue_action()` in `red_env.py`. Careful to port Boyu's mask + apply logic accurately.

**Commit (LOCAL):** `feat(rl): RedEnv blue_policy_path — learned-Blue opponent swap`

## Subtask B — red_train.py warmstart + blue-opponent CLI (~20-30 min, 1 commit)

Add `--warmstart <path>` and `--blue-opponent <path>` flags. Thread through to env construction + model init.

**Commit (LOCAL):** `feat(rl): red_train.py --warmstart + --blue-opponent flags`

## Subtask C — Smoke tests (~10-15 min)

Run 3 smoke tests per Design. Fix anything that breaks.

No commit here unless smoke revealed a bug fix needed.

## Subtask D — Launch 5M overnight training (~5 min + 90s verification)

Run the Start-Process launch command. Verify PID alive + log shows first iteration content. Apply powercfg no-sleep settings.

No commit.

## Subtask E — Un-stage Blue1 model.zip + final summary

Clean up staging: `git restore --staged team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip` (keeps file on disk, removes from index).

Write the final summary per template below.

# Rules

- **LOCAL ONLY commits** — do NOT push.
- **Do NOT commit the Blue1 or Red1 model.zip files** (un-stage at end).
- **Do NOT modify Boyu's env.py or train.py** — mirror, don't edit.
- **Do NOT modify game-core sim files**.
- **Start-Process for training, not run_in_background**. Training must survive session exit.
- **No force-push, no amend, no --no-verify**.

# Post-flight

Before exiting session:
1. Confirm `git status` — staged blue1 model removed, 2 new commits on rl-self-play-v1 local, clean otherwise (untracked files OK).
2. Confirm `nvidia-smi` shows training process using GPU.
3. Confirm log file growing: `Get-Content training_red_5m_vs_blue1.log -Tail 5` shows recent output (timestamp within last 60s).
4. powercfg settings applied.

# Deliverable — final summary for Chen (≤ 400 words)

1. **Commits landed (local)** — 2 hashes + one-line each.
2. **Smoke results** — 3/3 pass? Any warnings worth flagging?
3. **Training launch status** — PID, launch time, expected completion time (5M / observed-it-s seconds).
4. **Log file paths Chen checks in the morning:**
   - Main log: `team-missile-intercept/backend/training_red_5m_vs_blue1.log`
   - Error log: `team-missile-intercept/backend/training_red_5m_vs_blue1.err`
   - PID file: `team-missile-intercept/backend/training_red_5m_vs_blue1.pid`
   - Model output: `team-missile-intercept/backend/rl/runs/red_<timestamp>/model.zip`
5. **Morning checklist for Chen**:
   - Check training done: `Get-Content training_red_5m_vs_blue1.log -Tail 40` (should end with "Training complete" or similar)
   - Check no process: `Get-Process -Id (Get-Content .pid)` (should fail = process exited cleanly)
   - Launch cross-eval tournament: paste `PHASE2_CROSS_EVAL.md` into new session, but add Red2 to the tournament matrix (3×2: rule_Red, Red1, Red2 × rule_Blue, Blue1)
   - Reset sleep: `powercfg /change standby-timeout-ac 30`
6. **Any anomalies** — unexpected slow start, GPU not detected, mask shape warnings, Blue1 load warnings.

End session. Chen sleeps.
