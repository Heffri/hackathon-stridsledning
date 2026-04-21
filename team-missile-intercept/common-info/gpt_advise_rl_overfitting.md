## My verdict

**Phase 1 as-is is demoable but risky.** It is likely to produce two policies that are each competent against their training opponent but not necessarily compatible with each other. For a single 4-minute learned-vs-learned demo, the failure mode is not “judges discover lack of robustness”; it is more likely: **Red learns an exploit that only works on greedy BlueAI, Blue learns timing assumptions from scripted Red, and the final match becomes one-sided, passive, or weird.**

**I would do Level 2, but not exactly as written.** Do one extra fine-tune round using an **opponent pool / mixture**, then choose the best-looking pair from a small tournament. Do not spend that 1–2h on broad hyperparameter search unless the reward is clearly broken.

---

# 1. Reward design critique

Your planned Red reward:

```text
+damage
-spawn_cost / 1e6
+100 Red win
-100 Blue win
```

is directionally right, but I would fix four things.

## Biggest issue: terminal rewards may be almost irrelevant

With PPO’s default `gamma=0.99`, if decisions happen near 15 Hz, the effective credit horizon is only about:

```text
1 / (1 - gamma) = 100 decisions ≈ 6.7 seconds
```

So a `+100 Red win` at the end of a 600s episode barely affects launch decisions from minutes earlier. Dense damage shaping helps, but then the terminal win/loss bonus is mostly a late-game stabilizer, not the strategic objective.

For this environment, either:

```text
gamma = 0.9995 to 0.9999   if decision frequency is ~15 Hz
```

or:

```text
gamma = 0.995 to 0.999     if decision frequency is closer to 1 Hz
```

I would not rely on terminal reward alone. Keep dense shaping.

## Normalize reward components

Use deltas and normalized scales. For example:

```text
r_red =
    + 10.0 * Δsite_damage_fraction
    -  1.0 * Δred_spend_fraction
    +  0.2 * Δblue_spend_fraction     # optional, capped
    + terminal_bonus
```

Where:

```text
Δsite_damage_fraction = damage_this_step / total_site_hp_or_value
Δred_spend_fraction   = red_spawn_cost_this_step / red_budget
Δblue_spend_fraction  = blue_interceptor_cost_this_step / blue_budget
```

Then make terminal something like:

```text
+20 Red win
-20 Blue win
-5  draw / timeout
```

`+100/-100` is not automatically wrong, but it is too arbitrary unless you know the dense reward total is also roughly in that range.

SB3’s docs also emphasize that reward engineering usually needs iteration, and that model-free RL can need millions of interactions, so clean reward scale matters a lot in a custom environment. ([stable-baselines3.readthedocs.io][1])

## Add a draw / passivity penalty

Red has a dangerous degenerate option: **hold, avoid spending, reach timeout/draw**. If draw has no negative consequence, PPO may find “do nothing” locally attractive because spawning has immediate negative cost and delayed damage.

I would add:

```text
terminal:
    Red win:  +20
    Blue win: -20
    draw:     -5 or -10
```

Also log `red_budget_spent_fraction` and `time_to_first_spawn`. If Red learns to wait too long, add a tiny pressure term, but do not overdo it.

## “Make Blue spend budget” shaping: yes, but weakly

A Blue-spend term is useful because decoys and cost-exchange pressure are real Red tactics. But keep it weak and capped.

Good:

```text
+0.05 to +0.2 * Δblue_spend_fraction
```

Risky:

```text
+large_reward_for_blue_spending
```

The risky version teaches Red to spam cheap threats that burn interceptors but never threaten sites. Damage and win/loss must dominate.

## Check Blue’s cost penalty

You wrote:

```text
per-decision efficiency penalty -spent/1e6 * 0.05
```

Make sure `spent` means **new spending this decision**, not cumulative spending so far. If it is cumulative, you are penalizing the same missile launch repeatedly every decision after it happens, which will distort learning badly.

