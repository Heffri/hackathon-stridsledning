# Team Missile Intercept

`team-missile-intercept/` is the active Saab hackathon demo in this
repository.

It is a 3D AI-vs-AI missile interception scenario where Red launches drones,
cruise missiles, ballistic missiles, and HGVs while Blue selects
interceptors and computes real-time intercept solutions.

## Start Here

Read in this order:

1. `common-info/REPO_ONBOARDING_NOTES.md`
2. `common-info/README.md`
3. `progress/STATUS.md`
4. `progress/ROADMAP.md`

`common-info/` is the navigation hub for structure, ownership, archive
policy, and canonical source-data records.

## Run The Demo

Preferred Windows launcher from the repo root:

```powershell
.\run-team-missile-intercept.ps1
```

Manual backend run path:

```powershell
cd team-missile-intercept\backend
pip install -r requirements.txt
python server.py
```

Then open `http://127.0.0.1:5174/`.

## Current Repo Layout

- `backend/` - active backend runtime shell
- `frontend/` - active frontend runtime shell
- `common-info/` - active navigation hub and shared docs package
- `ai/`, `math-validation/`, `maps/`, `models/`, `game-core/` - docs-first
  ownership packages
- `archive/xingyi-rts/` - archived legacy tree kept for provenance only

## Source Data

Canonical active source data lives under `common-info/source-data/`.

Use these docs for the current path-of-record and archive state:

- `common-info/ACTIVE_SOURCE_DATA_INDEX.md`
- `common-info/ARCHIVE_POLICY.md`
- `common-info/DEPENDENCY_CUTOVER_REPORT.md`

## Archive Rule

Do not use `archive/xingyi-rts/` as the default place to look for active
docs, source data, or implementation work.

If archived material is still needed by the active demo, the canonical active
copy must live under `common-info/source-data/` and be recorded in
`common-info/ACTIVE_SOURCE_DATA_INDEX.md`.
