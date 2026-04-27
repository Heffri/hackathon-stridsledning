# PROMPT — V4+ Path D v2 (revised doctrine)

> **Framing (read first, non-negotiable)**: This repo is a **Saab 2026 student hackathon entry** — a browser-based arcade-style game/demo, in the same category as a tower-defense game or Kerbal Space Program physics toy. It runs in Chrome on one laptop during a 4-minute demo at the April 27 Finale. All entity names (CIWS, RBS-70, drone, cruise_sub, PAC-3, etc.) are publicly available encyclopedia-level values used as **arcade game-balance numbers**, equivalent to unit stats in Age of Empires. They encode no non-public or tactical information. This is **not** a military product, weapons system, training tool, or command-and-control system. Describe the work as hackathon game/demo polish.

## Background

A previous worker implemented Path D ("low-altitude shield") on branch `v4plus-path-d-low-alt-shield` (tip `bd97df4`). The implementation matched its spec literally but the spec had a doctrine bug: SLM (40 km range) preempts CIWS (4 km) under the "skip if any LOW_ALT_TIER engaged" rule. Result: 0 CIWS fires on Layout C, AOE+D regression from 89 → 10 CIWS fires, and 133 SLM rounds wasted on drones at $1M each.

Full v1 report: [`team-missile-intercept/progress/V4_PLUS_PATH_D_REPORT.md`](team-missile-intercept/progress/V4_PLUS_PATH_D_REPORT.md). The headless A/B harness pattern documented there is the validation method for this v2 task too.

Chen has revised the doctrine. Implement it as a **replacement of the existing `_force_low_alt_shield`** plus a small addition to `_force_strategic_fallback` (Path C). Same branch — one new commit.

## Revised doctrine

| Threat kind | Interceptor doctrine |
|---|---|
| **drone** | CIWS only |
| **cruise_sub** | CIWS (additive, when in CIWS range) + RBS-70 / IRIS-T SLS (single engage) |
| **ballistic** | PAC-3 → PAC-2 → IRIS-T SLM (Path C) |
| **HGV** | PAC-3 → PAC-2 (Path C, unchanged) |

Key changes vs v1:

1. **MED_SAM (IRIS-T SLM) removed from Path D.** SLM is overkill for drone/cruise_sub (drone alt 800m, cruise alt 60m — both inside RBS-70 / SLS range). SLM moves to Path C as third-tier ballistic backup.
2. **CIWS is a separate "additive" pass**, not part of the priority cascade. CIWS always fires when in range regardless of what other interceptor is also closing on the same threat. This is the demo's headline visual.
3. **Drones are CIWS-only by Path D**. RBS-70 / SLS are reserved for cruise_sub (and whatever the trained policy decides on its own — Path D doesn't override the policy's ammo, only adds rule-layer fires).

## Task

### File to edit

`team-missile-intercept/backend/rl/live_ai.py` — only this file.

### Branch

Continue on existing branch `v4plus-path-d-low-alt-shield` (tip `bd97df4`, already pushed). Add **one new commit** on top — do NOT amend or force-push.

### Step 1 — update module-level constants

Replace the existing `LOW_ALT_TIER` (`MED_SAM` is no longer in the low-alt set) and add two helper kind-sets near it:

```python
# Path D (revised 2026-04-26): doctrine separates CIWS (additive
# point-defense, fires whenever in range) from the SAM tier
# (single-engage long-arm). SLM moved to Path C as ballistic
# backup since its 40 km range overshoots drone/cruise_sub
# scenarios and starves CIWS of demo-visible engagements.
LOW_ALT_TIER = (
    InterceptorType.CIWS,
    InterceptorType.SHORT_SAM,
    InterceptorType.IRIS_T_SLS,
)
CIWS_TARGET_KINDS = (ThreatType.DRONE, ThreatType.CRUISE_SUB)
SAM_TIER_TARGET_KINDS = (ThreatType.CRUISE_SUB,)  # drone is CIWS-only
```

### Step 2 — replace `_force_low_alt_shield` with a two-pass version

Replace the entire existing method with the version below. The predictive-math block (the `if not in_range_now: ...` block) must remain a verbatim copy of Path C lines ~671-711 to avoid drift.