For Blue I would prefer:

```text
+intercept_value_normalized
-damage_normalized
-λ * interceptor_cost_this_step_normalized
+terminal_win_bonus
-terminal_loss_penalty
```

Also give Blue a negative terminal on Red win unless site damage already fully captures it.

---

# 2. Phase 1 overfit severity

I would rate the overfit risk as **medium-high**.

Not fatal for a hackathon, but very real.

## Blue vs scripted Red

Blue can learn:

```text
“At t≈X, expect cruise missiles toward southern sites.”
```

rather than:

```text
“Given these live threats, budgets, ranges, and launcher states, allocate interceptors well.”
```

Target randomness helps, but fixed timing/kind/count is still a big leak. If global time is in the observation, Blue can memorize schedule. If global time is not in the observation, it may still infer schedule from threat appearance patterns.

Cheap mitigation: randomize scripted Red during Blue training:

```text
launch time jitter: ±10–25%
counts: ±1 or small Poisson variation
target weights: random per episode
kind mix: small random swaps
initial threat headings / spawn points: small noise
```

## Red vs greedy deterministic BlueAI

This is probably worse. Red can learn the exact BlueAI cost-exchange thresholds:

```text
“Send this kind at this distance and greedy Blue picks the wrong interceptor.”
```

Then learned Blue may behave completely differently.

Cheap mitigation: randomize BlueAI during Red training:

```text
80–90% greedy cheapest viable
10–20% second-cheapest viable / random viable / delayed response
randomized engagement thresholds
randomized interceptor preference weights
```

This is a “Level 1.5” fix and often gives more robustness per engineering minute than fancy self-play.

## 1M timesteps

For fixed-opponent learning, 1M can produce visible behavior. For robust two-player strategy, it is not a lot.

If your decision frequency is 15 Hz and episodes are 600s, one full episode is about:

```text
600 * 15 = 9,000 agent steps
```

So 1M timesteps is only around 111 full episode-equivalents total, before accounting for early terminations and vectorization. That is enough to learn some tactics if the reward is dense and masks are good, but not enough to expect robust game-theoretic behavior.

Your PPO settings are basically sane:

```text
n_steps=512
n_envs=8–16
batch_size=512
n_epochs=8
clip_range=0.2
ent_coef=0.01
```

I would not hyperparameter-search those heavily right now. PPO is explicitly designed to limit update size via clipping, and SB3’s implementation uses common PPO modifications such as advantage normalization. ([stable-baselines3.readthedocs.io][2])

---

# 3. Level 2 ROI

**Yes, Level 2 is worth it**, assuming the environment/reward is not broken.

But I would change it from:

```text
Red2 trains only vs Blue1
Blue2 trains only vs Red2
```

to:

```text
Red2 fine-tunes vs mixture: 50–70% Blue1, 30–50% rule Blue
Blue2 fine-tunes vs mixture: 50–70% Red2/Red1, 30–50% randomized rule Red
```

Why? Pure sequential training can just move the overfit one step forward:

```text
Red2 overfits Blue1.
Blue2 overfits Red2.
Final Red2 has never seen Blue2.
```

With an opponent pool, each policy sees both a learned opponent and a stable anchor opponent. This reduces catastrophic forgetting and keeps behavior less weird.

My practical recommendation:

```text
1. Finish Phase 1.
2. Evaluate:
   Red1 vs Blue1
   Red1 vs rule Blue
   rule Red vs Blue1
3. Fine-tune Red1 -> Red2 for 500k vs opponent pool [rule Blue, Blue1].
4. Fine-tune Blue1 -> Blue2 for 500k vs opponent pool [randomized rule Red, Red1, Red2].
5. Run a small tournament:
   Red1, Red2, rule Red
   vs
   Blue1, Blue2, rule Blue
6. Pick the demo pair that is strongest and visually sane.
```

Do **not** blindly assume the newest pair is best.

