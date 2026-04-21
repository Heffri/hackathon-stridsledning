# Phase 2 — Cross-eval harness: Red1 vs Blue1 tournament

**How to use:** paste everything below (from `# Hackathon framing`) into a fresh Claude Code worker session at the repo root on Chen's PC. Bypass permissions. Budget: ~2-3 h. Commits to `rl-self-play-v1` locally; decision to push is Chen's.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition. A small browser-based arcade-style game / simulation in the tower-defense / KSP category. NOT a military product. All entity names and stats are publicly available encyclopedia-level arcade game-balance numbers. This worker writes a game-AI-vs-game-AI evaluation harness and runs a tournament between two trained policies. Game-dev framing throughout.

# Your role

Build a cross-evaluation harness that can play two trained RL policies against each other (both learned, no rule-based side), run a tournament including baselines, and produce a human-readable + machine-readable results report.

Prior art:
- **Chen's Red1**: MaskablePPO policy on branch `origin/red-ai`, path `team-missile-intercept/backend/rl/runs/red_20260421_205051/model.zip` (9.6 MB, ep_rew_mean=25.7 after 1M steps against rule-based BlueAI)
- **Boyu's Blue1**: MaskablePPO policy on branch `origin/blue-ai`, path `team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip` (13.8 MB, trained with a 2x-damage-penalty reward variant against rule-based Red waves)

Both policies use MaskablePPO from `sb3_contrib`. Both were trained with the same obs encoding and sim conventions (Chen's `RedEnv` was explicitly mirrored from Boyu's `MissileInterceptEnv`). Action spaces differ: Red is `MultiDiscrete([5, 3])` (kind × site), Blue is `MultiDiscrete([31]*15)` (per-launcher threat selection).

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`.

**Active branch: `rl-self-play-v1`** — this is where Chen's `red_env.py`, `red_train.py`, `blue_env.py` (Boyu's `env.py`), and all code artifacts live. You write the cross-eval harness here.

**Expected starting HEAD:** `a72adc5` (Red fix-up tip) or newer.

**Model files required:**
- Red1: local at `team-missile-intercept/backend/rl/runs/red_20260421_205051/model.zip` (check it's there)
- Blue1: needs to be fetched from `origin/blue-ai`. Use: `git checkout origin/blue-ai -- team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip`. This pulls only the file without switching branches.

Start by reading:
- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/backend/rl/env.py` — Boyu's Blue env (`MissileInterceptEnv`). Reference for Blue action application + obs encoding.
- `team-missile-intercept/backend/rl/red_env.py` — Chen's Red env (`RedEnv`). Reference for Red action application.
- `team-missile-intercept/backend/sim/blue_ai.py` — rule-based Blue (for baseline)
- `team-missile-intercept/backend/sim/red_ai.py` — rule-based Red / waves (for baseline)
- `team-missile-intercept/backend/sim/world.py` — `World.spawn_threat`, `World.spawn_interceptor`, `Scenario.winner`
- `team-missile-intercept/backend/sim/scenarios.py` — `build_default_scenario`, `Scenario` class
- `team-missile-intercept/backend/sim/types.py` — `MatchPhase`, threat/interceptor enums

# Pre-flight

