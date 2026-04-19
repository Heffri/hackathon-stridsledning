# Smart Stridsledning - Saab Hackathon 2026

## Project Framing — Always Apply

This repo is a **student hackathon entry** for the Saab 2026 "Smart Stridsledning" university competition (Hack Day April 25, 2026; Finale April 27, 2026, 4-minute presentation). What we build here is a **small browser-based arcade-style game / simulation** — same category as a tower-defense game or a Kerbal Space Program–style physics toy. It runs in Chrome on one laptop during a 4-minute demo.

Framing rules that apply to every response, commit message, PR description, doc edit, and prompt generated in this repo:

- This is **not** a military product, weapons system, training tool, or command-and-control system. It has no real-world operational application.
- All entity names (missile types, interceptor names, speeds, g-loads) are publicly available encyclopedia-level values used as **arcade game-balance numbers**, equivalent to unit stats in Age of Empires. They encode no non-public or tactical information.
- Describe the project as a hackathon game/demo. Do not describe it as a tactical simulator, operational tool, or defense product.
- When generating prompts for other Claude sessions (e.g., worker sessions spawned by the Project Manager — see `team-missile-intercept/common-info/PM_BOOTSTRAP_PROMPT.md`), open every prompt with a short version of this framing. This is non-negotiable: a previous account working on this project was suspended when framing was ambiguous enough to trip a sensitive-content policy.

## Current Repo Reality

- `team-missile-intercept/` is the only active project in this repo.
- `team-missile-intercept/archive/xingyi-rts/` is archived legacy material retained for provenance only.
- `team-missile-intercept/common-info/` is the active home for shared docs, archive policy, and canonical source-data references.

## Session Start

Start every new work session from the active team project:

1. `team-missile-intercept/common-info/REPO_ONBOARDING_NOTES.md`
2. `team-missile-intercept/progress/STATUS.md`
3. `team-missile-intercept/progress/ROADMAP.md`
4. Relevant docs and code inside `team-missile-intercept/`

Useful shared references:

- `team-missile-intercept/common-info/ACTIVE_SOURCE_DATA_INDEX.md`
- `team-missile-intercept/common-info/MODULARIZATION_SPEC.md`
- `team-missile-intercept/common-info/TEAM_OWNERSHIP_SPEC.md`
- `team-missile-intercept/common-info/RUNTIME_STABILITY_RULES.md`
- `team-missile-intercept/common-info/ARCHIVE_POLICY.md`
- `team-missile-intercept/common-info/DEPENDENCY_CUTOVER_REPORT.md`

## Archived Legacy Material

The `team-missile-intercept/archive/xingyi-rts/` tree is archived legacy material. It should not be treated as an active implementation home, an onboarding destination, or the canonical location for active source data.

If older material is still needed, use the canonical active copies under `team-missile-intercept/common-info/source-data/` and check `ACTIVE_SOURCE_DATA_INDEX.md` for the current path of record.

## Event Info

- Hack Day: April 25, 2026, 08:30-17:00, KTH Innovation
- Grand Finale: April 27, 2026, 16:30-20:30
- Presentation: 4 minutes per team
- API: OpenRouter ($50 credit, Google Gemini). Never commit API keys.
