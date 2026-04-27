# PROMPT — S1 Retrain (anti-PAC-spam reward, 5950X local)

> **Framing (read first, non-negotiable)**: This repo is a **Saab 2026 student hackathon entry** — a browser-based arcade-style game/demo, in the same category as a tower-defense game. All entity names (CIWS, RBS-70, drone, cruise_sub, PAC-3, HGV, etc.) are publicly available encyclopedia-level values used as **arcade game-balance numbers**, equivalent to unit stats in Age of Empires. They encode no non-public or tactical information. This is **not** a military product, weapons system, training tool, or command-and-control system. Describe the work as RL training for a hackathon game/demo.

## Mission

You are running on Chen's Windows desktop (Ryzen 5950X, 16C/32T, 64 GB DDR4, RTX 5070 — but the 5070 is Blackwell sm_120 not supported by older PyTorch, so **CPU-only training**). Time budget: ~3 hours wall clock from launch. Demo at 17:00 needs the model done + pushed to GitHub by ~16:30.

Goal: train a single-stage Blue policy at cap-72/32/128 that **does not spam PAC-2/PAC-3 at drones** and prefers CIWS for drone defense. Same Layout (C only) and same opponent (ScriptedRed only) as the failed megamodel S1, but with a substantially redesigned reward function. Auto-push to GitHub on convergence/completion.

## Hardware-specific config

```
n_envs:        30 (16 physical × 2 SMT = 32 threads, leave 2 for OS)
device:        cpu (5070 Blackwell incompatible w/ torch 2.5; would need torch 2.6+ nightly)
n_steps:       1024
batch_size:    256
total_steps:   1500000 (1.5M cap; auto-stop on convergence around 600k-1M expected)
save_every:    200000
episode_time:  3000.0 seconds (Hack Day demo length)
budget:        Red 150M / Blue 200M (matches expected demo distribution)
```

## Setup

### 1. Verify Chen's desktop state

```powershell
cd C:\Users\xingy\Documents\github\hackathon-stridsledning
git fetch origin
git worktree list
```

### 2. Create dedicated worktree off latest final-demo

```powershell
cd C:\Users\xingy\Documents\github\hackathon-stridsledning
git worktree add .claude\worktrees\s1-retrain -b train-s1-retrain-anti-pac-spam origin/final-demo
cd .claude\worktrees\s1-retrain\team-missile-intercept\backend
git push -u origin train-s1-retrain-anti-pac-spam
```

### 3. Python venv

Try sharing an existing venv from another worktree first (saves 5-10 min):

```powershell
$existingVenv = "..\..\..\..\.claude\worktrees\serene-mcclintock-f152f3\team-missile-intercept\backend\.venv"
if (Test-Path $existingVenv) {
    cmd /c "mklink /J .venv $existingVenv"
} else {
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install --upgrade pip wheel
    pip install numpy==1.26.4
    pip install -r requirements.txt
    pip install "torch>=2.4,<2.6" stable-baselines3 sb3-contrib gymnasium
}
.\.venv\Scripts\Activate.ps1
python -c "import numpy as np, torch, sb3_contrib; print(np.__version__, torch.__version__)"
```

Expect `1.26.4` numpy.

### 4. Smoke before any code change

```powershell
python -m rl.live_ai
```

Expect `Smoke OK.`

## Code changes (all in `team-missile-intercept/backend/rl/env.py`)

### Reward function rewrite

The current `_reward_from_events` on this branch (inherited from final-demo) is the **megamodel doctrine reward**. Replace its body and the surrounding constants with the anti-PAC-spam version.

Find the constants block (around line 50-80, before `_reward_from_events`). Replace with:

