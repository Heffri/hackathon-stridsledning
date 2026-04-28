# Smart Stridsledning — Saab Hackathon 2026

Top-5 finalist entry for the Saab + KTH 2026 university hackathon.
A browser-based AI-vs-AI missile-intercept sandbox: Python sim
backend (FastAPI / WebSocket) + Three.js 3D frontend +
RL-trained Blue / Red policies (PPO / MaskablePPO via
Stable-Baselines3).

This is a hackathon arcade-style game / decision-support sandbox.
All weapon names and stats are encyclopedia-level values used as
unit balance numbers.

## Run the demo

```bash
cd team-missile-intercept/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows; or `source .venv/bin/activate` on Linux/macOS
pip install --upgrade pip
pip install numpy==1.26.4         # MUST be 1.26.x, not 2.x
pip install -r requirements.txt
python server.py
```

Open `http://127.0.0.1:5174/` in Chrome. Click Start in SETUP phase.

The defaults (Layout C, Red 150M / Blue 200M, V4 Blue model,
Scripted Red) match the validated demo configuration. See
[`team-missile-intercept/backend/SETUP.md`](team-missile-intercept/backend/SETUP.md)
for the full setup checklist and common gotchas.

There is also a Windows launcher:

```powershell
.\run-team-missile-intercept.ps1
```

## What's in here

```
team-missile-intercept/
  backend/
    sim/             game core: physics, scenario, entities, sites,
                     red/blue rule AIs, win conditions, budget/HP
    rl/              RL envs (Blue + Red), training entries,
                     live inference wrappers, trained model artifacts
    server.py        FastAPI + WebSocket runtime
  frontend/          Three.js scene, HUD, drag-to-place launchers
  common-info/       team-ownership spec, runtime stability rules,
                     module spec, source-data knowledge base
  progress/          postmortems on what worked and what didn't
```

## Where to look first

If you want to understand the interesting parts of the project:

- **Sim engine and reward design**:
  [`team-missile-intercept/backend/rl/env.py`](team-missile-intercept/backend/rl/env.py)
  (observation / action / mask / reward), and
  [`team-missile-intercept/backend/sim/`](team-missile-intercept/backend/sim/)
  for the underlying game-core (scenarios, entities, world,
  win conditions, budget).
- **Postmortems** —
  [`team-missile-intercept/progress/`](team-missile-intercept/progress/)
  contains the writeups that have most of the actual learning value:
  - `BIG_MODELS_POSTMORTEM_en.md` / `_zh.md` — why the bigger Blue
    models (Boyu V2a / Cap120 / Megamodel) regressed into
    PAC-spam, and what the cheaper V4 + rule layer actually does.
  - `V4_DISTRIBUTION_SHIFT_UPDATE_zh.md` — the real root cause of
    the "PAC-spam" regression, found mid-Finale day:
    train / deploy distribution mismatch on layout + budget.
- **Module ownership and rules** —
  [`team-missile-intercept/common-info/`](team-missile-intercept/common-info/)
  for `TEAM_OWNERSHIP_SPEC.md`, `MODULARIZATION_SPEC.md`,
  `RUNTIME_STABILITY_RULES.md`.

## Authorship note

This is a 14-day, 5-person team project. Most of the runnable
code (~30k LOC) was produced by AI assistants (Claude Code) under
human direction, orchestrated across multiple async worker
sessions on local + rented EPYC hardware. The repo is preserved
as-is from the hackathon — Chinese / English mixed docs in
`progress/`, dated postmortems, and the trained-model artifacts
that ran in the live demo.

The team:

- Sebastijan Babic — team lead, maps + visual assets
- Boyu — Blue-side RL training
- Oskar — Blue-side rule logic
- Emil — math validation
- Xingyi Chen — game core, runtime integration, RL co-engineering
  during the Finale stretch

## Event info

- Hack Day: April 25, 2026, KTH Innovation
- Grand Finale: April 27, 2026
- This branch (`current/demo-live-v1.0`) is the validated post-Finale
  demo configuration.
- Older state lives on the archive branches (`archive/V1-knowledge-base`,
  `archive/V2-new-teamwork-split`, `archive/V2.5-live-demo`,
  `archive/V3-final-demo`, `archive/blue-training`,
  `archive/red-training`, `archive/experiments`).
