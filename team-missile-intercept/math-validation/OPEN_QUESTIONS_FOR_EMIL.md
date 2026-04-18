# Open Questions For Emil

These are the questions that looked too important to bury inside the checklists. Each one is a concrete sign-off decision.

| Priority | Question | Why it matters | Main files to inspect |
| --- | --- | --- | --- |
| High | Which values are canonical when runtime and docs disagree? | Several core balance and physics numbers differ across `types.py`, `config.py`, `WEAPON_SPECS.md`, and `STATUS.md`. Without a canonical source, every later tuning pass risks chasing the wrong target. | `backend/sim/types.py`, `backend/sim/config.py`, `WEAPON_SPECS.md`, `progress/STATUS.md` |
| High | Should proximity damage be quadratic as documented, or linear as currently implemented? | This directly changes lethality, shot count, and balance conclusions. | `backend/sim/world.py`, `WEAPON_SPECS.md` |
| High | Is PAC-3 supposed to be made viable by better guidance, or by enlarged hit geometry and prox damage? | Right now runtime PAC-3 values are much more forgiving than the reference spec, which changes both realism and budget efficiency. | `backend/sim/types.py`, `backend/test_pn.py`, `backend/test_ballistic.py`, `WEAPON_SPECS.md` |
| High | Is current site HP `100` intentional, or should the game still be calibrated around the older `60 HP` story? | This changes how many leaks are needed for a Red win and changes how `test_balance.py` results should be interpreted. | `backend/sim/config.py`, `backend/sim/scenarios.py`, `progress/STATUS.md` |
| High | Is HGV really a `10 G` target with `120 m/s/s` max-bleed, or should Emil sign off on the lower doc values instead? | This is one of the biggest active realism-vs-gameplay mismatches in the repo. | `backend/sim/types.py`, `backend/sim/entities.py`, `WEAPON_SPECS.md`, `progress/STATUS.md` |
| Medium | Should a threat count as a site hit as soon as it overflies the site within `1500 m` horizontally, even at altitude? | Current leak detection is a defended-area rule, not a strict impact rule. That may be correct, but it should be intentional. | `backend/sim/config.py`, `backend/sim/world.py` |
| Medium | Should Blue AI urgency still be measured against Main Base, or against the actual targeted site? | Base-centered urgency can distort fallback and last-resort behavior in a multi-site scenario. | `backend/sim/blue_ai.py`, `backend/sim/sites.py` |
| Medium | Is PAC-3 launcher capacity really `4` in the active game, or should it be `12` as the reference doc says? | This strongly affects budget pressure and the ability to survive ballistic/HGV waves. | `backend/sim/launcher.py`, `WEAPON_SPECS.md` |
| Medium | Are only 3 in-arena active sites acceptable for the current demo, or should the map transform / site filter be revisited? | Red target weighting and overall balance depend on how many sites are actually alive in runtime. | `backend/sim/sites.py`, `backend/sim/red_ai.py`, `progress/STATUS.md` |
| Medium | Is drone speed `120 m/s` in runtime a deliberate gameplay choice, or should it be closer to the `45 m/s` reference value? | Drone time-on-map, CIWS pressure, and budget use all depend on this. | `backend/sim/types.py`, `WEAPON_SPECS.md` |
| Medium | Should `test_ballistic.py` be treated as an acceptance test, or only as a smoke test? | It currently reports a range-based "intercept" without using the live world's CPA-plus-damage logic. | `backend/test_ballistic.py`, `backend/sim/world.py` |
| Low | Does `config.AIR_DENSITY` need to be wired into active formulas, or is it intentionally documentary only? | If it is dead documentation, future readers may assume more atmospheric fidelity than the sim actually uses. | `backend/sim/config.py`, `backend/sim/physics.py` |

## Specific Mismatches To Resolve Explicitly

These should not stay as silent drift:

- `SITE_HP_START`
  - Runtime: `100`
  - Recent status write-up: `60`

- HGV maneuver assumptions
  - Runtime: `max_g = 10`, `_HGV_BLEED_RATE = 120`
  - Reference docs/comments elsewhere: closer to `8 G`, about `50 m/s/s`

- Strategic threat speeds
  - Runtime ballistic: `4459 m/s`
  - Runtime HGV: `5831 m/s`
  - `WEAPON_SPECS.md` lists much lower values

- PAC-3 lethality geometry
  - Runtime direct radius: `60 m`
  - Runtime prox damage: `25`
  - Reference doc direct radius: `0.3 m`
  - Reference doc prox damage: `5`

- PAC-3 launcher ammo
  - Runtime magazine: `4`
  - Reference doc/example: `12`

## What Emil Should Hand Back To The Team

The most useful output is not a long essay. It is a short sign-off note with:

- a yes/no on each high-priority question
- a single canonical value set to use going forward
- a short list of "acceptable approximation" items
- a short list of "must fix before next serious balance pass" items
