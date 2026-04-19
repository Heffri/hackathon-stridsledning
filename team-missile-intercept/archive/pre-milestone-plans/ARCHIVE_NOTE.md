# Archive Note: Pre-Milestone Plans

Archived on: 2026-04-19 (post Milestone I, post modularization)

## What Is In This Folder

These documents captured the planning and technical-debt state **before**
the shipped game overtook them. They are retained for provenance only.

| File | Original role | Superseded by |
|---|---|---|
| `DEMO_PLAN.md` | Simplified MVP scope built for Milestone B (flat physics, binary kill, 3 weapons, unlimited ammo) | `progress/STATUS.md` + `progress/ROADMAP.md` |
| `PLAN.md` | Full pre-Milestone-B product vision / implementation roadmap | `progress/ROADMAP.md` + the module READMEs under `ai/`, `game-core/`, `maps/`, `models/`, `math-validation/` |
| `NOTES_MODEL_AND_PORT.md` | Pre-Milestone-D Windows port-reservation workarounds + mesh orientation notes | `RUNNING_TEAM_MISSILE_INTERCEPT.md` (ports) + `models/PIPELINE_NOTES.md` (mesh conventions) |

## Why They Were Archived

By the end of Milestone I the shipped game has:

- Real win conditions (per-site HP + Blue budget + 3600 s safety cap)
- 6 interceptor types with fuel + coast physics
- Saturation engagement + CIWS point defense + cost-exchange ladder
- Multi-site target model (7 Saab-located sites, per-site leak tracking)
- Per-launcher range math + visible Red launcher boxes
- HGV manoeuvre-override hook for Red AI
- Boreal Passage 3D terrain + 12 named landmarks
- Click-to-inspect status panel + AI decision logs + seeker cones

`DEMO_PLAN.md` described a subset of this roughly 9 milestones ago;
`PLAN.md` described it as aspirational future work. Neither is the right
entry point for a new collaborator any more — onboarding should start at
`common-info/REPO_ONBOARDING_NOTES.md` → `progress/STATUS.md` →
`progress/ROADMAP.md`.

`NOTES_MODEL_AND_PORT.md` was consolidated because the Windows port
workaround is now in `RUNNING_TEAM_MISSILE_INTERCEPT.md` and the
mesh-convention notes are the domain of `models/`.

## Rules (Same As The Rest Of `archive/`)

- Do not add new active project logic here.
- Do not take new active imports from here.
- If an active module still needs something in here, promote the
  canonical copy up to the appropriate active module first.