```python
# ---- Anti-PAC-spam reward shaping (S1 retrain, 2026-04-27) ----
# Goal: hard-discourage PAC-2/PAC-3 vs drone/cruise (no AOE redemption).
# Goal: let SAM tier (RBS-70 / SLS / SLM) gamble on drone — spend penalty
#       handles single-shot waste, AOE multi-kill recovers via per-kill
#       intercept reward.
# Goal: prefer CIWS for drone via small additive bonus.
# Goal: keep cheap-on-hard gamble bonus (CIWS/SAM vs ballistic/HGV).
# Goal: keep head-on bonus but only triggered for PAC × ballistic/HGV.

# Per-kill DOCTRINE PENALTY for forbidden expensive-on-cheap intercepts
# (negative values → severe penalty stacks on top of base intercept reward)
DOCTRINE_PENALTY = {
    (InterceptorType.HIT_TO_KILL, ThreatType.DRONE):      -5.0,
    (InterceptorType.HIT_TO_KILL, ThreatType.CRUISE_SUB): -2.0,
    (InterceptorType.LONG_SAM,    ThreatType.DRONE):      -3.0,
    (InterceptorType.LONG_SAM,    ThreatType.CRUISE_SUB): -1.0,
}

# Per-kill DOCTRINE BONUS — cheap-on-hard gamble or CIWS preference
DOCTRINE_BONUS = {
    # CIWS preference for drone — small additive nudge
    (InterceptorType.CIWS, ThreatType.DRONE): +0.05,
    # Cheap-on-hard gamble bonuses
    (InterceptorType.CIWS,       ThreatType.BALLISTIC): +2.0,
    (InterceptorType.CIWS,       ThreatType.HGV):       +2.0,
    (InterceptorType.SHORT_SAM,  ThreatType.BALLISTIC): +1.0,
    (InterceptorType.IRIS_T_SLS, ThreatType.BALLISTIC): +1.0,
    (InterceptorType.MED_SAM,    ThreatType.BALLISTIC): +1.0,
}

# Head-on bonus — only for PAC-2/PAC-3 vs ballistic/HGV intercepts.
# Rewards the geometric advantage of head-on engagement (lower miss rate).
HEAD_ON_WEIGHT = 0.5

# Leak tier weights (V4 CIWS-active variant — drone leaks bumped 2.0→4.0)
LEAK_TIER_WEIGHTS = {
    "hgv": 8.0,
    "ballistic": 6.0,
    "cruise_sub": 3.0,
    "drone": 4.0,
}

# Spend penalty — moderate (V4 was 0.05; megamodel was 0.5; 0.15 is balanced)
SPEND_PENALTY_PER_M = 0.15
```

Then replace `_reward_from_events`:

```python
def _reward_from_events(self, events: List[dict]) -> float:
    """Per-tick dense shaping (S1 retrain, anti-PAC-spam, 2026-04-27).

    Layered signal:
      1. Intercept event:
         - Base: threat.usd_cost / 1e6
         - + DOCTRINE_BONUS[(inter_kind, threat_kind)]    (CIWS-on-drone, cheap-on-hard)
         - + DOCTRINE_PENALTY[(inter_kind, threat_kind)]  (PAC-on-drone severe penalty)
         - + HEAD_ON_WEIGHT × base × max(0, -cos_angle)   (PAC × ballistic/HGV only)
         - Zeroed out entirely if threat targets a dead base (V4 inherit)
      2. Leak event:
         - tier_weight × dmg × base_weight  (military leaks)
         - base_weight = n_initial / n_alive (3:1.0, 2:1.5, 1:3.0) — V4 mirror
      3. Ground-crash credit: +0.2 (unchanged)

    Spend penalty is applied per-step in step() via SPEND_PENALTY_PER_M.
    """
    import math
    r = 0.0

    # Base-weight scaling (V4 mirror: protect last alive base 3× harder)
    military_subtypes = ('base', 'air_base')
    n_alive = max(1, sum(
        1 for s in sites_module.SOUTH_SITES
        if s.subtype in military_subtypes and s.hp > 0
    ))
    n_initial = max(1, sum(
        1 for s in sites_module.SOUTH_SITES
        if s.subtype in military_subtypes
    ))
    base_weight = n_initial / n_alive  # 3:1.0, 2:1.5, 1:3.0

    for ev in events:
        et = ev.get("type")

        if et == "intercept":
            tid = ev.get("threat")
            iid = ev.get("interceptor")
            threat = self.world.threats.get(tid) if tid is not None else None
            inter = self.world.interceptors.get(iid) if iid is not None else None
            if threat is None or inter is None:
                r += 1.0  # fallback (rare)
                continue

            # Dead-base zero-out (V4 inherit from megamodel)
            target_site_id = getattr(threat, '_target_site_id', None)
            if target_site_id is not None:
                target_site = sites_module.find_site_by_id(target_site_id)
                if target_site is not None and target_site.hp <= 0:
                    continue

            try:
                spec = self._threat_spec_by_str(threat.state.kind)
                base_value = spec.usd_cost / 1e6
            except KeyError:
                base_value = 1.0

            try:
                interceptor_kind = InterceptorType(inter.state.kind)
                threat_kind = ThreatType(threat.state.kind)
            except (KeyError, ValueError):
                r += base_value
                continue

            r_intercept = base_value
            r_intercept += DOCTRINE_BONUS.get((interceptor_kind, threat_kind), 0.0)
            r_intercept += DOCTRINE_PENALTY.get((interceptor_kind, threat_kind), 0.0)

            # Head-on bonus (PAC-2/PAC-3 vs ballistic/HGV only)
            if (interceptor_kind in (InterceptorType.LONG_SAM, InterceptorType.HIT_TO_KILL)
                    and threat_kind in (ThreatType.BALLISTIC, ThreatType.HGV)):
                t_vel = threat.state.vel
                i_vel = inter.state.vel
                t_speed_sq = t_vel[0]**2 + t_vel[1]**2 + t_vel[2]**2
                i_speed_sq = i_vel[0]**2 + i_vel[1]**2 + i_vel[2]**2
                if t_speed_sq > 1.0 and i_speed_sq > 1.0:
                    cos_angle = (
                        t_vel[0]*i_vel[0] + t_vel[1]*i_vel[1] + t_vel[2]*i_vel[2]
                    ) / (math.sqrt(t_speed_sq) * math.sqrt(i_speed_sq))
                    head_on_factor = max(0.0, -cos_angle)
                    r_intercept += base_value * HEAD_ON_WEIGHT * head_on_factor

            r += r_intercept

        elif et == "leak":
            dmg = ev.get("damage", 0)
            kind = ev.get("kind", "")
            tier = LEAK_TIER_WEIGHTS.get(kind, 4.0)
            site_name = ev.get("site", "")
            site = next(
                (s for s in sites_module.SOUTH_SITES if s.name == site_name),
                None,
            )
            if site is not None and site.subtype in military_subtypes:
                r -= float(dmg) * tier * base_weight  # base-weight scaling
            else:
                r -= float(dmg) * tier  # civilian leak — no scaling

        elif et == "ground_crash" and ev.get("threat") is not None:
            r += 0.2

    return r
```

