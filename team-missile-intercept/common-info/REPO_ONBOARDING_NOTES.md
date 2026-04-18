# Repo Onboarding Notes

## Purpose

This is the stable repo-level starting point for teammates working on the active demo.

## Active Working Area

- `team-missile-intercept/` is the mainline active project.
- `team-missile-intercept/common-info/` is the home for shared repo structure, archive policy, and active source-data records.
- `team-missile-intercept/common-info/source-data/` is the canonical active home for rehomed source material.

## Read Order

1. `team-missile-intercept/progress/STATUS.md`
2. `team-missile-intercept/progress/ROADMAP.md`
3. `team-missile-intercept/REPORT.md` for milestone history
4. The relevant `common-info/` specs for structure, ownership, runtime safety, and archive rules

## Common-Info Files To Know

- `MODULARIZATION_SPEC.md`
- `TEAM_OWNERSHIP_SPEC.md`
- `RUNTIME_STABILITY_RULES.md`
- `ACTIVE_SOURCE_DATA_INDEX.md`
- `ARCHIVE_POLICY.md`
- `DEPENDENCY_CUTOVER_REPORT.md`

## Archived Legacy Material

`team-missile-intercept/archive/xingyi-rts/` is archived legacy material kept for provenance only. Do not use it as the default place to look for active docs, source data, or implementation work.

If older material is still needed by the active project, move the active reference path to `common-info/source-data/` and record the change in the source-data index or cutover docs before treating it as canonical.

## Short Navigation

- Active code and demo: `team-missile-intercept/`
- Shared structure and source-data records: `team-missile-intercept/common-info/`
- Current project state: `team-missile-intercept/progress/STATUS.md`
- Next-step planning: `team-missile-intercept/progress/ROADMAP.md`
