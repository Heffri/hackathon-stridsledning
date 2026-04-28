# Progress Folder

This folder is the post-Finale archival snapshot for the project.

## Contents

- **[STATUS.md](STATUS.md)** — current ship state (post-Finale,
  `current/demo-live-v1.0` branch).
- **[BIG_MODELS_POSTMORTEM_en.md](BIG_MODELS_POSTMORTEM_en.md)** /
  **[_zh.md](BIG_MODELS_POSTMORTEM_zh.md)** — why the bigger RL
  Blue models (Boyu V2a / Cap120 / Megamodel) regressed into
  PAC-spam during demo testing, and how V4 + the rule layer
  ended up being the validated configuration.
- **[V4_DISTRIBUTION_SHIFT_UPDATE_zh.md](V4_DISTRIBUTION_SHIFT_UPDATE_zh.md)**
  — the real root cause of the PAC-spam regression, found
  mid-Finale day: training-vs-deployment distribution mismatch
  on layout + budget. The fix was simply matching the demo
  setup to the training distribution.

Older training reports, worker prompts, and evaluation logs
live on the `archive/*` branches.
