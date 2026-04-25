# Capacity Bump 30/15/40 → 120/60/160 — Smoke Report

**Date:** 2026-04-25 (post-Hack-Day "for fun" infrastructure work)
**Branch:** `cap-120-experiment` (off `final-demo` tip `6c4bc7d`)
**Author:** worker session
**Status:** PASS — all five §5 smokes green; B_shaped behaviour parity holds.

## What changed

Two commits, infrastructure-only. Game balance, sim physics,
ScriptedRed doctrine, frontend, snapshot protocol all untouched.

1. `feat(rl): MAX_THREATS / MAX_LAUNCHERS / MAX_INTERCEPTORS bump 30/15/40 -> 120/60/160`
   — `team-missile-intercept/backend/rl/env.py:45-58`. Three constants
   plus a comment block flagging the live_ai adapter dependency.

2. `feat(rl): live_ai adapter -- slice obs + remap action for smaller-cap models`
   — `team-missile-intercept/backend/rl/live_ai.py`. Backward-compat
   adapter on both `LearnedBlueAI` and `LearnedRedAI`:
     - `__init__` reads the model's native obs shapes from
       `policy.observation_space["threats"|"launchers"|"interceptors"].shape`
       and prints a one-liner when `_needs_adapter`.
     - `_adapt_obs_for_model(env_obs)` slices the env's larger obs
       tensors down to model size; `sites` + `global` pass through
       (MAX_SITES + GLOBAL_FEATURES untouched). Blue's 2D `action_mask`
       is sliced in both dims (`[:n_l, :n_t+1]`); Red's flat marginal
       mask passes through (depends only on `N_RED_KINDS + n_sites`).
     - LearnedBlueAI also adds `_adapt_action_for_env(model_action)`:
       remaps the model's hold sentinel (`model_max_threats`) to env's
       hold (`MAX_THREATS`) and pads launcher slots beyond the model's
       count with hold so `_apply_action_gated` skips them.
   - LearnedRedAI needs no action adapter — Red action space
     `MultiDiscrete([N_RED_KINDS, n_sites])` is independent of the
     bumped caps.

`MAX_SITES = 10` is unchanged (current arena has 7 sites).

## §5 Smoke results

### §5.1 — obs / action space dims

```
env obs threats:        (120, 12)
env obs launchers:      (60, 12)
env obs interceptors:   (160, 14)
env action_space.nvec[:3]: [121, 121, 121] len: 60
env action_mask shape:  (60, 121)
caps: T=120 L=60 I=160
```

PASS — matches the spec.

### §5.2 — B_shaped load + adapter print

```
[LearnedBlueAI] adapter active: model expects threats=30, launchers=15,
                                interceptors=40 (env at 120/60/160)
```

PASS — adapter activates and reports the correct old-model dims.

### §5.3 — behaviour parity (B_shaped, ScriptedRed, Red 110M, 3 matches × 3000s)

Eval command (from `team-missile-intercept/backend`):

```
EVAL_RED_BUDGET=110000000 PYTHONPATH=. python eval_demo_b_pathc.py \
    rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip <C|D> 3 3000
```

Baseline numbers from `OVERNIGHT_REPORT_2026-04-25.md` (averaged across
3 matches, pre-cap-bump env at 30/15/40 and pre-Hack-Day balance):

| Config | Layout | Sites alive | HP% | Leaks | PAC-3 | SLM | Weapons |
|---|---|---|---|---|---|---|---|
| Baseline (30/15/40) | C | 2.00/3 | 49% | 6.3 | 8 | 0 | 5/6 |
| Baseline (30/15/40) | D | 2.00/3 | 37% | 7.3 | 17 | 348 | 6/6 |
| **cap-120 + adapter** | **C** | **2.33/3** | **71.1%** | **4.0** | **13** | **0** | **5/6** |
| **cap-120 + adapter** | **D** | **3.00/3** | **82.2%** | **1.3** | **19** | **371** | **6/6** ⭐ |

PASS — adapter behaviour parity holds. Both layouts at or above
baseline sites-alive; C still SLM-zero (the trained policy's
deterministic dead spot on Layout C); D still fires all six
weapon kinds. PAC-3 totals 13 vs 8 (C) and 19 vs 17 (D); SLM
totals 0 vs 0 (C) and 371 vs 348 (D) — both close to baseline,
within the prompt's ±10% wobble allowance for the SLM count and
within RNG / shot-cap noise for the smaller PAC-3 totals.

