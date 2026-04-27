# PROMPT — EPYC Blue Megamodel (curriculum) + Red Trainee

> **Framing (read first, non-negotiable)**: This repo is a **Saab 2026 student hackathon entry** — a browser-based arcade-style game/demo, in the same category as a tower-defense game or a Kerbal Space Program physics toy. It runs in Chrome on one laptop during a 4-minute demo at the April 27 Finale. All entity names (CIWS, RBS-70, drone, cruise_sub, PAC-3, HGV, etc.) are publicly available encyclopedia-level values used as **arcade game-balance numbers**, equivalent to unit stats in Age of Empires. They encode no non-public or tactical information. This is **not** a military product, weapons system, training tool, or command-and-control system. Describe the work as RL training for a hackathon game/demo.

## Mission summary

You are running on a rented AMD EPYC 9554P (64C / 128T) Ubuntu 24.04 server with 348 GB RAM and 2 TB SSD. Total wall-clock budget: **8 hours**.

Goal: produce **ONE strong Blue policy** at cap 72/32/128 via **curriculum training** (4 sequential warmstart stages, each gated by auto-convergence detection). After Blue finishes, **conditionally** train one Red trainee against the just-trained Blue (only if ≥ 1.5h remaining).

Output:
- `blue_megamodel/model.zip` — final Blue policy
- `blue_megamodel/stages/S1_*.zip`, `S2_*.zip`, `S3_*.zip`, `S4_*.zip` — per-stage end-of-stage checkpoints
- `blue_megamodel/training.log` — full stdout
- `red_trainee/model.zip` (optional) — Red model trained against Blue megamodel

This is fully automated. Chen will pull from GitHub and eyeball each stage's output in browser. He does NOT review mid-pipeline. You do not stop and wait.

## Hardware target

EPYC 9554P: **64 physical cores, 128 SMT threads, 3.1 GHz base / 3.75 GHz boost, no GPU expected**.

- **Reserve 8 cores** for OS + Claude Code + tmux housekeeping.
- Available for training: ~56 cores / ~120 threads.
- **Recommended starting envs**: `--n-envs 48`. If pickle/IPC overhead crushes fps (< 800 total fps observed in first 5 min), drop to 32. If fps > 3000 try 64. **Tune ONCE early, then leave it.**
- Training is CPU-bound (small policy net, Python sim hot loop). `--device cpu` is correct; do NOT enable CUDA unless you have verified torch sees a working GPU.

## Setup tasks

### 1. System packages

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv python3-pip tmux htop rsync build-essential curl ca-certificates
```

### 2. Clone and branch

```bash
cd ~
git clone https://github.com/Heffri/hackathon-stridsledning.git
cd hackathon-stridsledning
git checkout -b train-megamodel-cap72 origin/final-demo
git push -u origin train-megamodel-cap72
```

### 3. Python venv with pinned numpy

```bash
cd team-missile-intercept/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
# CRITICAL: pin numpy 1.26.4 BEFORE other deps so pip doesn't pull numpy 2.x.
pip install numpy==1.26.4
pip install -r requirements.txt
pip install "torch>=2.4,<2.6" stable-baselines3 sb3-contrib gymnasium

