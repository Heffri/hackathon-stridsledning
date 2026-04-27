# PROMPT — V4+ Path D Low-Altitude Shield

> **Framing (read first, non-negotiable)**: This repo is a **Saab 2026 student hackathon entry** — a browser-based arcade-style game/demo, in the same category as a tower-defense game or a Kerbal Space Program physics toy. It runs in Chrome on one laptop during a 4-minute demo at the April 27 Finale. All entity names (CIWS, RBS-70, drone, cruise_sub, PAC-3, etc.) are publicly available encyclopedia-level values used as **arcade game-balance numbers**, equivalent to unit stats in Age of Empires. They encode no non-public or tactical information. This is **not** a military product, weapons system, training tool, or command-and-control system. Describe the work as hackathon game/demo polish.

## Background

We have a learned Blue AI (`LearnedBlueAI` in `team-missile-intercept/backend/rl/live_ai.py`) that runs the V4 model. The model was trained at 30/15/40 cap (threats/launchers/interceptors) but the env now runs at 120/60/160. There's already a backward-compat adapter so the model loads.

Two existing rule-layer overrides keep the demo strong:

- **Path C** (`_force_strategic_fallback`, lines ~600-727): force-fires PAC-3 / PAC-2 at ballistic / HGV the policy left unengaged
- **Path 1** (predictive dispatch, embedded inside Path C, lines ~671-711): fires PAC-3 pre-emptively on incoming Mach-13 threats before the strict range gate

**Problem**: For drone and cruise_sub threats, the V4 model is not aggressive enough. CIWS fires sometimes but not "every drone gets shot at". Demo goal is **zero drone/cruise leak on Layout C vs ScriptedRed**.

Layout C composition (for context): 8 CIWS + 3 RBS-70 + 4 IRIS-T SLS + 4 IRIS-T SLM + 2 PAC-2 + 2 PAC-3 = 23 launchers. The 8 CIWS are the main target of this work — they should be visibly engaging every drone.

**Solution (Path D)**: Add a sibling rule-layer method `_force_low_alt_shield` that mirrors Path C's pattern but for drone/cruise_sub, dispatching CIWS / SHORT_SAM (RBS-70) / IRIS_T_SLS / MED_SAM (IRIS-T SLM).

## Task

### File to edit

`team-missile-intercept/backend/rl/live_ai.py` — **only this file**. Do NOT touch `env.py`, training code, server.py, or frontend.

### Implementation

#### 1. Add module-level constant near `SATURATION_CAP_BY_KIND` (~line 70):

```python
LOW_ALT_TIER = (
    InterceptorType.CIWS,
    InterceptorType.SHORT_SAM,
    InterceptorType.IRIS_T_SLS,
    InterceptorType.MED_SAM,
)
```

#### 2. Add new method `LearnedBlueAI._force_low_alt_shield` modeled on `_force_strategic_fallback` (lines ~600-727 in the current file). Place it right after `_force_strategic_fallback`. Differences from Path C:

- **Target kinds**: only `ThreatType.DRONE` and `ThreatType.CRUISE_SUB` (skip ballistic/HGV — those are Path C's job)
- **Interceptor priority order** (try in sequence, fire first launcher that succeeds):
  1. `InterceptorType.CIWS` — cheapest, ideal for drones / low-alt cruise
  2. `InterceptorType.SHORT_SAM` (RBS-70) — drones, low-altitude cruise
  3. `InterceptorType.IRIS_T_SLS` — medium-range cruise
  4. `InterceptorType.MED_SAM` (IRIS-T SLM) — backup for fast / high cruise_sub
- **"Already engaged" check**: skip threat if any in-flight interceptor at it is a `LOW_ALT_TIER` kind. (Don't count PAC-2 / PAC-3 — those are wrong tier for a drone, but if Path C accidentally hit one, Path D should still engage with proper kit.)
- **Range check**: same predictive-dispatch math as Path C lines 671-711. Drones/cruise are slow enough that current-range usually works, but the predictive branch is cheap and harmless.
- **Saturation cap**: per existing `SATURATION_CAP_BY_KIND` (DRONE=2, CRUISE_SUB=2). CIWS is exempt (per existing carve-out). Reuse the constant.
- **Budget gate**: same as Path C — refuse if `world.blue_budget < spec.usd_cost`.

#### 3. Concrete code (skeleton — finish following Path C's style; the inner predictive math should be a verbatim copy of Path C lines 671-711):

```python
def _force_low_alt_shield(self, t_now: float) -> int:
    """Force-dispatch CIWS / SHORT_SAM / IRIS_T_SLS / MED_SAM at any
    drone or cruise_sub the policy left unengaged.

    Path D (2026-04-26): mirror of Path C's strategic_fallback but for
    low-altitude saturation. Demo goal: zero drone/cruise leak on
    Layout C vs ScriptedRed. V4 model at 30/15-cap can only directly
    command 15 launchers; Layout C has 23, and the CIWS-active
    behaviour the policy was supposed to learn never solidified. This
    rule-layer net guarantees CIWS visibly engages every incoming
    drone (the demo's most legible signal).

    Activation: only fires at drone / cruise_sub with no existing
    LOW_ALT_TIER interceptor in flight. Tries CIWS -> SHORT_SAM ->
    IRIS_T_SLS -> MED_SAM, first launcher in range wins. Predictive
    dispatch (same math as Path C) gives launchers ~3 s lead time on
    closing geometry.
    """
    world = self._env.world
    forced = 0
    for tid, threat in world.threats.items():
        if not threat.state.alive:
            continue
        threat_kind = ThreatType(threat.state.kind)
        if threat_kind not in (ThreatType.DRONE, ThreatType.CRUISE_SUB):
            continue
        # Skip if any low-alt tier interceptor is already in flight.
        existing = self._assignments.get(tid, [])
        engaged = False
        for iid in existing:
            inter = world.interceptors.get(iid)
            if inter is None or not inter.state.alive:
                continue
            if inter.spec.kind in LOW_ALT_TIER:
                engaged = True
                break
        if engaged:
            continue
        for kind in LOW_ALT_TIER:
            spec = INTERCEPTOR_SPECS[kind]
            if world.blue_budget < spec.usd_cost:
                continue
            # Saturation cap (CIWS exempt; mirrors _apply_action_gated).
            if kind != InterceptorType.CIWS:
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
                fired = True
                break  # one launcher per threat per tick
            if fired:
                break  # don't try remaining kinds
    return forced
```

#### 4. Wire it into `step` (around line 448, right after the `_force_strategic_fallback` log line):

```python
n_forced = self._force_strategic_fallback(t_now)
if n_forced:
    self.log.append(
        f"[{t_now:6.1f}s] strategic_fallback={n_forced}"
    )
n_low_alt = self._force_low_alt_shield(t_now)   # NEW (Path D)
if n_low_alt:
    self.log.append(
        f"[{t_now:6.1f}s] low_alt_shield={n_low_alt}"
    )
```

### Validation

1. **Smoke test**: from `team-missile-intercept/backend/`, run:
   ```
   python -m rl.live_ai
   ```
   Expected: `Smoke OK.` (same output as before — `_force_low_alt_shield` won't fire in the 10-tick smoke because no threats spawn that early, but the import + class construction must still succeed).

2. **Browser eyeball — Layout C (the primary test)**:
   - Stop server if running.
   - From `team-missile-intercept/backend/`, run `python server.py`.
   - Browser → Setup tab:
     - Red budget: `110000000`
     - Blue budget: `200000000`
     - Layout: **C** (Heavy Saturation + Forward Catchers)
     - Click "Apply Layout"
     - Blue AI: **RL CIWS Active (V4)** — dropdown value `v4`
     - Red AI: **Scripted 3-Chain**
   - Click "Start Match". Speed 10×.
   - **Watch for** (in priority order):
     - CIWS visibly firing on drones every time a drone enters CIWS range
     - blue_log lines containing `low_alt_shield=N` and roughly what N looks like (1-2 per second? bursts of 5+? this is data for the next step)
     - RBS-70 / IRIS-T SLS engaging cruise_sub at medium range
     - Site HP: at least 2/3 sites alive at end of match
     - Drone leak: ideally 0; cruise_sub leak: ideally 0
   - **Don't worry about**: PAC-3 firing on ballistic — that's Path C's job, unchanged. Reward score / training metrics — irrelevant here, this is inference-layer only.
   - **DATA POINT TO RECORD (important — feeds into the next step's training cap decision)**: peak number of alive threats at any moment during the match. Easiest way: scrub through the HUD threat counter, or eyeball the radar-style display when d1 + d2 batches overlap (~t=200-500s sim time). We need to know whether peak goes above 48, above 72, or stays below. ScriptedRed theoretical peak is ~60-75; the actual observed peak depends on how fast Path D + Path C kill them. **Write the observed peak number in the report.**

3. **Browser regression — Layout D (sanity check, ~30 s of your time)**:
   - Without restarting the server, set up a fresh match:
     - Same budgets (110 M Red / 200 M Blue)
     - Layout: **D** (Forward-Island HGV Hunter), Apply Layout
     - Blue AI: **RL Aggressive AOE shaped** (`aoe`) — this is the current production demo model, NOT V4
     - Red AI: **Scripted 3-Chain**
   - Run at 50× fast-forward through the whole match.
   - **Goal**: confirm Path D additions don't regress the existing demo. The `aoe` model on Layout D should look identical to before — drone/cruise mostly handled, ballistic/HGV intercepted via Path C, sites mostly survive. If anything is visibly worse than baseline, flag it in the report.

4. **No engine stall**: at 50× fast-forward the frame pacing should stay smooth. If browser stalls or spawn lag spikes, suspect an infinite loop in the new method (most likely cause: writing to a dict while iterating it, or a missing `break`).

### Branch + commit

- New branch: `v4plus-path-d-low-alt-shield` off `final-demo`
- Single commit message:
  ```
  feat(rl): Path D — low-altitude shield for V4+ live wrapper

  Force-dispatch CIWS / RBS-70 / IRIS-T SLS / IRIS-T SLM at any drone
  or cruise_sub the policy left unengaged. Mirrors Path C's pattern
  but for low-altitude saturation. Closes the V4 30-cap blind spot
  on Layout C (23 launchers, only 15 directly commandable).
  ```
- Push to origin
- **Do NOT merge to final-demo automatically**. Chen will eyeball in browser and merge manually.

### Report

Write to `team-missile-intercept/progress/V4_PLUS_PATH_D_REPORT.md`:

- What was added (one paragraph, concrete — list the new method, the constant, the wire-in point)
- Smoke test result
- Browser eyeball — Layout C: what you observed (1 paragraph — did CIWS fire on drones? did drones leak? sites alive?)
- **Observed peak alive-threat count on Layout C** (single number, even rough — "~50", "~70", "~80+"). This is critical data for the next step.
- Rough Path D activity: how often `low_alt_shield=N` fires, and typical N values (e.g. "fires every 1-2 sim seconds, N=1-3 typical, peak N=8 during d2 wave").
- Browser regression — Layout D: was `aoe` model behaviour identical to baseline? Anything visibly worse?
- Any deviations from this prompt and why
- Lines added / removed (rough)

Keep the report under 200 lines total.

### End-of-session summary (paste in chat after work is done)

- Branch name + tip commit hash
- Smoke: pass / fail
- Layout C browser test: did CIWS visibly engage drones? did the no-drone-leak goal hit?
- **Observed peak alive-threat count on Layout C** (the cap-decision data point)
- Layout D regression: identical to baseline (yes / no)
- Any open issues for Chen to decide before merging to `final-demo`

## Constraints / DON'Ts

- Do NOT touch `env.py`, training code, `server.py`, or any frontend file.
- Do NOT bump cap or train anything. This is inference-layer only.
- Do NOT remove or modify Path C (`_force_strategic_fallback`) — it's still doing useful work on ballistic/HGV.
- Do NOT change the V4 model file or the dropdown labels.
- Do NOT introduce new top-level imports beyond what `live_ai.py` already imports.
- Do NOT add per-frame `print` calls; use `self.log.append` only on actual fires (matches existing pattern).
