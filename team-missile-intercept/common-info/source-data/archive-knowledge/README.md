# archive-knowledge

Reference notes that originally belonged to a separate side project,
**`xingyi-rts/` — Xingyi's Personal Project**: an RTS-style air-defense
decision-support concept with a full IADS simulation, a 3-layer response
model (EW → evade → hard-kill), multi-wave scenarios, and a complete
Swedish air-defense knowledge base.

That side project was killed before the hackathon focused on the
team's missile-intercept sandbox. The bulk of its knowledge base
was either superseded or rolled into the active reference notes
under [`../knowledge/`](../knowledge/) (canonical, used by the
shipped sim).

This folder keeps the leftover files that were **not** part of
the active sync — they describe ideas the team-missile-intercept
sim did not end up using, but they are preserved here as
reference because parts may be reused if the project is ever
picked back up.

## Files

- [`data-model.md`](data-model.md) — abstract parameterized data
  model (Asset / Threat / Sensor entities) for an IADS-style
  decision-support layer. The shipped sim uses a simpler
  `Threat` / `Interceptor` / `Site` shape in
  `backend/sim/types.py`; this richer model was for the
  RTS-style concept.
- [`doctrine.md`](doctrine.md) — Swedish air-defense doctrine
  notes (layered defense, cost-exchange rules, engagement
  priority matrix, EW vs hard-kill response selection,
  multi-wave saturation handling). The shipped sim encodes a
  thinner version of this in `backend/sim/blue_ai.py` and the
  Blue RL reward shaping; the rest is unused.

## Active reference

The actively-used knowledge base for the shipped sim lives in
[`../knowledge/`](../knowledge/) and covers air assets, ground
defense, threats, sensors / C2, the scenario, and source
citations.
