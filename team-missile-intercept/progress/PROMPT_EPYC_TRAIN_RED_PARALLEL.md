# PROMPT — EPYC Red Trainee v2 (parallel to Blue megamodel)

> **Framing (read first, non-negotiable)**: This repo is a **Saab 2026 student hackathon entry** — a browser-based arcade-style game/demo, in the same category as a tower-defense game. All entity names (CIWS, RBS-70, drone, cruise_sub, PAC-3, HGV, etc.) are publicly available encyclopedia-level values used as **arcade game-balance numbers**, equivalent to unit stats in Age of Empires. They encode no non-public or tactical information. This is **not** a military product, weapons system, training tool, or command-and-control system. Describe the work as RL training for a hackathon game/demo.

## Mission summary

You are running on the same EPYC 9554P that's currently running a Blue megamodel curriculum training. Your job is to train **a Red AI in parallel**, against a **rotating pool of pre-trained Blue opponents**, with **fixed reward bugs** and **HGV maneuver capability wired in**.

The Blue training is happening in tmux session `train` (Claude orchestrator) and `megamodel` (sub-process). **DO NOT touch those tmux sessions, the `~/hackathon-stridsledning/` directory, the `train-megamodel-cap72` branch, or any file Blue is reading/writing**. You operate on an independent git worktree, independent branch, independent tmux.

This is fully automated. After you launch the training loop, you do not need user input. Each mini-stage's convergence triggers an immediate push.

Output:
- `rl/runs/red_local/red_trainee_parallel/model.zip` — final Red policy (cumulative, end-of-curriculum)
- `rl/runs/red_local/red_trainee_parallel/stages/R1a_*.zip` ... `R1d_*.zip` — per-mini-stage end checkpoints
- `rl/runs/red_local/red_trainee_parallel/training.log` — full stdout
- Per-stage commit + push to `train-red-trainee-parallel` branch

## Why this run is "v2"

The existing Red model in `rl/runs/` was trained against a `red_env.py` that has **two known bugs**:

1. **`_winner` returns "red wins" when ANY single base hits HP 0** — should be "all military bases dead" (mirror Blue env). Old Red learned to kill 1 base then expected episode termination; never learned full-takedown strategy.

2. **Reward only counts leak damage absolute** — gives 8× more reward for HGV (~80 dmg) than drone (~10 dmg) per leak, no cost awareness. Old Red learned to spam HGVs because that's the highest absolute-reward kit; never learned cost-effective tactics.

