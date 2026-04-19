# Known Doc Runtime Drift

This file logs the highest-impact mismatches surfaced while reviewing the new
ownership packages against the current runtime.

Use this as a warning list, not as a replacement for code review.

## Handling Rule

- Session 0 docs in `common-info/` still win for structure, ownership, and
  runtime-safety rules.
- For live behavior, current runtime code under `backend/` and `frontend/`
  wins over older prose unless a Session 0 doc explicitly says otherwise.

## Still-Open Runtime Drift

| Topic | Runtime truth | Drifted docs | Why it matters |
| --- | --- | --- | --- |
| HGV default behavior | `backend/sim/entities.py` now uses straight-line default HGV flight plus one-tick `Threat.override_maneuver(...)` commands | `progress/ROADMAP.md` Route 6 still describes current HGV behavior as a pre-scripted evasion pattern | AI and verification work can target behavior that no longer exists. |
| PAC-3 and CIWS lethality tables | Runtime PAC-3 is heavily widened for playability (`damage_prox = 25`, `radius_direct = 60`, `radius_prox = 80`); runtime CIWS also has a very large prox radius (`80`) | `WEAPON_SPECS.md` still frames PAC-3 as almost pure hit-to-kill (`0.3 m`, `5 dmg` prox) and CIWS as a much smaller-radius weapon in its lethality table | The doc weapon story and actual gameplay lethality are materially different. **Left open** because the right fix is Emil's math-validation decision, not a blind doc rewrite. |
| Launcher magazine counts | `backend/sim/launcher.py` gives PAC-3 launchers `4` ready rounds | `WEAPON_SPECS.md` says PAC-3 launchers have `12` | Ammo planning and cost reasoning can drift from what the demo actually supports. |
| Blue urgency model | `backend/sim/blue_ai.py` still computes time-to-impact relative to `BLUE_BASE_POS` | Multi-site status prose and AI handoff expectations can sound more site-aware than current code | Oskar should treat site-aware urgency as open work, not done work. |
| Visual landmarks vs gameplay sites | The scene still renders `12` landmarks, but `backend/sim/sites.py` now exposes only `3` active targetable sites after the arena filter | Older Milestone G/H prose still talks about capital and broader city targeting as if those sites are still active | Map/model work must not assume visual landmarks and gameplay targets are the same set. |
| Speed control surface | `backend/server.py` accepts `0.1x` through `20.0x`; the frontend slider in `frontend/index.html` exposes only `0.5x` through `5.0x` | Operator-facing expectations and UI affordances do not match | This is a real game-core/UI contract gap, already reflected in `game-core/CHEN_BACKLOG.md`. |

## Resolved In The 2026-04-19 Doc Cleanup

These items were reconciled by rewriting the prose to match the runtime.
The runtime was treated as authoritative; no code changed. If
`math-validation/` wants different numbers, it should raise the change
against the runtime, not the prose.

| Topic | How it was reconciled |
| --- | --- |
| Site HP baseline | `progress/STATUS.md` now says `100 HP` (was `60 HP`) and links to `config.SITE_HP_START`. |
| HGV / ballistic envelope speeds | `WEAPON_SPECS.md` and `GAME_DESIGN.md` now say ballistic `4,459 m/s (Mach 13)` and HGV `5,831 m/s (Mach 17)` (were `2,000 m/s` and `1,700 m/s`). |
| HGV speed-bleed formula | `WEAPON_SPECS.md` and `GAME_DESIGN.md` now quote the runtime form `_HGV_BLEED_RATE * (G_applied / max_G)²` with `120 m/s/s at max G` (was `~50 m/s/s`). |
| Proximity damage formula | `WEAPON_SPECS.md` now documents the runtime as linear falloff `max(1, damage_prox * (1 - dist / radius_prox))` and flags the math-validation choice for Emil. |
| STATUS.md commit-hash header | Updated to the current head and the Design-Docs table under "Resuming Work" no longer lists the three archived plans. |

## Doc-Only Navigation Drift

| Topic | Current state | Why it matters |
| --- | --- | --- |
| ROADMAP closed routes | The top of `progress/ROADMAP.md` correctly marks Route 2 and Route 7 as closed, but later sections still contain those routes as if they were pending workstreams | A teammate can accidentally pick already-completed work if they jump into the middle of the file. A clarifying banner was added to the affected sections in the 2026-04-19 pass. |

## What To Do When You Hit One Of These

- If the issue is structural, update the relevant `common-info/` Session 0
  document first or in the same session.
- If the issue is runtime behavior, verify in code before changing docs.
- If the issue is only historical prose, update the narrative docs after the
  runtime meaning is clear.
