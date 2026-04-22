# live-demo quickstart

**Hack Day demo branch** — drop-in live-AI matches for Saab 2026 Smart
Stridsledning. Pull, set two env vars, run. You'll see the same browser
game you always get, except Red and/or Blue are driven by a trained
MaskablePPO policy instead of the rule-based AI.

## What this branch is

| Branch             | Purpose                                              |
| ------------------ | ---------------------------------------------------- |
| `main`             | Shipping game-core + rule-based AIs.                 |
| `rl-self-play-v1`  | RL training harness + cross-eval tools (headless).   |
| `red-ai`           | Boyu / Chen Red policy training runs.                |
| `blue-ai`          | Boyu Blue policy training runs.                      |
| **`live-demo`**    | **This one.** Policies + glue + bundled model.zips.  |

`live-demo` is the only branch where `python server.py` opens a browser
match driven by a learned Red / Blue. All 4 model.zips are committed
directly into this branch (~47 MB total) so `git checkout live-demo`
gives you everything you need — no extra fetches, no submodules.

## One-time setup

```powershell
cd <repo root>
git fetch origin
git checkout live-demo
git pull
cd team-missile-intercept/backend
pip install -r requirements.txt   # only if first-time clone
```

## Running a match

Every match is a plain `python server.py` invocation. Two env vars
(`RED_POLICY_PATH` and `BLUE_POLICY_PATH`) select which side is learned.
Unset → rule-based AI for that side. Either side can be learned
independently. Open `http://localhost:5174/` in Chrome, click `Start`.

### PowerShell

```powershell
# Rule vs rule (baseline — always works)
python server.py

# Learned Red vs rule Blue (Red2 aggressive spawner)
$env:RED_POLICY_PATH = "rl/runs/red_20260421_234425/model.zip"
python server.py

# Rule Red vs learned Blue (Blue1 — 2x leak penalty)
$env:BLUE_POLICY_PATH = "rl/models/blue_ai_1m_2xpenalty/model.zip"
python server.py

# Learned Red vs learned Blue (Red2 vs Blue1 — the Hack Day headline)
$env:RED_POLICY_PATH  = "rl/runs/red_20260421_234425/model.zip"
$env:BLUE_POLICY_PATH = "rl/models/blue_ai_1m_2xpenalty/model.zip"
python server.py

# Red2 vs Blue2 (1x penalty — more aggressive Blue, cheaper shots)
$env:RED_POLICY_PATH  = "rl/runs/red_20260421_234425/model.zip"
$env:BLUE_POLICY_PATH = "rl/models/blue_ai_1m_1xpenalty/model.zip"
python server.py
```

To unset a var in the same shell: `Remove-Item Env:\RED_POLICY_PATH`.

### cmd.exe

```cmd
REM Both learned
set RED_POLICY_PATH=rl\runs\red_20260421_234425\model.zip
set BLUE_POLICY_PATH=rl\models\blue_ai_1m_2xpenalty\model.zip
python server.py
```

Unset: `set RED_POLICY_PATH=` (empty).

### bash / git-bash

```bash
RED_POLICY_PATH=rl/runs/red_20260421_234425/model.zip \
BLUE_POLICY_PATH=rl/models/blue_ai_1m_2xpenalty/model.zip \
python server.py
```

## Policies shipped in this branch

| Policy | Path (from `backend/`)                             | Size | Notes                               |
| ------ | -------------------------------------------------- | ---- | ----------------------------------- |
| Red1   | `rl/runs/red_20260421_205051/model.zip`            | 9.6M | Earlier Red training run.           |
| Red2   | `rl/runs/red_20260421_234425/model.zip`            | 9.6M | Later Red run — preferred default.  |
| Blue1  | `rl/models/blue_ai_1m_2xpenalty/model.zip`         | 14M  | 1M steps, 2x leak penalty.          |
| Blue2  | `rl/models/blue_ai_1m_1xpenalty/model.zip`         | 14M  | 1M steps, 1x penalty (more eager).  |

Paths are relative to `team-missile-intercept/backend/` (the folder you
run `python server.py` from).

## Verifying it's actually learned

After `Start`, watch server stdout — on boot you should see:

```
[server] Loaded learned Red policy: rl/runs/red_20260421_234425/model.zip
[server] Loaded learned Blue policy: rl/models/blue_ai_1m_2xpenalty/model.zip
```

Those two lines are the only sign in the UI that policies are in use —
the frontend HUD renders the same game either way. If the lines are
missing, the env vars didn't make it to the process (common pitfall:
setting them in one shell and running `python server.py` in a different
one).

## Adding a new policy to live-demo

Whenever Boyu (or anyone) pushes a new model to `origin/red-ai` or
`origin/blue-ai`, you can bundle it into `live-demo` in one commit:

```bash
git fetch origin
# Extract the model.zip blob from the source branch into live-demo's tree
git checkout origin/blue-ai -- rl/models/<new_blue_dir>/model.zip
# (or for Red: origin/red-ai -- rl/runs/<new_red_dir>/model.zip)

git add rl/models/<new_blue_dir>/model.zip
git commit -m "assets(rl): add Blue3 to live-demo"
git push origin live-demo
```

**No code changes needed.** `server.py` reads the env var and passes
whatever path you give it to `rl.live_ai.LearnedBlueAI` (or
`LearnedRedAI`). Any MaskablePPO model trained with the current
`rl/env.py` / `rl/red_env.py` contracts loads transparently.

If the source branch's repo layout differs from `live-demo`'s (e.g. the
training branches are rooted at `backend/` without the
`team-missile-intercept/` prefix), use `git cat-file -p <blob-hash>` or
`git show <branch>:<path>` to extract the blob directly and write it to
the target path in `live-demo`.

## Troubleshooting

**Connection refused from browser.** Port 5174 binding. Override with
`PORT=6000 python server.py` (or `$env:PORT = "6000"`) and open
`http://localhost:6000/`.

**`numpy._core.numeric` ImportError on Blue model load.** Shouldn't
happen — `rl/live_ai.py` applies the numpy-core compat shim at import
time. If you see it anyway, verify the shim actually ran:
`python -c "import rl.live_ai; import sys; print('numpy._core.numeric' in sys.modules)"` should print `True`.

**Policy load takes ~1 s.** Expected. MaskablePPO cold-loads torch
weights + builds an inference graph. Happens once per match (init +
Restart). If you need faster restarts for demo pacing, avoid Restart
and just reset speed.

**Learned match resolves differently from rule match.** That's the
whole point.

## Files in this branch that differ from `rl-self-play-v1`

- `team-missile-intercept/backend/rl/live_ai.py` — wrapper classes.
- `team-missile-intercept/backend/server.py` — env-var dispatch.
- `team-missile-intercept/backend/rl/runs/red_*/model.zip` — 2 Red models.
- `team-missile-intercept/backend/rl/models/blue_ai_1m_*/model.zip` — 2 Blue models.
- `team-missile-intercept/LIVE_DEMO_QUICKSTART.md` — this file.

Everything else is identical to `rl-self-play-v1@bb5d403`.