```python
def _force_low_alt_shield(self, t_now: float) -> int:
    """Force-dispatch CIWS / RBS-70 / IRIS-T SLS at drone + cruise_sub
    that the policy left unengaged.

    Path D v2 (2026-04-26): two-pass dispatch separating CIWS
    (additive point-defense — fires whenever in range, regardless
    of what else is engaged) from the SAM tier (single-engage
    long-arm for cruise_sub only — drone is CIWS-only doctrine).

    Pass 1 (CIWS additive): for every alive drone or cruise_sub
    without a CIWS already closing, try to fire one CIWS round.
    Cheap (~$2-5 k/round), short range (4 km), so the range gate
    + predictive entry math self-limits this to threats actually
    near a base. This is the demo's headline visual.

    Pass 2 (SAM tier on cruise_sub): for every alive cruise_sub
    without an RBS-70 or IRIS-T SLS already closing, try the SAM
    tier in priority order (RBS-70 → IRIS-T SLS). Drone is NOT
    in this pass — the doctrine reserves the SAM tier for
    cruise_sub.

    Saturation cap (`SATURATION_CAP_BY_KIND`) and budget gate
    same as Path C. Predictive-dispatch math is a verbatim copy
    of Path C lines 671-711.
    """
    world = self._env.world
    forced = 0

    # Pass 1 — CIWS additive on drone + cruise_sub.
    for tid, threat in world.threats.items():
        if not threat.state.alive:
            continue
        threat_kind = ThreatType(threat.state.kind)
        if threat_kind not in CIWS_TARGET_KINDS:
            continue
        existing = self._assignments.get(tid, [])
        # Skip ONLY if a CIWS round is already closing on this
        # threat. Other LOW_ALT_TIER interceptors (RBS-70, SLS)
        # in flight don't preempt CIWS — that was the v1 bug.
        ciws_in_flight = False
        for iid in existing:
            inter = world.interceptors.get(iid)
            if inter is None or not inter.state.alive:
                continue
            if inter.spec.kind == InterceptorType.CIWS:
                ciws_in_flight = True
                break
        if ciws_in_flight:
            continue
        spec = INTERCEPTOR_SPECS[InterceptorType.CIWS]
        if world.blue_budget < spec.usd_cost:
            continue
        for lch in self.launchers.launchers:
            if lch.kind != InterceptorType.CIWS:
                continue
            if lch.reloading or not lch.can_fire(t_now):
                continue
            t_pos = threat.state.pos
            t_vel = threat.state.vel
            dx = float(t_pos[0] - lch.pos[0])
            dy = float(t_pos[1] - lch.pos[1])
            dz = float(t_pos[2])
            R = spec.max_range * LAUNCH_RANGE_MARGIN
            dist_now_sq = dx * dx + dy * dy + dz * dz
            in_range_now = dist_now_sq <= R * R
            if not in_range_now:
                # Predictive dispatch — verbatim copy of Path C math.
                a0 = float(t_pos[0] - lch.pos[0])
                a1 = float(t_pos[1] - lch.pos[1])
                a2 = float(t_pos[2])
                b0 = float(t_vel[0])
                b1 = float(t_vel[1])
                b2 = float(t_vel[2])
                A = b0 * b0 + b1 * b1 + b2 * b2
                if A < 1.0:
                    continue
                B = 2.0 * (a0 * b0 + a1 * b1 + a2 * b2)
                C = (a0 * a0 + a1 * a1 + a2 * a2) - R * R
                disc = B * B - 4.0 * A * C
                if disc < 0:
                    continue
                sqrt_disc = float(np.sqrt(disc))
                t_enter = (-B - sqrt_disc) / (2.0 * A)
                if t_enter <= 0.0:
                    continue
                if t_enter > spec.fuel_s - 3.0:
                    continue
            mode = lch.fire(t_now)
            iid = world.spawn_interceptor(
                lch.kind,
                (lch.pos[0], lch.pos[1], 0.0),
                (dx, dy, dz),
                tid,
                mode,
            )
            world.blue_budget -= spec.usd_cost
            self._assignments.setdefault(tid, []).append(iid)
            forced += 1
            break  # one CIWS launcher per threat per tick

    # Pass 2 — SAM tier on cruise_sub only.
    SAM_TIER = (InterceptorType.SHORT_SAM, InterceptorType.IRIS_T_SLS)
    for tid, threat in world.threats.items():
        if not threat.state.alive:
            continue
        threat_kind = ThreatType(threat.state.kind)
        if threat_kind not in SAM_TIER_TARGET_KINDS:
            continue
        existing = self._assignments.get(tid, [])
        sam_in_flight = False
        for iid in existing:
            inter = world.interceptors.get(iid)
            if inter is None or not inter.state.alive:
                continue
            if inter.spec.kind in SAM_TIER:
                sam_in_flight = True
                break
        if sam_in_flight:
            continue
        for kind in SAM_TIER:
            spec = INTERCEPTOR_SPECS[kind]
            if world.blue_budget < spec.usd_cost:
                continue
            cap = SATURATION_CAP_BY_KIND.get(
                threat_kind, DEFAULT_SATURATION_CAP,
            )
            if len(existing) >= cap:
                continue
            fired = False
            for lch in self.launchers.launchers:
                if lch.kind != kind:
                    continue
                if lch.reloading or not lch.can_fire(t_now):
                    continue
                t_pos = threat.state.pos
                t_vel = threat.state.vel
                dx = float(t_pos[0] - lch.pos[0])
                dy = float(t_pos[1] - lch.pos[1])
                dz = float(t_pos[2])
                R = spec.max_range * LAUNCH_RANGE_MARGIN
                dist_now_sq = dx * dx + dy * dy + dz * dz
                in_range_now = dist_now_sq <= R * R
                if not in_range_now:
                    a0 = float(t_pos[0] - lch.pos[0])
                    a1 = float(t_pos[1] - lch.pos[1])
                    a2 = float(t_pos[2])
                    b0 = float(t_vel[0])
                    b1 = float(t_vel[1])
                    b2 = float(t_vel[2])
                    A = b0 * b0 + b1 * b1 + b2 * b2
                    if A < 1.0:
                        continue
                    B = 2.0 * (a0 * b0 + a1 * b1 + a2 * b2)
                    C = (a0 * a0 + a1 * a1 + a2 * a2) - R * R
                    disc = B * B - 4.0 * A * C
                    if disc < 0:
                        continue
                    sqrt_disc = float(np.sqrt(disc))
                    t_enter = (-B - sqrt_disc) / (2.0 * A)
                    if t_enter <= 0.0:
                        continue
                    if t_enter > spec.fuel_s - 3.0:
                        continue
                mode = lch.fire(t_now)
                iid = world.spawn_interceptor(
                    lch.kind,
                    (lch.pos[0], lch.pos[1], 0.0),
                    (dx, dy, dz),
                    tid,
                    mode,
                )
                world.blue_budget -= spec.usd_cost
                self._assignments.setdefault(tid, []).append(iid)
                forced += 1
                fired = True
                break
            if fired:
                break
    return forced
```