You are fixing both, plus adding:
- **Cost-asymmetric reward** (drain mode + cheap-killed-expensive penalty)
- **Base-weight scaling** (last-alive base 3× more valuable, V4 mirror)
- **HGV evasion capability** (action space expansion + sim-side `override_maneuver` integration that's already implemented in entities.py — just needs wiring)
- **HGV evasion reward** (only when actually dodging a real PAC, not for spinning in air)

## Hardware target

EPYC 9554P: 64 physical cores, 128 SMT threads. Use `--n-envs 48`.

Per-process IPC is independent: Blue's main process and Red's main process each have their own pipes. 48+48=96 env workers in parallel is well below 128 threads. If Blue's fps degrades > 30% from baseline (~500 fps), drop to 32; otherwise keep 48.

## Setup tasks

### 1. Verify Blue is running and you're not in its way

```bash
tmux ls
```

Should show at least `train: ...` and `megamodel: ...`. **Do not attach to either.** If they're not there, Blue may have crashed — STOP and ask the user.

### 2. Create independent git worktree

```bash
cd ~/hackathon-stridsledning
git fetch origin
git worktree add ../hackathon-stridsledning-red \
  -b train-red-trainee-parallel origin/final-demo
cd ../hackathon-stridsledning-red
git push -u origin train-red-trainee-parallel
```

### 3. Share Blue's venv (saves install time)

```bash
cd team-missile-intercept/backend
ln -s /home/chen/hackathon-stridsledning/team-missile-intercept/backend/.venv .venv
source .venv/bin/activate

# Sanity check
python -c "import numpy as np, torch, sb3_contrib; print(np.__version__, torch.__version__)"
```

If symlink fails, build an independent venv:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install numpy==1.26.4
pip install -r requirements.txt
pip install "torch>=2.4,<2.6" stable-baselines3 sb3-contrib gymnasium
```

### 4. Run base smoke

```bash
cd team-missile-intercept/backend
python -m rl.live_ai
```

Should print `Smoke OK.` Confirms repo runs as-is.

### 5. Create run dir

```bash
RED_RUN_DIR=rl/runs/red_local/red_trainee_parallel
mkdir -p ${RED_RUN_DIR}/stages
pip freeze > ${RED_RUN_DIR}/pip_freeze.txt
```

## Code changes

All changes are in **THIS worktree only** (`~/hackathon-stridsledning-red/`).

### 5A. Cap bump in `backend/rl/env.py`

```python
# Was: MAX_THREATS = 120, MAX_LAUNCHERS = 60, MAX_INTERCEPTORS = 160
MAX_THREATS = 72
MAX_LAUNCHERS = 32
MAX_INTERCEPTORS = 128
```

Same change Blue worker is making, but on this worktree's copy. Both Red and Blue trained at the same cap so future cross-eval / next-cycle co-training works without adapter dance.

### 5B. Fix `_winner` bug in `backend/rl/red_env.py`

Find the `_winner` method (around line 355). Replace:

```python
def _winner(self) -> Optional[str]:
    # Red wins when any military site's HP is depleted.
    for site in sites_module.SOUTH_SITES:
        if site.hp <= 0:
            return "red"
    cheapest = min(spec.usd_cost for spec in THREAT_SPECS.values())
    red_stuck = self.world.red_budget < cheapest
    no_threats = all(not t.state.alive for t in self.world.threats.values())
    if red_stuck and no_threats:
        return "blue"
    return None
```

With:

```python
def _winner(self) -> Optional[str]:
    # M-TIER3-RED-WINNER (2026-04-26): Red wins ONLY when ALL military bases
    # are dead. Old code returned "red" on any single base at hp=0, which
    # caused the trained Red to learn "kill one base then stop" — never
    # learned full-takedown strategy. This now mirrors Blue env's win
    # condition (env.py:_winner). Issue #9-style military-only gate.
    military_bases = [
        s for s in sites_module.SOUTH_SITES
        if s.subtype in ('base', 'air_base')
    ]
    if military_bases and all(s.hp <= 0 for s in military_bases):
        return "red"

    cheapest = min(spec.usd_cost for spec in THREAT_SPECS.values())
    red_stuck = self.world.red_budget < cheapest
    no_threats = all(not t.state.alive for t in self.world.threats.values())
    if red_stuck and no_threats:
        return "blue"
    return None
```

### 5C. Reward function rewrite in `backend/rl/red_env.py`

Find `_reward_from_events` (around line 487). Replace its body with:

```python
def _reward_from_events(self, events: List[dict]) -> float:
    """Per-tick dense shaping (Red trainee v2, 2026-04-26).

    Layered signal:
      1. Leak event:
         - Military base: 10 * (dmg / total_hp) * base_weight
           where base_weight = n_initial / n_alive (3 alive: 1.0, 1 alive: 3.0).
           Killing the LAST base gives 3x the reward of killing the first.
         - Civilian / unknown site: 2 * (dmg / total_hp), no scaling.

      2. Intercept event (Red threat killed by Blue interceptor):
         - inter_cost > 5x threat_cost: drain mode bonus
           (Blue paid > 5x to kill Red's cheap threat — Red wins exchange)
         - threat_cost >= $1M AND inter_cost < 0.1x threat_cost: penalty -1.5
           (Red wasted high-value kit on cheap counter)
         - else: 0 (single-charge cost model already taxed Red at spawn).

      3. Ground crash of a Blue PAC interceptor whose target was an
         alive HGV that was maneuvered within the last 10 ticks: +1.0
         (HGV truly dodged a PAC, not just spinning in air).

      4. Ground crash of a Red threat: -0.2 (wasted spawn).

    Caller invokes BEFORE world.prune_dead so events resolve to live
    interceptor / threat objects.
    """
    from sim.types import INTERCEPTOR_SPECS, InterceptorType

    r = 0.0

    # Base-weight scaling (V4 mirror).
    military_subtypes = ('base', 'air_base')
    n_alive = max(1, sum(
        1 for s in sites_module.SOUTH_SITES
        if s.subtype in military_subtypes and s.hp > 0
    ))
    n_initial = max(1, sum(
        1 for s in sites_module.SOUTH_SITES
        if s.subtype in military_subtypes
    ))
    base_weight = n_initial / n_alive  # 3 alive: 1.0, 2: 1.5, 1: 3.0

    for ev in events:
        et = ev.get("type")

        if et == "leak":
            dmg = ev.get("damage", 0)
            site_name = ev.get("site", "")
            site = next(
                (s for s in sites_module.SOUTH_SITES if s.name == site_name),
                None,
            )
            if site is not None and site.subtype in military_subtypes:
                r += 10.0 * (float(dmg) / self._total_site_hp) * base_weight
            else:
                r += 2.0 * (float(dmg) / self._total_site_hp)

        elif et == "intercept":
            iid = ev.get("interceptor")
            tid = ev.get("threat")
            inter = self.world.interceptors.get(iid) if iid is not None else None
            threat = self.world.threats.get(tid) if tid is not None else None
            if inter is not None and threat is not None:
                try:
                    inter_kind = InterceptorType(inter.state.kind)
                    threat_kind = ThreatType(threat.state.kind)
                    inter_cost = INTERCEPTOR_SPECS[inter_kind].usd_cost
                    threat_cost = THREAT_SPECS[threat_kind].usd_cost

                    if inter_cost > threat_cost * 5.0:
                        # Drain: Blue paid > 5x to kill Red's cheap threat.
                        r += min(inter_cost / threat_cost / 20.0, 1.0)
                    elif threat_cost >= 1_000_000 and inter_cost < threat_cost * 0.1:
                        # Red invested >$1M, killed by <10% the cost.
                        r -= 1.5
                except (KeyError, ValueError):
                    pass

        elif et == "ground_crash" and ev.get("interceptor") is not None:
            # HGV evasion bonus — only when target was an alive
            # maneuvered HGV and the dead interceptor is PAC-2/PAC-3.
            iid = ev["interceptor"]
            inter = self.world.interceptors.get(iid)
            if inter is None:
                continue
            target = self.world.threats.get(inter.target_id)
            if target is None or not target.state.alive:
                continue  # target already dead — not a dodge
            try:
                if ThreatType(target.state.kind) != ThreatType.HGV:
                    continue
                inter_kind = InterceptorType(inter.state.kind)
                if inter_kind not in (
                    InterceptorType.LONG_SAM, InterceptorType.HIT_TO_KILL,
                ):
                    continue
                last_maneuver = self._hgv_recently_maneuvered.get(
                    target.state.id, -999_999,
                )
                if self._tick_counter - last_maneuver < 10:
                    r += 1.0  # Real PAC dodge by maneuvered HGV.
            except (KeyError, ValueError):
                pass

        elif et == "ground_crash" and ev.get("threat") is not None:
            r -= 0.2

    return r
```

### 5D. HGV evasion wiring

Three sub-changes in `backend/rl/red_env.py`:

#### 5D-i. Action space: add evasion bit

Find where `action_space` is defined (likely in `__init__`):

```python
# Was: self.action_space = spaces.MultiDiscrete([N_RED_KINDS, n_sites])
# After:
self.action_space = spaces.MultiDiscrete([N_RED_KINDS, n_sites, 2])
# Third dim: 0 = no evasion this tick, 1 = trigger HGV evasion this tick.
```

#### 5D-ii. Action mask: extend for evasion bit

Find `_build_action_mask` (around line 415). Update:

```python
def _build_action_mask(self) -> np.ndarray:
    n_sites = self._n_sites
    # Extended for evasion bit: kind + site + 2 (evasion 0/1 always legal).
    mask = np.zeros(N_RED_KINDS + n_sites + 2, dtype=np.int8)
    mask[0] = 1  # hold
    budget = self.world.red_budget if self.world is not None else 0
    for k_idx in range(1, N_RED_KINDS):
        kind = RED_ACTION_KINDS[k_idx]
        spec = THREAT_SPECS[kind]
        if budget < spec.usd_cost:
            continue
        if kind in (ThreatType.DRONE, ThreatType.CRUISE_SUB):
            if not self.red_launchers.positions_for(kind):
                continue
        mask[k_idx] = 1
    # Site dim: every site valid.
    mask[N_RED_KINDS:N_RED_KINDS + n_sites] = 1
    # Evasion dim: both 0 and 1 always legal.
    mask[N_RED_KINDS + n_sites] = 1      # evasion = 0
    mask[N_RED_KINDS + n_sites + 1] = 1  # evasion = 1
    return mask
```

#### 5D-iii. `_apply_action` consumes evasion bit + state tracker

Add a state field in `__init__` / `reset`:

```python
# In __init__ or reset:
self._hgv_recently_maneuvered: Dict[int, int] = {}  # hgv_id → tick_when_maneuvered
self._tick_counter: int = 0
```

Update `step` to increment `_tick_counter` each call (find the existing `step` method):

```python
def step(self, action):
    self._tick_counter += 1
    # ... existing step logic
```

Update `_apply_action` (around line 380) to consume evasion bit:

```python
def _apply_action(self, action: np.ndarray) -> tuple:
    """Execute the Red decision. Returns (spawned, spawn_cost_usd).

    Action shape: (3,) — [kind_idx, site_idx, evasion_bit]
    Evasion bit (third dim, NEW v2):
      0 = no maneuver this tick
      1 = trigger HGV evasion: for every alive HGV with a Blue PAC
          interceptor in flight targeting it, compute perpendicular
          evasion direction (perpendicular to LOS to nearest such
          interceptor) and call override_maneuver(direction, 0.7 * max_g).
          Records the tick in `_hgv_recently_maneuvered` so the reward
          function can detect actual dodge events.
    """
    kind_idx = int(action[0])
    site_idx = int(action[1]) if action.shape[0] > 1 else 0
    evasion = bool(int(action[2])) if action.shape[0] > 2 else False  # NEW

    # ===== Existing spawn logic (unchanged) =====
    if kind_idx == 0:
        spawned = False
        cost_usd = 0.0
    elif kind_idx < 0 or kind_idx >= N_RED_KINDS:
        spawned = False
        cost_usd = 0.0
    else:
        kind = RED_ACTION_KINDS[kind_idx]
        spec = THREAT_SPECS[kind]
        if self.world.red_budget < spec.usd_cost:
            spawned = False
            cost_usd = 0.0
        else:
            sites_list = sites_module.SOUTH_SITES
            if not sites_list:
                spawned = False
                cost_usd = 0.0
            else:
                target_site = sites_list[site_idx % len(sites_list)]
                target_xy = target_site.pos
                target_site_id = target_site.id
                spawn_pos = self._pick_spawn(kind)
                if spawn_pos is None:
                    spawned = False
                    cost_usd = 0.0
                else:
                    try:
                        if kind == ThreatType.CRUISE_SUB:
                            wps = self._build_cruise_waypoints(spawn_pos, target_xy)
                            self.world.spawn_threat(
                                kind, spawn_pos, target_xy,
                                intermediate_waypoints=wps,
                                target_site_id=target_site_id,
                            )
                        else:
                            self.world.spawn_threat(
                                kind, spawn_pos, target_xy,
                                target_site_id=target_site_id,
                            )
                        self.world.red_budget = max(
                            0, self.world.red_budget - spec.usd_cost,
                        )
                        spawned = True
                        cost_usd = float(spec.usd_cost)
                    except ValueError:
                        spawned = False
                        cost_usd = 0.0

    # ===== NEW v2: HGV evasion application =====
    if evasion:
        self._apply_hgv_evasion()

    return spawned, cost_usd

def _apply_hgv_evasion(self) -> None:
    """For each alive HGV, find the nearest in-flight Blue PAC-2/PAC-3
    interceptor targeting it. If one exists, apply override_maneuver
    perpendicular to LOS at 0.7 * max_g and record the tick.

    HGVs without a PAC threatening them get NO maneuver — this prevents
    the policy from using evasion=1 to spin HGVs in safe airspace
    (the speed-bleed mechanic in entities._HGV_BLEED_RATE would be free
    money since no one's chasing).

    The reward function pairs this with the ground_crash detector: a
    PAC dies targeting a maneuvered HGV → +1.0 dodge bonus. Just
    triggering this method without an active PAC threat → no reward.
    """
    from sim.types import InterceptorType
    PAC_KINDS = (InterceptorType.LONG_SAM, InterceptorType.HIT_TO_KILL)

    for hgv_id, threat in list(self.world.threats.items()):
        if not threat.state.alive:
            continue
        try:
            if ThreatType(threat.state.kind) != ThreatType.HGV:
                continue
        except ValueError:
            continue

        # Find nearest in-flight PAC targeting this HGV.
        nearest_inter = None
        nearest_dist_sq = float("inf")
        for iid, inter in self.world.interceptors.items():
            if not inter.state.alive:
                continue
            if inter.target_id != hgv_id:
                continue
            try:
                inter_kind = InterceptorType(inter.state.kind)
            except ValueError:
                continue
            if inter_kind not in PAC_KINDS:
                continue
            dx = float(inter.state.pos[0] - threat.state.pos[0])
            dy = float(inter.state.pos[1] - threat.state.pos[1])
            dz = float(inter.state.pos[2] - threat.state.pos[2])
            d_sq = dx * dx + dy * dy + dz * dz
            if d_sq < nearest_dist_sq:
                nearest_dist_sq = d_sq
                nearest_inter = inter

        if nearest_inter is None:
            continue  # No PAC threat — skip (no spinning bonus).

        # Compute perpendicular direction in horizontal plane:
        # LOS = inter_pos - hgv_pos
        # perp = LOS x z_up  (gives a horizontal vector orthogonal to LOS)
        los = np.array([
            float(nearest_inter.state.pos[0] - threat.state.pos[0]),
            float(nearest_inter.state.pos[1] - threat.state.pos[1]),
            float(nearest_inter.state.pos[2] - threat.state.pos[2]),
        ])
        z_up = np.array([0.0, 0.0, 1.0])
        perp = np.cross(los, z_up)
        perp_norm = float(np.linalg.norm(perp))
        if perp_norm < 1e-6:
            continue
        direction = perp / perp_norm

        # Apply at 0.7 * max_g — keeps speed bleed manageable
        # (full max_g would stall HGV in ~30 sustained seconds).
        threat.override_maneuver(direction, threat.spec.max_g * 0.7)

        # Record for dodge detection in reward function.
        self._hgv_recently_maneuvered[threat.state.id] = self._tick_counter
```

### 5E. Obs additions: Blue budget + interceptor in-flight state

Find `_encode_obs` (around line 660 — for Red's perspective). The current obs likely has `global` (own budget, time, etc.) but probably misses Blue budget and per-kind interceptor counts.

**Goals**:
- Red knows Blue's remaining budget (drain mode triggers).
- Red knows how many interceptors of each kind are in flight (CIWS saturation signal).

Worker: read existing `_encode_obs`, identify the `global` field structure (likely 8-16 float features). Append fields:

```python
# In global obs (extend whatever's there):
g_arr[N_existing + 0] = self.world.blue_budget / BUDGET_SCALE   # NEW
g_arr[N_existing + 1] = ciws_in_flight / 20.0                   # NEW (ciws count, normalized)
g_arr[N_existing + 2] = sam_in_flight / 20.0                    # NEW (sam count, normalized)
g_arr[N_existing + 3] = pac_in_flight / 5.0                     # NEW (pac count, normalized)
```

Where:
```python
ciws_in_flight = sum(
    1 for i in self.world.interceptors.values()
    if i.state.alive and InterceptorType(i.state.kind) == InterceptorType.CIWS
)
sam_in_flight = sum(
    1 for i in self.world.interceptors.values()
    if i.state.alive and InterceptorType(i.state.kind) in (
        InterceptorType.SHORT_SAM, InterceptorType.IRIS_T_SLS, InterceptorType.MED_SAM,
    )
)
pac_in_flight = sum(
    1 for i in self.world.interceptors.values()
    if i.state.alive and InterceptorType(i.state.kind) in (
        InterceptorType.LONG_SAM, InterceptorType.HIT_TO_KILL,
    )
)
```

**Important**: extending obs requires updating `observation_space` `global` Box dim too. Bump it by 4 (or however many fields you add). Worker checks the existing dim and adds.

If the observation_space update is too invasive (touching too many places), **fall back to the simpler version**: only add Blue budget (1 new feature), skip the in-flight counts. Document the partial implementation in the report.

### 5F. Sanity smoke

```bash
cd team-missile-intercept/backend
python -m rl.live_ai
```

Should still print `Smoke OK.`. Then a quick verification:

```bash
python -c "
from rl.red_env import RedEnv
from rl.env import MAX_THREATS, MAX_LAUNCHERS, MAX_INTERCEPTORS
print(f'caps: {MAX_THREATS} {MAX_LAUNCHERS} {MAX_INTERCEPTORS}')
env = RedEnv()
print(f'action_space: {env.action_space}')
# Should print MultiDiscrete([N_RED_KINDS, n_sites, 2]) — note the 2!
mask = env.action_masks()
print(f'mask shape: {mask.shape}')
# Should be (N_RED_KINDS + n_sites + 2,)
"
```

If anything fails, fix before launching training.

## Convergence detection (helper script)

Create `scripts/check_convergence.py`:

```python
"""Same heuristic as Blue megamodel."""
import re, sys
from pathlib import Path

CONVERGENCE_RANGE = 5.0


def parse_ep_rew_means(log_path):
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
        sys.exit(2)
    values = parse_ep_rew_means(log)
    if len(values) < 3:
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

## Verify red_train.py CLI

```bash
python -m rl.red_train --help 2>&1 | head -50
```

Note which flags exist. Need at minimum:
- `--total-steps`, `--n-envs`, `--episode-time-limit`, `--save-every`, `--run-name`
- `--blue-policy-path` or `--blue-mode` (rule | learned)
- `--blue-budget`, `--red-budget`
- `--layouts-pool-slots`
- `--warmstart`

If a flag is missing, fallbacks:
1. `BLUE_POLICY_PATH=...` env var (live_ai.py reads this).
2. Patch red_train.py to add the flag.
3. Skip that mini-stage's specific opponent and use rule Blue.

## Curriculum: 4-5 mini-stages with rotating Blue opponents

Per-stage convergence loop, sequential warmstart between mini-stages, push after each.

### Common training flags

```bash
N_ENVS=48
N_STEPS=1024
BATCH_SIZE=256
N_EPOCHS=4
LR=3e-4
GAMMA=0.995
GAE_LAMBDA=0.95
ENT_COEF=0.01
CLIP_RANGE=0.2
EPISODE_LIMIT=5000.0           # match Blue
BLUE_BUDGET=200000000          # $200M (match Blue training)
RED_BUDGET=150000000           # $150M (match Blue training)
DEVICE=cpu
LAYOUTS_POOL="C C D D E F"     # C+D 33% each, E+F 17% each
RED_RUN_DIR=rl/runs/red_local/red_trainee_parallel
```

### Find old Blue models on disk

```bash
find rl/runs -name "model.zip" -path "*blue*" 2>/dev/null
find rl/runs -name "model.zip" -path "*aoe*" 2>/dev/null
find rl/runs -name "model.zip" -path "*v4*" 2>/dev/null
find rl/runs -name "model.zip" -path "*boyu*" 2>/dev/null
```

Pick 3-4 that exist and are distinct.

### Per-stage skeleton — single long train + SIGINT on convergence

**CRITICAL DESIGN NOTE**: Each `python -m rl.train` invocation spawns a fresh `SubprocVecEnv` with reset envs. Episode state does NOT persist across invocations. With `episode_time_limit=5000s` and `DECISION_EVERY` cadence, one episode = ~10000 decisions per env. Splitting a stage into 200k-step "increments" would mean 200k/48 = 4166 decisions per env per increment — **less than half an episode**. No episode would complete, `ep_rew_mean` would never be logged, and the convergence checker would never fire. (Blue worker hit this exact bug at start.)

**Correct pattern**: ONE long `python -m rl.train` per stage with `--total-steps = HARD_CAP`, with `--save-every 200000` so intermediate checkpoints exist, plus a background monitor that polls the training log and sends `SIGINT` when convergence is detected. SB3's `model.learn()` handles `SIGINT` gracefully — it saves the model and exits.

```bash
STAGE=R1?
HARD_CAP=...               # full stage cap (1M-1.5M)
WARMSTART_FROM=...          # prev stage's ckpt or "" for cold start
BLUE_OPTS="..."             # --blue-mode rule  or  --blue-policy-path PATH
RUN_NAME="${STAGE}"
STAGE_LOG=${RED_RUN_DIR}/${STAGE}_training.log

# Launch training in background
python -m rl.red_train \
  --total-steps $HARD_CAP \
  --warmstart "$WARMSTART_FROM" \
  --n-envs $N_ENVS \
  --n-steps $N_STEPS \
  --batch-size $BATCH_SIZE \
  --n-epochs $N_EPOCHS \
  --lr $LR \
  --gamma $GAMMA \
  --gae-lambda $GAE_LAMBDA \
  --ent-coef $ENT_COEF \
  --clip-range $CLIP_RANGE \
  --episode-time-limit $EPISODE_LIMIT \
  --device $DEVICE \
  --save-every 200000 \
  --run-name "$RUN_NAME" \
  $BLUE_OPTS \
  --layouts-pool-slots $LAYOUTS_POOL \
  --blue-budget $BLUE_BUDGET \
  --red-budget $RED_BUDGET \
  > $STAGE_LOG 2>&1 &
TRAIN_PID=$!
echo "[${STAGE}] training PID=$TRAIN_PID, hard cap=$HARD_CAP"

# Convergence monitor: poll log every 60s, SIGINT when converged
CHECK_INTERVAL=60
CONVERGED=0
while kill -0 $TRAIN_PID 2>/dev/null; do
  sleep $CHECK_INTERVAL
  if python scripts/check_convergence.py $STAGE_LOG; then
    echo "[${STAGE}] convergence detected; sending SIGINT to PID $TRAIN_PID"
    kill -SIGINT $TRAIN_PID
    wait $TRAIN_PID 2>/dev/null
    CONVERGED=1
    break
  fi
done
# Either converged + SIGINT'd, or hit HARD_CAP naturally — both OK.

# Locate latest checkpoint to use as stage final.
# SB3 with --save-every saves intermediate ckpts under run_name's dir.
# Try multiple plausible locations:
LATEST_CKPT=""
for candidate in \
  "${RED_RUN_DIR}/${RUN_NAME}/ckpt_latest.zip" \
  "${RED_RUN_DIR}/${RUN_NAME}/model.zip"; do
  if [ -f "$candidate" ]; then
    LATEST_CKPT="$candidate"
    break
  fi
done
# Fallback: scan for any model.zip under the run dir, take most recent
if [ -z "$LATEST_CKPT" ]; then
  LATEST_CKPT=$(find ${RED_RUN_DIR}/${RUN_NAME} -name "model.zip" -o -name "ckpt_*.zip" \
                | xargs -I{} ls -t {} 2>/dev/null | head -1)
fi
if [ -z "$LATEST_CKPT" ] || [ ! -f "$LATEST_CKPT" ]; then
  echo "[${STAGE}] FAILED to locate any saved ckpt — abort"
  exit 1
fi
cp "$LATEST_CKPT" "${RED_RUN_DIR}/stages/${STAGE}_final.zip"
echo "[${STAGE}] saved final ckpt: ${RED_RUN_DIR}/stages/${STAGE}_final.zip (from $LATEST_CKPT, converged=$CONVERGED)"
```

**Worker notes on this skeleton**:
1. `red_train.py` may save checkpoints to a different relative path. Check by listing files after the first 200k of training: `ls -la ${RED_RUN_DIR}/${RUN_NAME}/`. Adjust the `LATEST_CKPT` lookup paths to whatever red_train.py actually produces.
2. If `red_train.py` ignores `SIGINT` and exits non-gracefully (no save), increase `CHECK_INTERVAL` to give it time and rely on `--save-every` saves instead — the latest auto-save is what gets copied as stage final.
3. If neither `SIGINT` works nor periodic saves happen, fall back to letting the stage train to `HARD_CAP` and use the final model. Document in report.

After each stage, commit + push:

```bash
cd ~/hackathon-stridsledning-red
git add ${RED_RUN_DIR}/stages/${STAGE}_*
git add ${RED_RUN_DIR}/training.log
git commit -m "feat(rl): red trainee ${STAGE} done (converged=$CONVERGED)"
git push origin train-red-trainee-parallel
```

### R1a — vs rule Blue (cold start, 1.5M cap)

```bash
STAGE=R1a
HARD_CAP=1500000
WARMSTART_FROM=""
BLUE_OPTS="--blue-mode rule"
```

### R1b — vs B_shaped (warmstart R1a, 1M cap)

```bash
STAGE=R1b
HARD_CAP=1000000
WARMSTART_FROM=${RED_RUN_DIR}/stages/R1a_final.zip
BLUE_OPTS="--blue-mode learned --blue-policy-path rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip"
# If --blue-mode/--blue-policy-path don't exist, try env var:
# BLUE_POLICY_PATH=...  python -m rl.red_train ...
```

### R1c — vs V4 (warmstart R1b, 1M cap)

```bash
STAGE=R1c
HARD_CAP=1000000
WARMSTART_FROM=${RED_RUN_DIR}/stages/R1b_final.zip
BLUE_OPTS="--blue-mode learned --blue-policy-path rl/runs/blue_local/blue_v4_ciws_active/model.zip"
```

If V4 path doesn't exist, find via the search command and use what's there.

### R1d — vs Boyu V2a (warmstart R1c, 1M cap)

```bash
STAGE=R1d
HARD_CAP=1000000
WARMSTART_FROM=${RED_RUN_DIR}/stages/R1c_final.zip
BLUE_OPTS="--blue-mode learned --blue-policy-path rl/runs/blue_local/blue_boyu_v2a/model.zip"
```

Boyu V2a is at 96/24/128 cap — adapter handles. If load fails, skip to finalize.

### R1e — OPTIONAL: vs Blue megamodel S3 ckpt (warmstart R1d, 0.5M cap)

Only if Blue megamodel S3 has been pushed:

```bash
cd ~/hackathon-stridsledning
git fetch origin train-megamodel-cap72
ls rl/runs/blue_local/blue_megamodel/stages/S3_final.zip 2>/dev/null
cd ~/hackathon-stridsledning-red
```

If S3 exists:

```bash
STAGE=R1e
HARD_CAP=500000
WARMSTART_FROM=${RED_RUN_DIR}/stages/R1d_final.zip
BLUE_OPTS="--blue-mode learned --blue-policy-path /home/chen/hackathon-stridsledning/team-missile-intercept/backend/rl/runs/blue_local/blue_megamodel/stages/S3_final.zip"
```

If S3 isn't ready, skip — final is R1d_final.

### Finalize Red

```bash
LAST_STAGE=R1d   # or R1e if it ran
cp ${RED_RUN_DIR}/stages/${LAST_STAGE}_final.zip ${RED_RUN_DIR}/model.zip

cat > ${RED_RUN_DIR}/launch_cmd.txt <<EOF
[paste verbatim CLI for each stage]
EOF

cd ~/hackathon-stridsledning-red
git add ${RED_RUN_DIR}/
git commit -m "feat(rl): red trainee curriculum complete

Reward fixes (2026-04-26):
- _winner now requires ALL bases dead (was: any 1 base)
- Cost-asymmetric reward: drain bonus for cheap-vs-expensive,
  penalty for expensive-killed-by-cheap
- Base-weight scaling on leak (V4 mirror)
- HGV evasion bonus: only when actually dodging an active PAC

HGV evasion wired:
- Action space adds evasion bit
- _apply_action triggers override_maneuver(perp_to_LOS, 0.7*max_g)
  for each alive HGV with a PAC targeting it
- _hgv_recently_maneuvered tracker enables dodge detection in reward

R1a (vs rule Blue): converged at \${R1A_STEPS} steps
R1b (vs B_shaped): converged at \${R1B_STEPS} steps
R1c (vs V4): converged at \${R1C_STEPS} steps
R1d (vs Boyu V2a): \${R1D_STEPS} steps or skipped
R1e (vs megamodel S3): \${R1E_STEPS} steps or skipped

Final cumulative: \${TOTAL_STEPS} steps
Wall: \${WALL_MIN} min
"
git push origin train-red-trainee-parallel
```

## Periodic CPU contention check

Every 30-45 min:

```bash
tmux capture-pane -t megamodel -p | tail -10
htop -d 5    # 'q' to quit
```

If Blue's `fps` has dropped > 30% from its baseline (~500 fps), drop your `--n-envs` from 48 to 32 in the next mini-stage's launch.

## Report

Write to `team-missile-intercept/progress/TRAIN_RED_TRAINEE_REPORT.md`:

1. **Bug fixes confirmed**: `_winner` now multi-base, reward overhauled (4 dimensions: leak base-weight, cost-asym drain, cost-asym loss, HGV evasion bonus).
2. **HGV evasion wiring**: action space dim added, `_apply_action` evasion logic, `_hgv_recently_maneuvered` tracker, evasion reward gate.
3. **Hardware reality**: actual fps, n_envs settled, wall clock.
4. **Per-stage trajectory**: ep_rew_mean per 200k checkpoint.
5. **Opponents used**: which Blue model paths actually loaded vs fell back.
6. **CPU contention with Blue**: did Blue's fps degrade?
7. **HGV evasion behaviour observed**: spot-check the training log for "real dodge" reward firing — if it never fires, the evasion gating may be too restrictive.
8. **Compatibility notes**: numpy / torch / sb3 versions.
9. **Branch tip commit hash**.

Keep under 350 lines.

## End-of-session summary (paste in chat)

- Branch tip commit hash on `train-red-trainee-parallel`
- Per-stage convergence steps: R1a=X, R1b=Y, R1c=Z, R1d=W, R1e=V (or skipped)
- Final Red model location
- Did Blue's fps degrade?
- HGV evasion reward fired non-zero count over training (should be > 0 if HGV is actually maneuvering and surviving PACs)
- Verbatim training launch command from training.log for each stage. Missing flag = retrain invalid.

## Constraints / DON'Ts

- **DO NOT touch `~/hackathon-stridsledning/` or any file Blue is reading/writing**
- **DO NOT touch tmux sessions `train` or `megamodel`**
- **DO NOT push to `train-megamodel-cap72`**
- **DO NOT modify any file in `~/hackathon-stridsledning/`** — only `~/hackathon-stridsledning-red/`
- **DO NOT change `_reward_from_events` in env.py** — that's Blue's reward, in Blue's env. You only edit `red_env.py`'s reward function.
- **DO NOT remove the existing single-charge cost model** — spawn cost is still applied at action time, not on intercept. The new intercept rewards are ADDITIONAL signals on top, not replacements.
- **DO NOT trigger evasion (override_maneuver) when no PAC is targeting an HGV** — `_apply_hgv_evasion` self-gates this. Never call `override_maneuver` unconditionally.
- **DO NOT cap `--n-envs` past 48 unless Blue's tmux shows it's been idle** — don't steal envs from Blue.
- DO NOT install numpy 2.x.
- DO NOT use `--device cuda` unless you've verified torch sees a working GPU.
- DO NOT skip the explicit `--blue-budget 200000000 --red-budget 150000000` flags. config.py defaults are 100M/120M.
- DO NOT extend a mini-stage past `HARD_CAP` even if not converged.
- DO NOT block waiting for Blue megamodel — if S3 isn't ready when R1e would run, skip R1e.
- DO NOT amend or force-push.
- DO NOT register Red in `server.py::RED_AI_MODELS` or the frontend.
- DO NOT commit `.venv/`, `__pycache__/`, or temp files.