If you only have time for one extra training run, I would fine-tune **Red vs Phase 1 Blue**. That makes the final learned-vs-learned match less “first contact.” Then evaluate Red2 vs Blue1. If it is balanced or exciting, ship that.

---

# 4. Hidden gotchas to watch

## Red action space: I would change this

You currently plan:

```text
MultiDiscrete([5 kinds, N_sites])
```

I would strongly consider replacing it with:

```text
Discrete(1 + 4 * N_sites)
```

Meaning:

```text
0 = hold
1..N = drone targeting site i
...
```

Why this matters: `MultiDiscrete([kind, site])` usually factorizes the action distribution as:

```text
P(kind, site | obs) = P(kind | obs) * P(site | obs)
```

So the policy cannot easily learn:

```text
“Use drones against site A, ballistic against site B.”
```

It learns one kind distribution and one target distribution independently. Also, `hold + site_id` creates meaningless target choices during hold.

A flat discrete action gives you exact action masking:

```text
hold valid
spawn drone/site_i valid only if budget + launcher + site alive
spawn HGV/site_j valid only if budget + launcher + site alive
```

This is cheap and likely improves Red immediately.

MaskablePPO does support `MultiDiscrete` action spaces and `Dict` observations, but you still need to be careful about how masks and factorized action heads behave. ([sb3-contrib.readthedocs.io][3])

## MaskablePPO evaluation must use mask-aware utilities

For evaluation, use:

```python
from sb3_contrib.common.maskable.evaluation import evaluate_policy
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback
```

And when using `SubprocVecEnv`, implement `action_masks` inside the environment itself; `ActionMasker` cannot be used with `SubprocVecEnv`. The sb3-contrib docs call this out directly. ([sb3-contrib.readthedocs.io][4])

## Normalize observations

Budgets in USD, positions in meters, velocities, time, hitpoints, and counts should be normalized.

Examples:

```text
budget_remaining / initial_budget
position / map_extent
velocity / max_velocity
time / episode_length
cooldown_remaining / max_cooldown
site_hp / max_site_hp
```

SB3 recommends normalizing inputs for custom PPO/A2C problems. ([stable-baselines3.readthedocs.io][1])

## Threat/entity ordering

If observations contain arrays like:

```text
threats[0:MAX_THREATS]
interceptors[0:MAX_INTERCEPTORS]
launchers[0:MAX_LAUNCHERS]
```

make ordering deterministic and meaningful.

Good:

```text
sort threats by time-to-impact or distance-to-target
sort interceptors by target_id then time-to-intercept
sort launchers by site_id / type
include valid/present masks
```

Bad:

```text
arbitrary Python list order
spawn order that changes randomly
```

A plain MLP `MultiInputPolicy` is not permutation-invariant. Bad ordering creates avoidable learning noise.

## Partial observability

MaskablePPO does not support recurrent policies in sb3-contrib. ([sb3-contrib.readthedocs.io][4])

So make sure the observation is close to Markov:

```text
current positions
velocities
target sites
cooldowns
budgets
reload states
time-to-impact
interceptor assignments
```

If the agent needs history, add explicit features or simple frame stacking.

## TensorBoard / training signals

Watch these:

### Game metrics

These matter more than raw reward.

```text
win_rate_red / win_rate_blue / draw_rate
episode_length
red_damage_done
sites_destroyed
red_budget_spent
blue_budget_spent
red_spawn_count_by_kind
blue_launch_count_by_interceptor_kind
intercept_rate_by_threat_kind
leak_rate_by_threat_kind
time_to_first_spawn
timeout_rate
```

### PPO metrics

Useful red flags:

```text
explained_variance < 0 for long periods
    value function is not fitting; reward scale/observation scale may be bad

approx_kl repeatedly > 0.03–0.05
    updates too aggressive; lower LR, reduce n_epochs, or add target_kl

clip_fraction constantly very high, e.g. > 0.3–0.5
    policy updates are too large

entropy collapses very early
    policy may be overfitting or action masks/reward make one action dominate

entropy stays near max and reward does not improve
    policy is not learning; reward too sparse, masks wrong, observation bad

value_loss huge or exploding
    reward scale likely too large or inconsistent
```

