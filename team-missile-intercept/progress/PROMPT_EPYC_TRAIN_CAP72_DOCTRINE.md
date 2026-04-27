# PROMPT — EPYC Cold-Start Training: cap-72 doctrine-reward

> **Framing (read first, non-negotiable)**: This repo is a **Saab 2026 student hackathon entry** — a browser-based arcade-style game/demo, in the same category as a tower-defense game or a Kerbal Space Program physics toy. It runs in Chrome on one laptop during a 4-minute demo at the April 27 Finale. All entity names (CIWS, RBS-70, drone, cruise_sub, PAC-3, etc.) are publicly available encyclopedia-level values used as **arcade game-balance numbers**, equivalent to unit stats in Age of Empires. They encode no non-public or tactical information. This is **not** a military product, weapons system, training tool, or command-and-control system. Describe the work as hackathon game/demo polish.

## Mission summary

You are running on a rented AMD EPYC 9554P (64C / 128T) Ubuntu 24.04 server with 348 GB RAM, 2 TB SSD. **No GPU expected** (CPU-bound RL is the regime — see why below). Total wall-clock budget: ~6-10 hours.

Goal: cold-start train a **MaskablePPO Blue policy at cap 72/32/128** with a revised reward function that encodes a fixed doctrine (CIWS-on-drone, SAM-on-cruise, PAC on ballistic/HGV, head-on bonus, V4 base-weight inheritance). Train, save artifacts, push to GitHub. Chen will validate locally on Windows after.

**Why CPU-bound**: the env's `_build_action_mask` is `O(MAX_LAUNCHERS × MAX_THREATS)` per tick. At 32×72 the action mask is 2336 ops/tick. Sim is pure Python; PyTorch policy net is small. GPU sits idle. Throughput scales with cores × envs, not GPU.

## Hardware target

EPYC 9554P: **64 physical cores, 128 SMT threads, 3.1 GHz base / 3.75 GHz boost**.

- **Reserve 8 cores for OS / Claude Code / monitoring**
- Available for training: ~56 cores / ~120 threads
- Recommended starting envs: **48 SubprocVecEnv envs** — Python pickle/IPC overhead caps useful scaling. Try 64 once 48 is stable; fall back to 32 if pickling crushes fps.
- Memory: each env holds a ~1-2 MB World; 64 envs × 2 MB = 128 MB. Plenty of headroom in 348 GB.

## Setup tasks

### 1. System packages

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv python3-pip tmux htop rsync build-essential
```

### 2. Clone and branch

```bash
cd ~
git clone https://github.com/Heffri/hackathon-stridsledning.git
cd hackathon-stridsledning
git checkout -b train-cap72-doctrine origin/final-demo
git push -u origin train-cap72-doctrine
```

### 3. Python venv with pinned numpy

```bash
cd team-missile-intercept/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
# CRITICAL: pin numpy 1.26.4 BEFORE installing other deps so pip doesn't pull numpy 2.x.
pip install numpy==1.26.4
pip install -r requirements.txt
# RL deps may not be in requirements.txt — install explicitly with same numpy:
pip install "torch>=2.4,<2.6" stable-baselines3 sb3-contrib gymnasium
# Lock the install:
pip freeze > rl/runs/blue_local/_PIP_FREEZE_PLACEHOLDER.txt   # placeholder; overwrite during run
```

Sanity check the install:

```bash
python -c "import numpy as np; print('numpy', np.__version__); import torch; print('torch', torch.__version__); import sb3_contrib; print('sb3_contrib OK')"
```

Expect `numpy 1.26.4`, `torch 2.4.x` or `2.5.x`, `sb3_contrib OK`. If numpy reports 2.x, **stop and reinstall** — Boyu-style numpy-2 pickle issues will haunt the model later.

### 4. Run smoke before any code change

```bash
cd team-missile-intercept/backend
python -m rl.smoke   # or: python -m rl.live_ai
```

Should print `Smoke OK.` Confirms the repo runs as-is on this Ubuntu before we touch anything.

## Code changes (all in `backend/rl/env.py`)

### A. Cap bump: 120/60/160 → 72/32/128

In `team-missile-intercept/backend/rl/env.py` near the top of the file (around line 50-55), update the constants:

```python
# Was: MAX_THREATS = 120, MAX_LAUNCHERS = 60, MAX_INTERCEPTORS = 160
MAX_THREATS = 72
MAX_LAUNCHERS = 32
MAX_INTERCEPTORS = 128
```

The cap-120 expansion (2026-04-25) supplied a backward-compat adapter in `live_ai.py` that slices oversized env obs to the model's native size. Trained-at-72 model + env-at-120-on-Windows works because Windows env size > model size + adapter slices down. We're going the other way (env at 72/32/128) because **action mask 32×73 = 2336** is much smaller than the cap-120 mask 60×121 = 7260, so training fps is ~3× faster.

Layouts at the new cap: Layout C has 23 launchers (fits 32 with 40% headroom), peak threat count observed in v4 + Path D testing was ~45 (fits 72 with 60% headroom). All current layouts fit comfortably.

### B. Reward function rewrite (`_reward_from_events`)

Replace the **entire body** of `_reward_from_events` (around lines 384-432 in env.py) with the version below. This adds:

1. **Doctrine multiplier** on intercept reward (encodes "right interceptor for right threat")
2. **Head-on bonus** for PAC-2/PAC-3 vs ballistic/HGV (geometry-aware)
3. **V4 base-weight scaling** on leak penalty (`n_initial / n_alive`)
4. **Dead-base zero-out** on intercept reward (don't reward intercepting threats targeting already-dead bases)

```python
import math  # at top of env.py if not already imported