# Sanity check:
python -c "import numpy as np, torch, sb3_contrib; print(np.__version__, torch.__version__)"
```

Expect `1.26.4 2.4.x` or `2.5.x`. If numpy is 2.x, **stop and reinstall** — Boyu-style numpy-2 pickle issues haunt the model later.

### 4. Save pip freeze for reproducibility

```bash
mkdir -p rl/runs/blue_local/blue_megamodel
pip freeze > rl/runs/blue_local/blue_megamodel/pip_freeze.txt
```

### 5. Sanity smoke before any code change

```bash
python -m rl.live_ai
```

Should print `Smoke OK.` Confirms repo runs as-is on Ubuntu before we touch anything.

## Code changes (all in `backend/rl/env.py`)

### A. Cap bump: 120/60/160 → 72/32/128

In `team-missile-intercept/backend/rl/env.py` (around lines 50-55):

```python
# Was: MAX_THREATS = 120, MAX_LAUNCHERS = 60, MAX_INTERCEPTORS = 160
MAX_THREATS = 72
MAX_LAUNCHERS = 32
MAX_INTERCEPTORS = 128
```

### B. Reward function rewrite (`_reward_from_events`)

Replace the entire body with the version below. Key additions vs current V4 reward:
1. **Doctrine multiplier** on intercept (gamble bonuses for cheap-on-hard, light penalty for SAM-on-drone)
2. **Head-on bonus** for PAC-2/PAC-3 vs ballistic/HGV (geometry-aware)
3. **V4 base-weight scaling** on leak penalty (`n_initial / n_alive`, leaks scale up to 3× as bases die)
4. **Dead-base zero-out** on intercept reward (don't reward intercepting threats targeting dead bases)
5. **Budget-aware spend penalty** (multiplied in `step()` — see section C)

```python
import math  # add to imports if not already there

# ---- Reward shaping constants (megamodel doctrine reward 2026-04-26) ----
DOCTRINE_MULTIPLIER = {
    # Gamble bonuses (cheap interceptor on hard target — paid off)
    (InterceptorType.CIWS,        ThreatType.BALLISTIC): 2.0,
    (InterceptorType.CIWS,        ThreatType.HGV):       2.0,
    (InterceptorType.SHORT_SAM,   ThreatType.BALLISTIC): 1.5,
    (InterceptorType.IRIS_T_SLS,  ThreatType.BALLISTIC): 1.5,
    (InterceptorType.MED_SAM,     ThreatType.BALLISTIC): 2.0,
    (InterceptorType.MED_SAM,     ThreatType.HGV):       1.3,
    # Force CIWS-only-on-drone — light penalty pulls SAM tier toward cruise
    (InterceptorType.SHORT_SAM,   ThreatType.DRONE):     0.7,
    (InterceptorType.IRIS_T_SLS,  ThreatType.DRONE):     0.7,
}
# All other (interceptor, threat) pairs use multiplier 1.0:
# - canonical (CIWS->drone, *->cruise, PAC-2/PAC-3->ballistic/HGV)
# - wasteful (PAC-3->drone) — handled by spend penalty alone

HEAD_ON_WEIGHT = 0.5            # max head-on bonus = 50% of base intercept reward
LEAK_TIER_WEIGHTS = {
    "hgv": 8.0,
    "ballistic": 6.0,
    "cruise_sub": 3.0,
    "drone": 2.0,
}


def _reward_from_events(self, events: List[dict]) -> float:
    """Per-tick dense shaping with doctrine reward (megamodel 2026-04-26).

    Layered signal:
      1. Intercept event:
         - Base reward: threat.usd_cost / 1e6
         - x DOCTRINE_MULTIPLIER for (interceptor, threat) — 1.3-2.0x for
           gamble pairs, 0.7x for SAM-on-drone, 1.0x default
         - + HEAD_ON_WEIGHT * base * head_on_factor for PAC-2/PAC-3 vs
           ballistic/HGV (head_on_factor = max(0, -cos(angle)))
         - Zeroed entirely if threat targets a dead base (V4 inherit)
      2. Leak event:
         - tier_weight * dmg * base_weight (military leaks only)
         - base_weight = n_initial / n_alive — protect last-alive bases harder
      3. Ground-crash credit: +0.2 (unchanged)

    Caller must invoke this BEFORE world.prune_dead so events resolve.
    """
    r = 0.0

    # Base-weight scaling (V4 inherit).
    military_subtypes = ('base', 'air_base')
    n_alive = max(1, sum(
        1 for s in sites_module.SOUTH_SITES
        if s.subtype in military_subtypes and s.hp > 0
    ))
    n_initial = max(1, sum(
        1 for s in sites_module.SOUTH_SITES
        if s.subtype in military_subtypes
    ))
    base_weight = n_initial / n_alive  # 3 alive: 1.0, 2 alive: 1.5, 1 alive: 3.0

    for ev in events:
        et = ev.get("type")

        if et == "intercept":
            tid = ev.get("threat")
            iid = ev.get("interceptor")
            threat = self.world.threats.get(tid) if tid is not None else None
            inter = self.world.interceptors.get(iid) if iid is not None else None
            if threat is None or inter is None:
                r += 1.0  # fallback to old behaviour
                continue

            # V4 inherit: zero reward if target base already dead.
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
            multiplier = DOCTRINE_MULTIPLIER.get(
                (interceptor_kind, threat_kind), 1.0,
            )
            r_intercept = base_value * multiplier

            # Head-on bonus for PAC-2/PAC-3 vs ballistic/HGV.
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
            tier = LEAK_TIER_WEIGHTS.get(kind, 2.0)
            site_name = ev.get("site", "")
            site = next(
                (s for s in sites_module.SOUTH_SITES if s.name == site_name),
                None,
            )
            if site is not None and site.subtype in military_subtypes:
                r -= float(dmg) * tier * base_weight
            else:
                r -= float(dmg) * tier  # civilian: no scaling

        elif et == "ground_crash" and ev.get("threat") is not None:
            r += 0.2

    return r
