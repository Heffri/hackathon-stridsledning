# Common Info Navigation Package

This folder is the main navigation package for active teammates working on
`team-missile-intercept/`.

Use it to answer four questions quickly:

- What is the active project?
- What is live right now?
- Where should I start for my role?
- Which docs are authoritative versus historical?

## Start Here

1. [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)
2. [CURRENT_STATE_SUMMARY.md](CURRENT_STATE_SUMMARY.md)
3. [TEAM_HANDOFF_GUIDE.md](TEAM_HANDOFF_GUIDE.md)
4. [../progress/STATUS.md](../progress/STATUS.md)
5. [../progress/ROADMAP.md](../progress/ROADMAP.md)

## Fast Reference

- Full doc map: [DOCS_INDEX.md](DOCS_INDEX.md)
- Known doc/runtime mismatches: [KNOWN_DOC_RUNTIME_DRIFT.md](KNOWN_DOC_RUNTIME_DRIFT.md)
- Repo onboarding note: [REPO_ONBOARDING_NOTES.md](REPO_ONBOARDING_NOTES.md)
- Active source data index: [ACTIVE_SOURCE_DATA_INDEX.md](ACTIVE_SOURCE_DATA_INDEX.md)

## Session 0 Source-of-Truth Docs

These remain the structural authority:

- [MODULARIZATION_SPEC.md](MODULARIZATION_SPEC.md)
- [TEAM_OWNERSHIP_SPEC.md](TEAM_OWNERSHIP_SPEC.md)
- [RESTRUCTURE_SEQUENCE.md](RESTRUCTURE_SEQUENCE.md)
- [RUNTIME_STABILITY_RULES.md](RUNTIME_STABILITY_RULES.md)
- [ARCHIVE_POLICY.md](ARCHIVE_POLICY.md)
- [DEPENDENCY_CUTOVER_REPORT.md](DEPENDENCY_CUTOVER_REPORT.md)

## Practical Rules

- `team-missile-intercept/` is the active project.
- `backend/` and `frontend/` are still the live runtime shells.
- `ai/`, `math-validation/`, `maps/`, `models/`, and `game-core/` are
  docs-first ownership packages in this phase.
- `common-info/source-data/` is the canonical active home for rehomed
  source data.
- `archive/xingyi-rts/` is archived provenance only. Do not use it as the
  default starting point for active work.

## Conflict Rule

- If a structural decision conflicts with older prose, follow the Session 0
  docs in this folder.
- If current behavior conflicts with prose docs, treat current runtime code
  under `backend/` and `frontend/` as the source of truth unless a Session 0
  doc explicitly says otherwise.