# ---- Reward shaping constants (doctrine-reward 2026-04-26) ----
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
# - canonical pairs (CIWS->drone, *->cruise, PAC-2/PAC-3->ballistic/HGV)
# - wasteful pairs (PAC-3->drone) — handled by spend penalty alone

HEAD_ON_WEIGHT = 0.5            # max head-on bonus = 50% of base intercept reward
LEAK_TIER_WEIGHTS = {           # unchanged from V4
    "hgv": 8.0,
    "ballistic": 6.0,
    "cruise_sub": 3.0,
    "drone": 2.0,
}


def _reward_from_events(self, events: List[dict]) -> float:
    """Per-tick dense shaping with doctrine-reward shaping (2026-04-26).

    Layered reward signal:
      1. Intercept event:
         - Base reward: threat.usd_cost / 1e6
         - Multiplied by DOCTRINE_MULTIPLIER for the (interceptor, threat)
           pair — gambles get 1.3-2.0x, anti-doctrine drone-on-SAM gets 0.7
         - Plus head-on bonus for (PAC-2|PAC-3) x (ballistic|HGV): up to
           +HEAD_ON_WEIGHT (0.5) x base reward when interceptor and threat
           velocities are anti-parallel
         - Zeroed-out entirely if threat targets a dead base (V4 inherit)
      2. Leak event:
         - tier_weight x dmg x base_weight
         - base_weight = n_initial_bases / n_alive_bases — leaks scale up
           to 3x as bases die (V4 inherit)
      3. Ground-crash credit: +0.2 (unchanged)

    Caller must invoke this BEFORE world.prune_dead so intercept/leak
    events can still resolve threat / interceptor handles.
    """
    r = 0.0

    # Base-weight scaling factor (V4 inherit — protect last alive bases harder)
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
                # Lookup failed — fall back to neutral credit, same as old behaviour.
                r += 1.0
                continue

            # V4 inherit: zero reward if target base already dead.
            target_site_id = getattr(threat, '_target_site_id', None)
            if target_site_id is not None:
                target_site = sites_module.find_site_by_id(target_site_id)
                if target_site is not None and target_site.hp <= 0:
                    continue  # threat already worthless; don't reward

            # Base reward = threat usd_cost in $M.
            try:
                spec = self._threat_spec_by_str(threat.state.kind)
                base_value = spec.usd_cost / 1e6
            except KeyError:
                base_value = 1.0

            # Doctrine multiplier on (interceptor_kind, threat_kind).
            try:
                interceptor_kind = InterceptorType(inter.state.kind)
                threat_kind = ThreatType(threat.state.kind)
            except (KeyError, ValueError):
                r += base_value  # fallback — old behaviour
                continue
            multiplier = DOCTRINE_MULTIPLIER.get(
                (interceptor_kind, threat_kind), 1.0,
            )
            r_intercept = base_value * multiplier

            # Head-on bonus: PAC-2 / PAC-3 vs ballistic / HGV only.
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
                    head_on_factor = max(0.0, -cos_angle)  # 0 to 1
                    r_intercept += base_value * HEAD_ON_WEIGHT * head_on_factor

            r += r_intercept

        elif et == "leak":
            dmg = ev.get("damage", 0)
            kind = ev.get("kind", "")
            tier = LEAK_TIER_WEIGHTS.get(kind, 2.0)
            # Apply base_weight only if leak hit a military base.
            # Leak event has `"site": site.name` (string). Resolve to site obj.
            site_name = ev.get("site", "")
            site = next(
                (s for s in sites_module.SOUTH_SITES if s.name == site_name),
                None,
            )
            if site is not None and site.subtype in military_subtypes:
                r -= float(dmg) * tier * base_weight
            else:
                r -= float(dmg) * tier  # civilian or unknown — no scaling

        elif et == "ground_crash" and ev.get("threat") is not None:
            r += 0.2

    return r