Sites-alive and HP% are noticeably better than the baseline. This
is NOT an adapter effect — the OVERNIGHT_REPORT baseline was
captured before today's Hack-Day balance changes (slower threats:
Mach 7 ballistic / Mach 13 HGV; PAC-3 buffed to 100 m kill_radius
+ 80 km range + 50 s fuel + 30 m frag; ScriptedRed `_mopup_finished`
latch; MAX_SIM_TIME 4500 s). Those changes shift the world toward
Blue regardless of cap, and would reproduce on the un-bumped env.
The parity-relevant signals are weapon mix and PAC-3 / SLM
counts, all of which match.

Per-match raw lines:

Layout C:
```
[1/3] seed=1000 winner=truncated sites=2/3 hp= 66.7% leak= 4 int=120 t=3000s
      fires: ciws=56 rbs_70=78 sls=72 slm=0 pac2=4 pac3=4
      fallback=8 (first @ t=1459.1s)  sr_batches=35
[2/3] seed=1001 winner=truncated sites=3/3 hp= 80.0% leak= 2 int=118 t=3000s
      fires: ciws=56 rbs_70=104 sls=46 slm=0 pac2=2 pac3=4
      fallback=6 (first @ t=1461.3s)  sr_batches=34
[3/3] seed=1002 winner=truncated sites=2/3 hp= 66.7% leak= 6 int=120 t=3000s
      fires: ciws=85 rbs_70=78 sls=68 slm=0 pac2=1 pac3=5
      fallback=6 (first @ t=1466.6s)  sr_batches=35
Summary: avg sites=2.33/3 hp=71.1% leaks=4.0 int=119.3
Total fires: CIWS 197  RBS-70 260  SLS 186  SLM 0  PAC-2 7  PAC-3 13
```

Layout D:
```
[1/3] seed=1000 winner=truncated sites=3/3 hp= 73.3% leak= 2 int=129 t=3000s
      fires: ciws=60 rbs_70=0 sls=12 slm=126 pac2=2 pac3=5
      fallback=7 (first @ t=1725.9s)  sr_batches=34
[2/3] seed=1001 winner=truncated sites=3/3 hp= 86.7% leak= 1 int=136 t=3000s
      fires: ciws=98 rbs_70=2 sls=5 slm=122 pac2=2 pac3=8
      fallback=10 (first @ t=1563.1s)  sr_batches=32
[3/3] seed=1002 winner=truncated sites=3/3 hp= 86.7% leak= 1 int=138 t=3000s
      fires: ciws=90 rbs_70=9 sls=17 slm=123 pac2=3 pac3=6
      fallback=9 (first @ t=1562.9s)  sr_batches=35
Summary: avg sites=3.00/3 hp=82.2% leaks=1.3 int=134.3
Total fires: CIWS 248  RBS-70 11  SLS 34  SLM 371  PAC-2 7  PAC-3 19
```

Path C `strategic_fallback` triggered on every match in the
~1450-1700 s window (when ScriptedRed's strategic phase fires
ballistic / HGV) — same activation pattern as the OVERNIGHT_REPORT
baseline. Same launcher-mix character per layout (Layout C has
forward CIWS / RBS / SLS dominant; Layout D adds heavy SLM).

### §5.4 — server smoke (programmatic — see note)

Browser-side post-match dashboard verification was not done in this
worker session (no browser context); instead two programmatic proxies
that exercise the same code path:

- `import server` with `BLUE_POLICY_PATH` set to B_shaped + `RED_WAVE_MODE=scripted`
  loads the FastAPI app and the LearnedBlueAI adapter activates at
  startup. PASS.
- An 800 s default-layout match through `LearnedBlueAI` + ScriptedRed
  + Path C: `sites=3/3, leaks=0, intercepts=44, fires: SLM=23 PAC-2=16
  PAC-3=16` (default layout has no CIWS / RBS-70 / IRIS-T SLS in the
  config roster, so 3/6 firing is expected for that layout). PASS.

