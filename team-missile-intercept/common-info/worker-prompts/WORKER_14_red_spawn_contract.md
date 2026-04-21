# Worker 14 — Red spawn contract: spatial validation for Boyu's AI

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Worker runs **autonomously** — Chen verifies at end via test pass + reads new CONTRACT_SEAMS section. Budget: ~1.5–2 h. Five small subtasks → five commits.

**Prerequisite:** W13 overnight batch landed. Confirm `git log --oneline -6` shows `545036b docs: W13 overnight batch close` near the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names and numerical stats are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingyi chen\Documents\GitHub\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). Push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `545036b` or newer.

Start by reading:
- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — focus on Issue #3 (no-waves direction), Issue #8 (red_budget, landed M-TIER3), Issue #10-12 (threat contract, landed M-TIER3-THREAT-CONTRACT)
- `team-missile-intercept/game-core/CONTRACT_SEAMS.md` §8.1 — unified Threat control contract (Boyu's consumption surface)
- `team-missile-intercept/progress/STATUS.md`

Key files (this worker touches these; read them before editing):
- `team-missile-intercept/backend/sim/terrain.py` — `point_on_south_land`; may or may not have a `point_on_north_land` yet
- `team-missile-intercept/backend/sim/config.py` — constants (`STRAIT_CENTER_Y`, arena bounds, red/blue launcher positions)
- `team-missile-intercept/backend/sim/red_ai.py` — `_sample_spawn` uses the strategic Y band for ballistic/HGV; `_spawn_point` for drone/cruise
- `team-missile-intercept/backend/sim/world.py` — `World.spawn_threat` (the single entry point every spawner goes through; this is where validation lands)
- `team-missile-intercept/backend/sim/types.py` — `ThreatType` enum

# Pre-flight

1. `git status` — clean. If dirty, `git stash push -m "worker14-preflight"` and pop at end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -6` — confirm `545036b` or newer.
6. Preflight tests must all pass (if any fail, STOP):
   - `python team-missile-intercept/backend/test_match_phase.py`
   - `python team-missile-intercept/backend/test_match_phase_integration.py`
   - `python team-missile-intercept/backend/test_engagement_mode.py`
   - `python team-missile-intercept/backend/test_launcher_id.py`
   - `python team-missile-intercept/backend/test_placement_api.py`
   - `python team-missile-intercept/backend/test_launcher_base_cost.py`
   - `python team-missile-intercept/backend/test_roster_api.py`
   - `python team-missile-intercept/backend/test_ciws_saturation.py`
   - `python team-missile-intercept/backend/test_ciws_shot_cap.py`
   - `python team-missile-intercept/backend/test_winner_budget_not_loss.py`
   - `python team-missile-intercept/backend/test_red_budget.py`
   - `python team-missile-intercept/backend/test_threat_contract.py`
   - `python team-missile-intercept/backend/test_cruise_impact.py`
   - `python team-missile-intercept/backend/test_hgv_impact.py`
   - `python team-missile-intercept/backend/test_ballistic_cep.py`

# Design target

**Goal**: Formalise the spatial spawn contract that Boyu's future Red AI will consume. Today, `RedAI.step` routes all spawns through `_spawn_point` / `_sample_spawn` which happen to produce valid locations by construction (fixed `RED_LAUNCHER_POSITIONS` for drone/cruise + `STRATEGIC_Y_BAND` for ballistic/HGV). This is implicit. The future Red AI will call `world.spawn_threat` directly with chosen `(x, y, z)`, and there is currently **no enforcement** that those coordinates are sensible.

Chen's 2026-04-20 design intent:
- **Drone + Cruise**: Red AI picks ANY (x, y) on the north-side landmass. Not fixed to the current 5 visible red-box launchers. Constraint: must be on north-side land (not sea). Altitude per existing spec defaults.
- **Ballistic + HGV**: Red AI picks ANY X in the strategic-Y band. Not fixed to random sampling. Constraint: Y must be ≥ `STRATEGIC_Y_FLOOR` so Blue AI has enough flight time to react (rough target: ≥ 60 km of flight at Mach 13-17, ≈ 5-10 s reaction window). Altitude per existing spec defaults.

**Deliverable shape:**
1. `terrain.point_on_north_land(x, y) -> bool` (add if missing; symmetric cousin of `point_on_south_land`).
2. `config.STRATEGIC_Y_FLOOR = 180_000` new constant (metres). Sized so ballistic (Mach 13 ≈ 4459 m/s over ~180 km Y = ~40 s) and HGV (Mach 17 ≈ 5831 m/s over ~180 km Y = ~31 s) both give Blue at least ~20+ s of engagement window before terminal phase. Not the 235-245 km strategic BAND — that's a narrower sampling range for today's random spawner. The FLOOR is the minimum Y the future Red AI is allowed to pick.
3. Validation in `World.spawn_threat` — on violation, raise `ValueError` with a descriptive message naming the offending coord + the rule. Current `_spawn_point` / `_sample_spawn` paths always produce valid coords, so existing callers are unaffected.
4. Tests: valid + invalid spawn per kind. Existing regressions stay green.
5. Documentation in `CONTRACT_SEAMS.md` (new § "Red spawn contract") so Boyu knows the rules before writing AI code.
6. Issue #30 captures the contract for traceability.

# Subtasks

## Subtask A — `terrain.point_on_north_land` + config constant (~20-30 min)

1. Read `backend/sim/terrain.py`. Confirm whether `point_on_north_land(x, y)` already exists. It should — it's the symmetric cousin of `point_on_south_land` and is used (or was planned to be used) for Red launcher validation. If it does NOT exist, add it following the exact same pattern as `point_on_south_land`: parse Saab CSV polygons at module load, point-in-polygon check against the north-side landmass polygons.
2. Add `STRATEGIC_Y_FLOOR = 180_000` to `backend/sim/config.py` with a clarifying comment:
   ```python
   # W14 (Issue #30, 2026-04-20): minimum Y (metres north of origin) at
   # which future Red AI is allowed to spawn a ballistic or HGV threat.
   # Sized so even a Mach-17 HGV has ~31 s of flight time before reaching
   # a typical southern site, giving Blue AI a realistic engagement
   # window. The existing `STRATEGIC_Y_BAND = [235_000, 245_000]` used
   # by today's random wave spawner is a narrower sampling range (very
   # far back). The FLOOR is the future-AI rule; the BAND is the current
   # spawner's habit.
   STRATEGIC_Y_FLOOR = 180_000
   ```
3. Minimal test additions — new `test_red_spawn_contract.py`:
   - `test_north_land_helper_basic`: sample a few known-north-land coords (from `RED_LAUNCHER_POSITIONS`) and assert `point_on_north_land` returns True for each. Sample a few known-sea coords (e.g. strait centre) and assert False.
   - `test_strategic_y_floor_is_configured`: assert `config.STRATEGIC_Y_FLOOR >= 150_000` and `<= config.ARENA_Y`.

**Commit:** `feat(game-core): terrain.point_on_north_land + STRATEGIC_Y_FLOOR (W14 prereq)`

Push.

**STOP:** if `point_on_north_land` exists but doesn't match the south-side pattern (e.g. uses different polygon data, different return shape), STOP and report — this worker should not unify terrain APIs.

## Subtask B — Validation in `World.spawn_threat` (~30-40 min)

1. In `backend/sim/world.py::spawn_threat`, after arg parsing and before the `Threat(...)` construction, add a validation block:
   ```python
   # W14 (Issue #30): enforce the Red spawn contract. Boyu's future Red
   # AI calls spawn_threat with arbitrary (x, y) — the runtime validates
   # the location per kind so a misbehaving AI can't cheat by spawning
   # an HGV directly over a Blue site.
   x_spawn = float(start_xy[0])
   y_spawn = float(start_xy[1])
   if kind in (ThreatType.DRONE, ThreatType.CRUISE_SUB):
       if not terrain.point_on_north_land(x_spawn, y_spawn):
           raise ValueError(
               f"{kind.value} spawn at ({x_spawn:.0f}, {y_spawn:.0f}) "
               f"is not on north-side land. Drone / cruise must launch "
               f"from Red mainland or islands (see terrain.point_on_north_land)."
           )
   elif kind in (ThreatType.BALLISTIC, ThreatType.HGV):
       if y_spawn < config.STRATEGIC_Y_FLOOR:
           raise ValueError(
               f"{kind.value} spawn y={y_spawn:.0f} is too close to the "
               f"front line. Strategic-range assets must spawn with "
               f"y >= {config.STRATEGIC_Y_FLOOR} "
               f"(gives Blue ~20+ s of engagement window)."
           )
   ```
2. Import `terrain` at the top of `world.py` if not already imported.
3. Rationale for `ValueError` vs silent-reject: today's only spawn callers are `RedAI.step` (wave spawner — always produces valid coords) and tests. Any future caller producing invalid coords is a bug that must surface loudly, not silently drop the spawn. The AI layer can catch + retry; the raise is the clearest signal.
4. Altitude is NOT validated in this subtask — `_sample_spawn` currently enforces altitude floors (ballistic ≥ 20 km, HGV ≥ 30 km) and those remain advisory. Future Red AI can use default altitude by omitting z; if a bad altitude causes the threat to behave poorly, that's gameplay feedback not a spawn-contract violation.

**Commit:** `feat(game-core): validate Red spawn location per kind in World.spawn_threat (Issue #30)`

Push.

**STOP:** if adding the validation breaks any existing test (it shouldn't — all current callers produce valid coords), STOP and inspect. Either the test has a latent bad spawn (fix the test) or the validation rule is too tight (loosen it).

## Subtask C — Test coverage for the contract (~30-40 min)

Extend `test_red_spawn_contract.py` (from Subtask A) with four categories of cases:

1. **Valid spawns succeed** (regression guard):
   - Drone at each of `RED_LAUNCHER_POSITIONS["drone"]` + altitude defaults → `spawn_threat` returns an int id, no raise.
   - Cruise at each `RED_LAUNCHER_POSITIONS["cruise_sub"]` → succeeds.
   - Ballistic at (75_000, 240_000, 40_000) → succeeds.
   - HGV at (75_000, 240_000, 35_000) → succeeds.

2. **Drone / cruise in sea → rejected** (validation fires):
   - Drone at (75_000, 120_000, 2_000) — middle of the strait — `assertRaises(ValueError)` with a message mentioning `north-side land`.
   - Cruise at (10_000, 110_000, 3_000) — also strait-ish — `assertRaises(ValueError)`.

3. **Drone / cruise on SOUTH land → rejected** (should never happen; sanity):
   - Drone at `config.BLUE_BASE_POS[0], config.BLUE_BASE_POS[1], 2_000` — Blue mainland — `assertRaises(ValueError)`.

4. **Ballistic / HGV below the Y floor → rejected**:
   - Ballistic at (75_000, 50_000, 30_000) — Y well south of `STRATEGIC_Y_FLOOR` — `assertRaises(ValueError)` with a message mentioning `STRATEGIC_Y_FLOOR`.
   - HGV at (75_000, config.STRATEGIC_Y_FLOOR - 1, 35_000) — exactly one metre below the floor — `assertRaises(ValueError)`. (Boundary condition.)
   - HGV at (75_000, config.STRATEGIC_Y_FLOOR, 35_000) — exactly AT the floor — succeeds (floor is inclusive).

5. **Default scenario still runs end-to-end**:
   - Build `build_default_scenario(auto_start=True)`, step 250 s of sim. Assert `scn.red.done` True and `scn.world.threats_spawned == 26` (the default wave count). No `ValueError` raised anywhere in the sim loop. This confirms the existing `_sample_spawn` + `_spawn_point` paths always produce coords the new validation accepts.

**Commit:** `test(game-core): Red spawn contract — valid + invalid cases per kind (Issue #30)`

Push.

**STOP:** if test 5 (default scenario regression) fails, either the validation is wrong for a corner case the wave spawner can hit, or the wave spawner has a latent bad-coord bug. Both worth a STOP + report; do NOT mask the failure by loosening the validation.

## Subtask D — Documentation: CONTRACT_SEAMS + Issue #30 (~20-30 min)

1. `team-missile-intercept/game-core/CONTRACT_SEAMS.md`: add a new section **§9 Red spawn contract (M-TIER3+, Issue #30, 2026-04-20)** summarising:
   - What the contract guarantees.
   - Per-kind validation rules (table).
   - The `ValueError` protocol — Red AI callers are expected to produce valid coords; invalid coords raise so bugs surface loudly.
   - Altitude is not validated (Red AI's choice; degraded behaviour is gameplay feedback).
   - Existing wave spawner is unaffected (it produces valid coords by construction via `_sample_spawn` + `_spawn_point`).
   - Pointer to `test_red_spawn_contract.py` as the acceptance harness.
2. `team-missile-intercept/game-core/ISSUES_2026-04-19.md`: add **Issue #30 — Red spawn contract for Boyu's AI**. State: Done. Owner: Chen (runtime) + Boyu (consumer). Tier: 3. Cross-ref to Issue #3 (no-waves direction) + Issue #8 (red_budget).
3. `team-missile-intercept/progress/STATUS.md`: append a small `1.1 W14 — Red spawn contract landed` block.

**Commit:** `docs: W14 close — Red spawn contract (Issue #30) + CONTRACT_SEAMS §9`

Push.

# Non-goals / hard guardrails

- **Do NOT change Red AI wave behaviour**, `_sample_spawn`, `_spawn_point`, or `build_demo_waves`. The current spawner produces valid coords; leave it alone. This worker only adds the validation LAYER; the wave spawner is unaffected.
- **Do NOT change Blue side** — `spawn_interceptor`, `blue_ai`, Blue launcher placement. Different subsystem, no overlap.
- **Do NOT change `STRATEGIC_Y_BAND`**. That's the current spawner's habit; `STRATEGIC_Y_FLOOR` is the new floor. Both coexist.
- **Do NOT validate altitude**. Future scope; altitude is advisory.
- **Do NOT add tests that depend on the legacy `STRATEGIC_Y_BAND`**. The contract is `Y >= STRATEGIC_Y_FLOOR`.
- **Do NOT modify `world.spawn_interceptor`**. Red spawn contract is specifically for threats.
- **Do NOT commit API keys.**
- **No `--no-verify`, no `git amend`, no force-push.**
- **English** in commits, code, comments, docs.
- **Kill any server** you start for smoke. Port 5174 must be free at session end.

# Hard rules

- One commit per subtask. 4 subtasks → 4 commits (Subtask A, B, C, D).
- Each commit pushed immediately after local tests pass.
- Each commit ends with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- If a STOP condition hits, ship prior subtasks (if committed), STOP, write final summary.
- Budget: ~1.5–2 h total.
- **Chen is NOT paired.** Self-verify via test pass + code-reading. No browser smoke needed (backend-only change).

# Post-flight

1. `git status` — clean.
2. `git log --oneline -8` — 4 new commits above `545036b`.
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity.
4. If stashed: `git stash pop`.
5. Full preflight test list PLUS new `test_red_spawn_contract.py` all green.

# Deliverable — final summary (≤ 400 words)

1. **Commits landed** (4 hashes + one-line each).
2. **Subtask A** — was `point_on_north_land` present already or added? Did `STRATEGIC_Y_FLOOR` land at 180_000 or a different value (if different, WHY)?
3. **Subtask B** — confirm `ValueError` raised on violation, `ValueError` message format, zero impact on existing callers.
4. **Subtask C** — test case table: valid spawns pass (with counts), invalid spawns raise (with counts), default scenario regression (spawned=26 confirmed).
5. **Subtask D** — doc locations landed.
6. **Test delta** — preflight → postflight, new test file size.
7. **Anything blocking or surprising** — especially if `point_on_north_land` revealed a terrain-data inconsistency Chen should know about.
8. **For Boyu** — one-sentence how-to: "import `world.spawn_threat`, pass `(x, y)` per §9 rules, catch `ValueError` on invalid coord and retry / pick a different location."
