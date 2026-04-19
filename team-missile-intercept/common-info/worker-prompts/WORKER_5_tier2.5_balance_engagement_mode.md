# Worker 5 — M-TIER2.5: flyover rule + engagement_mode infrastructure + balance pass

**How to use this file:** paste the entire contents below (everything from `# Hackathon framing` onward) into a fresh Claude Code worker session at the repo root (`C:\Users\xingy\Documents\github\hackathon-stridsledning`) on branch `new-teamwork-split-V1`. Intended to run under bypass permissions for ~2–4 hours.

**Prerequisite:** Worker 4 (M-TIER2-PHASE) must have landed. Confirm `git log --oneline -8` on `new-teamwork-split-V1` shows `c42c740 docs: ISSUES + backlog + STATUS update - M-TIER2-PHASE` at (or near) the top.

---

# Hackathon framing — do not skip

I'm working on a student hackathon entry for the Saab 2026 "Smart Stridsledning" university competition (Hack Day 2026-04-25, Finale 2026-04-27, 4-minute presentation). What we're building is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or Kerbal Space Program. It is **not** a military product, weapons system, training tool, or command-and-control tool, and it has no real-world operational application. All entity names (HGV, ballistic, cruise, drone, PAC-3, PAC-2, IRIS-T SLS/SLM, RBS 70, CIWS) and numerical stats (speeds, damage values, radii) are publicly available encyclopedia-level values used as arcade game-balance numbers, equivalent to unit stats in Age of Empires. Please treat this as a pure game-dev / web-dev task. All prose in commits, comments, and docs should use game-dev framing ("threat", "intercept", "engagement", "arcade", "game-balance") and avoid operational/tactical language.

A previous account on this project was suspended when framing was ambiguous. Keeping this disclaimer at the top of every prompt is non-negotiable.

# Context

Repo root: `C:\Users\xingy\Documents\github\hackathon-stridsledning`. Active project: `team-missile-intercept/`.