Then update spend penalty in `step()` (look for the existing `reward = event_reward - spent / 1e6 * <CONSTANT>`):

```python
reward = event_reward - spent / 1e6 * 0.15  # was 0.5 (megamodel) or 0.05 (V4)
```

### Sanity check

```powershell
python -m rl.live_ai
python -c "
from rl.env import (
    DOCTRINE_PENALTY, DOCTRINE_BONUS, HEAD_ON_WEIGHT,
    LEAK_TIER_WEIGHTS, SPEND_PENALTY_PER_M,
)
print('penalties:', len(DOCTRINE_PENALTY))
print('bonuses:', len(DOCTRINE_BONUS))
print('head_on:', HEAD_ON_WEIGHT)
print('drone_leak:', LEAK_TIER_WEIGHTS['drone'])
print('spend:', SPEND_PENALTY_PER_M)
"
```

Expect:
```
penalties: 4
bonuses: 6
head_on: 0.5
drone_leak: 4.0
spend: 0.15
```

If anything off, fix before launching training.

## Training launch

Create the run dir + launch script:

```powershell
$RUN_NAME = "blue_s1_retrain"
$RUN_DIR = "rl\runs\blue_local\$RUN_NAME"
New-Item -ItemType Directory -Force -Path $RUN_DIR
pip freeze > "$RUN_DIR\pip_freeze.txt"

# Save launch command for audit
$launchCmd = @"
python -m rl.train ``
  --total-steps 1500000 ``
  --n-envs 30 ``
  --n-steps 1024 ``
  --batch-size 256 ``
  --n-epochs 4 ``
  --lr 3e-4 ``
  --gamma 0.995 ``
  --gae-lambda 0.95 ``
  --ent-coef 0.01 ``
  --clip-range 0.2 ``
  --episode-time-limit 3000.0 ``
  --device cpu ``
  --save-every 200000 ``
  --run-name $RUN_NAME ``
  --layouts-pool-slots C ``
  --red-mode-pool scripted ``
  --blue-budget 200000000 ``
  --red-budget 150000000
"@
$launchCmd | Out-File "$RUN_DIR\launch_cmd.txt" -Encoding utf8
```

**Every flag matters — skipping any resurrects bugs we already fixed**:
- `--blue-budget 200000000 --red-budget 150000000` — config.py default is 120M/100M (different from training distribution)
- `--episode-time-limit 3000.0` — Hack Day demo length, not megamodel's 5000s
- `--layouts-pool-slots C` — single Layout C only
- `--red-mode-pool scripted` — ScriptedRed only
- `--n-envs 30` — Chen's 5950X has 32 threads, leave 2 for OS
- `--device cpu` — 5070 Blackwell incompatible with current torch