```

### C. Budget-aware spend penalty (in `step()`)

Find the line in `step()` (around line 280):

```python
reward = event_reward - spent / 1e6 * 0.05  # weak efficiency penalty per $M spent
```

Replace with:

```python
# Budget-aware spend penalty (megamodel 2026-04-26):
# When Blue has more budget than Red, spend penalty drops (Blue can afford
# expensive defense to relieve CIWS pressure). When Blue is poor relative
# to Red, spend penalty rises (must conserve). Clamped 0.5x..2.0x.
budget_ratio = self.world.blue_budget / max(1.0, float(self.world.red_budget))
spend_modifier = max(0.5, min(2.0, 1.0 / max(0.01, budget_ratio)))
reward = event_reward - spent / 1e6 * 0.5 * spend_modifier
```

Effects:
- Blue $200M / Red $50M (ratio=4): modifier=0.25→clamp **0.5**, spend penalty effective **0.25/M** (afford expensive)
- Blue $50M / Red $150M (ratio=0.33): modifier=3.0→clamp **2.0**, spend penalty effective **1.0/M** (conserve)
- Both $200M: modifier=1.0, spend penalty 0.5/M (default)

### D. Sanity check before launching curriculum

```bash
cd team-missile-intercept/backend
python -m rl.live_ai
```

Should still print `Smoke OK.`. Then:

```bash
python -c "
from rl.env import (
    MAX_THREATS, MAX_LAUNCHERS, MAX_INTERCEPTORS,
    DOCTRINE_MULTIPLIER, HEAD_ON_WEIGHT,
)
print('caps:', MAX_THREATS, MAX_LAUNCHERS, MAX_INTERCEPTORS)
print('multiplier entries:', len(DOCTRINE_MULTIPLIER))
print('head_on:', HEAD_ON_WEIGHT)
"
```

Expect `caps: 72 32 128`, `multiplier entries: 8`, `head_on: 0.5`.

## Convergence detection (helper script)

Create `team-missile-intercept/backend/scripts/check_convergence.py`:

```python
"""Parse training log for ep_rew_mean trajectory; decide if converged.

Convergence rule (matches Chen's spec):
  1. Need at least 3 logged ep_rew_mean values to judge (i.e., past 600k
     transitions assuming 200k log frequency).
  2. Range of last 3 ep_rew_mean values must be < 5.0 (absolute units;
     ep_rew_mean lives in -100..+50 range typically).
  3. Latest must NOT be a new global max (trend is flat, not still climbing).

Exit codes:
  0  converged — caller advances to next stage
  1  not converged yet — caller continues training
  2  log unparsable / no data — caller continues training
"""
import re
import sys
from pathlib import Path

CONVERGENCE_RANGE = 5.0


