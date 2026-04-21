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
- **`team-missile-intercept/common-info/gpt_advise_rl_overfitting.md`** — external senior-ML-eng consultation on reward design, action space, overfit risk, and hyperparameters for this exact task. **Read sections 1, 2, 4.** Design decisions in this prompt reflect its recommendations; read it so you understand the rationale behind gamma=0.9995, flat `Discrete` action, normalized reward, and `-5` draw penalty.
- `team-missile-intercept/backend/rl/env.py` — Boyu's Blue env (`MissileInterceptEnv`). This is the **primary reference** — mirror its shape for Red.
- `team-missile-intercept/backend/rl/train.py` — Boyu's training entry. Mirror for Red.
- `team-missile-intercept/backend/rl/eval.py` — eval harness (reference for policy load API)
- `team-missile-intercept/backend/rl/smoke.py` — smoke test (mirror for Red)
- `team-missile-intercept/backend/rl/__init__.py` — module exports
- `team-missile-intercept/backend/sim/blue_ai.py` — `BlueAI` class (your opponent)
- `team-missile-intercept/backend/sim/red_ai.py` — see how `RedAI.step(world.t, world)` is invoked in `env.py::step` (you mirror with `BlueAI`)
- `team-missile-intercept/backend/sim/world.py` — `World.spawn_threat(kind, spawn_pos, target_xy, ...)` — you call this directly from `RedEnv.step`
- `team-missile-intercept/backend/sim/types.py` — `ThreatType` enum, `ThreatSpec.usd_cost`, `MatchPhase`
- `team-missile-intercept/backend/sim/config.py` — `RED_BUDGET_START`, `BLUE_BUDGET_START`, `RED_LAUNCHER_POSITIONS`, `RED_SPAWN_Y`
- `team-missile-intercept/backend/sim/sites.py` — `SOUTH_SITES` (Blue targets; Red agent picks one per spawn)

**Note on `gpt_advise_rl_overfitting.md`**: that file will be at the above path after Chen commits it alongside this prompt update. If not present at preflight time, proceed without it — the key takeaways are already baked into this prompt's spec sections below.

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

## Action space — FLAT Discrete (revised per 2026-04-21 external RL consult)

**Per decision:** `gym.spaces.Discrete(1 + 4 * len(SOUTH_SITES))`

Action layout:
- `0` = hold (no spawn this decision)
- `1 + kind * N_SITES + site` = spawn `kind` threat targeting `SOUTH_SITES[site]`, where `kind ∈ {0:drone, 1:cruise_sub, 2:ballistic, 3:hgv}`, `site ∈ [0, N_SITES)`.

So total action count is `1 + 4 * N_SITES`. For example, with `N_SITES = 5`: actions `1..5` = drone→site_0..4, `6..10` = cruise→..., `11..15` = ballistic→..., `16..20` = hgv→..., `0` = hold.

**Why flat `Discrete` instead of `MultiDiscrete([5, N_SITES])`?** External RL consult (`common-info/gpt_advise_rl_overfitting.md`, section 4) flagged that `MultiDiscrete` factorizes the action distribution as `P(kind, site | obs) = P(kind | obs) × P(site | obs)`, so the policy cannot easily learn coupled strategies like "drones against site A, HGV against site B" — it can only learn one kind distribution and one target distribution independently. `Discrete(1 + 4*N_SITES)` lets the policy head emit a joint distribution, and action masking is exact and simple.

**Why no launcher / maneuver selection?** V1 simplification retained:
- Launcher is implied by kind:
  - drone → auto-select from `RED_LAUNCHER_POSITIONS['drone']` (round-robin or least-recently-used)
  - cruise_sub → auto-select from `RED_LAUNCHER_POSITIONS['cruise_sub']`
  - ballistic → spawn at far-north strip (`y ≈ RED_SPAWN_Y`, random x within arena width; consult `world.py::spawn_threat` for current convention)
  - hgv → same as ballistic
- maneuver_schedule defaults to empty (no jink). HGV uses default glide-path dive.

Document this scope cut in the module docstring of `red_env.py` with a TODO for Boyu's extension.

## Action masking

For `Discrete(1 + 4*N_SITES)`, mask shape is `Box(0, 1, (1 + 4 * len(SOUTH_SITES),), dtype=np.int8)` — one entry per action index.