Now launch (use `run_in_background: true` since this runs ~1-2 hours):

```powershell
python -m rl.train `
  --total-steps 1500000 `
  --n-envs 30 `
  --n-steps 1024 `
  --batch-size 256 `
  --n-epochs 4 `
  --lr 3e-4 `
  --gamma 0.995 `
  --gae-lambda 0.95 `
  --ent-coef 0.01 `
  --clip-range 0.2 `
  --episode-time-limit 3000.0 `
  --device cpu `
  --save-every 200000 `
  --run-name $RUN_NAME `
  --layouts-pool-slots C `
  --red-mode-pool scripted `
  --blue-budget 200000000 `
  --red-budget 150000000 `
  *> "$RUN_DIR\training.log"
```

Track the bash background task ID. Use `BashOutput` periodically to read log.

## Monitoring + early stop on convergence

Every 5-10 minutes (or after notable elapsed time), check progress:

```powershell
Get-Content rl\runs\blue_local\blue_s1_retrain\training.log -Tail 30
```

Look for:
- `ep_rew_mean`: should appear after first ~500k steps (env runs long episodes)
- `fps`: ~150-300 expected on 5950X with n_envs 30
- `total_timesteps`: progress indicator

**Convergence check** — implement in PowerShell or Python helper. Reuse the exact heuristic from the megamodel run (last 5 ep_rew_mean values: range < 20.0, latest not new global max, ≥2 distinct values):

```powershell
# Simple inline check
$logPath = "rl\runs\blue_local\blue_s1_retrain\training.log"
$matches = Select-String -Path $logPath -Pattern "ep_rew_mean\s*\|\s*([-\d.eE+]+)"
$values = $matches.Matches | ForEach-Object { [double]$_.Groups[1].Value }
if ($values.Count -ge 5) {
    $last5 = $values[-5..-1]
    $span = ($last5 | Measure-Object -Maximum -Minimum).Maximum - ($last5 | Measure-Object -Maximum -Minimum).Minimum
    $globalMax = ($values | Measure-Object -Maximum).Maximum
    $latestIsNewMax = $last5[-1] -ge $globalMax
    $distinctCount = ($last5 | Select-Object -Unique).Count
    $converged = ($span -lt 20.0) -and (-not $latestIsNewMax) -and ($distinctCount -ge 2)
    Write-Host "last5=$last5 span=$span new_max=$latestIsNewMax distinct=$distinctCount converged=$converged"
}
```

When converged: **send SIGINT to the python process** so SB3 saves the final model:

```powershell
$pid = (Get-Process python | Where-Object { $_.CommandLine -like "*rl.train*" }).Id
if ($pid) {
    # Windows PowerShell doesn't have direct SIGINT — use Stop-Process or send Ctrl-C
    # SB3 catches KeyboardInterrupt; Stop-Process is harder to graceful-stop
    # Cleanest: use taskkill /F as last resort, but try Ctrl-C signal first via:
    Add-Type -Name 'Console' -Namespace 'PInvoke' -MemberDefinition '
        [DllImport("kernel32.dll")] public static extern bool GenerateConsoleCtrlEvent(uint dwCtrlEvent, uint dwProcessGroupId);
    '
    [PInvoke.Console]::GenerateConsoleCtrlEvent(0, $pid)  # Ctrl-C
    Start-Sleep -Seconds 10  # let SB3 save
}
```

If Ctrl-C signal doesn't work in PowerShell context (it's flaky on Windows), let it run to HARD_CAP (1.5M). The wall time is what limits — at 200 fps × 30 envs = 6000 transitions/sec, 1.5M steps = ~250 sec... no that can't be right. At 1500 fps (estimated megamodel-like throughput), 1.5M / 1500 = 1000 sec = 17 min. Even with overhead 1-2h max for full HARD_CAP. So just letting it run to cap is fine.

Actually: total fps on 5950X with cap-72 + n_envs 30 is unknown until first iter logs. After first iter, project: HARD_CAP / actual_fps = wall time. If projection > 2.5h, **stop early at the latest 200k checkpoint**.

## Post-training — register + push

After training completes (natural end at HARD_CAP, or SIGINT-stopped):

```powershell
# Verify model saved
ls "$RUN_DIR\model.zip"

