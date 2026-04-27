# Running Team Missile Intercept

Preferred Windows launcher from the repo root:

```powershell
.\run-team-missile-intercept.ps1
```

What the launcher does:

- starts `team-missile-intercept/backend/server.py`
- opens the demo at `http://127.0.0.1:5174/` once the server is up

If dependencies are missing or the dropdown silently falls back
to the heuristic Blue, see the install checklist:

- `team-missile-intercept/backend/SETUP.md`

Manual run path:

```powershell
cd team-missile-intercept\backend
pip install -r requirements.txt
python server.py
```

For project state and known limitations:

- `team-missile-intercept/progress/STATUS.md`
