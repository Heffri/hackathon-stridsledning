# Status — Demo Live ver 1.0 (post-Finale)

**Branch**: `current/demo-live-v1.0`
**Last updated**: 2026-04-28

This is the post-Finale shipping state. The project is no longer
under active development; this branch is the validated demo
configuration captured for archival.

## What's live

- 3D AI-vs-AI missile-intercept sandbox in the browser.
- Backend: Python 3.12 + FastAPI + WebSocket, ~30 Hz state stream.
- Frontend: Three.js scene, HUD with budget / site HP / magazine,
  drag-to-place launchers in SETUP, click-to-inspect on entities.
- Sim: 6 interceptor kinds (CIWS / RBS-70 / IRIS-T SLS / IRIS-T SLM
  / PAC-2 / PAC-3) and 4 threat kinds (drone / cruise_sub / ballistic
  / HGV) with proportional-navigation guidance, fuel-burn + coast
  physics, multi-site HP, per-side budget, win conditions.
- AI: rule-based Red and Blue baselines plus RL-trained policies
  loadable from the SETUP dropdown.

## Validated demo configuration

- **Layout**: C (selected by default in SETUP).
- **Budgets**: Red 150 M / Blue 200 M (default in SETUP).
- **Blue**: `RL CIWS Active (V4)` from
  `backend/rl/runs/blue_local/blue_reward_v4_finetune/` plus the
  Path 1 predictive-dispatch rule layer in
  `backend/rl/live_ai.py`.
- **Red**: `Scripted 3-Chain` (the rule baseline). The
  `Red Trainee v2` policy is also bundled and shows the
  bait-and-saturate emergent strategy described in the postmortems.

## Available models in the dropdown

Blue side (in `backend/rl/runs/blue_local/` unless noted):

- Heuristic — rule baseline in `backend/sim/blue_ai.py`
- RL v3 / v4 finetunes — early reward iterations
- RL CIWS Active (V4) — the validated demo Blue
- Boyu V2 / V2a — early curriculum-trained Blue
- Cap120 — capacity-bumped scratch run
- Megamodel + Megamodel S1–S4 — EPYC overnight curriculum
- S1 retrain (final + peak) — anti-PAC-spam reward retrain

Red side:

- Scripted 3-Chain — rule baseline
- Attrition Red — rule variant
- Red Trainee v2 — cost-aware + HGV evasion RL Red

## Known limitations

- **Distribution shift**: most RL Blue models were trained at
  Red 150M / Blue 200M / Layout C. Running them at the older
  120M / 100M defaults reproduces the PAC-spam regression. See
  `progress/V4_DISTRIBUTION_SHIFT_UPDATE_zh.md`.
- **Cross-match state leak**: `LearnedBlueAI` carries internal
  state (`_assignments`, `_tick_counter`) across matches. First
  match clean, second match degrades. ~10 line fix in
  `live_ai.py` if this is ever picked back up.
- **WebSocket race under rapid model switching**: the legacy
  `websockets` library can hit a keepalive assertion when the
  AI model is hot-swapped mid-match. Workaround: configure once,
  don't switch mid-match.
- **PN precision**: still Euler 0.05 s — CPA on ballistic /
  HGV is in the 20–80 m range. PAC-3 `radius_direct=60 m` is
  the in-game compensation.
- **No radar / sensor model** — Blue AI has omniscient
  detection.

## Where the writing is

- `progress/BIG_MODELS_POSTMORTEM_en.md` / `_zh.md` — why the
  bigger Blue models regressed into PAC-spam.
- `progress/V4_DISTRIBUTION_SHIFT_UPDATE_zh.md` — the real
  root cause: training-vs-deployment distribution mismatch.
- `backend/SETUP.md` — installation, gotchas, retrain
  command-line.
- `backend/rl/README.md` — RL env / training overview.
- `GAME_DESIGN.md` and `WEAPON_SPECS.md` — gameplay reference.

## Run

```bash
cd team-missile-intercept/backend
pip install -r requirements.txt    # see SETUP.md for the numpy 1.26.4 pin
python server.py
# open http://127.0.0.1:5174/
```
