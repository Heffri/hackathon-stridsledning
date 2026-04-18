# Running Team Missile Intercept

The active demo in this repo is `team-missile-intercept/`.

Preferred Windows launch path from the repo root:

```powershell
.\run-team-missile-intercept.ps1
```

What the launcher does:

- starts `team-missile-intercept/backend/server.py` from the existing backend
  shell
- keeps `backend/` and `frontend/` in their current runnable locations
- opens the demo at `http://127.0.0.1:5174/` when the server is ready

If dependencies are missing, install them from:

```powershell
pip install -r team-missile-intercept\backend\requirements.txt
```

For project navigation and current state, read:

- `team-missile-intercept/common-info/README.md`
- `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
- `team-missile-intercept/progress/STATUS.md`