def parse_ep_rew_means(log_path: Path) -> list:
    """Return list of ep_rew_mean values in chronological order."""
    pattern = re.compile(r"ep_rew_mean\s*\|\s*([-\d.eE+]+)")
    values = []
    with log_path.open("r") as f:
        for line in f:
            m = pattern.search(line)
            if m:
                try:
                    values.append(float(m.group(1)))
                except ValueError:
                    pass
    return values


def main():
    if len(sys.argv) != 2:
        print("usage: check_convergence.py <training.log>", file=sys.stderr)
        sys.exit(2)
    log = Path(sys.argv[1])
    if not log.exists():
        print(f"log not found: {log}", file=sys.stderr)
        sys.exit(2)
    values = parse_ep_rew_means(log)
    if len(values) < 3:
        print(f"not enough ep_rew_mean entries yet ({len(values)})", file=sys.stderr)
        sys.exit(1)
    last3 = values[-3:]
    span = max(last3) - min(last3)
    is_new_max = last3[-1] >= max(values)
    converged = (span < CONVERGENCE_RANGE) and (not is_new_max)
    print(f"last3={last3} span={span:.2f} new_max={is_new_max} converged={converged}")
    sys.exit(0 if converged else 1)


if __name__ == "__main__":
    main()
```

`chmod +x scripts/check_convergence.py`.

## Phase 1: Blue Megamodel curriculum

All 4 stages share these constants:

```bash
# Common training flags
N_ENVS=48                      # adjust after first 5 min if fps off
N_STEPS=1024
BATCH_SIZE=256
N_EPOCHS=4
LR=3e-4
GAMMA=0.995
GAE_LAMBDA=0.95
ENT_COEF=0.01
CLIP_RANGE=0.2
EPISODE_LIMIT=5000.0           # bumped from 3000s per Chen
BLUE_BUDGET=200000000          # $200M
RED_BUDGET=150000000           # $150M (bumped per Chen)
DEVICE=cpu

# Run dir
RUN_DIR=rl/runs/blue_local/blue_megamodel
mkdir -p ${RUN_DIR}/stages
```

**Per-stage convergence loop pattern** (you'll repeat this skeleton for each stage):

```bash
# Stage skeleton (pseudo-code — adapt per stage):
INCREMENT=200000     # train 200k steps per increment
HARD_CAP=2000000     # max 2M steps per stage
ACCUMULATED=0
WARMSTART_FROM=...   # path to prev stage's final ckpt (or "" for S1)

while [ $ACCUMULATED -lt $HARD_CAP ]; do
  # train INCREMENT more steps
  python -m rl.train \
    --total-steps $INCREMENT \
    --warmstart "$WARMSTART_FROM" \
    [other stage-specific flags] \
    --run-name "${RUN_NAME}_inc_${ACCUMULATED}" \
    2>&1 | tee -a ${RUN_DIR}/stages/${STAGE}_training.log

  # update warmstart to point to just-saved model
  WARMSTART_FROM=${RUN_DIR}/stages/${STAGE}_inc_${ACCUMULATED}/model.zip
  ACCUMULATED=$((ACCUMULATED + INCREMENT))

  # check convergence
  python scripts/check_convergence.py ${RUN_DIR}/stages/${STAGE}_training.log
  if [ $? -eq 0 ]; then
    echo "Stage ${STAGE} converged at ${ACCUMULATED} steps"
    break
  fi
done
# copy final increment's model as the stage end-of-stage ckpt
cp ${WARMSTART_FROM} ${RUN_DIR}/stages/${STAGE}_final.zip
```

(You may also implement this as a single Python driver script `scripts/run_megamodel.py` — that's likely cleaner. Either way is fine; use whichever is more reliable.)

After every stage end, **immediately push to GitHub** so Chen can git pull and start eyeballing while later stages run:

```bash
git add rl/runs/blue_local/blue_megamodel/stages/${STAGE}_*
git add rl/runs/blue_local/blue_megamodel/training.log
git commit -m "feat(rl): megamodel ${STAGE} converged at ${ACCUMULATED} steps"
git push origin train-megamodel-cap72
```

### Stage S1 — Layout C cold start vs ScriptedRed only

**Goal**: model learns the basics on the demo's primary layout against the demo's primary opponent.

```bash
STAGE=S1
INCREMENT=200000
HARD_CAP=2000000
WARMSTART_FROM=""   # cold start