```

### C. Spend penalty bump (in `step()`)

Find the line in `step()` (around line 280):

```python
reward = event_reward - spent / 1e6 * 0.05  # weak efficiency penalty per $M spent
```

Change to:

```python
reward = event_reward - spent / 1e6 * 0.5  # was 0.05; bumped 10x for doctrine reward shaping (2026-04-26)
```

### D. Sanity check before launching

```bash
cd team-missile-intercept/backend
python -m rl.smoke    # or python -m rl.live_ai
```

Smoke must still pass. If not, check imports (`math` at top of env.py) and the cap constants.

Then a quick interactive sanity:

```bash
python -c "
from rl.env import RedEnv, MAX_THREATS, MAX_LAUNCHERS, MAX_INTERCEPTORS, DOCTRINE_MULTIPLIER, HEAD_ON_WEIGHT
print('caps:', MAX_THREATS, MAX_LAUNCHERS, MAX_INTERCEPTORS)
print('DOCTRINE_MULTIPLIER size:', len(DOCTRINE_MULTIPLIER))
print('HEAD_ON_WEIGHT:', HEAD_ON_WEIGHT)
"
```

Expect `caps: 72 32 128`, `DOCTRINE_MULTIPLIER size: 8`, `HEAD_ON_WEIGHT: 0.5`.

## Training launch

### 1. Create the training launch script

Create `team-missile-intercept/backend/scripts/train_cap72_doctrine.sh`:

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

RUN_NAME="blue_cap72_doctrine_$(date +%Y%m%d_%H%M)"

# Save the launch command verbatim for audit.
mkdir -p rl/runs/blue_local/${RUN_NAME}
cat > rl/runs/blue_local/${RUN_NAME}/launch_cmd.txt <<EOF
python -m rl.train \
  --total-steps 10000000 \
  --n-envs 48 \
  --n-steps 1024 \
  --batch-size 256 \
  --n-epochs 4 \
  --lr 3e-4 \
  --gamma 0.995 \
  --gae-lambda 0.95 \
  --ent-coef 0.01 \
  --clip-range 0.2 \
  --episode-time-limit 3000.0 \
  --device cpu \
  --save-every 500000 \
  --checkpoint-every 500000 \
  --run-name ${RUN_NAME} \
  --red-mode-pool scripted \
  --layouts-pool-slots C D \
  --blue-budget 200000000 \
  --red-budget 110000000
EOF

pip freeze > rl/runs/blue_local/${RUN_NAME}/pip_freeze.txt

python -m rl.train \
  --total-steps 10000000 \
  --n-envs 48 \
  --n-steps 1024 \
  --batch-size 256 \
  --n-epochs 4 \
  --lr 3e-4 \
  --gamma 0.995 \
  --gae-lambda 0.95 \
  --ent-coef 0.01 \
  --clip-range 0.2 \
  --episode-time-limit 3000.0 \
  --device cpu \
  --save-every 500000 \
  --checkpoint-every 500000 \
  --run-name ${RUN_NAME} \
  --red-mode-pool scripted \
  --layouts-pool-slots C D \
  --blue-budget 200000000 \
  --red-budget 110000000 \
  2>&1 | tee rl/runs/blue_local/${RUN_NAME}/training.log
```

`chmod +x scripts/train_cap72_doctrine.sh`.

**Every one of these flags matters — skipping any resurrects a bug we already fixed**:
- `--blue-budget 200000000 --red-budget 110000000`: training distribution must match Hack Day demo budgets, NOT config.py defaults (the old "policy hoards budget" bug came from this).
- `--red-mode-pool scripted`: ScriptedRed (3-chain attack), the demo Red.
- `--layouts-pool-slots C D`: train on Layout C (Heavy Saturation, 23 launchers) + D (Forward HGV Hunter, 19 launchers). NOT default layout.
- `--episode-time-limit 3000.0`: matches Hack Day demo.
- `--device cpu`: GPU sits idle anyway, and torch+cuda often misconfigures on rented EPYC.

