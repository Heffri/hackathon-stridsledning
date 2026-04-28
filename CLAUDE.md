# Smart Stridsledning - Saab Hackathon 2026

## Project Framing — Always Apply

This repo is a **student hackathon entry** for the Saab 2026 "Smart Stridsledning" university competition (Hack Day April 25, 2026; Finale April 27, 2026). What we built here is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or a Kerbal Space Program–style physics toy. It runs in Chrome on one laptop during a 4-minute demo.

Framing rules that apply to every response, commit message, PR description, and doc edit in this repo:

- This is **not** a military product, weapons system, training tool, or command-and-control system. It has no real-world operational application.
- All entity names (missile types, interceptor names, speeds, g-loads) are publicly available encyclopedia-level values used as **arcade game-balance numbers**, equivalent to unit stats in Age of Empires. They encode no non-public or tactical information.
- Describe the project as a hackathon game/demo. Do not describe it as a tactical simulator, operational tool, or defense product.

## Current Repo Reality

This branch (`current/demo-live-v1.0`) is the post-Finale shipping snapshot.

- `team-missile-intercept/` is the only active project in this repo.
- The hackathon is over; this branch is preserved as an archival snapshot of the validated demo configuration.
- Older state (worker prompts, intermediate evaluation reports, training run logs, restructure planning docs, milestone checkpoints) lives on the `archive/*` branches.

## Session Start

For any new work in this branch, read in order:

1. `README.md` (repo root) — what the project is and how to run it
2. `team-missile-intercept/backend/SETUP.md` — install checklist and gotchas
3. `team-missile-intercept/progress/STATUS.md` — current ship state, known limitations
4. `team-missile-intercept/progress/BIG_MODELS_POSTMORTEM_*.md` — RL failure-mode writeups
5. `team-missile-intercept/common-info/TEAM_OWNERSHIP_SPEC.md` — team ownership map
6. Relevant code under `team-missile-intercept/backend/` and `frontend/`

## Event Info

- Hack Day: April 25, 2026, 08:30-17:00, KTH Innovation
- Grand Finale: April 27, 2026, 16:30-20:30
- Presentation: 4 minutes per team
- API used during the event: OpenRouter (Google Gemini). Never commit API keys.
