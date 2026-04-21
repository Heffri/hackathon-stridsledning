# Phase 2b Step 1 — Opponent pool + warmstart support (coding + smoke)

**How to use:** paste everything below (from `# Hackathon framing`) into a fresh Claude Code worker session at the repo root on Chen's PC. Bypass permissions. Budget: ~1.5-2 h. Worker does coding + smoke test ONLY — does NOT kick off long training. Chen launches overnight training manually after this worker lands.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition. A small browser-based arcade-style game / simulation in the tower-defense / KSP category. NOT a military product. All entity names and stats are publicly available encyclopedia-level arcade game-balance numbers. This worker adds opponent-pool training capability for a game AI (reinforcement learning). Game-dev framing throughout.

# Your role

Add two capabilities to Chen's Red training stack so Red2 can fine-tune overnight against a mixed-opponent pool:

1. **Opponent pool** in `RedEnv`: at each `reset()`, pick the Blue opponent from a pool (configurable mix). Supports:
   - `"rule"`: rule-based `BlueAI.step(world.t, world)` (current behavior)
   - `"learned:<path.zip>"`: load a MaskablePPO policy and call `.predict()` → apply as Blue action each decision
2. **Warmstart** in `red_train.py`: load an existing Red `model.zip` and continue training (vs training from scratch).

Smoke-test both. Commit locally. Return the overnight launch command to Chen. Do **NOT** start the long training.

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`.

**Active branch: `rl-self-play-v1`** — Chen's Red env + train code lives here. You modify these files in place.

**Expected starting HEAD:** `a72adc5` or newer. (`origin/red-ai` is at `49ffd6d` = a72adc5 + Red1 model.zip, but that's irrelevant for this coding task.)

**Model files needed:**
- Red1 warmstart source: `team-missile-intercept/backend/rl/runs/red_20260421_205051/model.zip` — should already be present locally
- Blue1 opponent: fetch from `origin/blue-ai` via `git checkout origin/blue-ai -- team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip`

Start by reading:
- `team-missile-intercept/backend/rl/red_env.py` — Chen's RedEnv (the class you're modifying)
- `team-missile-intercept/backend/rl/env.py` — Boyu's MissileInterceptEnv — reference for **how Blue actions are applied** to the sim. Your learned Blue opponent needs to apply actions just like Boyu's env does.
- `team-missile-intercept/backend/rl/red_train.py` — Chen's train script (adding warmstart here)
- `team-missile-intercept/backend/rl/train.py` — Boyu's train script (reference; don't modify)
- `team-missile-intercept/backend/sim/blue_ai.py` — rule-based `BlueAI.step` signature
- `team-missile-intercept/common-info/gpt_advise_rl_overfitting.md` — external consult; particularly section 3 (Level 2 ROI) which motivated this opponent-pool design

# Pre-flight

1. `git status` — must be clean. If dirty, stash.
2. `git fetch origin --prune`
3. `git checkout rl-self-play-v1`
4. `git pull --ff-only origin rl-self-play-v1`
5. Fetch Blue1: `git checkout origin/blue-ai -- team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip`. After this, `git status` will show `models/blue_ai_1m_2xpenalty/model.zip` as a staged new file. **Don't commit it** — it's a training artifact for Chen's machine only. Leave it staged; the worker might need to unstage at the end.
6. Verify files: `ls runs/red_20260421_205051/model.zip` and `ls models/blue_ai_1m_2xpenalty/model.zip` (both from `backend/`).
7. Run `python -m rl.red_smoke` from `backend/` — must pass (3/3).

If any step fails, STOP.

# Design

## Opponent interface

Create a new module `team-missile-intercept/backend/rl/blue_opponents.py` with:

```python
from abc import ABC, abstractmethod
from sim.blue_ai import BlueAI
from sb3_contrib import MaskablePPO
import numpy as np

class BlueOpponent(ABC):
    """Abstract Blue opponent used by RedEnv. Stateless per episode."""
    
    @abstractmethod
    def reset(self, world) -> None:
        """Called at episode start. Bind to new world instance."""
    
    @abstractmethod
    def act(self, world, red_encoded_obs) -> None:
        """Called each decision step (at Red's cadence). Mutates world by
        firing Blue interceptors. Red-encoded obs passed in for convenience
        (Blue obs = Red obs in our env, see Chen's earlier worker summary)."""


class RuleBlueOpponent(BlueOpponent):
    """Wraps BlueAI.step — the existing rule-based greedy cost-exchange."""
    def reset(self, world):
        self._ai = BlueAI()  # assumes zero-arg ctor per worker's earlier finding
    def act(self, world, red_encoded_obs):
        self._ai.step(world.t, world)


