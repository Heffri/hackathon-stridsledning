# Engagement Mode Design (M-TIER2.5)

## Purpose

`engagement_mode` is a per-shot enum field on every `Interceptor`
instance, carried end-to-end from launch decision to damage
resolution. It lets a caller (today: BlueAI; future: Oskar's learned
Blue AI or a placement-aware planner) declare **how** a given
interceptor should engage the incoming threat, without touching any
spec damage / radius value.

The infrastructure landed in M-TIER2.5 (commit `960d041`). **No
caller opts into the non-default mode yet** — this is scaffolding
for the next Blue AI worker (Oskar) plus any future balance pass
that wants to experiment with HTK-style engagement selection.

## The two modes

- **`prox`** — current auto direct-then-prox falloff, unchanged
  bit-for-bit from pre-M-TIER2.5:
  - CPA < `radius_direct` → `damage_direct` (event `hit_kind="direct"`)
  - CPA < `radius_prox`   → `damage_prox × (1 − d/radius_prox)` with
    a minimum of 1 damage; event `hit_kind="prox"`
  - CPA ≥ `radius_prox`   → 0 damage; event `hit_kind="miss"`

- **`htk`** (hit-to-kill) — direct-or-miss, no fallback:
  - CPA < `radius_direct` → `damage_direct × 2`, event
    `hit_kind="htk_direct"`
  - CPA ≥ `radius_direct` → 0 damage; event `hit_kind="htk_miss"`

Semantics live in `backend/sim/world.py::resolve_damage(spec, mode,
d_min)`. Existing event strings (`direct` / `prox` / `miss`) are
preserved in `prox` mode for frontend / test compatibility; the two
new strings (`htk_direct` / `htk_miss`) only appear when HTK fires.

## When to pick HTK

HTK pays off when the shooter is confident the CPA will land inside
`radius_direct`. In that regime, doubling the direct-hit damage is
the correct call — the shot one-shots harder targets (ballistic hp
80, HGV hp 60) without "wasting" the prox-fuse falloff that HTK
gives up.

Current Euler-0.05 s PN guidance typically produces CPA in the
20–80 m range. So HTK is naturally useful for interceptors whose
`radius_direct` is wider than that drift (pac_3 at 60 m) and
uninteresting for interceptors where `radius_direct` is 1–3 m
(SHORT_SAM / SLS / SLM / pac_2 all have 1–3 m) — those would almost
always miss in HTK mode given typical PN error.

A future Blue AI could still pick HTK on a dual-mode interceptor
when:

1. It has a cheaper `prox` shot available for the *next* layer of
   saturation, and
2. Miss/hit is acceptable — i.e. this shot is a "bonus HTK attempt"
   rather than the last-chance intercept.

## When to pick prox

The safe default. With Euler-0.05 s PN, most hits land in the
20–80 m band — far from `radius_direct` but well inside
`radius_prox` (100–180 m for SAMs). Prox mode converts that miss
distance into 6–25 damage instead of 0. The saturation ladder in
`blue_ai.py` stacks these to kill a hardened target across multiple
shots; HTK breaks that arithmetic.

**Rule of thumb:** if you do not have a specific reason to pick
HTK, let the default apply.

## Per-spec mode configuration

Declared in `backend/sim/types.py::INTERCEPTOR_SPECS`:

| Interceptor type | Mode choices     | Default | Rationale |
|------------------|------------------|---------|-----------|
| CIWS             | `('prox',)`      | `prox`  | Cannon rounds have no HTK concept. |
| SHORT_SAM        | `('prox','htk')` | `prox`  | Dual-mode. HTK opt-in. |
| IRIS_T_SLS       | `('prox','htk')` | `prox`  | Dual-mode. HTK opt-in. |
| MED_SAM          | `('prox','htk')` | `prox`  | Dual-mode. HTK opt-in. |
| LONG_SAM         | `('prox','htk')` | `prox`  | Dual-mode. HTK opt-in. |
| HIT_TO_KILL      | `('htk',)`       | `htk`   | pac_3 is physically HTK-only; no prox fuse. |

## Calling convention

```python
# spec default (current behaviour — no balance change):
lch.fire(t_now)
# → returns 'prox' for all SAMs, 'htk' for pac_3

# explicit mode (new; opt-in only):
resolved = lch.fire(t_now, engagement_mode='htk')
world.spawn_interceptor(kind, pos, dir, target_id,
                        engagement_mode=resolved)
```

`Launcher.fire` validates the mode against the spec's
`engagement_mode_choices` and raises `ValueError` before touching
ammo state. The resolved string must be passed to
`World.spawn_interceptor` so the `Interceptor` instance carries it
into damage resolution.

## Test coverage

`backend/test_engagement_mode.py` — 23 unit tests:

- Spec-level: CIWS prox-only, dual-mode quartet, pac_3 htk-only.
- `resolve_damage`: prox direct / prox band / min-1 falloff edge /
  miss, htk direct / htk miss at prox-band / htk miss wide;
  unknown-mode ValueError.
- `Launcher.fire`: default resolution, explicit prox + htk on
  dual-mode, ValueError on CIWS + htk, ValueError on pac_3 + prox,
  pac_3 default is htk, ammo not deducted on rejected fire.
- `Interceptor.__init__`: default from spec, explicit htk on
  dual-mode, ValueError on illegal mode.
- `World.spawn_interceptor`: plumbs engagement_mode through; default
  uses spec default.

## Forward compatibility

If a future Red AI wants a symmetric mode field on threats
(e.g. HGV kinetic-impactor vs airburst variants), the same
`choices / default` pattern can be mirrored on `ThreatSpec`. That is
out of scope for M-TIER2.5; no hooks have been added threat-side.

## Cross-team notes

- **Oskar (Blue AI)** — this is the primary consumer. When you
  replace the rule-based ladder in `blue_ai.py::_fire`, you can
  opt individual shots into HTK by passing `engagement_mode='htk'`
  to `launcher.fire` and threading the resolved string into
  `spawn_interceptor`. Nothing else in BlueAI changes.
- **Boyu (Red AI)** — no action. Threats are untouched.
- **Chen (game-core)** — this worker (M-TIER2.5) landed the
  infrastructure. Future balance passes decide when to make any
  SAM default to htk.