# Stage-specific flags:
EXTRA_FLAGS=(
  --layouts-pool-slots C
  --red-mode-pool scripted
)
```

Expected wall: 30-90 min. Convergence often hits at 600k-1.2M for a single-layout single-opponent task.

### Stage S2 — Add Layout D (warmstart from S1)

**Goal**: model retains C skills and extends to D. Train on `C D` 50/50 mix vs ScriptedRed only.

```bash
STAGE=S2
INCREMENT=200000
HARD_CAP=2000000        # additional, on top of S1's accumulated steps
WARMSTART_FROM=${RUN_DIR}/stages/S1_final.zip

EXTRA_FLAGS=(
  --layouts-pool-slots C D
  --red-mode-pool scripted
)
```

Expected wall: 30-60 min. Warmstart accelerates.

### Stage S3 — Add multi-Red opponents (warmstart from S2)

**Goal**: model handles ScriptedRed + rule-based RedAI + an old learned Red HGV-spammer. The learned Red provides high-density HGV practice — Blue's reward already favours head-on PAC-3 vs HGV, so behavior naturally adapts.

#### Find the old learned Red opponent

Before training, scan for available Red models:

```bash
find rl/runs -name "model.zip" -path "*red*" 2>/dev/null
find rl/runs -name "model.zip" -path "*Red*" 2>/dev/null
```

Pick the one with the most training. Heuristic: largest training.log file size, OR most recent file that has "red" in path. If the README in `rl/runs/blue_local/_RED_MODELS_INDEX.md` exists, read it for guidance.

Verify the chosen Red model loads and is compatible with the current cap-72 env. If it was trained at 30/15/40 or 96/24/128, the live_ai adapter (`LearnedRedAI._adapt_obs_for_model`) handles it — but you can sanity-check:

```bash
python -c "
import os
from rl.live_ai import LearnedRedAI
from sim.scenarios import build_default_scenario

red_path = os.environ['RED_PATH']
scn = build_default_scenario(auto_start=False)
red = LearnedRedAI(red_path, scn)
print(f'OK: loaded Red from {red_path}')
print(f'  model expects threats={red._model_max_threats}, launchers={red._model_max_launchers}, interceptors={red._model_max_interceptors}')
print(f'  adapter active: {red._needs_adapter}')
"
```

If load fails (numpy mismatch, missing keys, etc.): **skip the learned Red** — fall back to S3 with `--red-mode-pool scripted scripted rule` (no learned). Document this in the report. Don't block the pipeline waiting to fix Red compat.

#### Stage S3 launch

```bash
STAGE=S3
INCREMENT=200000
HARD_CAP=2000000
WARMSTART_FROM=${RUN_DIR}/stages/S2_final.zip
LEARNED_RED_PATH=...   # path from the scan above; empty string if none usable

EXTRA_FLAGS=(
  --layouts-pool-slots C D
  --red-mode-pool scripted scripted rule learned
)
if [ -n "$LEARNED_RED_PATH" ]; then
  EXTRA_FLAGS+=(--red-policy-path "$LEARNED_RED_PATH")
else
  # Fallback: drop "learned" from the pool
  EXTRA_FLAGS=(
    --layouts-pool-slots C D
    --red-mode-pool scripted scripted rule
  )