class LearnedBlueOpponent(BlueOpponent):
    """Loads a MaskablePPO policy and applies its action as Blue each step.
    
    Action application must match Boyu's `_apply_action` in env.py —
    for each of 15 launchers, the action index ∈ [0, 30] picks:
      - 0..29: fire at threat index `i` in Boyu's sorted threat list
      - 30: hold
    See env.py for the sorting order and launcher iteration.
    """
    def __init__(self, policy_path: str):
        self.policy = MaskablePPO.load(policy_path)
        self._world = None
    
    def reset(self, world):
        self._world = world
    
    def act(self, world, red_encoded_obs):
        # Use the Red-encoded obs directly as Blue obs (same shape per worker's
        # earlier verification). If action_mask field differs, re-encode the
        # Blue-specific mask — check Boyu's env for his mask shape.
        blue_mask = red_encoded_obs["action_mask"]  # may need shape conversion
        action, _ = self.policy.predict(
            red_encoded_obs, deterministic=False, action_masks=blue_mask
        )
        # Apply Blue action — port from Boyu's env.py::_apply_action
        self._apply_blue_action(world, action)
    
    def _apply_blue_action(self, world, action):
        """Port from Boyu's MissileInterceptEnv._apply_action."""
        # Read Boyu's env.py carefully for this logic. Should be ~30 lines.
        ...
```

**Critical engineering check**: the mask shape. Red env's action_mask is `(1 + 4*N_SITES,)` flat OR `(5, N_SITES)` — Chen's RedEnv action space is MultiDiscrete([5, 3]) per the worker's delivery summary. Blue's mask is for `MultiDiscrete([31]*15)` = length `sum(nvec) = 15*31 = 465` flat. **These are DIFFERENT shapes** — the Red obs dict's `action_mask` field won't match Blue's expected mask.

**Fix**: in `LearnedBlueOpponent.act()`, compute Blue's mask from scratch from `world` state, mimicking how Boyu's env builds its mask. That's another ~20 lines ported from Boyu's env.

If the obs Dict otherwise matches (same threats/launchers/interceptors/sites/global encoding), only the `action_mask` field needs re-encoding for Blue.

## Opponent pool

In `RedEnv`:

```python
# Replace self.blue = BlueAI() with:
self.opponent_pool: list[tuple[BlueOpponent, float]] = opponents  # [(opp, weight), ...]

def _select_opponent(self):
    weights = np.array([w for _, w in self.opponent_pool])
    idx = np.random.choice(len(self.opponent_pool), p=weights/weights.sum())
    return self.opponent_pool[idx][0]

# In reset():
self.blue = self._select_opponent()
self.blue.reset(self.world)

