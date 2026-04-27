# Team Missile Intercept

The active Saab hackathon entry on this branch
(`current/demo-live-v1.0`, post-Finale shipping snapshot).

A 3D AI-vs-AI missile-intercept sandbox: Red AI launches drones,
cruise missiles, ballistic missiles, and HGVs; Blue AI selects
interceptors and computes real-time intercept solutions. Both
sides have rule-based baselines plus RL-trained policies
(PPO / MaskablePPO via Stable-Baselines3) loadable from the
SETUP dropdown.

## Run

Preferred Windows launcher from the repo root:

```powershell
.\run-team-missile-intercept.ps1
```

Manual:

```powershell
cd backend
pip install -r requirements.txt
python server.py
```

Then open `http://127.0.0.1:5174/`. See
[`backend/SETUP.md`](backend/SETUP.md) for the install
checklist (especially the `numpy==1.26.4` pin) and common
gotchas.

## Layout

- `backend/sim/` — game core (physics, scenario, entities, sites,
  rule-based AIs, win conditions).
- `backend/rl/` — RL envs, training entries, live inference
  wrappers, trained model artifacts under `runs/`.
- `backend/server.py` — FastAPI + WebSocket runtime.
- `frontend/` — Three.js scene, HUD, drag-to-place launchers.
- `common-info/` — team-ownership spec + canonical source-data
  knowledge base.
- `progress/` — postmortems on what worked and what didn't.

## Reference docs

- [`GAME_DESIGN.md`](GAME_DESIGN.md) — gameplay mechanics and
  design rules.
- [`WEAPON_SPECS.md`](WEAPON_SPECS.md) — arsenal reference table.
- [`progress/STATUS.md`](progress/STATUS.md) — current ship
  state and known limitations.