fi
```

**Important**: verify `train.py` accepts `--red-policy-path`. If the flag doesn't exist, check `rl/red_env.py` for how Red opponents are wired. As a fallback, set the env var `RED_POLICY_PATH=...` before launching `python -m rl.train` — `live_ai.py` reads it for `LearnedRedAI` construction. Worker: pick whichever path actually works on a 30-second dry run before the full S3 launch.

Expected wall: 30-90 min.

### Stage S4 (CONDITIONAL — only if remaining time ≥ 1.5h)

**Goal**: polish with broader layout pool. Skip if budget tight.

Before launching, check remaining wall:

```bash
ELAPSED=$(($(date +%s) - $START_TIME))
TOTAL_BUDGET=$((8 * 3600))
REMAINING=$((TOTAL_BUDGET - ELAPSED))
if [ $REMAINING -lt 5400 ]; then  # less than 1.5h
  echo "S4 skipped — only ${REMAINING}s remaining; want at least 1.5h"
  cp ${RUN_DIR}/stages/S3_final.zip ${RUN_DIR}/model.zip
  exit 0   # advance to Phase 2 / push
fi
```

If S4 launches:

```bash
STAGE=S4
INCREMENT=200000
HARD_CAP=1000000        # smaller cap — polish only
WARMSTART_FROM=${RUN_DIR}/stages/S3_final.zip

EXTRA_FLAGS=(
  --layouts-pool-slots C C D D E
  --red-mode-pool scripted scripted rule learned
)
# Same learned Red path as S3 (or fallback if S3 fell back)
```

Expected wall: 15-45 min.

### After Phase 1 — finalize Blue

```bash
# The end-of-curriculum model is whichever stage ran last.
LAST_STAGE_FINAL=...   # S4_final.zip if S4 ran, else S3_final.zip
cp $LAST_STAGE_FINAL ${RUN_DIR}/model.zip

# Save launch command + final pip freeze
cat > ${RUN_DIR}/launch_cmd.txt <<EOF
[paste verbatim training launch commands for each stage here]
EOF
pip freeze > ${RUN_DIR}/pip_freeze.txt

# Push final
git add ${RUN_DIR}/
git commit -m "feat(rl): blue megamodel curriculum complete

S1 (Layout C, scripted): converged at ${S1_STEPS} steps
S2 (+ Layout D, scripted): converged at ${S2_STEPS} steps
S3 (+ rule + learned Red): converged at ${S3_STEPS} steps
S4 (+ Layout E): ${S4_STEPS} steps or skipped

Final cumulative steps: ${TOTAL_STEPS}
Wall clock: ${PHASE1_WALL_MIN} min
"
git push origin train-megamodel-cap72
```

## Phase 2: Red Trainee (CONDITIONAL — only if remaining time ≥ 1.5h)

**Goal**: train a new Red AI against the Blue megamodel just produced. Red learns to break through Blue's defense — drone/cruise saturation to suppress, ballistic+HGV to break through. Output goes to `rl/runs/red_local/red_trainee_megamodel/`.

```bash
ELAPSED=$(($(date +%s) - $START_TIME))
REMAINING=$(((8 * 3600) - $ELAPSED))
if [ $REMAINING -lt 5400 ]; then
  echo "Phase 2 skipped — only ${REMAINING}s remaining"
  exit 0
fi

RED_RUN_DIR=rl/runs/red_local/red_trainee_megamodel
mkdir -p $RED_RUN_DIR

# Use red_train.py (existing in repo). Verify its CLI flags first:
python -m rl.red_train --help 2>&1 | head -40

# Adapt the launch to whatever flags red_train.py accepts. Common pattern:
python -m rl.red_train \
  --total-steps 5000000 \
  --n-envs 48 \
  --n-steps 1024 \
  --batch-size 256 \
  --lr 3e-4 \
  --gamma 0.995 \
  --ent-coef 0.01 \
  --episode-time-limit 5000.0 \
  --device cpu \
  --save-every 500000 \
  --run-name red_trainee_megamodel \
  --blue-policy-path ${RUN_DIR}/model.zip \
  --layouts-pool-slots C D \
  --blue-budget 200000000 \
  --red-budget 150000000 \
  2>&1 | tee ${RED_RUN_DIR}/training.log
```

(Worker: if `red_train.py`'s flags differ, adapt. The spirit is: 5M steps, against the trained Blue, on Layout C+D, same budgets.)

After Red converges (or hits 5M):

```bash
git add ${RED_RUN_DIR}/
git commit -m "feat(rl): red trainee trained against blue megamodel

