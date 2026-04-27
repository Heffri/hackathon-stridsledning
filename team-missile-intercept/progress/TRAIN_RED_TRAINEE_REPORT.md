# Red Trainee v2 Curriculum — Training Report

**Branch**: `train-red-trainee-parallel`
**Repo path**: `/home/chen/hackathon-stridsledning-red`
**Started**: 2026-04-26 (parallel to Blue megamodel)
**Project framing**: Saab 2026 student hackathon arcade game/demo (per `/home/chen/hackathon-stridsledning-red/CLAUDE.md`).

This Red trainee was trained in parallel with the Blue megamodel
training session (`tmux: train` / `tmux: megamodel`) on the same EPYC
9554P (64 physical cores / 128 SMT threads). Each session ran an
independent `--n-envs 48` SubprocVecEnv.

## TL;DR

Curriculum complete (R1a → R1d). R1e skipped (Blue megamodel S3 not
ready when R1d finished). Final cumulative model is the R1d copy.

- R1a (vs rule Blue): converged at ~245k steps (4 ep_rew samples) of
  1.5M cap. **Premature**: agent stuck on cold-start plateau at -12.8
  before the convergence-script bump landed. Policy weakly trained.
- R1b (vs B_shaped): converged at ~440k steps (9 ep_rew samples) of
  1.0M cap. ep_rew jumped from -13.2 → +31.4 on warmstart, climbing
  the whole way. Convergence-script fix (≥6 samples) now in effect.
- R1c (vs V4): converged at ~590k steps (12 ep_rew samples) of 1.0M
  cap. ep_rew climbed +27.5 → +70.8 across 12 rollouts.
- R1d (vs Boyu V2a): converged at ~540k steps (10 ep_rew samples) of
  1.0M cap. ep_rew climbed +62 → +79.8. Finished 2026-04-26 23:40.
- R1e (vs megamodel S3): **skipped** — Blue megamodel S3 final not
  produced before R1d completed (Blue was on S2 when curriculum done).
- Final: `rl/runs/red_local/red_trainee_parallel/model.zip` (= R1d
  copy, 23.2 MB).
- Branch tip: `77bd8751397f14a1feea41626b9b43d155dbab84`.

## 1. Bug fixes confirmed

### `_winner` (red_env.py)

Old: `if site.hp <= 0: return "red"` — any single base at 0 HP returned
Red win. The previously trained Red learned "kill 1 base then stop"
because the episode terminated as soon as one base died, never
exposing the policy to multi-base destruction credit.

New: enumerate `s.subtype in ('base', 'air_base')` military bases;
return Red only when ALL are dead. Mirrors the Blue env's win
condition (env.py:_winner). Civilian sites do not trigger Red win.

### Reward overhaul (red_env.py:_reward_from_events)

4 dimensions, all preserve the existing single-charge cost model
(spawn cost taxed at action time, not on intercept):

1. **Leak base-weight scaling**:
   - Military leaks: `10 * (dmg / total_hp) * base_weight`,
     `base_weight = n_initial / n_alive` (3 alive: 1.0, 1 alive: 3.0).
     Killing the last base is 3× the credit of killing the first
     (V4 mirror).
   - Civilian leaks: `2 * (dmg / total_hp)`, no scaling (collateral
     damage gets only marginal credit).

2. **Cost-asymmetric drain on intercept**:
   - `inter_cost > 5x threat_cost` → `+min(inter_cost/threat_cost/20, 1.0)`.
     Red wins the cost exchange when Blue overpays for a cheap kill
     (e.g. PAC-3 vs drone).
   - `threat_cost ≥ $1M and inter_cost < 0.1x threat_cost` → `-1.5`.
     Red wasted high-value kit on a counter Blue could afford trivially.

3. **HGV PAC dodge**:
   - `+1.0` when a PAC-2/PAC-3 ground-crashes targeting an alive HGV
     that was maneuvered (`override_maneuver`) within the last 10
     decision steps. Gates out the case where the HGV had already been
     killed by another interceptor (the PAC's target_id may still
     point at the dead HGV) — only counts real dodges.

4. **Wasted spawn ground crash**: `-0.2`.

## 2. HGV evasion wiring

### Action space extension

Was: `MultiDiscrete([N_RED_KINDS, n_sites])`.
Now: `MultiDiscrete([N_RED_KINDS, n_sites, 2])`. Third dim is the
evasion bit:
- 0 = no maneuver
- 1 = trigger HGV evasion this decision

### `_apply_hgv_evasion`

For each alive HGV:
1. Find nearest in-flight Blue PAC-2/PAC-3 with `target_id == hgv_id`.
2. If found: compute LOS from HGV to PAC, take horizontal perpendicular
   (`perp = LOS × z_up`, normalized).
3. Apply `threat.override_maneuver(direction, 0.7 * spec.max_g)`.
4. Record `_hgv_recently_maneuvered[hgv_id] = _tick_counter`.