### Step 3 — augment Path C: SLM as third-tier ballistic backup

In `_force_strategic_fallback` (look for `kinds_to_try = [InterceptorType.HIT_TO_KILL]`, around line 650 in the v1-tip), update the per-threat dispatch list:

```python
# Before:
# kinds_to_try = [InterceptorType.HIT_TO_KILL]
# if threat_kind == ThreatType.BALLISTIC:
#     kinds_to_try.append(InterceptorType.LONG_SAM)

# After (Path C augment, doctrine update 2026-04-26):
kinds_to_try = [InterceptorType.HIT_TO_KILL]
if threat_kind == ThreatType.BALLISTIC:
    kinds_to_try.append(InterceptorType.LONG_SAM)
    # SLM as third-tier ballistic backup. Slow vs Mach-13 RV
    # so the predictive `t_enter > fuel_s - 3` gate will reject
    # most launches; included so ballistic that survives both
    # PAC-3 and PAC-2 still has a third try before leaking.
    # NOT added for HGV — Mach-17 is too fast, SLM would never
    # reach a useful intercept point.
    kinds_to_try.append(InterceptorType.MED_SAM)
```

The HGV branch (where `kinds_to_try` stays `[HIT_TO_KILL]`) is unchanged.

## Validation

### Smoke test