Phase 2: ${RED_STEPS} steps against blue_megamodel/model.zip,
Layout C+D, scripted-derived reward."
git push origin train-megamodel-cap72
```

## Monitoring during the run

Open a SECOND tmux session for periodic peek (don't poll, just check when natural):

```bash
tmux new -s monitor -d
```

To peek:

```bash
tmux capture-pane -t train -p | tail -40
ls -la ${RUN_DIR}/stages/ 2>/dev/null
tail -30 ${RUN_DIR}/training.log | grep -E "ep_rew_mean|approx_kl|fps"
```

What you're watching for:
- **`ep_rew_mean`** climbs monotonically over each stage (with noise). If completely flat after 1M in a stage, something's wrong — abort that stage, save what's there, move on.
- **`approx_kl`** under 0.05 is normal. Spikes > 0.1 mean the policy is shifting too fast.
- **`fps`** steady at the level you tuned to. If it tanks mid-run, an env probably hung.

Don't sleep-poll. Run check naturally when convenient.

## Push & report

After Phase 1 (and Phase 2 if it ran), write `team-missile-intercept/progress/TRAIN_MEGAMODEL_REPORT.md`:

1. **Hardware reality**: actual fps, n_envs settled on, total wall clock.
2. **Per-stage trajectory**: for S1/S2/S3/S4, ep_rew_mean at every 200k checkpoint, plus convergence step.
3. **Reward changes summary**: cap, doctrine multipliers, head-on, base-weight, dead-base, budget-aware spend.
4. **Learned Red opponent in S3**: which model was used, or note "fell back to scripted+rule only".
5. **Phase 2 status**: ran / skipped (with remaining-time reason). If ran, brief Red trajectory.
6. **Compatibility notes**: numpy/torch/sb3 versions for Chen to match on Windows.
7. **Branch tip commit hash**.

Keep under 400 lines.

## End-of-session summary (paste in chat)

- Branch tip commit hash
- Total wall clock used / 8h budget
- Per-stage convergence steps: S1=X, S2=Y, S3=Z, S4=W (or skipped)
- Final Blue model location
- Phase 2: ran (X steps) / skipped (reason)
- **Verbatim training launch command from training.log** for each stage. Missing flag = retrain invalid.
- Hardware fps actually observed
- Any open issues for Chen

## Constraints / DON'Ts

- DO NOT skip the explicit `--blue-budget 200000000 --red-budget 150000000` CLI flags. config.py defaults are 100M/120M (demo-safe), training-side budgets MUST override via CLI. **Every one of these flags matters — skipping any resurrects a bug we already fixed.**
- DO NOT install numpy 2.x. Pin 1.26.4 BEFORE other deps.
- DO NOT run training in Claude Code foreground — use tmux. Claude session closing kills the foreground process.
- DO NOT touch `live_ai.py`, `server.py`, frontend, or any file outside `rl/env.py`, `scripts/check_convergence.py`, and your training driver.
- DO NOT register the new model in `server.py::BLUE_AI_MODELS` or the frontend dropdown — Chen does that on Windows after validation.
- DO NOT use `--device cuda` unless you've verified torch sees a working GPU on the EPYC box.
- DO NOT block the pipeline waiting for compatible learned Red. If the old Red doesn't load, fall back to `scripted scripted rule` and document it.
- DO NOT extend a stage past `HARD_CAP` even if not converged. Save what's there, advance.
- DO NOT amend or force-push. Each stage = its own commit.
- DO NOT skip the per-stage push. Chen pulls between stages to test early checkpoints.
- DO NOT spend > 30 min total on Phase 2 setup if `red_train.py` is broken or incompatible — just skip Phase 2 and document.
- DO NOT commit `.venv/`, `__pycache__/`, `node_modules/`, or any temp files.
- DO NOT add a new model to dropdown / frontend — Chen handles deployment.
- DO NOT delete or modify any existing reward-related code beyond replacing `_reward_from_events` and bumping spend penalty.
