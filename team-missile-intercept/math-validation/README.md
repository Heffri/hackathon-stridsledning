# Math Validation Package

This folder is Emil's documentation home for manually auditing the active simulation math, assumptions, and balance calibration.

Scope for this package:

- Documentation only
- No runtime code changes
- Current runtime behavior lives in `backend/sim/*.py`
- Design intent and historical calibration notes live in `WEAPON_SPECS.md`, `progress/STATUS.md`, and `progress/ROADMAP.md`

## Recommended Audit Order

1. Read `FILES_TO_CHECK.md` to see which files matter and why.
2. Work through `PHYSICS_CHECKLIST.md` with a calculator or spreadsheet.
3. Work through `BALANCE_CHECKLIST.md` without changing weapon unit prices.
4. Record decisions, disagreements, or missing acceptance thresholds in `OPEN_QUESTIONS_FOR_EMIL.md`.

## Ground Rules For Manual Audit

- Treat runtime code as the source of truth for "what the sim does now".
- Treat `WEAPON_SPECS.md` and `STATUS.md` as the source of truth for "what the team says it intends".
- When those disagree, do not silently average them. Flag the mismatch.
- Check units every time: meters, seconds, m/s, m/s^2, G, USD.
- Recompute at least one representative case by hand for each major formula.
- Separate "physically plausible" from "good for gameplay". A value can pass one test and fail the other.

## Highest Priority Flags Already Visible

- `backend/sim/world.py` uses a linear proximity-damage falloff, while `WEAPON_SPECS.md` documents a quadratic falloff.
- Several active runtime values differ from reference docs:
  - `SITE_HP_START` is `100` in `backend/sim/config.py`, but `progress/STATUS.md` repeatedly describes `60 HP`.
  - HGV bleed is `120 m/s/s` at max command in `backend/sim/entities.py`, while `WEAPON_SPECS.md` says the tunable expectation is about `50 m/s/s`.
  - HGV `max_g` is `10` in `backend/sim/types.py`, but some comments and docs describe `8 G`.
  - Ballistic speed is `4459 m/s` and HGV speed is `5831 m/s` in runtime, while `WEAPON_SPECS.md` lists much lower values.
  - PAC-3 direct/proximity parameters in runtime are much larger than the reference spec.
  - PAC-3 launcher magazine is `4` in `backend/sim/launcher.py`, while `WEAPON_SPECS.md` describes `12`.
- `backend/test_ballistic.py` is a useful smoke test, but it does not reproduce the live world's CPA-based damage resolution.
- `backend/sim/blue_ai.py` still estimates urgency against the Main Base for some decisions, even though Red actually targets multiple sites.

## Suggested Output From Emil

By the end of the audit, Emil should be able to give short written sign-off on:

- Which formulas are mathematically acceptable as-is
- Which values are deliberate gameplay approximations
- Which doc/code mismatches must be resolved before future tuning sessions
- What acceptance thresholds should be used for PN, CPA, HGV bleed, site HP, and starting budget
