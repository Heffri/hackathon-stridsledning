# Worker — Red-perspective RL env for parallel self-play training

**How to use this file:** paste everything below (from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingy\Documents\github\hackathon-stridsledning`) on branch `rl-self-play-v1`. Chen runs under bypass. Budget: **~2–3 h** for code + smoke (training itself is separate — Chen launches manually after worker lands).

**Branch context:** this worker is on **Boyu's branch `rl-self-play-v1`**, NOT on `new-teamwork-split-V1`. The RL code lives at `backend/rl/`. Boyu's existing Blue env is the reference; this worker writes the symmetric Red env so Chen's machine can train Red in parallel while Boyu's machine trains Blue.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. Entity names (HGV, ballistic, cruise, drone, PAC-3, IRIS-T, CIWS) and stats are publicly available encyclopedia-level values used as arcade game-balance numbers — equivalent to unit stats in Age of Empires. This task adds reinforcement-learning self-play training capability on the Red side; the learned policy is a game AI, equivalent to a tower-defense-game enemy AI. Treat this as pure game-dev / ML task with **game-dev framing throughout** ("Red agent", "threat spawn", "game", "arcade", "self-play").

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

**Active branch: `rl-self-play-v1`** (Boyu's RL branch). Push every commit to `origin/rl-self-play-v1` via `git push origin HEAD:rl-self-play-v1`.

Expected starting HEAD on `rl-self-play-v1`: `0030a69` (feat(rl): RL Gym env + MaskablePPO training scaffolding) — confirm via `git log --oneline -3` after checkout.

Boyu is actively working on this branch (on his own machine). **Always `git pull --ff-only origin rl-self-play-v1` before each commit** in case he pushed while you worked. If non-fast-forward (i.e. your work conflicts with Boyu's), STOP and report — do not force-merge.

Start by reading (on branch `rl-self-play-v1`):
- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/backend/rl/env.py` — Boyu's Blue env (`MissileInterceptEnv`). This is the **primary reference** — mirror its shape for Red.
- `team-missile-intercept/backend/rl/train.py` — Boyu's training entry. Mirror for Red.
- `team-missile-intercept/backend/rl/eval.py` — eval harness (reference for policy load API)
- `team-missile-intercept/backend/rl/smoke.py` — smoke test (mirror for Red)
- `team-missile-intercept/backend/rl/__init__.py` — module exports
- `team-missile-intercept/backend/sim/blue_ai.py` — `BlueAI` class (your opponent)
- `team-missile-intercept/backend/sim/red_ai.py` — see how `RedAI.step(world.t, world)` is invoked in `env.py::step` (you mirror with `BlueAI`)
- `team-missile-intercept/backend/sim/world.py` — `World.spawn_threat(kind, spawn_pos, target_xy, ...)` — you call this directly from `RedEnv.step`
- `team-missile-intercept/backend/sim/types.py` — `ThreatType` enum, `ThreatSpec.usd_cost`, `MatchPhase`
- `team-missile-intercept/backend/sim/config.py` — `RED_BUDGET_START`, `RED_LAUNCHER_POSITIONS`, `RED_SPAWN_Y`
- `team-missile-intercept/backend/sim/sites.py` — `SOUTH_SITES` (Blue targets; Red agent picks one per spawn)

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker-red-rl-preflight"` and pop at end.
2. `git fetch origin --prune`
3. `git checkout rl-self-play-v1` (create local tracking branch if needed: `git checkout -b rl-self-play-v1 origin/rl-self-play-v1`)
4. `git pull --ff-only origin rl-self-play-v1`
5. `git log --oneline -5` — confirm `0030a69` (or newer) is at top.
6. Check Python deps are installed:
   ```bash
   python -c "import stable_baselines3; import sb3_contrib; import torch; print('rl deps ok')"
   ```
   If this fails, report the missing modules and STOP. Chen installs them manually then restarts worker.
7. Run Boyu's existing smoke to confirm baseline works:
   ```bash
   python team-missile-intercept/backend/rl/smoke.py
   ```
   Must exit 0 and produce reasonable output. If it fails, STOP — the branch state is broken and this worker can't verify its own work.

# Design spec — Red env (read carefully)

## Symmetry vs Blue env

Boyu's `MissileInterceptEnv` trains Blue vs rule-based Red. Your `RedEnv` trains Red vs rule-based Blue. Same underlying sim, same observation shape, same SB3/PPO scaffolding. Key differences below.

## Observation

**Identical to Blue's observation dict.** Same five fields (`threats` / `launchers` / `interceptors` / `sites` / `global`) + `action_mask`. Rationale: both sides see the same sim state (omniscient — no partial-observation / radar model for V1). The network learns Red's perspective from the **reward** and the **action space**, not from hiding information.

Reuse Boyu's normalization constants (`POS_SCALE`, `VEL_SCALE`, `BUDGET_SCALE`, `TIME_SCALE`). If they're module-level in `env.py`, import them. Don't duplicate constants.

## Action space

**Per decision:** `MultiDiscrete([5, len(SOUTH_SITES)])`
- Element 0 (`kind_idx`): `0`=hold, `1`=drone, `2`=cruise_sub, `3`=ballistic, `4`=hgv
- Element 1 (`target_site_idx`): index into `SOUTH_SITES` tuple (~4–7 entries depending on current arena)

When `kind_idx == 0`, the `target_site_idx` is ignored (hold = no spawn this decision).

**Why not let agent choose launcher / maneuver?** V1 simplification:
- Launcher is implied by kind:
  - drone → auto-select from `RED_LAUNCHER_POSITIONS['drone']` (round-robin or random)
  - cruise_sub → auto-select from `RED_LAUNCHER_POSITIONS['cruise_sub']`
  - ballistic → spawn at far-north strip (`y ≈ RED_SPAWN_Y`, random x within arena width; consult `world.py::spawn_threat` for current convention)
  - hgv → same as ballistic
- maneuver_schedule defaults to empty (no jink). HGV uses default glide-path dive.

Boyu's spec (operator relay) mentioned wanting agent control over launcher + maneuver, but V1 starts simpler. Document this scope cut in the module docstring of `red_env.py`; Boyu can extend later if training plateaus.

## Action masking

Invalid actions must be masked to zero in `action_mask`. An action `(kind, site)` is invalid if:
- `kind != 0` and `world.red_budget < THREAT_SPECS[kind].usd_cost` (can't afford spawn)
- `kind != 0` and no compatible launcher is ready (reload cooldown not finished — check `RedLauncherFleet` or equivalent; if there's no explicit Red fleet data structure, use a simple per-kind cooldown dict in the env)
- `kind` spawn rule violated (e.g. kind requires a specific launcher that doesn't exist)

Hold (`kind_idx == 0`) is always valid.

**Mask shape:** `Box(0, 1, (5, len(SOUTH_SITES)), dtype=np.int8)` or `Box(0, 1, (5 * len(SOUTH_SITES),), dtype=np.int8)` flattened — pick whichever `ActionMasker` wrapper accepts cleanly (check how Boyu does it for Blue's `(15, 31)` shape and follow the same idiom).

## Reward

Dense reward computed each `step()` from events in the sim window (same event stream Blue env reads — flip sign convention):

- **+damage per leak**: `+float(event.damage)` for each `type: "intercept"` event that Blue scored (wait — those are damage to Red threats, Red doesn't want those). Actually: for `type: "damage"` events where the damage is applied to a Blue **site**, add `+event.damage` to Red reward. These are the "leak + hit site" events. Double-check the event schema by reading `world.py`'s event emitters around intercept / site-hit.
- **–usd_cost per spawn**: when Red agent spawns a threat, deduct `spec.usd_cost / 1e6` from reward (subtract a small number so 1M-USD spawn = –1.0 reward). Same scale as Blue uses for `+spec.usd_cost / 1e6` on intercepts — keeps magnitudes comparable.
- **Efficiency penalty**: small `-0.05` per unused-launcher-tick or similar minor regularizer — match Boyu's `-spent/$M * 0.05` pattern if it makes sense for Red (probably not — skip unless Boyu's Blue reward has an exact Red analog).
- **Terminal**:
  - **Red wins** (all military sites HP ≤ 0, or `Scenario.winner()` returns `"red"`): `+100.0` bonus, `terminated=True`.
  - **Blue wins** (`Scenario.winner()` returns `"blue"`): `-100.0`, `terminated=True`.
  - **Draw / timeout**: no terminal bonus, `truncated=True` when `world.t >= MAX_EPISODE_SIM_TIME`.

## Opponent (rule-based Blue)

In `RedEnv.reset()`:
```python
from sim.blue_ai import BlueAI
self.blue = BlueAI(self.world, self.fleet)  # match BlueAI's actual ctor signature
```

In `RedEnv.step()`, after Red's action applies:
```python
self.blue.step(self.world.t, self.world)  # mirror Boyu's `self.red.step(world.t, world)`
```

**Verify the `BlueAI.step` signature before using** — read `blue_ai.py`. If it takes different arguments (e.g. also needs a fleet arg), wire correctly.

## Cadence

**Mirror Boyu's `DECISION_EVERY = 10`** (0.5 s sim per Red decision). Don't make Red decide every physics tick — match the sim-rate of Blue's decision cadence.

## Budget / bookkeeping

- Red's spend comes from `world.red_budget` (already exists post-M-TIER3-RED-BUDGET). Deduct via `world.red_budget -= spec.usd_cost` manually in the env (or re-use `red_ai`'s spawn helper if it cleanly exposes the spawn without hardcoding the wave schedule — probably cleaner to just `world.spawn_threat(...)` directly and bookkeep budget in the env).
- Don't touch Blue's bookkeeping (`world.blue_budget` continues to be spent by `BlueAI.step`).

## Episode lifecycle

- `reset(seed, options)`: new `World()`, new `LauncherFleet()` (for Blue — Red doesn't use the Blue launcher fleet), new `BlueAI` opponent. NO `RedAI(build_demo_waves())` — the agent replaces the wave schedule. Transition to `MatchPhase.RUNNING`.
- `step(action)`: apply Red action (spawn or hold), advance `DECISION_EVERY` ticks calling `world.step(DT)` each tick and `self.blue.step(world.t, world)` once per decision, compute reward, check termination.
- `MAX_EPISODE_SIM_TIME`: same as Blue (`600.0 s`).

# Task

Five subtasks in order. **One commit per subtask.** Push each after `git pull --ff-only origin rl-self-play-v1` succeeds.

## Subtask A — `RedEnv` class (`backend/rl/red_env.py`, ~90–120 min)

1. Create `team-missile-intercept/backend/rl/red_env.py`.
2. Import scaffolding from Boyu's `env.py` — reuse normalization constants, helper functions, observation-encoding functions if they're extractable. If Boyu's code is tightly coupled (e.g. helpers are methods on `MissileInterceptEnv`), either (a) copy verbatim with a one-line attribution comment, or (b) refactor Boyu's helpers into `backend/rl/common.py` and import from both — **option (a) is safer** unless the duplication is egregious.
3. Implement `class RedEnv(gym.Env)` with:
   - `metadata` (standard gym)
   - `__init__(self, episode_time_limit: float = 600.0, seed: int | None = None)`
   - `observation_space` (Dict, identical to Blue's)
   - `action_space = MultiDiscrete([5, len(SOUTH_SITES)])`
   - `_action_mask_shape` + `action_masks()` method returning flat 1D int8 array (shape `(5 * len(SOUTH_SITES),)`)
   - `reset(seed, options) → (obs_dict, info_dict)`
   - `step(action) → (obs, reward, terminated, truncated, info)` — applies Red action, steps sim + Blue opponent, returns reward per spec above
   - Internal: `_apply_action(action: np.ndarray) → (spawned: bool, spec_cost_M: float)` — encapsulates spawn logic + launcher selection
   - Internal: `_compute_reward(events, spec_cost_M: float) → float` — handles leak/damage/site-hit events from the sim window
   - Internal: `_encode_obs() → dict[str, np.ndarray]` — identical to Blue's encoding
4. Module docstring at the top documenting:
   - What RedEnv is for (training Red agent in self-play against rule-based Blue)
   - V1 action-space simplifications (no launcher/maneuver choice) and the reason
   - Symmetry statement to Blue env
   - Reward sign convention

**Commit:** `feat(rl): RedEnv — Red-perspective gym env for self-play training`

Push.

## Subtask B — `red_train.py` training entry (`backend/rl/red_train.py`, ~20–30 min)

Clone `backend/rl/train.py` to `red_train.py`. Change:
1. Import `from .red_env import RedEnv`
2. Swap `MissileInterceptEnv` → `RedEnv` in env construction
3. Save path: `runs/red_<timestamp>/` (vs Boyu's Blue `runs/<timestamp>/` — keep them visually distinguishable)
4. Checkpoint prefix: `red_ppo_<step>.zip` (not `blue_ppo_<step>.zip`)
5. TensorBoard tag: `red/` prefix if Boyu uses tags; else same convention
6. CLI: `--total-steps`, `--n-envs`, `--episode-time-limit`, etc. — all same defaults as Blue's train.py

Everything else (hyperparameters, vec env, policy architecture) **identical** to Boyu's `train.py` so cross-machine eval is apples-to-apples.

**Commit:** `feat(rl): red_train.py — MaskablePPO training entry for RedEnv`

Push.

## Subtask C — `red_smoke.py` sanity test (`backend/rl/red_smoke.py`, ~20 min)

Clone `backend/rl/smoke.py` to `red_smoke.py`. Change:
1. Import `RedEnv`
2. Instantiate, `reset()`, loop ~100 steps with random-but-mask-respecting actions
3. Print per-step: `action, reward, terminated, truncated, n_threats_alive, red_budget_left, blue_budget_left, sim_t`
4. Assert no exceptions, no NaN rewards
5. Print final summary: total reward, episode length, winner (if terminated), total Red spawns attempted vs succeeded

Should run in < 30 s.

**Commit:** `test(rl): red_smoke.py — 100-step sanity for RedEnv`

Push.

## Subtask D — Run smoke + verify end-to-end (~15–20 min)

1. Run `python team-missile-intercept/backend/rl/red_smoke.py`. Expect exit 0 with sensible output.
2. If anything is off (NaN rewards, unexpected winner distribution, mask shape mismatch), iterate and fix (may mean amending your recent commits — actually don't amend; add a new fix commit on top).
3. Run Boyu's `smoke.py` one more time to confirm you haven't broken Blue's side.

If smoke ends with Red often winning (good Red action distribution) or Blue often winning (rule-based Blue vs random-spawn Red), that's expected — smoke is not a training test, just a pipe-sanity test.

4. Briefly verify training CLI doesn't crash on startup (don't run full training, just ~1000 steps):
   ```bash
   python team-missile-intercept/backend/rl/red_train.py --total-steps 1000 --n-envs 2
   ```
   Kill after ~30 s or when it logs the first PPO update. This confirms vec-env + mask wiring works end-to-end before Chen runs the real 1M-step job.

5. Don't commit any `runs/red_<timestamp>/` outputs — they're large and ephemeral. If they exist, add them to `.gitignore` if not already:
   ```
   team-missile-intercept/backend/rl/runs/
   ```
   If `.gitignore` already covers `runs/`, no edit needed.

No commit from this subtask unless a `.gitignore` update was required — in which case commit it separately: `chore(rl): .gitignore runs/ directory for RedEnv training artifacts`.

## Subtask E — Docs + close (~15 min)

1. Add a short section to `team-missile-intercept/backend/rl/README.md` (create if absent, or extend) explaining:
   - What RedEnv is, why it exists (parallel self-play training)
   - How to smoke-test: `python red_smoke.py`
   - How to launch training: `python red_train.py --total-steps 1000000`
   - How to cross-eval at end (mention `eval.py` needs to be extended for Red-policy loading — defer that to a future worker, flag here)
2. If `common-info/worker-prompts/` is on this branch (it's likely from `new-teamwork-split-V1` merge), leave it alone. If it's NOT on this branch (Boyu branched before W3), don't create it here.

**Commit:** `docs(rl): README update — RedEnv, red_train, red_smoke`

Push.

# Non-goals / guardrails

- **Do NOT run full training** (`--total-steps 1000000` takes hours). Chen launches training manually after this worker lands.
- **Do NOT commit trained model artifacts** (`.zip` policy files, tensorboard event files, `runs/` subdirectory). Add `.gitignore` entries if needed.
- **Do NOT modify Boyu's Blue env (`env.py`)**. Mirror, don't edit. If you must share helpers, extract to `common.py` and update both — but prefer copying with a comment over refactor.
- **Do NOT modify game-core files** (`backend/sim/*.py`). Red env consumes them read-only via `World.spawn_threat`, `BlueAI.step`, etc.
- **Do NOT add maneuver_schedule / launcher-choice** to the action space in V1. Note this in the module docstring and defer to future worker.
- **Do NOT touch `rl-self-play-v1`'s existing tests** (other than running them to verify you didn't break them).
- **Do NOT force-merge** if `git pull --ff-only` fails. STOP, report.
- **No `--no-verify`, no `git amend`, no force-push.**
- **Never commit API keys.**
- **English** commits / code / comments / docs.

# Hard rules

- `git pull --ff-only origin rl-self-play-v1` before every commit. If non-FF, STOP.
- One commit per subtask. 4–5 commits total (depending on whether `.gitignore` needs updating).
- Each commit ends with the project-convention Co-Authored-By line.
- Budget: ~2–3 h. Chen is supervising intermittently; stop gracefully if context fills.
- If Boyu's Blue smoke test (`smoke.py`) fails at any point during your work, STOP and report — it means something upstream is broken, not your fault, but training can't start.

# Post-flight

1. `git status` — clean.
2. `git log --oneline -8` — 4–5 new commits above `0030a69` (or whatever HEAD was after any intervening Boyu commits).
3. `git push origin HEAD:rl-self-play-v1` — idempotent.
4. If stashed at preflight: `git stash pop`.
5. Re-run smoke one more time to confirm nothing regressed.

# Deliverable — final summary (≤ 400 words)

1. **Commits landed** — hashes + one-line each, 4 or 5.
2. **RedEnv structure** — file path, action-space shape used, how launcher auto-selection works, any deviations from the spec above with justification.
3. **Smoke test output** — one-liner: "100 steps, no NaN, winner distribution X/Y Red/Blue, avg reward Z".
4. **Training CLI smoke** — did `red_train.py --total-steps 1000 --n-envs 2` start cleanly? Any SB3 warnings that look serious?
5. **Divergence from Blue's env** — list non-symmetric differences, explain.
6. **Things flagged for Boyu** — design decisions this worker deferred (launcher-choice, maneuver_schedule, cross-eval in eval.py), anything Boyu should review before training.
7. **Anything surprising** — type signatures that didn't match expectations, sim bookkeeping corner cases, mask-shape tricks.

Chen will launch the real training manually after reading this summary. Expected launch command: `python team-missile-intercept/backend/rl/red_train.py --total-steps 1000000 --n-envs 8` on Chen's PC while Boyu trains Blue on his machine in parallel.