Action `0` (hold) is **always valid** (mask=1).

Action `1 + kind * N_SITES + site` is valid iff ALL of:
- `world.red_budget >= THREAT_SPECS[kind].usd_cost` (can afford)
- A compatible launcher for `kind` is ready (off cooldown, not reloading). For drone/cruise_sub, check `RedLauncherFleet` (or equivalent) state; for ballistic/hgv the "launcher" is the abstract far-north strip so just check a per-kind cooldown dict local to the env.
- Site at index `site` is still alive (`sites[site].hp > 0`). No point targeting a dead site.

Implement action masking **inside the env's `action_masks()` method** (not via `ActionMasker` wrapper) — per sb3-contrib docs, `ActionMasker` is incompatible with `SubprocVecEnv`, so the env-native approach is required for our 8–16 parallel training. Check Boyu's `env.py` to confirm his pattern; match it.

## Reward — normalized fractions (revised per 2026-04-21 external RL consult)

Dense reward computed each `step()` from events in the sim window. Use **normalized fractions**, not raw $USD amounts — this keeps reward scale stable across the episode and comparable to the terminal bonus magnitude. Consult `common-info/gpt_advise_rl_overfitting.md` section 1 for the rationale.

**Per-step dense reward (sum of these components):**

```python
# At env init, compute the total starting site HP (sum across all Blue sites):
#     TOTAL_SITE_HP = sum(s.hp_max for s in sites)

# Per step:
r = 0.0

# (1) +10.0 × Δsite_damage_fraction  — primary Red objective
#     damage_this_step = sum of event.damage across all "damage" events
#     where event.target is a Blue site this step
r += 10.0 * (damage_this_step / TOTAL_SITE_HP)

# (2) -1.0 × Δred_spend_fraction  — cost of spawning (suppresses spam)
#     red_spend_this_step = spec.usd_cost if the agent spawned this step else 0
r -= 1.0 * (red_spend_this_step / RED_BUDGET_START)

# (3) +0.1 × Δblue_spend_fraction  — cost-exchange pressure (capped weak shaping)
#     blue_spend_this_step = sum of interceptor costs launched by BlueAI this step
#     Keep this weight SMALL (0.05 to 0.2); too high teaches decoy-spam
r += 0.1 * (blue_spend_this_step / BLUE_BUDGET_START)
```

**Terminal reward** (applied on episode end, in addition to the dense step reward):

```python
# Via Scenario.winner() check after the final sim step:
if winner == "red":
    r += 20.0     # Red win bonus
elif winner == "blue":
    r -= 20.0     # Blue win penalty
else:  # None / timeout / draw
    r -= 5.0      # Draw penalty — prevents "hold forever to avoid spawn cost"
    #             # degenerate policy. Without this, "do nothing" is locally optimal.
```

**Magnitudes rationale:** with dense-component sum typically in the range `[-1.0, +1.5]` per step × ~1200 steps/episode = `[-1200, +1800]` cumulative dense reward across a full episode. Terminal `±20` is therefore **NOT** dominant (unlike a `+100` terminal that would overwhelm dense signal, or a `+5` terminal that would be ignored). Pick these to sit at "same order of magnitude" as integrated dense reward. See `gpt_advise_rl_overfitting.md` for the reasoning.

**Event schema discovery**: read `backend/sim/world.py`'s event emitters around `intercept`, `damage` (site-hit), and `leak` events. Identify which event reliably fires when a Blue site takes damage (that's the `+10 × Δsite_damage_fraction` source). Boyu's `env.py` already consumes this stream for Blue reward — inspect his code to see the exact event field names.

**What to NOT add:**
- Do not add a per-tick efficiency penalty like Boyu's Blue `-spent/$M * 0.05`. For Red, the `-Δred_spend_fraction` term already captures the spawn cost; a per-tick regularizer would double-count.
- Do not add "time pressure" (penalty for long episodes) unless training diagnostics show Red learning to stall. Start without it.

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

## Discount factor (gamma) — HIGH IMPACT change

**For `red_train.py`: override SB3 PPO's default `gamma=0.99` to `gamma=0.9995`.**