# In step():
self.blue.act(self.world, current_red_obs)
```

Constructor signature change: `RedEnv(episode_time_limit=600.0, seed=None, opponents=None)`. Default `opponents = [(RuleBlueOpponent(), 1.0)]` (backward compat with single rule opponent).

## Train.py CLI additions

In `red_train.py`:

1. `--warmstart <path>`: if provided, `MaskablePPO.load(path)` as initial policy instead of constructing a new one. The VecEnv is built normally; the loaded model's `env` gets rebound.

2. `--opponent-pool <spec>`: parse a spec string like `"rule:0.5,learned:models/blue_ai_1m_2xpenalty/model.zip:0.5"`. Comma-separated entries; each entry is `<type>:<weight>` for rule, or `<type>:<path>:<weight>` for learned. Pass the parsed list to `RedEnv(opponents=...)`.

Default behavior (no CLI flags): rule-only pool, no warmstart — matches existing behavior.

## Smoke test

After coding, run these 3 tests (all should complete in < 1 minute each):

1. **Rule-only (regression)**: `python -m rl.red_smoke` — should still pass 3/3.
2. **Rule vs Blue1 pool**: add a new test in `red_smoke.py` or a new `red_smoke_pool.py` that:
   - Constructs `RedEnv` with `opponents=[(RuleBlueOpponent(), 0.5), (LearnedBlueOpponent("models/blue_ai_1m_2xpenalty/model.zip"), 0.5)]`
   - Runs 20 steps with random-masked Red action
   - Confirms no crashes, no NaN rewards
   - Prints "opponent used this episode" from env's info dict (add this for diagnostics)
3. **Warmstart smoke**: `python -m rl.red_train --total-steps 10000 --n-envs 2 --gamma 0.9995 --warmstart runs/red_20260421_205051/model.zip --opponent-pool "rule:0.5,learned:models/blue_ai_1m_2xpenalty/model.zip:0.5"` — should produce 1 PPO iteration without crash, save model.

Save all test outputs.

# Task

4 subtasks, 4 commits. **LOCAL ONLY** — do NOT push.

## Subtask A — `blue_opponents.py` module (~45-60 min)

Implement the `BlueOpponent` abstract class + `RuleBlueOpponent` + `LearnedBlueOpponent` per design above. Include the Blue action-application port from Boyu's env.py.

**Commit:** `feat(rl): blue_opponents — RuleBlueOpponent + LearnedBlueOpponent for pool training`

## Subtask B — RedEnv opponent-pool support (~30-45 min)

Modify `red_env.py` to accept an `opponents` list in constructor, select per-episode at `reset()`, and delegate `act()` each step. Backward compat: default is `[(RuleBlueOpponent(), 1.0)]`.

**Commit:** `feat(rl): RedEnv opponent-pool support (per-episode opponent selection)`

## Subtask C — red_train.py warmstart + pool CLI (~30-45 min)

Add `--warmstart <path>` and `--opponent-pool <spec>` CLI flags to `red_train.py`. Wire through to VecEnv construction and model init.

**Commit:** `feat(rl): red_train.py --warmstart + --opponent-pool flags`

## Subtask D — Smoke + final summary (~20-30 min)

Run the 3 smoke tests per Design above. Fix anything that breaks. Update `red_smoke.py` if a pool-aware test is worth adding there (or a separate `red_smoke_pool.py`).

**Commit:** `test(rl): opponent-pool smoke tests + warmstart verification`

**Do NOT run the overnight training.** That's Chen's manual launch.

# Rules

- **LOCAL ONLY commits** on `rl-self-play-v1`. Do NOT push.
- **Do NOT commit the Blue1 model.zip** (at `models/blue_ai_1m_2xpenalty/model.zip`). That's a local training asset. If it's staged at end of worker, `git restore --staged <path>` to un-stage (keeps file on disk, removes from index). Leave it untracked.
- **Do NOT commit Red1 model.zip or training runs directories** (they remain untracked locally).
- **Do NOT modify Boyu's `env.py` or `train.py`** — those stay clean for Boyu's use.
- **Do NOT modify game-core sim code** (`backend/sim/*.py`) — read-only.
- **No force-push, no amend, no --no-verify** (moot since no pushing).
- **English** in code / comments / commits.

# Post-flight

1. `git status` — clean commit-wise (may show untracked model.zip + runs directories, that's fine).
2. `git log --oneline -6 rl-self-play-v1` — 4 new commits above `a72adc5`.
3. Do NOT push.

# Deliverable — final summary (≤ 400 words)

1. **Commits landed (local)** — 4 hashes + one-line each.
2. **Opponent pool design** — how you structured `BlueOpponent` interface, how pool selection works, any surprises in Blue action-mask conversion.
3. **Warmstart wiring** — does `--warmstart` correctly load Red1 and continue?
4. **Smoke test results** — 3/3 tests with outputs. Flag anything suspicious (e.g., reward magnitudes changing when swapping opponents).
5. **The overnight launch command** — **exact command Chen copy-pastes** to start the 8M overnight run. For example:
   ```powershell
   cd C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend
   python -u -m rl.red_train --total-steps 8000000 --n-envs 16 --gamma 0.9995 --save-every 1000000 --warmstart runs/red_20260421_205051/model.zip --opponent-pool "rule:0.5,learned:models/blue_ai_1m_2xpenalty/model.zip:0.5" 2>&1 | Tee-Object -FilePath training_red_8m_pool.log
   ```
   Adjust per your actual CLI flag names. Include a pre-check: "make sure `nvidia-smi` shows 5070 free before launching, and confirm Blue1 model.zip is in place."
6. **Expected wall-clock for 8M** — based on your smoke test's steps/sec, estimate the overnight duration. If < 8 hours, can increase to 10M; if > 9 hours, reduce to 6M so Chen doesn't wake up to in-progress training.
7. **Flag for morning cross-eval** — once Red2 lands tomorrow, what tournament should Chen run? (Probably 3×2 matrix: rule_Red, Red1, Red2 × rule_Blue, Blue1. That's 6 pairs × 30 games = 180 games, still fast.)

Chen reads this summary, launches the command in a standalone PowerShell, goes to bed. Morning = Red2 ready.