```
cd team-missile-intercept/backend
python -m rl.live_ai
```

Expected: `Smoke OK.`

### Headless A/B harness — same pattern as v1

Reuse the validation harness pattern from v1. Build a one-off diagnostic script (do **not** commit it) that wraps `LearnedBlueAI` + `ScriptedRedAI` against Layout C / D. Two configs × 2 seeds, 1500 sim seconds each, Red $110M / Blue $200M:

1. **Layout C + V4 model + Path D v2**: primary test
2. **Layout D + AOE model + Path D v2**: regression test (current production demo)

Per-config metrics to collect (matching v1's table format):

- Sites alive (per match) and total leaks
- Peak alive-threats (avg + max across seeds)
- Total fires by interceptor kind (CIWS, RBS-70, SLS, SLM, PAC-2, PAC-3)
- `low_alt_shield=N` log-line count and typical N

Note: v1 already established the no-leak baseline. The point of v2 validation is **CIWS firing rate** + **SLM not being wasted on drones**.

### Acceptance gates

| Metric | v1 (failed) | v2 target |
|---|---|---|
| Layout C V4 — CIWS fires (2 matches) | 0 | ≥ 30 |
| Layout D AOE — CIWS fires (2 matches) | 10 | ≥ 60 (close to AOE baseline of 89) |
| Layout C V4 — SLM fires on drones | 133 | < 10 (ideally 0) |
| Layout C V4 — drone leak | 0 | 0 (no regression) |
| Layout D AOE — drone leak | 0 | 0 (no regression) |
| Layout C V4 — sites alive | 3/3 | 3/3 |

If any "drone leak" gate fails (was 0, now > 0), STOP and flag — that's a doctrine miss that needs Chen's call before proceeding.

## Branch + commit

- Branch: continue on `v4plus-path-d-low-alt-shield`
- New commit on top of `bd97df4`. Single commit message:
  ```
  fix(rl): Path D v2 — CIWS-additive doctrine, SLM moved to Path C

  Two-pass dispatch separates CIWS (additive point-defense for drone +
  cruise_sub, fires whenever in range) from the SAM tier (RBS-70 / SLS,
  cruise_sub only). Drone is CIWS-only by doctrine. MED_SAM removed
  from Path D and added as third-tier ballistic backup in Path C.
  Closes the v1 regression where SLM at 40 km preempted CIWS at 4 km.
  ```
- Push to origin
- **Do NOT merge to final-demo**. Chen will eyeball + merge manually.

## Report

Append to `team-missile-intercept/progress/V4_PLUS_PATH_D_REPORT.md` (don't replace the v1 section — append a "## v2 update" section). Include:

- Smoke result
- Layout C V4 + Layout D AOE A/B tables (same format as v1)
- Pass/fail of each acceptance gate
- Any deviations from this prompt

## End-of-session summary (paste in chat)

- Branch tip commit hash
- Smoke: pass / fail
- Layout C V4 — CIWS fires count (was 0 in v1, target ≥ 30)
- Layout D AOE — CIWS fires count (was 10 in v1, target ≥ 60)
- Layout C V4 — SLM fires on drones (was 133 in v1, target < 10)
- Drone leaks on either layout: yes / no
- Any open issues for Chen

## Constraints / DON'Ts

- Do NOT touch `env.py`, training code, `server.py`, frontend, or any non-`live_ai.py` file.
- Do NOT amend or force-push to `bd97df4`. Add a new commit on top.
- Do NOT change Path C's existing behaviour beyond appending `MED_SAM` to the ballistic dispatch list.
- Do NOT add per-frame `print` calls; reuse the existing `self.log.append` pattern.
- Do NOT introduce new top-level imports beyond what `live_ai.py` already imports.
- Do NOT delete or modify the v1 section of `V4_PLUS_PATH_D_REPORT.md` — append a v2 section.