1. `git status` — must be clean. If dirty, stash.
2. `git fetch origin --prune` — see latest remote state
3. `git checkout rl-self-play-v1`
4. `git pull --ff-only origin rl-self-play-v1` (shouldn't be divergent since nobody pushes to rl-self-play-v1 anymore — Chen is on red-ai for Red policies, Boyu is on blue-ai for Blue policies)
5. **Fetch Blue1 model**: `git checkout origin/blue-ai -- team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip` — pulls the one file. After this, `git status` will show `models/blue_ai_1m_2xpenalty/model.zip` as **staged new file**. That's fine — we may commit it or reset it later per Chen's preference.
6. Verify both model files exist: `ls team-missile-intercept/backend/rl/runs/red_20260421_205051/model.zip` and `ls team-missile-intercept/backend/rl/models/blue_ai_1m_2xpenalty/model.zip`.
7. Baseline smoke: run Boyu's `python -m rl.smoke` and Chen's `python -m rl.red_smoke` from `backend/` — both should still pass. (Quick sanity that no code regressed.)

If any preflight step fails, STOP and report.

# Design: CrossEvalEnv + CrossEvalRunner

## The core abstraction

`CrossEvalEnv` is a Python class (NOT a gym.Env — it's a harness not a training env). It:

1. Instantiates a fresh `World` + `Scenario` each episode
2. On each decision tick:
   - Encodes sim state as "Red obs dict" (same encoding as `RedEnv._encode_obs`)
   - Encodes sim state as "Blue obs dict" (same encoding as `MissileInterceptEnv._encode_obs`). **Key insight: if the two encodings are byte-identical (which they should be per Chen's worker summary), you can encode ONCE and feed the same dict to both policies.** Verify this by comparing the two env's `_encode_obs` implementations. If they diverge (e.g. different action_mask shape), encode twice.
   - Queries Red policy: `red_action, _ = red_policy.predict(red_obs, deterministic=True, action_masks=red_mask)` — MaskablePPO predict signature
   - Queries Blue policy: `blue_action, _ = blue_policy.predict(blue_obs, deterministic=True, action_masks=blue_mask)`
   - Applies both actions to the sim
   - Steps `DECISION_EVERY=10` sim ticks
3. Continues until `Scenario.winner()` is non-None OR `world.t >= MAX_EPISODE_SIM_TIME`
4. Records per-episode metrics

Each policy can be either:
- A MaskablePPO-loaded model (via `MaskablePPO.load(path)`)
- A **rule-based wrapper** for baselines:
  - `RuleRedAdapter(world) → .predict(obs) = wave-script action` (proxies `red_ai.step` into a per-decision action)
  - `RuleBlueAdapter(world) → .predict(obs) = greedy cost-exchange action` (proxies `BlueAI.step`)

So the tournament can pit any combination: learned-vs-learned, learned-vs-rule, rule-vs-rule.

## Action application

**Red action (MultiDiscrete [5, 3])**:
- `kind_idx ∈ {0:hold, 1:drone, 2:cruise_sub, 3:ballistic, 4:hgv}`
- `site_idx ∈ [0, len(SOUTH_SITES))`
- Reuse `RedEnv._apply_action` (extract or import). Budget deduction, launcher selection, spawn — same as Red's training.

**Blue action (MultiDiscrete [31]*15)**:
- Per-launcher: `0..29` = fire at threat index in sorted threat list (Boyu's convention — verify by reading his env), `30` = hold
- Reuse Boyu's `MissileInterceptEnv._apply_action` (extract or import).

## Adapter classes for rule-based baselines

```python
class RuleBluePolicy:
    """Wraps BlueAI.step into a policy-like predict() interface."""
    def __init__(self, world):
        self.blue_ai = BlueAI()
        self.world = world
    def predict(self, obs, deterministic=True, action_masks=None):
        # Option 1: call self.blue_ai.step(world.t, world) to apply its internal logic,
        # then extract what fires happened and encode as MultiDiscrete action.
        # Option 2: monkey-patch BlueAI.fire to record actions, then encode.
        # The simplest: don't encode at all — have step() call blue_ai.step directly
        # as a special-case in CrossEvalEnv.
        ...
```

**Practical approach**: don't try to make rule-based policies "look like" MaskablePPO policies. Instead, have `CrossEvalEnv` accept a `side_policies: Dict[str, Any]` where each side is EITHER a MaskablePPO model OR a special sentinel like `"rule"`. Then the step logic branches:

```python
if red_policy == "rule":
    red_ai.step(world.t, world)  # scripted wave spawner
else:
    red_obs, red_mask = encode_red(world)
    red_action, _ = red_policy.predict(red_obs, deterministic=True, action_masks=red_mask)
    apply_red_action(world, red_action)
```

Similarly for Blue. Clean and avoids fake-wrapping rule-based AI.

## Tournament matchups

Matrix: 3 Red policies × 3 Blue policies = 9 pairs. Each pair plays N episodes.

| | Blue_rule | Blue1 (Boyu) | (Blue2 placeholder) |
|---|---|---|---|
| Red_rule | baseline, symmetric default | eval Blue1 vs scripted Red | N/A |
| Red1 (Chen) | eval Red1 vs rule (= training opponent) | **main event: Red1 vs Blue1** | N/A |
| (Red2 placeholder) | | | N/A |

For now, skip Red2 / Blue2 (placeholders for future fine-tune work). 2×2 matrix is enough.

**Games per pair**: 30 episodes each. Total 4 × 30 = 120 episodes. At ~100-200 decisions per episode (Red's policy tends to end matches fast), that's ~4000-24000 total decisions. Should run in under 10 minutes wall-clock.

Use fixed seed list `eval_seeds = [1000, 1001, ..., 1029]` so all pairs play the SAME seeds. Enables paired comparisons (reduces noise).

## Metrics to record per episode

- `winner`: `"red"`, `"blue"`, or `"draw"` (from `Scenario.winner()`)
- `episode_length`: number of decisions
- `sim_time`: `world.t` at end (wallclock = sim_time / speed)
- `sites_destroyed`: count of sites with hp=0
- `sites_total_damage`: sum of damage taken across all sites
- `red_budget_remaining`: `world.red_budget`
- `blue_budget_remaining`: `world.blue_budget`
- `red_spawns_by_kind`: dict of {drone: N, cruise_sub: N, ballistic: N, hgv: N}
- `blue_launches_by_kind`: dict of {ciws: N, rbs_70: N, iris_t_sls: N, iris_t_slm: N, pac_2: N, pac_3: N}
- `intercept_count`: total intercepts
- `leak_count`: total leaks

Aggregate per pair: mean, std, win rate %.

# Task

5 subtasks, one commit per. All commits **LOCAL ONLY** to `rl-self-play-v1` — do NOT push. Chen decides whether to push after reviewing.

## Subtask A — Cross-eval env (`cross_eval.py`, ~60-90 min)

1. Create `team-missile-intercept/backend/rl/cross_eval.py`
2. Implement `CrossEvalEnv` class per design above
3. Implement rule-based adapter logic (see "Practical approach" in design section)
4. Sanity test: within the module, a `__main__` block that runs 2 episodes (one Red1-rule vs rule-rule, one Red1-vs-Blue1) and prints one-line-per-episode result. Should run in < 30s.

**Commit (local only):** `feat(rl): cross_eval.py — CrossEvalEnv harness for learned-vs-learned eval`

## Subtask B — Tournament runner (~30-45 min)

Extend `cross_eval.py` or add `cross_eval_tournament.py` (your call, whichever reads cleaner):

1. CLI: `python -m rl.cross_eval_tournament --n-episodes 30 --seeds 1000-1029 --red-policies rule,models/runs/red_20260421_205051/model.zip --blue-policies rule,models/blue_ai_1m_2xpenalty/model.zip`
2. Construct the 2x2 matrix (4 pairs)
3. For each pair, play 30 episodes (same seed list)
4. Aggregate metrics per pair
5. Write results to:
   - `tournament_2026-04-21.json` — machine-readable, full metrics per episode per pair
   - `tournament_2026-04-21.md` — human-readable: markdown tables with win rates, key stats

**Commit (local only):** `feat(rl): tournament runner for cross_eval`

## Subtask C — Run the tournament (~15-30 min wall-clock)

Run the command. Capture output. Verify:
- All 120 episodes complete without errors
- JSON file written, parsable
- Markdown file human-readable

If anything crashes, debug + fix. Re-run.

**Commit (local only)** — the output files:
`results(rl): Phase 2 tournament — Red1 vs Blue1 (+ rule baselines)`

Include the JSON + MD files in the commit.

## Subtask D — Results analysis + demo recommendation (~20 min)

Read the tournament.md file. In your final summary, analyze:

1. **Red1 vs Blue1 head-to-head win rate**. What does it mean?
   - Red 30-55%: balanced, good demo material
   - Red >70% or <10%: imbalanced, demo risk
2. **Compare vs training opponents**:
   - Red1 vs rule_Blue = Red's training regime. Expected ~80% Red win since that's what it overfit to.
   - Red_rule vs Blue1 = Blue's training regime. Expected Blue wins with 2xpenalty reward pushing aggression.
3. **Cross-eval**: does Red1 drop significantly from its "trained on rule" win rate when facing real Blue? If yes → overfit confirmed.

Recommend to Chen:
- Is this pair **demo-worthy as-is**?
- If unbalanced: does the losing side need Phase 2b fine-tune against the winning side? (a ~1M step run)
- Or is the matchup just visually interesting regardless of win rate (close matches, smart plays)?

## Subtask E — Close (~10 min)

- Update `team-missile-intercept/game-core/ISSUES_2026-04-19.md` if you want to track this work (optional — this is RL territory, not game-core; can skip if no natural issue fits)
- Do NOT update PR #4 or worker-prompt archive for this phase unless Chen asks
- Final summary to Chen per template below

# Rules

- **LOCAL ONLY commits** — do NOT push to origin. Chen decides post-review.
- **DO NOT modify red_env.py or env.py (Blue)** — the cross-eval harness is a separate module, NOT a training env.
- **DO NOT modify game-core sim code** — read-only consumer.
- **DO NOT touch Boyu's branch** — we only read his model.zip, not edit.
- **No force-push, no amend, no --no-verify** (though since you're not pushing, mostly moot).
- **English** in code + commits.

# Post-flight

1. `git status` — clean (or note the model.zip pull from blue-ai if you didn't commit it)
2. `git log --oneline -6 rl-self-play-v1` — should show 3 new local commits above `a72adc5`
3. Do NOT push.

# Deliverable — final summary (≤ 500 words)

1. **Commits landed (local)** — 3 hashes + one-line each
2. **Tournament results** — 2×2 matrix table:
   ```
                    Blue_rule    Blue1
   Red_rule         rrB% / bbB%  ...
   Red1             ...          ...  <- main event
   
   Metrics per cell: Red win% / Blue win% / draw%, mean episode length, mean sites destroyed
   ```
3. **Red1 vs Blue1 headline**: win rate, episode length, typical match shape
4. **Overfit diagnosis**: did Red1 drop from its rule-Blue win rate when facing Blue1? By how much?
5. **Demo recommendation**:
   - Ship Red1 vs Blue1 as-is?
   - Or fine-tune one side with Phase 2b?
   - Or abort and use rule-vs-rule as the demo baseline?
6. **Anything surprising** — bugs discovered (e.g. obs encoding differences between envs), weird match outcomes, throughput numbers
7. **Flag for Boyu**: if Chen plans to tell Boyu the tournament results, what should Boyu know about his Blue1's behavior?

Under 500 words, structured. Chen needs to decide next steps (Phase 2b fine-tune vs ship as-is) from your summary.
