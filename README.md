# Smart Stridsledning — Air Defense Decision Support

Prototype of an intelligent command & control decision support system for Swedish air defense.

**Saab + KTH Hackathon** | Hack Day: April 25, 2026

Our concept: We're building an AI-powered battle management decision support system for air defense. It takes in real-time threat data — incoming missiles, drones, aircraft — and recommends optimal resource allocation to the commander: which assets to deploy, what weapons to use, and critically, when not to shoot (to conserve ammo for higher-priority threats).

How we'll demo it: A web-based interface styled like an RTS game — a map showing blue force assets and incoming red force threats in real-time. The AI engine analyzes each threat wave and displays recommendations. We'll run the same scenario twice: once with naive decisions (everything gets shot at, ammo runs out, defenses collapse) and once with AI-assisted decisions (smart triage, EW jamming, evasion, cost-effective intercepts). The contrast sells the value.

The AI's key insight: A system that recommends "don't shoot, just move" against cheap GPS-guided drones — saving your expensive missiles for the cruise missiles coming 20 minutes later — is smarter than one that fires at everything.


## Knowledge Base

The `knowledge/` directory contains structured domain reference data for building the simulation:

| File | Contents |
|------|----------|
| [air-assets.md](knowledge/air-assets.md) | Gripen E, GlobalEye, Meteor, IRIS-T, loyal wingman |
| [ground-defense.md](knowledge/ground-defense.md) | Patriot PAC-3, IRIS-T SLM/SLS, RBS 70 NG, Lvkv 90 |
| [threats.md](knowledge/threats.md) | 10 threat types, RCS table, cost-exchange ratios |
| [sensors-c2.md](knowledge/sensors-c2.md) | Radar specs, data links, Silent Attack, sensor fusion |
| [doctrine.md](knowledge/doctrine.md) | 3-layer response (soft kill/evade/hard kill), SEAD evasion |
| [data-model.md](knowledge/data-model.md) | Abstract parameterized data model for simulation |
| [scenario.md](knowledge/scenario.md) | Multi-wave mixed threat demo scenario |
| [SOURCES.md](knowledge/SOURCES.md) | Full citation list with source credibility tiers |

Each file includes **simulation parameter blocks** (YAML-style) ready to be used in code.

## Claude Code Integration

This repo includes a `CLAUDE.md` that auto-loads project context into Claude Code sessions. If your team uses Claude Code, it will automatically understand the project scope, equipment specs, and design constraints.
