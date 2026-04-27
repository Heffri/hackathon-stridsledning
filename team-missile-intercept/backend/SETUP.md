# Setup — Demo Live ver 1.0

**Branch**: `demo-live-v1.0` (release tag of this stage of work)
**Last verified**: 2026-04-27 on Windows + Ubuntu 24.04, Python 3.12

---

## TL;DR

```bash
git clone <repo>
cd hackathon-stridsledning/team-missile-intercept/backend
python -m venv .venv

# Activate venv:
#   Windows PowerShell:  .\.venv\Scripts\Activate.ps1
#   Linux/macOS:         source .venv/bin/activate

pip install --upgrade pip
pip install numpy==1.26.4   # MUST be 1.26.x, NOT 2.x
pip install -r requirements.txt

python -m rl.live_ai        # Smoke test — should print "Smoke OK."
python server.py             # Then open http://localhost:8000/ (or :5174)
```

If smoke fails, see "Common gotchas" below.

---

## Why a fresh checklist (and not just `pip install -r requirements.txt`)

Up until this branch, `requirements.txt` only had `fastapi` / `uvicorn` / `numpy`. **The actual RL stack — `gymnasium`, `stable-baselines3`, `sb3-contrib`, `torch`, `tensorboard`, `tqdm`, `rich` — was missing.** Teammates pulling the demo would get:

- ✗ Server starts but **dropdown selections silently fall back to rule-based** (because `LearnedBlueAI` import fails at runtime)
- ✗ Browser shows "Heuristic" behavior even when "RL Megamodel" is selected
- ✗ `python -m rl.train` crashes immediately on missing tensorboard / tqdm / rich

`requirements.txt` in this branch lists everything that's actually needed to run the demo + retrain. Always install via `pip install -r requirements.txt` rather than picking individual packages.

---

## What's required vs optional

### Required for the browser demo (i.e., loading any RL model from the dropdown)

| Package | Pinned version | Why |
|---|---|---|
| `fastapi` | 0.115.0 | Server framework |
| `uvicorn[standard]` | 0.30.6 | ASGI runner with WebSocket support |
| `numpy` | **1.26.4** ← MUST NOT upgrade to 2.x | Boyu V2/V2a were pickled under numpy 2; the compat shim in `rl/red_env.py` only handles 2→1.26 unpickle |
| `torch` | >=2.4,<2.6 | Pytorch backend for SB3 inference (CPU-only is fine) |
| `stable-baselines3` | 2.8.0 | PPO library, used by inference wrapper |
| `sb3-contrib` | 2.8.0 | MaskablePPO (action masking) |
| `gymnasium` | >=1.0,<2.0 | SB3's env API (transitively required) |

### Required only for retraining

These are **not needed to run the demo browser** — only if you `python -m rl.train` to train a new model:

| Package | Why |
|---|---|
| `tensorboard` | SB3's default logger writes TB events |
| `tqdm` | SB3's `ProgressBarCallback` |
| `rich` | Same |

`requirements.txt` includes them anyway (small footprint, simpler one-line install).

---

## What's intentionally NOT pinned

- Operating-system-level packages (Python itself, git, build-essential). Use Python 3.10+ (3.12 tested).
- GPU-specific torch wheels. The default `pip install torch` gives the CPU build, which works for everything. If you want CUDA, install the appropriate wheel from pytorch.org separately.

---

## Common gotchas

### 1. "Selected RL model but it behaves like Heuristic"

Most likely cause: `LearnedBlueAI` failed silently to load the model — server fell back to rule-based. Run smoke test:

```bash
python -m rl.live_ai
```

If it fails on `import sb3_contrib` or `MaskablePPO.load(...)`, your venv is missing deps. Reinstall:

```bash
pip install -r requirements.txt
```

If it fails on `numpy.core` import, you have numpy 2.x. Downgrade:

```bash
pip install numpy==1.26.4 --force-reinstall
```

### 2. "Default budget shows 120 / 100" after pulling

This branch (Demo Live ver 1.0) ships defaults at **Red 150M / Blue 200M** (matches V4 + Megamodel + S1-retrain training distributions). If you see 120/100, you're on `final-demo` or earlier.

### 3. "Default layout is 'current'" after pulling

This branch ships `Layout C` selected by default (matches V4 + Megamodel-S1 training distribution). If you see "Layout: Current", you're on an older branch.

### 4. "Models in dropdown but `s1_retrain_peak` is missing"

S1 retrain final + peak checkpoints are included in this branch under `rl/runs/blue_s1_retrain/`. If `git pull` didn't bring them, run `git lfs pull` (if LFS-tracked) or check disk:

```bash
ls -la rl/runs/blue_s1_retrain/model.zip                    # 44 MB
ls -la rl/runs/blue_s1_retrain/ckpt/blue_ppo_1399860_steps.zip  # 44 MB
```

### 5. WebSocket "AssertionError keepalive ping failed" mid-demo

Known issue with the legacy `websockets` library when rapidly switching AI models / layouts. Set up your match config once and don't switch mid-match. If it crashes, just `python server.py` again — model files persist.

