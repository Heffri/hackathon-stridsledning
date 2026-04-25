# Smart Stridsledning - Saab Hackathon 2026

> Saab + KTH Hackathon | Organized by 2Hero | Hack Day: April 25, 2026

---

## 🚀 Hack Day Final-Demo Quickstart (`final-demo` branch)

This branch ships the Hack Day demo package — bundled trained models +
all balance / safety-net polish + supporting eval data.

### Prerequisites

- Windows + PowerShell
- Python 3.12 + repo deps installed (see
  [`team-missile-intercept/backend/requirements.txt`](team-missile-intercept/backend/requirements.txt))
- Browser (Chrome) for the demo frontend

### Startup A — Live demo (Blue learned policy + Path C vs scripted Red) ⭐

The primary 4-minute demo. Trained Blue (`blue_aoe_aggressive_B_shaped`,
~3.3 M cumulative PPO steps with B-path reward shaping) plus
`live_ai.py`'s Path C `_force_strategic_fallback` rule-layer safety net
guaranteeing PAC-3 / PAC-2 dispatch on ballistic / HGV. Red is the
scripted 3-chain doctrine.

```powershell
cd .claude\worktrees\cool-golick-1340ba\team-missile-intercept\backend
$env:RED_WAVE_MODE = "scripted"
$env:BLUE_POLICY_PATH = "$pwd\rl\runs\blue_local\blue_aoe_aggressive_B_shaped\model.zip"
Remove-Item Env:RED_POLICY_PATH -ErrorAction SilentlyContinue
python server.py
```

Browser: `http://127.0.0.1:5174`

In SETUP phase before clicking Start:
1. **Budget panel**: set Red `110_000_000`, Blue `200_000_000`
   (defaults are 100M / 120M — too tight for this demo)
2. **Layout**: D (full 6-launcher firing including SLM + PAC-3) or
   C (slightly safer, no SLM but sites hold cleaner)
3. **Apply Layout** → **Start Match**
4. Speed slider 10-20× for detail, 50× to fast-forward quiet stretches

### Startup B — Legacy AI vs AI (judges who want to see the old self-play pair)

The 2026-04-21 self-play snapshot: trained Red AI vs trained Blue AI on
the original 250 km arena balance.

```powershell
cd .claude\worktrees\cool-golick-1340ba\team-missile-intercept\backend
Remove-Item Env:RED_WAVE_MODE -ErrorAction SilentlyContinue
$env:BLUE_POLICY_PATH = "$pwd\rl\models\blue_ai_1m_2xpenalty\model.zip"
$env:RED_POLICY_PATH  = "$pwd\rl\runs\red_20260421_234425\model.zip"
python server.py
```

Browser same URL. Layout doesn't matter much — both AIs adapt.

### Switching between A and B

`Ctrl+C` to stop the current `server.py`, change env vars per the
target startup, run `python server.py` again. The frontend will
auto-reconnect on browser refresh.

### Bundled models

| Model | Path | Use |
|---|---|---|
| Blue (B-path retrained) | `rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip` | Startup A — current demo Blue |
| Blue (legacy) | `rl/models/blue_ai_1m_2xpenalty/model.zip` | Startup B — legacy AI-vs-AI Blue |
| Red (legacy) | `rl/runs/red_20260421_234425/model.zip` | Startup B — legacy AI-vs-AI Red |

### Demo storyline (4 min)

1. Open Layout D + Startup A. Speed 50×.
2. **First 30 s real-time** (~ 1500 s sim): drones cruise south, CIWS
   and RBS-70 light up; mid-range threats engaged by IRIS-T SLS / SLM.
3. **30-50 s real-time** (~ 1500-2500 s sim): ScriptedRed transitions
   to ballistic + HGV; PAC-3 launches (Path C dispatch when policy
   doesn't fire); ballistic kills look like flak rings.
4. **50-90 s real-time** (~ 2500-4500 s sim): mop-up phase, Red drains
   leftover budget on drone harassment; Blue defends; match resolves
   to "BLUE WINS" once the last threat lands or is intercepted.

### Eval evidence (in this branch)

- `team-missile-intercept/backend/blue_aoe_A_redBudget110_eval.md`
- `team-missile-intercept/backend/blue_aoe_A_redBudget110_long_eval.md`
- `team-missile-intercept/backend/blue_aoe_B_full_eval.md`
- `team-missile-intercept/progress/OVERNIGHT_REPORT_2026-04-25.md`
  (full Hack-Day-eve autonomous run summary)

---

## Mainline Project

[`team-missile-intercept/`](team-missile-intercept/) is the active team
project and the mainline working area for this repository.

It is a 3D AI-vs-AI missile interception demo where Red AI launches threats
and Blue AI selects interceptors using real-time physics-based intercept
math.

## Where Teammates Should Start

- Repo onboarding:
  [`team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`](team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md)
- Common navigation hub:
  [`team-missile-intercept/common-info/`](team-missile-intercept/common-info/)
- Current status:
  [`team-missile-intercept/progress/STATUS.md`](team-missile-intercept/progress/STATUS.md)
- Roadmap:
  [`team-missile-intercept/progress/ROADMAP.md`](team-missile-intercept/progress/ROADMAP.md)

## Run The Active Demo

Windows launcher from the repo root:

```powershell
.\run-team-missile-intercept.ps1
```

Short running note:

- [`RUNNING_TEAM_MISSILE_INTERCEPT.md`](RUNNING_TEAM_MISSILE_INTERCEPT.md)

## Active Source Data

Canonical active source data lives under
[`team-missile-intercept/common-info/source-data/`](team-missile-intercept/common-info/source-data/).

Use these documents to understand the current cutover and archive state:

- [`ACTIVE_SOURCE_DATA_INDEX.md`](team-missile-intercept/common-info/ACTIVE_SOURCE_DATA_INDEX.md)
- [`ARCHIVE_POLICY.md`](team-missile-intercept/common-info/ARCHIVE_POLICY.md)
- [`DEPENDENCY_CUTOVER_REPORT.md`](team-missile-intercept/common-info/DEPENDENCY_CUTOVER_REPORT.md)

## Archived Legacy Material

The archived legacy tree now lives at
[`team-missile-intercept/archive/xingyi-rts/`](team-missile-intercept/archive/xingyi-rts/).

It is kept for provenance and historical traceability only. It is not an
active working project, not the onboarding path for teammates, and not the
canonical home for active source data.