### 2. Launch training in tmux

```bash
tmux new -s train -d
tmux send-keys -t train "cd ~/hackathon-stridsledning/team-missile-intercept/backend && bash scripts/train_cap72_doctrine.sh" C-m
```

Verify it's running:

```bash
tmux capture-pane -t train -p | tail -20
```

You should see SubprocVecEnv spawn lines and the first PPO rollout starting. If you see `KeyError`, `ImportError`, or anything red, kill the tmux session and fix the code first.

### 3. Tune envs if fps is bad

After ~5 minutes of training, capture fps:

```bash
tmux capture-pane -t train -p | grep -E "fps|n_updates" | tail -5
```

- If `fps > 1500`: leave at 48 envs.
- If `fps < 800`: drop to 32 envs (kill tmux, re-launch with `--n-envs 32`). Pickle/IPC overhead is dominating.
- If `fps > 3000`: try bumping to 64 envs for faster wall-clock convergence.

Don't tune more than once. If the fps is in a reasonable range, leave it; tweaking eats wall-clock.

## Monitoring (every 30 minutes)

Open a second tmux session for periodic checks:

```bash
tmux new -s monitor -d
```

Run a one-shot check command (NOT a background loop — the agent runs it manually):

```bash
RUN_DIR=$(ls -td rl/runs/blue_local/blue_cap72_doctrine_* | head -1)
tmux capture-pane -t train -p | tail -40
echo "---"
ls -la ${RUN_DIR}/ckpt/ 2>/dev/null | tail -10
echo "---"
tail -30 ${RUN_DIR}/training.log | grep -E "ep_rew_mean|approx_kl|loss|fps" | tail -10
```

What you're watching for:

- **`ep_rew_mean`**: should drift positive over the first 1-2M steps. If still flat negative after 2M steps, training is stuck — likely a reward-scale bug. Stop and audit.
- **`approx_kl`**: should stay < 0.05 normally. If consistently > 0.1, the policy is shifting too fast — `--clip-range` too loose.
- **`fps`**: should be steady. If it crashes mid-run, an env probably hung. Kill + restart from latest checkpoint.
- **Checkpoints**: every 500k steps a `ckpt/ckpt_X.zip` should appear.

Run this check **every 30-60 min during training**. Don't sleep-poll — just `tmux capture-pane` and read.

## Acceptance gates

After training completes (or you stop early), run an automated eval to gate the model:

```bash
cd ~/hackathon-stridsledning/team-missile-intercept/backend
source .venv/bin/activate

RUN_DIR=$(ls -td rl/runs/blue_local/blue_cap72_doctrine_* | head -1)
MODEL=${RUN_DIR}/model.zip

# Use the existing per-layout evaluator (or write a one-off if it doesn't fit).
# Configure: 5 matches each on Layout C and Layout D, ScriptedRed, Red 110M, Blue 200M.
python -m rl.per_layout_eval \
  --blue-policy ${MODEL} \
  --layouts C D \
  --n-matches 5 \
  --red-mode scripted \
  --blue-budget 200000000 \
  --red-budget 110000000 \
  --episode-time-limit 3000.0 \
  --output ${RUN_DIR}/eval_report.json
```

(Adapt CLI flags if `per_layout_eval.py` uses different names — check its `argparse` block.)

### Pass gate (must hit ALL three)

| Metric | Target |
|---|---|
| Layout C avg sites alive | ≥ 2.5 / 3 |
| Layout C drone leak rate | ≤ 5% (drones killed / spawned) |
| Layout C CIWS-fires-per-match | ≥ 30 (visible CIWS engagement) |

If all three pass: model is **deployment-candidate**. Push branch + write summary report.

If any fails: model is **experimental only**. Push branch but write the report flagging which gate failed and what the metric values were. Chen will decide whether to use it.

## Save artifacts and push

After training + eval finishes, ensure these files are in the run dir:

```
rl/runs/blue_local/<run_name>/
├── model.zip                 # final model (sb3 saves this)
├── ckpt/
│   ├── ckpt_500000.zip
│   ├── ckpt_1000000.zip
│   └── ...
├── training.log              # full stdout from training
├── pip_freeze.txt            # exact dep versions
├── launch_cmd.txt            # verbatim training launch command
└── eval_report.json          # per-layout eval result
```