---

## Recommended demo configuration

```
Blue:    RL CIWS Active (V4)  ← stable
         OR RL S1 Retrain peak (1.4M)  ← experimental, may be even better
Red:     Scripted 3-Chain
Layout:  C (default)
Budget:  Red 150M / Blue 200M (default)
```

For story value, the stretch demo:

```
Blue:    RL CIWS Active (V4)
Red:     RL Trainee v2 (cost-aware + HGV evasion)
Layout:  C
Budget:  Red 150M / Blue 200M
```

This shows the Red AI's emergent **bait-and-saturate** strategy (27 cheap ballistic missiles to drain Blue's PAC budget, then drone flood). See [BIG_MODELS_POSTMORTEM_zh.md](../progress/BIG_MODELS_POSTMORTEM_zh.md) for context.

---

## Where to find what

```
team-missile-intercept/
├── backend/
│   ├── server.py          # FastAPI server, model dropdown registration
│   ├── requirements.txt   # ← THIS FILE'S DEP LIST
│   ├── SETUP.md           # ← THIS FILE
│   ├── sim/               # Game engine
│   │   ├── config.py      # Default budgets (Blue 200M / Red 150M)
│   │   ├── world.py
│   │   ├── entities.py
│   │   └── ...
│   ├── rl/
│   │   ├── env.py         # MissileInterceptEnv, MAX_THREATS=120 etc.
│   │   ├── live_ai.py     # LearnedBlueAI / LearnedRedAI inference wrappers
│   │   ├── red_env.py     # Red's training env
│   │   ├── train.py       # Blue training entry point
│   │   ├── red_train.py   # Red training entry point
│   │   └── runs/          # Trained model artifacts
│   │       ├── blue_local/
│   │       │   ├── blue_aoe_aggressive_B_shaped/   # B-path Blue (Hack Day demo)
│   │       │   ├── blue_megamodel/                  # EPYC curriculum (S1-S4)
│   │       │   └── ...
│   │       ├── blue_s1_retrain/                    # S1 retrain (anti-PAC-spam)
│   │       └── red_local/
│   │           └── red_trainee_parallel/           # Red v2 (cost-aware + HGV evasion)
│   └── tests/
└── frontend/
    ├── index.html         # SETUP UI, dropdown options
    ├── style.css
    └── js/
        ├── main.js
        ├── scene.js
        ├── entities.js
        ├── hud.js
        └── ...
```

---

## Reports and postmortems

In `team-missile-intercept/progress/`:

- `BIG_MODELS_POSTMORTEM_en.md` / `_zh.md` — why Boyu V2a / Cap120 / Megamodel all regressed into PAC-spam
- `V4_DISTRIBUTION_SHIFT_UPDATE_zh.md` — the real root cause (training-vs-deployment distribution mismatch)
- `TRAIN_MEGAMODEL_REPORT.md` — EPYC curriculum training run
- `TRAIN_RED_TRAINEE_REPORT.md` — Red Trainee v2 training run + cost-aware reward
- `HANDOFF_S1_RETRAIN_INFLIGHT_2026-04-27.md` — S1 retrain methodology + reward design
- `PROMPT_*.md` — worker prompts used to drive the EPYC overnight + S1-retrain runs

---

## Re-running the S1 retrain (or training a new variant)

If you want to retrain S1 with different reward shaping on your local machine:

```bash
cd team-missile-intercept/backend
python -m rl.train \
  --total-steps 1500000 \
  --n-envs 30 \
  --n-steps 1024 --batch-size 256 --n-epochs 4 \
  --lr 3e-4 --gamma 0.995 --gae-lambda 0.95 \
  --ent-coef 0.01 --clip-range 0.2 \
  --episode-time-limit 3000.0 \
  --device cpu --save-every 200000 \
  --run-name my_s1_retrain \
  --layouts-pool-slots C \
  --red-mode-pool scripted \
  --blue-budget 200000000 --red-budget 150000000
```

Adjust `_reward_from_events` in `rl/env.py` first to change shaping. See `rl/env.py` for the current `DOCTRINE_PENALTY`, `DOCTRINE_BONUS`, `HEAD_ON_WEIGHT`, `LEAK_TIER_WEIGHTS`, `SPEND_PENALTY_PER_M` constants.

---

## Open questions / future work

- The `s1_retrain` final model regressed slightly relative to the `s1_retrain_peak` checkpoint at 1.4M steps. SB3's `EvalCallback` (auto-save best model) wasn't used — adding it would prevent this.
- Cross-match LearnedBlueAI state (`_assignments`, `_tick_counter`) leaks between matches — first match clean, second match degrades. Fix would be ~10 lines in `live_ai.py` adding a `reset_state()` method called from `Scenario.reset()`.
- WebSocket race condition under rapid model switching is a `websockets` library issue, fixable by upgrading to `websockets>=12`.
- Future training rounds should add eval episodes during training (deterministic rollouts every 100k steps) to track real win rate, not just `ep_rew_mean`.