Rationale (per `gpt_advise_rl_overfitting.md` section 1): at `DECISION_EVERY=10` (0.5s sim per decision), a 600s episode has 1200 decisions. With `gamma=0.99`, the effective credit horizon is `1/(1-gamma) = 100 decisions ≈ 50 seconds` — so the terminal win/loss reward is discounted to near-zero from an early-episode decision's perspective. That's why dense shaping matters, but it also means strategy-level learning (when to spawn HGV vs drone, when to save budget) gets no gradient signal.

`gamma=0.9995` gives horizon `~2000 decisions = ~1000s`, covering an entire episode. This is the right scale for competitive game strategy.

Also set `gae_lambda=0.95` (same as Boyu's Blue). Don't tune broadly — `target_kl=0.03` as a safety clamp is worth setting (stops PPO updates that diverge too far, matches SB3 community default for unstable action-space-change runs).

## Observation — ordering matters (documented per external consult)

Since the observation uses fixed-size arrays (`threats[0:MAX_THREATS]`, `launchers[0:MAX_LAUNCHERS]`, etc.), **ordering must be deterministic and meaningful** — not Python spawn order. Per `gpt_advise_rl_overfitting.md` section 4, a plain MLP `MultiInputPolicy` is not permutation-invariant, so bad ordering creates avoidable learning noise.

**Read Boyu's `env.py`** and confirm his ordering scheme. Most likely options:
- Threats sorted by time-to-impact (ascending) — closest threat first
- Launchers sorted by `(kind, position_index)` — stable across episodes
- Interceptors sorted by `(target_id, time-to-intercept)` — ordered by engagement

Match whatever Boyu does. If Boyu's ordering is `arbitrary Python list order` (spawn order), flag that as a concern in your deliverable summary but **do not change his ordering** — consistency between Blue and Red envs matters more than "perfect" ordering. Cross-eval apples-to-apples requires symmetric encoding.

# Task

Five subtasks in order. **One commit per subtask.** Push each after `git pull --ff-only origin rl-self-play-v1` succeeds.

## Subtask A — `RedEnv` class (`backend/rl/red_env.py`, ~90–120 min)

1. Create `team-missile-intercept/backend/rl/red_env.py`.
2. Import scaffolding from Boyu's `env.py` — reuse normalization constants, helper functions, observation-encoding functions if they're extractable. If Boyu's code is tightly coupled (e.g. helpers are methods on `MissileInterceptEnv`), either (a) copy verbatim with a one-line attribution comment, or (b) refactor Boyu's helpers into `backend/rl/common.py` and import from both — **option (a) is safer** unless the duplication is egregious.
3. Implement `class RedEnv(gym.Env)` with:
   - `metadata` (standard gym)
   - `__init__(self, episode_time_limit: float = 600.0, seed: int | None = None)`
   - `observation_space` (Dict, identical to Blue's shape)
   - `action_space = gym.spaces.Discrete(1 + 4 * len(SOUTH_SITES))` — flat discrete per Action space section above
   - `action_masks()` method returning 1D int8 array shape `(1 + 4 * len(SOUTH_SITES),)`. Index 0 (hold) always 1; other indices follow validity checks in the Action Masking section above.
   - `reset(seed, options) → (obs_dict, info_dict)`
   - `step(action: int) → (obs, reward, terminated, truncated, info)` — applies Red action, steps sim + Blue opponent, returns normalized reward per spec above
   - Internal: `_decode_action(action: int) → (is_spawn: bool, kind: ThreatType | None, site_idx: int | None)` — decodes the flat action index
   - Internal: `_apply_action(...) → (spawned: bool, red_spend_usd: float)` — encapsulates spawn logic + launcher selection + budget deduction
   - Internal: `_compute_reward(damage_this_step, red_spend_usd, blue_spend_usd, winner) → float` — assembles dense + terminal reward per the normalized-fractions spec
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
7. **Hyperparameter overrides (HIGH IMPACT — revised per external consult)**:
   - `gamma = 0.9995` (NOT Boyu's default `0.99` — see Discount factor section above; this is the single most important change)
   - `gae_lambda = 0.95` (match Boyu if he uses this)
   - `target_kl = 0.03` (safety clamp — stops PPO updates that diverge too far; match Boyu's value if he has one, otherwise default to 0.03)
   - Everything else (n_steps, batch_size, n_epochs, clip_range, ent_coef, learning_rate, policy_kwargs / net_arch) **IDENTICAL** to Boyu's `train.py` so cross-eval is apples-to-apples.
8. **CLI flag `--gamma` exposed** so Chen can ablate it later if needed. Default = 0.9995.

The divergence from Boyu's train.py is intentional: Red's strategic horizon (when to save budget for late-game, spawn-decoy-to-drain-Blue tactics) needs a longer discount horizon than Blue's tactical-allocation task. If Boyu later sees Blue policy plateau, he may want to bump his own gamma too — but that's his call, not ours.

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

# Deliverable — final summary (≤ 500 words)

1. **Commits landed** — hashes + one-line each, 4 or 5.
2. **RedEnv structure** — file path, action-space shape used (`Discrete(1 + 4*N_SITES)` = ? for current `N_SITES`), how launcher auto-selection works, any deviations from the spec above with justification.
3. **Reward wiring** — which sim events feed each reward component, what denominators you used for normalization (`TOTAL_SITE_HP`, `RED_BUDGET_START`, `BLUE_BUDGET_START`). Confirm the draw penalty fires on timeout.
4. **Hyperparameter overrides in red_train.py** — confirm `gamma=0.9995` is set (not inherited default), `target_kl=0.03` safety clamp applied. Note if Boyu's `train.py` defined any of these differently at the time of cloning.
5. **Smoke test output** — one-liner: "100 steps, no NaN, winner distribution X/Y Red/Blue, mean episode reward Z".
6. **Training CLI smoke** — did `red_train.py --total-steps 1000 --n-envs 2` start cleanly? Any SB3 warnings that look serious (e.g. action-mask shape mismatch, device warnings on Blackwell sm_120 GPU)?
7. **Divergence from Blue's env** — list non-symmetric differences, explain. Include: action space flat-vs-factorized, reward normalized-vs-raw, gamma 0.9995-vs-0.99.
8. **Things flagged for Boyu** — action items for his review:
   - Design decisions this worker deferred (launcher-choice, maneuver_schedule in Red action space, cross-eval in eval.py for Red policies)
   - **Verify Boyu's Blue efficiency penalty semantics**: the spec `-spent/$M * 0.05` in `env.py` — confirm `spent` is **new spending this decision step**, NOT cumulative. If cumulative, that's a bug penalizing the same launch repeatedly every decision after it happens (flagged by external RL consult). Don't fix Boyu's env; just flag in the summary so Chen can relay.
   - If Boyu's ordering scheme in obs arrays is `spawn order` rather than `time-to-impact` / `distance` / `id`, flag as a latent learning-noise concern for him to consider (again, don't change, just flag).
9. **Anything surprising** — type signatures that didn't match expectations, sim bookkeeping corner cases, mask-shape tricks, event schema surprises.
10. **TensorBoard red flags to watch during Chen's real training** — include in summary so Chen knows what to monitor:
    - `explained_variance < 0` for long periods → reward/obs scale broken
    - `approx_kl > 0.03–0.05` repeatedly → policy updates too aggressive, LR too high
    - `clip_fraction > 0.3–0.5` constantly → updates too large
    - `entropy` collapses very early → policy degenerate (one action dominates)
    - `entropy` stays max + `ep_rew_mean` flat → not learning (reward / mask bug)
    - `value_loss` huge or exploding → reward scale miscalibration

Chen will launch the real training manually after reading this summary. Expected launch command: `python team-missile-intercept/backend/rl/red_train.py --total-steps 1000000 --n-envs 16 --gamma 0.9995` on Chen's PC (5950X + 5070) while Boyu trains Blue on his machine in parallel. Expected wall-clock at Chen's hardware: 30-60 minutes for 1M steps.

**Phase 2 follow-up (not this worker's scope)**: after Phase 1 lands, a separate follow-up worker will implement opponent-pool fine-tuning (Red2 vs [rule_Blue + Blue1], Blue2 vs [Red1 + Red2 + rule_Red]) and tournament cross-eval to select the final demo pair. That worker needs the `eval.py` extension hinted at in Subtask E. You don't do any of that here — just make sure your RedEnv is stable and document the seams cleanly so that follow-up has a good base.
