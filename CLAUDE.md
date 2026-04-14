# Smart Stridsledning — Air Defense Decision Support

## Project

Build an intelligent command & control decision support prototype for Swedish air defense.
- **Hackathon**: Saab + KTH, organized by 2Hero
- **Hack Day**: April 25, 2026 (09:30-16:30). Grand Finale: April 27.
- **API**: OpenRouter ($50 credit, Google Gemini). **NEVER commit API keys.**

## Core Problem

Optimally allocate limited air defense assets when threats are detected:
- Which aircraft to scramble, from where?
- Which effector (air-to-air, SAM, SPAAG, drone)?
- How to sustain capability after resource expenditure?
- Think multiple steps ahead, not just current crisis.

## System Positioning

Decision support module on **GlobalEye AEW&C** — receives fused multi-domain situational picture, recommends optimal resource allocation to commander.

## Knowledge Base

Domain knowledge lives in `knowledge/`:
- `air-assets.md` — Gripen E/F, GlobalEye, Meteor, IRIS-T AAM, loyal wingman
- `ground-defense.md` — Patriot PAC-3, IRIS-T SLM/SLS, RBS 70 NG, Lvkv 90
- `threats.md` — 10 threat types, RCS table, cost-exchange ratios
- `sensors-c2.md` — Radar specs, data links, Silent Attack, TDFE sensor fusion
- `doctrine.md` — Layered defense, engagement priority, SEAD evasion, forward planning
- `data-model.md` — Abstract parameterized data model (Asset/Threat/Assignment)

All specs cite official manufacturer sources where available. See `knowledge/SOURCES.md` for full citation list.

## Code Conventions

- Internal model uses **abstract parameterized units** (extensible to any equipment)
- Demo layer maps abstract units to real Saab/Swedish equipment names
- Threat actors labeled **"Red Force"** — never name specific countries
- Prioritize Saab products in demo (GlobalEye, Gripen, RBS 70)

## Demo Strategy

- Narrow scope: pick ONE compelling slice
- Present full vision first, then demo the built piece
- Key metric: "Does this help the user do significantly better than before?"