Commit the env.py + training script changes:

```bash
cd ~/hackathon-stridsledning
git add team-missile-intercept/backend/rl/env.py
git add team-missile-intercept/backend/scripts/train_cap72_doctrine.sh
git add team-missile-intercept/backend/rl/runs/blue_local/<run_name>/
# DO NOT commit .venv/ or any node_modules
git status   # verify nothing weird is staged

git commit -m "feat(rl): cold-start training cap-72 with doctrine reward shaping

- Bump env cap 120/60/160 → 72/32/128 (covers observed peak 45 with 60% headroom).
- Add DOCTRINE_MULTIPLIER on intercept reward: gamble bonuses for cheap-on-hard
  pairings (CIWS->ballistic 2.0, SLM->ballistic 2.0), anti-doctrine penalty
  for SAM-on-drone (0.7).
- Add head-on bonus (HEAD_ON_WEIGHT=0.5) for PAC-2/PAC-3 vs ballistic/HGV.
- V4 inherit: leak penalty scales by n_initial/n_alive bases; intercept reward
  zeroed when target base is dead.
- Spend penalty 0.05 -> 0.5 (10×) so single-fire waste hurts.

Trained on EPYC 9554P, Ubuntu 24.04, $RUN_NAME.
"
git push origin train-cap72-doctrine
```

**The model.zip is ~50-100 MB; commit it.** ckpt files (~50 MB each) commit too — Chen wants them for rollback.

If git push fails because of LFS / large file limits, switch to git LFS:

```bash
git lfs install
git lfs track "*.zip"
git add .gitattributes
git add rl/runs/blue_local/<run_name>/
git commit -m "chore: track model artifacts via git LFS"
git push origin train-cap72-doctrine
```

If LFS isn't an option (no quota), zip the run dir and upload to a transient share (whatever Chen has access to). Note the URL in the report.

## Report

Write to `team-missile-intercept/progress/TRAIN_CAP72_DOCTRINE_REPORT.md`:

1. **Hardware reality**: actual fps observed, n_envs settled on, total wall clock for X M steps.
2. **Code changes**: list of lines touched in env.py + the training script.
3. **Reward changes summary**: doctrine multipliers, head-on weight, base-weight, dead-base zero-out, spend bump.
4. **Training trajectory**: ep_rew_mean at 1M, 2M, 5M, 10M (or final). approx_kl trend. Any anomalies.
5. **Eval result**: pass / fail per gate, raw metrics for Layout C and D.
6. **Compatibility notes**: numpy version, torch version, sb3 version (paste from pip_freeze.txt) — Chen will match these on Windows.
7. **Branch tip commit hash**.

Keep under 300 lines. Tables welcome.

## End-of-session summary (paste in chat after work is done)

- Branch tip commit hash
- Training: total steps reached / target, total wall-clock time, final ep_rew_mean
- Eval gates: 3/3 pass / 2/3 / 1/3 / 0/3, with per-gate values
- **Verbatim training launch command from training.log** (not the script — what actually ran). If a flag is missing, the retrain is invalid.
- Artifact locations (run dir on EPYC + git push status)
- Hardware fps actually observed
- Any open issues for Chen

## Constraints / DON'Ts

- DO NOT run `sudo npm install -g` for Node packages (Anthropic docs warn against it).
- DO NOT install numpy 2.x. Pin 1.26.4 BEFORE other deps.
- DO NOT run training in Claude foreground — use tmux.
- DO NOT skip the explicit `--blue-budget` / `--red-budget` CLI flags. config.py defaults are 100M/120M (demo-safe values), training-side budgets MUST override via CLI.
- DO NOT touch `live_ai.py`, `server.py`, frontend, or any file outside `rl/env.py` and the training script you create.
- DO NOT rebase or amend commits — make a new commit per logical change.
- DO NOT register the new model in `server.py::BLUE_AI_MODELS` or the frontend dropdown — Chen will do that on Windows after validation.
- DO NOT delete the existing `LAUNCH_RANGE_MARGIN`, `SATURATION_CAP_BY_KIND`, or any existing reward / live-ai code. Doctrine reward is additive; live_ai stays untouched.
- DO NOT commit `.venv/`, `__pycache__/`, or any `node_modules/`.
- DO NOT skip the `pip freeze > pip_freeze.txt` step. Without it Chen can't reproduce on Windows.
- DO NOT use `--device cuda` unless you've verified torch sees a GPU and a quick PPO update step works on it. CPU is the safe default.
