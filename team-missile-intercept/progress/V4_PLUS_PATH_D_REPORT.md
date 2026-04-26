# V4+ Path D — Low-Altitude Shield (rule-layer net for V4 model)

**Branch**: `v4plus-path-d-low-alt-shield` (off `final-demo`)
**Date**: 2026-04-26
**Scope**: hackathon game/demo polish — inference-layer rule net only.
**Files changed**: `team-missile-intercept/backend/rl/live_ai.py` (one file).

## What was added

A sibling of Path C in `LearnedBlueAI`:

- **Constant** `LOW_ALT_TIER` near `SATURATION_CAP_BY_KIND` (top of `rl/live_ai.py`): tuple `(CIWS, SHORT_SAM, IRIS_T_SLS, MED_SAM)`. Doubles as the dispatch priority list and the "already-engaged" allow-set.
- **Method** `LearnedBlueAI._force_low_alt_shield(t_now)` placed right after `_force_strategic_fallback`. Force-fires the cheapest in-priority `LOW_ALT_TIER` interceptor whose launcher matches `kind` and is range-eligible (current range OR the same Path C predictive math) at any drone or `cruise_sub` not already engaged by a `LOW_ALT_TIER` interceptor. Honors the same per-kind saturation cap (with CIWS exempt) and the same `world.blue_budget < spec.usd_cost` budget gate.
- **Wire-in** in `LearnedBlueAI.step()` directly after the Path C call (~line 469). Logs `low_alt_shield=N` lines on actual fires only, mirroring Path C.

Lines added: ~130. Lines removed: 0. No new imports.

## Smoke test

```
$ python -m rl.live_ai
=== live_ai smoke ===
[LearnedRedAI] adapter active: model expects threats=30, launchers=15, interceptors=40 (env at 120/60/160)
[OK] Loaded learned Red: model.zip
[LearnedBlueAI] adapter active: model expects threats=30, launchers=15, interceptors=40 (env at 120/60/160)
[OK] Loaded learned Blue: model.zip
[OK] 10 ticks advanced: t=0.500s, phase=running, threats=1, interceptors=1
Smoke OK.
```

Smoke: **PASS**.

## Validation method — deviation from prompt

Prompt asked for in-browser eyeball at 10× / 50× speed. This session has no interactive browser to drive `localhost:5173`, so I substituted a **headless A/B harness** (`_path_d_diag.py`, deleted before commit) wrapping `LearnedBlueAI` + `ScriptedRedAI` + the same Layout C / D rosters from `rl/top3_layouts_CD.json`. Same wrapper code paths the browser exercises; no policy / env / scenario differences. Each run is 2 matches × 1500 sim seconds, Red $110M / Blue $200M (matches the prompt's setup). The harness directly counts fires by interceptor kind, parses the new `low_alt_shield=N` log lines, and records peak alive-threat count.

Limitations of substitution: cannot judge frame pacing or visual smoothness; cannot scrub HUD by hand. Frame pacing should be unchanged because Path D is O(threats × tiers × launchers) per tick — same shape as Path C, which already runs every tick at full speed.

## Layout C (V4) — primary test

| metric                   | V4 baseline (no Path D) | V4 + Path D       |
| ------------------------ | ----------------------: | ----------------: |
| Sites alive              | 3 / 3 (100%)            | 3 / 3 (100%)      |
| Total leaks              | 0                       | 0                 |
| Peak alive-threats (avg) | 59 (max 63)             | 41 (max 45)       |
| Total intercepts (avg)   | 49.5                    | 70.5              |
| CIWS fires (2 matches)   | **45**                  | **0**             |
| RBS-70 fires             | 61                      | 16                |
| SLS fires                | 52                      | 2                 |
| SLM fires                | 0                       | **133**           |
| PAC-3 fires              | 3                       | 5                 |
| Path D log lines / match | n/a                     | 70 (peak N=1)     |

Functional outcome: Path D **does** drive drone/cruise_sub leakage to zero on Layout C (already 0 in baseline, but Path D shaves the peak threat count from ~60 down to ~41 by killing things faster).

**Issue worth flagging — CIWS visual is gone, replaced by SLM dispatch.** Path D's spec ("try CIWS first; if no CIWS launcher in range, fall through to RBS-70 → SLS → SLM; skip the threat if any LOW_ALT_TIER is already in flight") interacts badly with the range hierarchy. Drones spawn at the north edge ~100 km out, and SLM has 40 km range (10× CIWS's 4 km). So SLM is the first launcher in range, fires first, registers as a LOW_ALT_TIER engagement, and the engaged-skip then prevents CIWS from being added once the drone closes. Net result on Layout C: 0 CIWS fires across 2 matches with 80+ drones spawned. The demo's most legible visual signal — CIWS rounds streaming up at drones — is essentially silent.