### Behavioral red flags

For Red:

```text
holds forever
spends entire budget immediately
only spawns one threat kind
always targets same site regardless of state
gets positive reward by making Blue spend but never damages sites
```

For Blue:

```text
fires everything immediately
never fires due to cost penalty
overkills same threat with many launchers
ignores HGV/ballistic threats
wins vs scripted Red but collapses vs small timing jitter
```

Overfitting looks like:

```text
training-opponent win rate rises
held-out randomized-opponent win rate flat or falling
behavior breaks under ±10–20% timing/count perturbations
```

Early instability looks like:

```text
all eval curves are noisy
entropy still high
some improvement appears but not sustained yet
```

---

# 5. Cross-eval protocol

Do **not** use only `episode_reward_mean`. Your Red and Blue rewards are shaped differently and not necessarily zero-sum. Use neutral game metrics.

Minimum tournament:

```text
Rows:    Red_rule, Red1, Red2
Columns: Blue_rule, Blue1, Blue2
Games:   20–50 per pair if possible
```

For each pair report:

```text
Red win %
Blue win %
Draw %
mean sites destroyed
mean site damage
mean terminal time
mean Red budget spent
mean Blue budget spent
mean leaks by threat kind
mean intercepts by interceptor kind
```

Use a fixed held-out seed list:

```text
eval_seeds = [1000, 1001, ..., 1049]
```

Then run every policy pair on the same seed list. That gives paired comparisons and makes results less noisy.

Also evaluate two modes:

```python
deterministic=True   # likely demo mode
deterministic=False  # robustness / stochastic behavior check
```

For the final live demo, I would probably use `deterministic=True` unless stochastic looks visibly better.

SB3 also recommends using a separate test environment for evaluation, several runs/seeds because RL results vary by seed, and deterministic prediction for stochastic policies like PPO often improves evaluation behavior. ([stable-baselines3.readthedocs.io][1])

---

# 6. One thing I would change

**Do a Level 2 opponent-pool fine-tune, then select the demo pair from a small tournament.**

Not full PSRO. Not broad hyperparameter search. Just:

```text
Red2 = fine-tune Red1 vs [rule Blue + Blue1]
Blue2 = fine-tune Blue1 vs [randomized rule Red + Red1/Red2]
Evaluate Red1/Red2 vs Blue1/Blue2
Pick the best-looking robust pair
```

That directly addresses your highest demo risk: the two learned policies meeting cold.

My second-most-important implementation change, if it is quick: **flatten Red’s action space to `Discrete(1 + 4*N_sites)` instead of `MultiDiscrete([kind, site])`.** That removes a real expressivity/masking issue and should make Red training cleaner.

## Final practical call

I would not ship pure Level 1 unless Phase 1 cross-eval already looks good over at least 20 held-out games.

Recommended priority order:

```text
1. Fix obvious reward/gamma/passivity issues.
2. Flatten Red action if quick.
3. Train Phase 1.
4. Cross-eval immediately.
5. Run Level 2 opponent-pool fine-tune.
6. Tournament-select the final demo pair.
```

For a hackathon, this is the best tradeoff: minimal new engineering, much lower chance of a broken learned-vs-learned demo, and no expensive full self-play framework.

[1]: https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html "Reinforcement Learning Tips and Tricks — Stable Baselines3 2.9.0a2 documentation"
[2]: https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html "PPO — Stable Baselines3 2.9.0a2 documentation"
[3]: https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html?utm_source=chatgpt.com "Maskable PPO - Stable Baselines3 - Contrib - Read the Docs"
[4]: https://sb3-contrib.readthedocs.io/en/v2.5.0/modules/ppo_mask.html "Maskable PPO — Stable Baselines3 - Contrib 2.5.0 documentation"