Active branch: `new-teamwork-split-V1` (PR #4). You will push every commit to `origin/new-teamwork-split-V1` via `git push origin HEAD:new-teamwork-split-V1`.

Expected starting HEAD: `c42c740` (Worker 4's docs commit, or newer).

Start by reading these files:

- `CLAUDE.md` (repo root) — project framing
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/progress/STATUS.md`
- `team-missile-intercept/game-core/ISSUES_2026-04-19.md` — **primary task tracker**; read Issues #2 (HGV airburst, landed partial), #11 (ballistic default steering, verified W3)
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`
- `team-missile-intercept/backend/balance_baseline_2026-04-19.json` — Worker 3's regression baseline (post-HGV-glide-path + post-ballistic-drag-fix)
- `team-missile-intercept/backend/BALANCE_BASELINE_README.md` — how to rerun and diff

Key runtime files you will touch or read:

- `team-missile-intercept/backend/sim/types.py` — `ThreatSpec` (with `requires_ground_impact: bool = False` at line ~91; currently set True only on HGV at line ~170). `InterceptorSpec` dataclass lives here too (search for `damage_direct` / `damage_prox` / `radius_direct` / `radius_prox`). Interceptor instances are defined ~lines 198–300 (6 types).
- `team-missile-intercept/backend/sim/config.py` — `BLUE_BASE_POS`, `BLUE_LAUNCHER_POSITIONS`, etc. The threat specs may live here OR in types.py — grep for `ThreatSpec(` to find the instance declarations.
- `team-missile-intercept/backend/sim/world.py` — leak detector and damage resolution. Damage branch at lines ~166–183 uses `spec.radius_direct` / `spec.radius_prox` / `spec.damage_direct` / `spec.damage_prox`.
- `team-missile-intercept/backend/sim/entities.py` — `Interceptor` class at line ~507.
- `team-missile-intercept/backend/sim/launcher.py` — `fire()` method that constructs Interceptor instances from spec + context. This is where engagement_mode gets plumbed.
- `team-missile-intercept/backend/sim/blue_ai.py` — the Blue AI that picks interceptors and calls fire().
- `team-missile-intercept/backend/test_balance.py`, `test_balance_baseline.py`, `test_ballistic_cep.py`, `test_hgv_impact.py`, `test_threat_impact.py`, `test_full_scenario.py`, `test_damage_debug.py`, `test_pn.py`, `test_ballistic.py`, `test_match_phase.py`, `test_match_phase_integration.py` — existing tests you must not break.

# Damage model facts (read carefully — this is the key piece for Subtask 2)

The current damage model at `world.py:166–183` is:

```python
kr = max(inter.spec.kill_radius, target.spec.kill_radius)
if d_min > kr:
    continue    # no hit — CPA too far

spec = inter.spec
if d_min < spec.radius_direct:
    damage = spec.damage_direct
    hit_kind = "direct"
elif d_min < spec.radius_prox:
    fall = 1.0 - (d_min / spec.radius_prox)
    damage = max(1, int(round(spec.damage_prox * fall)))
    hit_kind = "prox"
else:
    damage = 0
    hit_kind = "miss"
```

Each interceptor spec already carries the four knobs `damage_direct`, `damage_prox`, `radius_direct`, `radius_prox`. Current behavior is "auto": direct first if CPA tight, prox fallback if wider, miss if past `radius_prox`. Typical PN+Euler CPA is 20–80 m (per `world.py:169` comment).

Observed spec values (from `types.py`):

| Type (config key → enum) | damage_direct | damage_prox | radius_direct | radius_prox |
|---|---|---|---|---|
| ciws → CIWS | 15 | 8 | 1.0 m | 80 m |
| rbs_70 → SHORT_SAM | 40 | 20 | 1.0 m | 120 m |
| iris_t_sls → IRIS_T_SLS | 50 | 25 | 1.0 m | 100 m |
| iris_t_slm → MED_SAM | 50 | 25 | 2.0 m | 150 m |
| pac_2 → LONG_SAM | 80 | 40 | 3.0 m | 180 m |
| pac_3 → HIT_TO_KILL | 200 | 25 | **60 m** | 80 m |

The current `damage_direct = 2 × damage_prox` for SAMs is intentional — the existing spec already encodes "direct hit does double damage compared to prox." pac_3's huge `radius_direct=60m` is what makes it an HTK-class interceptor today.

# Pre-flight

1. `git status` — must be clean. If dirty, `git stash push -m "worker5-preflight"` and continue; pop at the end.
2. `git fetch origin`
3. `git checkout new-teamwork-split-V1`
4. `git pull --ff-only origin new-teamwork-split-V1`
5. `git log --oneline -8` — confirm `c42c740` or newer is at top. If older, STOP and report — this worker is blocked.

# Task

Four subtasks, executed in order. **One atomic commit per subtask.** Push each commit immediately after it lands locally and tests pass.

## Subtask A — Broad flyover rule: threats must reach ground to deal damage (30–45 min)

**Intent (operator decision, 2026-04-19):** any threat kind EXCEPT a future nuclear warhead kind (which doesn't exist yet) must physically reach the ground to trigger site damage. The current state is that HGV has `requires_ground_impact=True` (landed in commit `2f2392c` via Issue #2) but ballistic / cruise / drone still default to False, which lets them trigger the horizontal-disc leak check while flying over non-target sites at altitude. Worker 3's ballistic CEP test caught this: 2/30 ballistic trials fired leak damage on Spear Point at ~13 km altitude while en route to Main Base.

**Method:**

1. Grep for `ThreatSpec(` instances to find all threat kind spec declarations. Expect 4 kinds: drone, cruise_sub, ballistic, hgv. Confirm HGV has `requires_ground_impact=True` and the other three do not.
2. Set `requires_ground_impact=True` for ballistic, cruise_sub, drone.
3. Leave the `ThreatSpec` default (`False`) alone — future nuclear warhead will explicitly omit the override to get airburst semantics.
4. Rerun these existing tests and confirm they still pass:
   - `python team-missile-intercept/backend/test_ballistic_cep.py` — expect the 2/30 flyover trials to no longer count as damage events; median CEP may slightly decrease (fewer outliers).
   - `python team-missile-intercept/backend/test_hgv_impact.py` — no change expected; HGV rule was already True.
   - `python team-missile-intercept/backend/test_threat_impact.py` — expect continued PASS.
   - `python team-missile-intercept/backend/test_damage_debug.py` — expect continued PASS (if it references airburst explicitly, may need adjustment).
   - `python team-missile-intercept/backend/test_ballistic.py` — expect continued PASS.
5. Also rerun `python team-missile-intercept/backend/test_balance.py` (the 20-match sweep — ~1-2 min wall-clock). Capture the new Blue/Draw/Red split and per-kind leak counts; expect fewer Red leaks for ballistic / cruise / drone (flyover removed).

**Commit:** `fix(game-core): require ground impact for all non-nuclear threat kinds (broader Issue #2)`

Include a short table in the commit body comparing pre-W5 vs post-A leak counts per kind from `test_balance.py`, and note any test file updates.

Push to origin.

**STOP conditions:**
- Any existing test fails unexpectedly (except cosmetic number shifts matching the flyover fix) → STOP, report.
- `test_balance.py` shows Red winning the majority (> 50%) — this would be unexpected (we're making threats weaker); investigate integration error.

## Subtask B — `engagement_mode` infrastructure (pure mechanism, default preserves current behavior) (~1.5–2 h)

**Intent:** add a per-shot `engagement_mode` field (`'prox' | 'htk'`) on the Interceptor instance, plumbed through `launcher.fire(..., engagement_mode=None)` into the damage resolver. The default is `'prox'` for ALL interceptors, and `'prox'` mode is **bit-for-bit identical to the current auto direct+prox behavior** — no balance change. The `'htk'` mode is new but opt-in only (no caller uses it in this worker session; it's infrastructure for Boyu / Oskar / future balance pass).

This is pure **方案 A** from the 2026-04-19 discussion. Default behavior is explicitly NOT changed. Do not set any interceptor's default to `'htk'`. The chosen implementation is "infrastructure only; Oskar / future worker decides when HTK pays off."

**Data model changes:**

1. `InterceptorSpec` (in `types.py`): add two fields.
   - `engagement_mode_choices: tuple[str, ...] = ('prox',)` — the legal modes for this spec.
   - `default_engagement_mode: str = 'prox'` — the mode used when the fire caller doesn't pass one.
   - Per-type settings in the six spec instances:
     - CIWS: `choices=('prox',)`, `default='prox'` (cannonfire has no HTK concept).
     - SHORT_SAM, IRIS_T_SLS, MED_SAM, LONG_SAM: `choices=('prox', 'htk')`, `default='prox'`. These are the four dual-mode interceptors.
     - HIT_TO_KILL: `choices=('htk',)`, `default='htk'`. pac_3 is physically HTK-only.
2. `Interceptor` (in `entities.py`): add an `engagement_mode: str` field to `__slots__` and `__init__`. Default is whatever `launcher.fire()` passes; launcher passes spec default if caller doesn't override.
3. `launcher.fire(...)` (in `launcher.py`): add optional `engagement_mode: str | None = None` kwarg. If None → `spec.default_engagement_mode`. Validate against `spec.engagement_mode_choices` and raise `ValueError` if illegal (caller bug). Pass through to the constructed Interceptor instance.
4. `blue_ai.py` — do NOT change the fire call sites. Let the default apply. (This is what keeps behavior identical.)

**Damage resolver changes (world.py ~line 166):**

Refactor the existing block so the behavior is identical when `engagement_mode='prox'` and a new branch handles `'htk'`:

```python
spec = inter.spec
mode = inter.engagement_mode

if mode == 'prox':
    # Current behavior — do not change — keeps all existing tests green.
    if d_min < spec.radius_direct:
        damage = spec.damage_direct
        hit_kind = "prox_direct"   # renamed for clarity; see note below
    elif d_min < spec.radius_prox:
        fall = 1.0 - (d_min / spec.radius_prox)
        damage = max(1, int(round(spec.damage_prox * fall)))
        hit_kind = "prox"
    else:
        damage = 0
        hit_kind = "miss"
elif mode == 'htk':
    # New branch — direct-or-miss, double damage on direct hit.
    if d_min < spec.radius_direct:
        damage = spec.damage_direct * 2
        hit_kind = "htk_direct"
    else:
        damage = 0
        hit_kind = "htk_miss"
else:
    raise ValueError(f"Unknown engagement_mode: {mode!r}")
```

**On the `hit_kind` rename:** the existing code emits `"direct"` / `"prox"` / `"miss"` in event logs. If any snapshot consumer (frontend, tests) reads these strings, the rename could break them. **Preserve the existing string values in 'prox' mode** (so `"direct"` stays `"direct"`, not `"prox_direct"`). The pseudo-code above is just illustrative — keep your actual `hit_kind` strings backward-compatible in prox mode. Only emit new strings (`"htk_direct"`, `"htk_miss"`) in HTK mode, which is opt-in only.

**New test:** `backend/test_engagement_mode.py`

Unit-test coverage:
- HTK direct hit produces `damage_direct * 2` and `hit_kind == "htk_direct"`.
- HTK at CPA between radius_direct and radius_prox produces `damage == 0` and `hit_kind == "htk_miss"` (no prox fallback).
- Prox mode at all three CPA bands matches current behavior (identical damage values).
- `launcher.fire(..., engagement_mode='htk')` on a CIWS launcher raises `ValueError` (illegal mode for that spec).
- `launcher.fire(..., engagement_mode=None)` on a dual-mode interceptor uses `'prox'` default.
- `launcher.fire(..., engagement_mode='htk')` on a dual-mode interceptor constructs an Interceptor instance with `engagement_mode='htk'`.
- Snapshot (if there's a to_dict or similar) includes the mode for debugging.

**Regression verification:**

Rerun every existing test. The full list: `test_balance.py`, `test_balance_baseline.py`, `test_ballistic.py`, `test_ballistic_cep.py`, `test_damage_debug.py`, `test_full_scenario.py`, `test_hgv_impact.py`, `test_match_phase.py`, `test_match_phase_integration.py`, `test_pn.py`, `test_threat_impact.py`. All must pass with behavior-identical numbers to before Subtask B (the flyover-fix shift from Subtask A is already baked in at this point — don't confuse it with mode-related drift).

**Commit:** `feat(game-core): engagement_mode infrastructure (htk | prox) — default preserves current behavior`

Push to origin.

**STOP conditions:**
- Any existing test shows behavior-drift in the 'prox' default path → STOP; something is off in the prox branch refactor.
- Circular import or dataclass migration headache → STOP, report; the infra change should be surgical.
- Unit test for HTK branch fails twice after a fix attempt → STOP, report.

## Subtask C — Baseline rerun + optional budget tune (30–45 min)

**Intent:** capture post-Subtask-A+B balance numbers, then decide whether a Blue budget bump is needed. The rule (operator 2026-04-19): target Blue win rate in 30–55% band across the 20-match `test_balance.py` sweep. If Subtask A (flyover fix) alone got us into or near the band, do not tune budget. If rate < 30%, bump budget by ≤ 20% and rerun once. If rate > 55%, leave budget alone and note (Blue stronger is a good problem).

**Method:**

1. Rerun `python team-missile-intercept/backend/test_balance.py` — capture the 20-match Blue/Draw/Red split. (Subtask A already ran this; this is the clean post-B rerun with no expected behavior change from B.)
2. Rerun `python team-missile-intercept/backend/test_balance_baseline.py` (the 1800 s full-scenario variant) — produces `backend/balance_baseline_<today>.json`. Write as a NEW file `balance_baseline_2026-04-20.json` (don't overwrite the W3 baseline — keep both for diffing).
3. Decide based on the test_balance.py rate:
   - **Rate ∈ [30%, 55%]** → no budget change. Commit the new baseline + a short note.
   - **Rate < 30%** → bump `world.blue_budget` (find it in `config.py` under the "Milestone I: win conditions + economy" section) by 20% once. Rerun `test_balance.py` once. Commit with old and new budget values + old and new win rates in the commit body.
   - **Rate > 55%** → no change; note in commit body that Blue is over target.
4. Update `backend/BALANCE_BASELINE_README.md` with a short "2026-04-20 entry" paragraph: what changed (flyover broad fix + engagement_mode infra), what the new Blue win rate is, and (if budget changed) what the budget tune was. Keep it < 30 lines added.

**Commit:** `balance(game-core): post-W5 baseline + blue_budget tune (if any)`

Body should include:
- W3 baseline Blue/Draw/Red: (from the committed `balance_baseline_2026-04-19.json` or the W3 summary table)
- Post-A Blue/Draw/Red: (captured in Subtask A commit body — reproduce for clarity)
- Post-B Blue/Draw/Red: (this subtask)
- Budget before / after (if changed)
- Total Blue win rate delta: `N% → M%`

Push to origin.

**STOP conditions:**
- After at most one budget bump attempt, Blue win rate is still way below 30% (< 15%) → STOP, report; deeper tuning is out of scope for W5.
- test_balance.py hangs or exceeds 5 min wall-clock → STOP, report (shouldn't happen — W3 reported 35.6 s for the full_match scenario).

## Subtask D — Docs: design note for Oskar + ISSUES + STATUS (20–30 min)

1. **New design doc** `team-missile-intercept/game-core/ENGAGEMENT_MODE_DESIGN.md` (~40–80 lines). Content:
   - What `engagement_mode` is and why it exists
   - The two modes' semantics (prox = current auto direct+prox behavior; htk = direct-or-miss, 2× damage_direct)
   - When HTK is worth choosing (CPA < radius_direct, typically requires Blue AI that can predict + lead precisely)
   - When prox is safer (general case; typical PN CPA 20–80 m means prox fallback is where most hits land)
   - How to call from Blue AI: `launcher.fire(..., engagement_mode='htk')` to explicitly choose; default preserves current behavior
   - Per-spec mode-choice table (the 6 interceptor types, their `engagement_mode_choices`, their `default_engagement_mode`)
   - Short note: this is infrastructure only in W5; no caller uses HTK in W5. Future Blue AI (Oskar) or balance worker decides when HTK pays off.
   - Forward-compatibility note: future Red AI may gain a similar mode field (e.g. HGV kinetic-impactor mode), but that is out of scope.
2. **Update `team-missile-intercept/game-core/ISSUES_2026-04-19.md`:**
   - Issue #2 (HGV airburst): append one-line note: "Broad flyover rule extended to ballistic/cruise/drone in W5 (M-TIER2.5)."
   - Append new entry to "Tier execution order" under Tier 2: `4. **M-TIER2.5-BALANCE:** broad flyover rule + engagement_mode infra + post-W5 balance baseline. Landed 2026-04-19.` Renumber following items accordingly (Milestone J Part 1 becomes the next Tier 2 item).
   - In the "Cross-team coordination" table, add a row: "engagement_mode consumer (Oskar Blue AI)" — primary Oskar, collaborator Chen.
3. **Update `team-missile-intercept/progress/STATUS.md`:** short "M-TIER2.5 landed" entry with the commit range (4 commits from Subtask A onwards) and the new Blue win rate.
4. **Update `team-missile-intercept/game-core/CHEN_BACKLOG.md`** if relevant — check whether any backlog items map to W5. Minimal edit OK.

**Commit:** `docs: W5 engagement_mode design + ISSUES / STATUS / backlog update`

Push to origin.

# Non-goals / guardrails

- **Do NOT set `default_engagement_mode='htk'` on any interceptor.** Default is `'prox'` everywhere (except pac_3 which is HTK-only by physics — `choices=('htk',)`, `default='htk'`). This is explicit operator decision: infrastructure only, no demo-saving buff.
- **Do NOT change any existing `damage_direct` / `damage_prox` / `radius_direct` / `radius_prox` spec value.** These are Emil's (math-validation) judgment values; changing them requires his sign-off. HTK's 2× multiplier is applied at resolution time in the code, not baked into specs.
- **Do NOT touch `kill_radius` values.** Same reason.
- **Do NOT change Blue AI firing logic or PRIMARY_RULES / FALLBACK_RULES.** Oskar owns that package.
- **Do NOT change Red AI or wave structure.** Boyu owns that.
- **Do NOT touch physics (integrator, drag, PN gain, MAX_ACCEL, dt).** Route 3 (RK4) is a separate future item.
- **Do NOT touch frontend files.** W5 is pure backend + tests + docs.
- **Do NOT add `target_site_id` to Threat or the unified threat-control contract.** That's Tier 3 (Issue #10); coordinate with Boyu when it's time.
- **Do NOT touch `Scenario.winner` or `requires_ground_impact` logic in `world.py`.** Subtask A only flips the `ThreatSpec` flag values; the detector code is already correct.
- **Do NOT rename existing `hit_kind` event strings in prox mode.** Frontend may be reading them. New strings (`htk_direct`, `htk_miss`) only emerge in htk mode (which no caller uses in this worker).
- **Do NOT commit the W3 baseline file** (`balance_baseline_2026-04-19.json`). Leave it intact; add a new dated file.
- **No `--no-verify`, no `git amend`, no force-push.**
- **Never commit API keys.**
- **English only** in commits, code, comments, docs.

# Hard rules

- One commit per subtask. Four subtasks → four commits.
- Push each commit immediately after local tests pass: `git push origin HEAD:new-teamwork-split-V1`.
- Each commit message ends with a Co-Authored-By line matching project convention.
- If any subtask hits a STOP condition, stop the entire worker session immediately and write the final summary with what landed and what is outstanding.
- Budget: ~2–4 hours. If exceeded or context fills, stop gracefully.

# Post-flight

1. `git status` — must be clean.
2. `git log --oneline -10` — confirm 4 new commits above `c42c740` (Worker 4 tip).
3. `git push origin HEAD:new-teamwork-split-V1` — idempotent sanity push.
4. If you stashed at pre-flight, `git stash pop`.

# Deliverable — final summary (≤ 400 words)

Write it back to the user (Chen) with this structure:

1. **Commits landed** (4 hashes + one-line each).
2. **Subtask A (flyover)** — which specs flipped, old vs new `test_balance.py` leak counts per threat kind.
3. **Subtask B (engagement_mode)** — what the mechanism looks like (file list + new fields), unit test coverage summary, confirmation that all existing tests still pass with behavior-identical prox numbers.
4. **Subtask C (baseline + budget)** — W3 vs post-W5 Blue/Draw/Red, whether budget was tuned, new balance_baseline JSON path.
5. **Subtask D (docs)** — where the Oskar-facing design doc lives, which ISSUES entries updated.
6. **Anything surprising** — tests that needed updating beyond expected, hidden couplings, unexpected balance swings.
7. **Next-worker handoff notes** — the Milestone J Part 1 worker and (later) the Oskar Blue AI worker both need to know what's here. Flag anything about SETUP phase, placement contract, or engagement_mode API that future workers should be aware of.