**Cost side-effect**: SLM is $1M/round vs CIWS at $2k/round. 133 SLM fires = $133M of demo budget consumed for drones a $5k CIWS round would handle. Path D's saturation cap (per `SATURATION_CAP_BY_KIND`) bounds it to 2 SLMs/drone, so it's not unbounded, but it's clearly not the cost-exchange the operator brief targets.

`low_alt_shield=N` activity is steady: every sim second from ~150s onward shows `N=1` (one Path D fire/tick); peak N=1 across both matches, no bursts.

## Layout D (AOE) — regression check

| metric                   | AOE baseline (no Path D) | AOE + Path D     |
| ------------------------ | -----------------------: | ---------------: |
| Sites alive              | 3 / 3 (100%)             | 3 / 3 (100%)     |
| Total leaks              | 0                        | 0                |
| Peak alive-threats (avg) | 49.5 (max 50)            | 44 (max 44)      |
| CIWS fires (2 matches)   | **89**                   | **10**           |
| SLM fires                | 111                      | 124              |
| Path D log lines / match | 0                        | 58 (peak N=1)    |

Same regression on Layout D: CIWS firing rate drops from 45/match to 5/match. Site survival identical (already 100%), so functionally no regression — but the AOE production demo's CIWS visual is muted by the same SLM-preempts-CIWS dynamic.

## Peak alive-threat count — cap-decision data point

Across the four 1500-second matches measured (V4+C and AOE+D, with and without Path D), peak alive-threat count topped out at **63** (V4+C baseline, max across 2 seeds). With Path D enabled, peak dropped to **45**. Per-kind composition at peak was dominated by drones (40-50 alive) with 5-20 cruise_sub, 0-2 ballistic, 0-1 HGV.

**Recommendation for next-step training cap**: stays well under 72. The 30-cap V4 model + the 60-cap env + Path C/D rule layer is already keeping peak threat count in the 40-60 range. No urgent need to bump training MAX_THREATS beyond 30 for this demo.

## Open issues for Chen before merging to `final-demo`

1. **CIWS visual is the demo's headline beat**, and Path D as specified silences it on both V4+C and AOE+D. Two carve-outs that would restore CIWS firing while keeping Path D's no-leak guarantee:
   - **CIWS-additive carve-out**: change the engaged-skip to `if engaged and kind != InterceptorType.CIWS: continue` so CIWS still fires when it gets in range even if SLM is already engaged. Mirrors the existing CIWS exemption from `SATURATION_CAP_BY_KIND`.
   - **Range-first dispatch**: instead of strict tier order, fire the cheapest tier that has a launcher in range *now* (skip predictive for non-CIWS). Lets CIWS "win" the dispatch whenever a drone enters its range, with SLM only firing on cruise_sub the cheaper kit can't reach.
2. The $1M-per-drone cost is a quiet demo problem — Path D as specified converts a 90%-CIWS-handled wave into 90%-SLM. Worth deciding whether to absorb that or apply one of the carve-outs above.
3. Headless eval substituted for browser — Chen should still spot-check in browser before the Finale to confirm frame pacing is smooth and the radar/HUD reads correctly with Path D logs flowing.

## Deviations from prompt

- **No browser eyeball**: substituted headless A/B harness as described above. All A/B numbers come from the same `LearnedBlueAI` + `ScriptedRedAI` code path the browser uses.
- **Implementation matches spec exactly** (priority order, engaged-check semantics, predictive math is a verbatim copy of Path C lines 671-711, budget gate, saturation cap with CIWS exempt, log line format). The CIWS-preemption finding is a consequence of the spec, not a deviation.
