# Saab Smart Stridsledning Hackathon

> This file auto-loads into every Claude Code session in this directory.

## Project Context

**What**: Build an intelligent command & control decision support prototype for Swedish air defense.
**When**: Hack day April 25, 2026 (09:30-16:30). Grand Finale April 27.
**Who**: Team lead Sebastijan Babic. Member Xingyi Chen (math undergrad @ Stockholm University, military domain knowledge).
**API**: OpenRouter ($50 credit, Google Gemini). Do NOT commit API keys.

## Core Problem

Given detected threats, optimally allocate limited air defense assets:
- Which aircraft to scramble, from where?
- Which effector to use (air-to-air, SAM, SPAAG, drone)?
- How to sustain capability after resource expenditure?
- Think multiple steps ahead, not just current crisis.

## System Positioning

Decision support module running on **GlobalEye AEW&C** platform — receives fused multi-domain situational picture, recommends optimal resource allocation to commander.

## Knowledge Base

Detailed domain knowledge is in `knowledge/` directory:
- `knowledge/air-assets.md` — Gripen E/F, GlobalEye, drones, air-to-air weapons
- `knowledge/ground-defense.md` — Patriot, IRIS-T SLM/SLS, RBS 70, Lvkv 90
- `knowledge/threats.md` — Threat types, RCS, speed profiles, engagement logic
- `knowledge/sensors-c2.md` — Radar specs, data links, sensor fusion
- `knowledge/doctrine.md` — Swedish air defense doctrine, layered defense, SEAD evasion
- `knowledge/data-model.md` — Abstract parameterized data model for simulation
- `knowledge/scenario.md` — Multi-wave mixed threat demo scenario with optimal responses

Full Chinese-language reference: `Saab hackathon knowledge base.md`

## Code Conventions

- System internals use **abstract parameterized units** (extensible)
- Demo layer maps abstract units to real Saab/Swedish equipment names (impress judges)
- Threat actors labeled "Red Force / Adversary" — NEVER name specific countries
- Prioritize Saab products in demo (GlobalEye, Gripen, RBS 70)

## Event Format (2Hero Hackathon)

- **Organizer**: 2Hero (formerly Cillers), Saab Digital Battlespace Solutions provides the challenge
- **Kickoff**: April 13 (Discord server, tech resources) — DONE
- **Saab Q&A**: April 16, 15:00-16:00 — ASK THEM what demo level they expect
- **AI Coding Lab**: April 20, 12:00-13:30
- **Hack Day**: April 25, 08:30-17:00, KTH Innovation — coding 09:30, demos ~14:30
- **Grand Finale**: April 27, 16:30-20:30 — 5 finalist teams present + Saab executive dinner
- **Presentation**: 4 minutes per team. Jury = Saab technical leaders and decision-makers
- **"Prize"**: Not money — jury votes by requesting meetings with teams. Leads to thesis work, consulting, or recruitment at Saab
- **Deliverable**: Working prototype + demo video. No mandated tech stack. Demo > slides
- **Two tracks**: (1) Decision support system, (2) Simulation engine (alternative)

## Demo Strategy

- Narrow scope: pick ONE compelling slice, build it well
- Present full vision first, then demo the core built piece
- Core metric: "Does this help the user do significantly better than before?"
- **4 minutes is not enough for a full RTS game** — focus on the A/B comparison:
  - Run scenario WITHOUT AI → naive decisions → ammo wasted → assets destroyed
  - Run scenario WITH AI → smart 3-layer response → ammo conserved → assets intact
- **Core selling point**: AI recommending "don't shoot" is smarter than always recommending a weapon

## Tech Direction

- Optimization: LP, Hungarian algorithm, or multi-objective optimization for resource allocation
- Simulation: Discrete event simulation with time-stepping
- LLM layer: Natural language interface for commander queries via OpenRouter/Gemini
- Visualization: Web-based map UI showing assets, threats, AI recommendations, ammo forecast
- A/B comparison mode: "with AI" vs "without AI" side-by-side
