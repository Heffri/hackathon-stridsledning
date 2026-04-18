# Known Doc Runtime Drift

This file logs the highest-impact mismatches surfaced while reviewing the new
ownership packages against the current runtime.

Use this as a warning list, not as a replacement for code review.

## Handling Rule

- Session 0 docs in `common-info/` still win for structure, ownership, and
  runtime-safety rules.
- For live behavior, current runtime code under `backend/` and `frontend/`
  wins over older prose unless a Session 0 doc explicitly says otherwise.

## High-Impact Runtime Drift

| Topic | Runtime truth | Drifted docs | Why it matters |
| --- | --- | --- | --- |
| Site HP baseline | `backend/sim/config.py` sets `SITE_HP_START = 100` | `progress/STATUS.md` repeats `60 HP` in Milestone I sections | Balance discussion and win-rate interpretation can be based on the wrong baseline. |
| HGV default behavior | `backend/sim/entities.py` now uses straight-line default HGV flight plus one-tick `Threat.override_maneuver(...)` commands | `progress/ROADMAP.md` still includes a manual check for visible HGV jink and still describes current HGV behavior as a pre-scripted evasion pattern in Route 6 | AI and verification work can target behavior that no longer exists. |
| HGV and ballistic envelope | Runtime uses ballistic `4459 m/s`, HGV `5831 m/s`, HGV `max_g = 10`, and `_HGV_BLEED_RATE = 120` | `WEAPON_SPECS.md` and older prose still describe about `2000 m/s`, `1700 m/s`, `8 G`, and about `50 m/s/s` bleed | Math, AI, and balance work can reason from the wrong target envelope. |
| Proximity damage formula | `backend/sim/world.py` uses linear falloff plus a minimum of `1` damage once inside prox radius | `WEAPON_SPECS.md` and some comments describe quadratic falloff | Emil's audit and weapon expectations must use runtime code, not prose. |
| PAC-3 and CIWS lethality tables | Runtime PAC-3 is heavily widened for playability (`damage_prox = 25`, `radius_direct = 60`, `radius_prox = 80`); runtime CIWS also has a very large prox radius (`80`) | `WEAPON_SPECS.md` still frames PAC-3 as almost pure hit-to-kill (`0.3 m`, `5 dmg` prox) and CIWS as a much smaller-radius weapon | The doc weapon story and actual gameplay lethality are materially different. |
| Launcher magazine counts | `backend/sim/launcher.py` gives PAC-3 launchers `4` ready rounds | `WEAPON_SPECS.md` says PAC-3 launchers have `12` | Ammo planning and cost reasoning can drift from what the demo actually supports. |
| Blue urgency model | `backend/sim/blue_ai.py` still computes time-to-impact relative to `BLUE_BASE_POS` | Multi-site status prose and AI handoff expectations can sound more site-aware than current code | Oskar should treat site-aware urgency as open work, not done work. |
| Visual landmarks vs gameplay sites | The scene still renders `12` landmarks, but `backend/sim/sites.py` now exposes only `3` active targetable sites after the arena filter | Older Milestone G/H prose still talks about capital and broader city targeting as if those sites are still active | Map/model work must not assume visual landmarks and gameplay targets are the same set. |
| Speed control surface | `backend/server.py` accepts `0.1x` through `20.0x`; the frontend slider in `frontend/index.html` exposes only `0.5x` through `5.0x` | Operator-facing expectations and UI affordances do not match | This is a real game-core/UI contract gap, already reflected in `game-core/CHEN_BACKLOG.md`. |

## Doc-Only Navigation Drift

| Topic | Current state | Why it matters |
| --- | --- | --- |
| ROADMAP closed routes | The top of `progress/ROADMAP.md` correctly marks Route 2 and Route 7 as closed, but later sections still contain those routes as if they were pending workstreams | A teammate can accidentally pick already-completed work if they jump into the middle of the file. |
| STATUS header metadata | `progress/STATUS.md` still pins an older latest commit while the live workspace head has moved on | Treat the header as historical context, not as a reliable live workspace marker. |

## What To Do When You Hit One Of These

- If the issue is structural, update the relevant `common-info/` Session 0
  document first or in the same session.
- If the issue is runtime behavior, verify in code before changing docs.
- If the issue is only historical prose, update the narrative docs after the
  runtime meaning is clear.