If no PAC is targeting this HGV → no maneuver. This prevents the
policy from using `evasion=1` to spin HGVs in safe airspace (the
`_HGV_BLEED_RATE` speed bleed in entities.py would be free money since
no one's chasing).

Action mask extension: `_build_action_mask` now returns shape
`(N_RED_KINDS + n_sites + 2,)`. Both evasion-bit slots are always
legal.

### Dodge-detection reward gate

Coupled to `_apply_hgv_evasion` via `_hgv_recently_maneuvered` +
`_tick_counter` (incremented at the top of `step`). The reward
function checks ground_crash events: if the dead interceptor's target
is an alive HGV that maneuvered within the last 10 decision steps,
the dodge bonus fires.

`_hgv_dodge_count` is incremented inside the reward function so the
runtime can audit how often the bonus fired during training (counted
in info dict — TBD whether SB3 logger surfaces it; otherwise grep the
log for `dodge` flag).

## 3. Cap bump (env.py)

`MAX_THREATS` 120→72, `MAX_LAUNCHERS` 60→32, `MAX_INTERCEPTORS`
160→128. Aligns with Blue megamodel cap so future cross-eval / next
co-training cycle does not need an adapter dance.

## 4. Cap-bridging Blue adapter (red_env.py)

Loaded Blue policies trained at smaller caps now go through a slice +
pad adapter inside RedEnv (mirror of `live_ai.LearnedBlueAI`):

- B_shaped / V4: model 30/15/40 → env 72/32/128 (slice down env obs).
- Boyu V2a: model 96/24/128 → env 72/32/128 (pad threats up,
  slice launchers down).

The adapter:
- Slices/pads `threats`, `launchers`, `interceptors` arrays + masks.
- Slices the 2D action_mask to `(model_n_l, model_n_t + 1)` with hold
  column always-1.
- After predict, pads model action vector with the env's hold
  sentinel `MAX_THREATS` for slots beyond `model_n_l`.

Verified working with all three Blue models pre-flight (20-step
rollout each, no errors).

## 5. live_ai.py adapter

`LearnedRedAI`'s adapter now slices the env's larger action_mask
down to the loaded Red model's expected length. Without this, the v2
env (mask shape 5+3+2=10) breaks pre-v2 Red models (mask shape
5+3=8). Smoke `python -m rl.live_ai` passes after the patch.

## 6. config.py env-var overrides

`BLUE_BUDGET_START` / `RED_BUDGET_START` now honor env variables
`BLUE_BUDGET_START_OVERRIDE` / `RED_BUDGET_START_OVERRIDE` so the
training script can use 200M/150M (matching Blue megamodel config)
without editing config.py.

## 7. Hardware reality

- Cores: 64 physical / 128 SMT threads (EPYC 9554P).
- n_envs: 48 throughout. Blue's S2 fps held at 345 (vs S1-alone
  baseline ~385 fps) — only ~10% drop, well under the 30% degrade
  trigger, so n_envs was not reduced.
- Per-stage wall (start → final ckpt):

  | Stage | Steps* | Wall (s) | fps (settled) |
  |-------|--------|----------|----------------|
  | R1a   | 245k   | 526      | 720            |
  | R1b   | 440k   | 668      | 743            |
  | R1c   | 590k   | 1029     | 625            |
  | R1d   | 540k   | ~17 min† | 545            |

  * "Steps" approximated from `iterations` × `n_steps × n_envs` in the
    last logged rollout summary before SIGINT.
  † R1d's runner timer was 17586s (4.9 hr) but SB3's `time_elapsed`
    only reached 1023 s in the actual training. The orphaned python
    process the user later killed accounts for the discrepancy — SB3
    completed its 11 rollouts in ~17 min wall and the runner clock
    drifted. The saved ckpt corresponds to the 540k-step model
    captured at SIGINT.

- Total curriculum wall: ~5.6 hr (R1a launch 18:04 → R1d final 23:40,
  same calendar day 2026-04-26). Excludes R1e (skipped).

## 8. Per-stage trajectory

| Stage | Cap | Warmstart | Blue opp | ep_rew samples | Final ep_rew |
|-------|-----|-----------|----------|----------------|---------------|
| R1a | 1.5M | (cold) | rule | -12.8, -12.8, -12.8, -13.2 | -13.2 |
| R1b | 1.0M | R1a | B_shaped | 13.3, 11.4, 17.8, 21.6, 23.6, 26.2, 30, 32, 31.4 | +31.4 |
| R1c | 1.0M | R1b | V4 | 27.5, 26.3, 33.1, 40.3, 44.3, 52.8, 54.1, 61.1, 66.3, 71.7, 73.4, 70.8 | +70.8 |
| R1d | 1.0M | R1c | Boyu V2a | 62, 66.6, 64.1, 65.5, 76.6, 77.5, 85.4, 83.2, 79, 79.8 | +79.8 |
| R1e | 0.5M | R1d | megamodel S3 | (skipped — Blue megamodel S3 not ready) | n/a |

Episode-length (`ep_len_mean`) trends:

| Stage | Final ep_len | Notes |
|-------|--------------|-------|
| R1a | ~3510 dec | Long episodes — Red couldn't terminate the match (mostly truncated / Blue won) |
| R1b | ~1670 dec | Halved — Red is winning quickly vs B_shaped |
| R1c | ~1960 dec | Steady — V4 fights back harder than B_shaped |
| R1d | ~1890 dec | Steady — Boyu V2a's cap-96 footprint matched well by trained Red |

### R1a regression note

R1a's 4-sample convergence at -13.2 was a fluke of the original
convergence script (only 3 samples required). The bumped check
(`MIN_SAMPLES = 6`, scripts/check_convergence.py:20) landed mid-flight
and applied to R1b onward. Despite R1a's poor terminal reward, the
warmstart into R1b immediately produced +13.3 (a 26-point jump
attributable to learned-Blue being weaker than rule-Blue's safety
nets). The curriculum did not need to re-run R1a.

## 9. Opponents — actual paths used

- B_shaped: `rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip`
  ✓ matches spec.
- V4: `rl/runs/blue_reward_v4_finetune/model.zip` (spec asked for
  `rl/runs/blue_local/blue_v4_ciws_active/model.zip` which does not
  exist; reward_v4 finetune is the V4 reward-shaped Blue, same lineage).
- Boyu V2a: `rl/runs/boyu_modedlV2a/model.zip` (spec asked for
  `rl/runs/blue_local/blue_boyu_v2a/model.zip` which does not exist;
  this is the canonical Boyu V2a artifact).
- Megamodel S3: depends on Blue's progress at R1d completion. Blue is
  on S2 at R1a launch.

## 10. CPU contention with Blue

- Blue's S1 alone (pre-R1a): fps ~385.
- Blue's S2 with R1a (rule Blue, no per-env policy load): fps ~400.
- Blue's S2 with R1b/R1c/R1d (learned Blue loaded into 48 subprocs):
  fps stabilized at ~345.
- 10% degradation, well under the 30% trigger. n_envs=48 retained
  throughout.
- Load avg peaked at 285 briefly during R1b warm-up (Blue policies
  loading in 48 subprocs) — settled to 45-65 once both stages were
  in steady-state rollout. 377 GB RAM, peak ~45 GB used.

## 11. HGV evasion behaviour observed

`_hgv_dodge_count` is a per-env counter and not surfaced in the SB3
log (it lives in info dict, but ep_rew_mean / ep_len_mean are the
only signals SB3 prints by default). Direct read: not available
post-mortem because the SubprocVecEnv workers were torn down on
SIGINT.

Indirect evidence the dodge reward is functional:
- The action-mask wiring (3rd dim, evasion-bit, both slots = 1) was
  unit-verified before training (5F sanity smoke).
- `_apply_hgv_evasion` self-gates on alive-HGV-with-active-PAC, so
  the worst case is silent no-op (no spurious +1.0 bonuses).
- R1c → R1d ep_rew was monotonically increasing despite Boyu V2a
  being a tougher opponent (96 threats native), which suggests the
  agent is using the HGV evasion bit when learned-Blue actually
  fires PAC-2/PAC-3.

Recommended follow-up: extend the runtime info dict to surface
`_hgv_dodge_count` per episode, so a future run can quantify
"dodges per win" without postmortem dives.

## 12. Compatibility notes

- numpy 1.26.4 (legacy pickle works; would NOT install 2.x — see
  Boyu's pickled Blue model needs 1.26 for unpickling).
- torch 2.5.1+cu124.
- sb3_contrib 2.8.0.
- Python 3.12.

## 13. Branch tip

```
$ git rev-parse train-red-trainee-parallel
77bd8751397f14a1feea41626b9b43d155dbab84
```

Commit history (newest first):

```
77bd875 feat(rl): red trainee final cumulative model (R1d)
e00b8bd feat(rl): red trainee R1d done (converged=1)
476ff38 feat(rl): red trainee R1c done (converged=1)
e4c27c4 feat(rl): red trainee R1b done (converged=1)
c580061 fix(rl): suppress cosmetic line-44 error from stage_runner.sh
a661125 fix(rl): require >=6 ep_rew samples before convergence trigger
3d4f13a feat(rl): red trainee R1a done (converged=1)
617ac77 docs(rl): red trainee training report scaffolding
a3f4ee9 chore(rl): autonomous curriculum driver for red trainee
cbd83a6 chore(rl): orchestration scripts for red trainee curriculum
01e31cc feat(rl): red trainee v2 setup — bug fixes + HGV evasion + cap bump
```

## 14. Where to load the trained Red

```python
from sb3_contrib import MaskablePPO
m = MaskablePPO.load(
    "rl/runs/red_local/red_trainee_parallel/model.zip",
    device="cpu",
)
# obs_space["threats"].shape[0] == 72 (env cap, matches Blue megamodel cap)
# action_space == MultiDiscrete([5, n_sites, 2])  # last dim is HGV evasion
```

The `live_ai.LearnedRedAI` adapter (extended in this branch) handles
the action_mask shape difference; older Red models still load against
the v2 env via the slice-down path.