# Quick load test
python -c "from sb3_contrib import MaskablePPO; m = MaskablePPO.load('$RUN_DIR/model.zip', device='cpu'); print('OK', m.observation_space['threats'].shape, m.action_space)"
```

Expect `OK (72, 12) MultiDiscrete([73 73 ...])`.

### Register in dropdown

Edit `team-missile-intercept/backend/server.py`. Find `BLUE_AI_MODELS` list, add as the LAST entry (after megamodel S3):

```python
("s1_retrain", "RL S1 Retrain (anti-PAC-spam, V4-style reward)", "rl/runs/blue_local/blue_s1_retrain/model.zip"),
```

Edit `team-missile-intercept/frontend/index.html`. Find `<select id="blue-ai-select">` block, add as last option (after `megamodel_s3`):

```html
          <option value="s1_retrain">Blue: RL S1 Retrain (anti-PAC-spam)</option>
```

### Commit + push

```powershell
git add team-missile-intercept/backend/server.py
git add team-missile-intercept/frontend/index.html
git add team-missile-intercept/backend/rl/env.py
git add team-missile-intercept/backend/rl/runs/blue_local/blue_s1_retrain/

git commit -m "feat(rl): S1 retrain with anti-PAC-spam reward

Single-stage cap-72 training on Layout C + ScriptedRed (matches
megamodel S1's training distribution) with substantially redesigned
reward to prevent the PAC-spam regression that all megamodel stages
exhibited.

Reward design changes vs megamodel S1:
- DOCTRINE_PENALTY (NEW): per-kill flat penalty for PAC-on-drone /
  PAC-on-cruise (HIT_TO_KILL/drone: -5.0, etc.) — no AOE escape since
  HTK class can't redeem via multi-kill.
- DOCTRINE_BONUS (NEW): per-kill bonus for CIWS-on-drone (+0.05) and
  cheap-on-hard gambles (CIWS-on-ballistic +2.0, etc.).
- Spend penalty 0.5/M -> 0.15/M (between V4's 0.05 and megamodel's
  0.5, balances 'don't waste' against 'don't be paralyzed').
- Episode time 5000s -> 3000s (Hack Day demo length).
- Drone leak weight 2.0 -> 4.0 (CIWS-active V4 emphasis).
- Head-on bonus retained but only triggers on PAC-2/PAC-3 vs
  ballistic/HGV (correct gating).
- Base-weight scaling retained (V4 mirror; protect last-alive bases).

Trained on Chen's Ryzen 5950X local desktop, n_envs=30, ~1-2h wall.
Auto-pushed to GitHub for venue testing before 17:00 Finale.

Targets V4 + Layout C + Red 150M / Blue 200M deployment distribution
exactly to avoid distribution-shift regression at deployment."

git push origin train-s1-retrain-anti-pac-spam
```

## End-of-session summary (paste in chat)

When done, output:

```
== S1 Retrain Done ==
Branch tip: <hash>
Wall clock: <X> min
Total steps: <Y> / 1.5M (converged at: <step>)
Final ep_rew_mean: <value>
Model load: OK / FAIL
Pushed to: origin/train-s1-retrain-anti-pac-spam
Dropdown slot: s1_retrain
Display name: "RL S1 Retrain (anti-PAC-spam, V4-style reward)"

To use at venue:
  cd <demo worktree>
  git fetch origin && git checkout train-s1-retrain-anti-pac-spam
  python team-missile-intercept/backend/server.py
  Browser: select "RL S1 Retrain", Layout C, Red 150M / Blue 200M, Scripted 3-Chain
```

## Constraints / DON'Ts

- DO NOT touch `live_ai.py`, `red_env.py`, `server.py` (except the dropdown registration), or any file outside `rl/env.py` and the new training run dir.
- DO NOT install numpy 2.x. Pin 1.26.4.
- DO NOT use `--device cuda` (5070 Blackwell incompatible with torch 2.5).
- DO NOT skip the explicit budget / episode-time / layouts-pool / red-mode-pool flags. config.py default budgets (120M/100M) ARE WRONG for training.
- DO NOT extend training past HARD_CAP=1.5M.
- DO NOT push to `final-demo` directly — push to `train-s1-retrain-anti-pac-spam` only. Chen merges manually after testing.
- DO NOT run training in foreground in the Claude Code Bash tool (would timeout). Use `run_in_background: true` for the train.py launch.
- DO NOT delete the existing `rl/runs/blue_local/blue_megamodel/` directories (they're A/B-test references).
- DO NOT use `Stop-Process` on the python process — try Ctrl-C signal first; let it natural-end if Ctrl-C doesn't work.