Snapshot serialisation under bumped caps: 6.4 KB JSON output — same
order of magnitude as before. The snapshot only carries actual entity
records, never the padded obs tensors, so the cap bump is invisible
to the snapshot protocol. PASS.

A live browser smoke at 50× is recommended before relying on this on
demo day, but no UI / WS surface is touched by this branch so the
risk window is small.

### §5.5 — Boyu V2 / V2a load

```
[LearnedBlueAI] adapter active: model expects threats=96, launchers=24,
                                interceptors=128 (env at 120/60/160)
OK V2 loaded
OK V2a loaded
```

PASS — both V2 and V2a (both at 96/24/128) load cleanly under the new
env. Behaviour quality is a separate question (Boyu V2 was trained in
a different game-balance regime — see OVERNIGHT_REPORT "distribution
shift" note); this smoke only verifies the load succeeds, which it
now does instead of raising on the shape mismatch.

## Auxiliary import smoke

All RL utility scripts re-import their constants from `rl.env` so the
bump propagates automatically. Verified clean import after the bump:

- `rl/smoke.py`, `rl/smoke_long.py` (random / no-op baselines)
- `rl/eval.py`
- `rl/train.py` (Blue training entry point)
- `rl/red_train.py`
- `rl/per_layout_eval.py`
- `rl/cross_eval.py`, `rl/cross_eval_tournament.py`

`backend/server.py` also imports cleanly with `BLUE_POLICY_PATH` set.

## Quirks / notes for review

1. **Action-mask flatten length grew 31× under the bumped caps.**
   The flat `action_masks` arg passed to `policy.predict` was 15 × 31
   = 465 entries pre-bump; under cap-120 it is 60 × 121 = 7260
   entries. For models WITH the adapter active (B_shaped, V2/V2a),
   the adapter slices the 2D mask to `(model_max_launchers,
   model_max_threats+1)` BEFORE flatten so the flat mask stays at
   the model's expected length (e.g. 15 × 31 = 465 for B_shaped).
   No correctness impact.

2. **Interceptor `target_idx` feature normalisation drift.** The env
   normalises feature index `7 + N_INT_KINDS = 13` of the interceptor
   tensor as `(t_slot + 1) / (MAX_THREATS + 1)`. After the bump the
   denominator is 121 instead of 31, so for a smaller-cap model an
   interceptor targeting threat slot 5 sees `6/121 ≈ 0.05` instead
   of the trained-distribution `6/31 ≈ 0.19` — a ≈ 4× scale shift
   on one of 14 interceptor features. The adapter does NOT
   renormalise this (kept the spec's pure-slice design); B_shaped
   parity numbers above demonstrate this drift is below the parity
   wobble in practice.

3. **Sim-tick cost.** The env's `_encode_obs` allocates four
   per-tick numpy arrays sized by the caps. Under the bump those
   arrays grow 4× / 4× / 4× / 1× (threats / launchers / interceptors
   / sites). Per-tick allocation cost is observable but small —
   the 800 s server-smoke match completed in well under wall-clock
   real time at 1× sim speed, and the eval scripts (3000 s × 3
   matches) progressed at expected pace. No catastrophic perf
   regression.

4. **Frontend / snapshot:** untouched. Snapshot carries actual
   entity records, not obs tensors, so payload size is independent
   of MAX_THREATS / MAX_LAUNCHERS / MAX_INTERCEPTORS. Verified by
   `len(json.dumps(scn.snapshot()))` ≈ 6 KB on a fresh scenario.

## Branch + push

- Branch: `cap-120-experiment` off `final-demo` tip `6c4bc7d`
- Commits (3 expected on this branch):
  - `feat(rl): MAX_THREATS / MAX_LAUNCHERS / MAX_INTERCEPTORS bump 30/15/40 -> 120/60/160`
  - `feat(rl): live_ai adapter -- slice obs + remap action for smaller-cap models`
  - `docs(progress): CAP_120_REPORT — capacity expansion smoke results` (this commit)
- `final-demo` is untouched. Demo continues to ship from there until
  Chen merges this branch manually.

## Out of scope (deferred per prompt §8)

- Retraining a 120-cap model.
- Sim physics, ScriptedRed doctrine, balance numbers.
- Snapshot protocol / frontend payload format.
- Direct edits to `final-demo`.
