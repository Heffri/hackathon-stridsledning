# Smart Stridsledning — Air Defense Decision Support

Prototype of an intelligent command & control decision support system for Swedish air defense.

**Saab + KTH Hackathon** | Hack Day: April 25, 2026

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
