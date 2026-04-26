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

[fill once curriculum done]

- R1a (vs rule Blue): converged at TBD steps (cap 1.5M)
- R1b (vs B_shaped): TBD steps (cap 1M)
- R1c (vs V4): TBD steps (cap 1M)
- R1d (vs Boyu V2a): TBD steps (cap 1M)
- R1e (vs megamodel S3): TBD steps or skipped (cap 0.5M)
- Final: `rl/runs/red_local/red_trainee_parallel/model.zip`

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

[fill once stages done]

- Cores: 64 physical / 128 SMT threads (EPYC 9554P)
- n_envs: 48 (target). If Blue's fps degraded > 30%, drop to 32.
  - R1a: n_envs=48; reported fps = TBD
  - R1b: TBD
  - ...
- Wall clock per stage: TBD

## 8. Per-stage trajectory

[fill from training logs]

| Stage | Cap | Warmstart | Blue opp | Steps to converge | Final ep_rew_mean |
|-------|-----|-----------|----------|-------------------|---------------------|
| R1a | 1.5M | (cold) | rule | TBD | TBD |
| R1b | 1.0M | R1a | B_shaped | TBD | TBD |
| R1c | 1.0M | R1b | V4 | TBD | TBD |
| R1d | 1.0M | R1c | Boyu V2a | TBD | TBD |
| R1e | 0.5M | R1d | megamodel S3 | TBD/skipped | TBD |

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

[fill once observed]

Initial (R1a launch): both python mains running, load avg 47/128
threads → headroom. Blue showed fps ~ TBD; Red fps ~ TBD.

Over the run: TBD.

## 11. HGV evasion behaviour observed

[fill once observed]

Spot-checked the training log for the HGV dodge reward firing.
`_hgv_dodge_count` snapshot at end of R1a / R1b / R1c / R1d: TBD.

If never fires, evasion gating is too restrictive — early debugging
hint: HGV `_apply_hgv_evasion` requires an in-flight PAC with
`target_id == hgv_id`; rule Blue's BlueAI may not actually fire PAC-2
/ PAC-3 reliably at HGVs (we know this from B_shaped / V4 retraining
history, see BLUE_AOE_LONG_REPORT.md). Against learned-Blue
opponents, behaviour is more representative.

## 12. Compatibility notes

- numpy 1.26.4 (legacy pickle works; would NOT install 2.x — see
  Boyu's pickled Blue model needs 1.26 for unpickling).
- torch 2.5.1+cu124.
- sb3_contrib 2.8.0.
- Python 3.12.

## 13. Branch tip

[fill at end]

```
git rev-parse train-red-trainee-parallel
```
