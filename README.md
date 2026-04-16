# Smart Stridsledning — AI-Powered Air Defense Battle Management

> Saab + KTH Hackathon | Organized by 2Hero | Hack Day: April 25, 2026

## What We're Building

A decision support module designed to run on Saab's **GlobalEye AEW&C** platform. It receives the fused multi-domain situational picture and recommends optimal resource allocation to the commander in real-time.

**Core problem:** When threats are detected, the system must decide which assets to deploy, which weapons to use, how to sustain capability as resources are consumed, and think several steps ahead. The critical insight is that *not shooting* is often the smartest decision — saving expensive interceptors for the threats that actually matter.

## Three-Layer Response Model

Instead of simply matching weapons to targets, the system evaluates three layers of response in order:

1. **Soft Kill (EW)** — Can we jam it? GPS-guided drones can be defeated with electronic warfare at near-zero cost.
2. **Evade** — Can we just move? If a Shahed drone flies to pre-programmed coordinates and our SAM battery is mobile, we drive away. It hits empty ground.
3. **Hard Kill** — Only as last resort, using the cheapest effective interceptor. Never waste a $4M Patriot missile on a $500 drone.

## Demo Concept

A web-based **RTS-style interface** showing a map with blue force assets and red force threats. We run a multi-wave attack scenario twice:

| | Without AI | With AI |
|---|---|---|
| Wave 1: 40x cheap drones | Operator panics, fires all IRIS-T missiles | EW jam + evade + gun systems only |
| Wave 2: SEAD probe | Radars still on, 2 radar sites destroyed | Radars already off, Gripen Silent Attack |
| Wave 3: 8x cruise missiles | No missiles left, only expensive Patriot | Full IRIS-T stock available, all intercepted |
| Wave 4: 2x ballistic missiles | Patriot depleted | Patriot intercepts both |
| **Result** | Air base destroyed, IADS crippled | All assets intact, ammo reserves healthy |

The contrast demonstrates the value: **AI recommending "don't shoot" saved 30 missiles in Wave 1, which were then available to stop the real threat in Wave 3.**

## Stretch Goal: Red vs Blue AI Self-Play

Both sides controlled by AI, competing against each other like AlphaGo. We feed in real weapon parameters and known tactics, let them play thousands of games overnight, and analyze whether the system discovers novel tactical patterns that human planners haven't considered.

Battlefield tactics have historically been paid for in lives. We can let two AIs develop them over coffee instead.

Our concept: We're building an AI-powered battle management decision support system for air defense. It takes in real-time threat data — incoming missiles, drones, aircraft — and recommends optimal resource allocation to the commander: which assets to deploy, what weapons to use, and critically, when not to shoot (to conserve ammo for higher-priority threats).

How we'll demo it: A web-based interface styled like an RTS game — a map showing blue force assets and incoming red force threats in real-time. The AI engine analyzes each threat wave and displays recommendations. We'll run the same scenario twice: once with naive decisions (everything gets shot at, ammo runs out, defenses collapse) and once with AI-assisted decisions (smart triage, EW jamming, evasion, cost-effective intercepts). The contrast sells the value.

The AI's key insight: A system that recommends "don't shoot, just move" against cheap GPS-guided drones — saving your expensive missiles for the cruise missiles coming 20 minutes later — is smarter than one that fires at everything.


## Knowledge Base

The `knowledge/` directory contains fact-checked domain reference data with simulation parameters:

| File | Contents |
|------|----------|
| [air-assets.md](knowledge/air-assets.md) | Gripen E/F, GlobalEye, Meteor, IRIS-T, loyal wingman — with sim params |
| [ground-defense.md](knowledge/ground-defense.md) | Patriot PAC-3, IRIS-T SLM/SLS, RBS 70 NG, Lvkv 90 |
| [threats.md](knowledge/threats.md) | 11-tier threat classification (T1-T11), RCS table, cost-exchange ratios |
| [sensors-c2.md](knowledge/sensors-c2.md) | Radar specs, AESA trade-offs, data links, Silent Attack, burn-through formula |
| [doctrine.md](knowledge/doctrine.md) | 13 sections: 3-layer response, GlobalEye protection, CAP rotation, mixed defense groups, distributed sensor network |
| [data-model.md](knowledge/data-model.md) | Abstract parameterized data model (Asset / Threat / Assignment / DefendedArea) |
| [scenario.md](knowledge/scenario.md) | 5-wave mixed threat demo scenario with optimal responses and A/B scoring |
| [SOURCES.md](knowledge/SOURCES.md) | Full citation list — official manufacturer PDFs, tiered by credibility |

All specs sourced from official Saab/MBDA/Diehl/Hensoldt datasheets where available. Fact-checked against 38 data points with 3 independent sources each.

## Built With Real Data

| Source Tier | Examples |
|-------------|---------|
| Manufacturer PDFs | Saab Gripen E factsheet, GlobalEye product sheet, RBS 70 NG datasheet, MBDA Meteor datasheet, Leonardo Raven ES-05 |
| Official product pages | Saab, Diehl Defence, Hensoldt TRML-4D, BAE Bofors 3P |
| Cross-referenced | 2025 Operation Sindoor combat data, Ukraine theater FPV/loitering munition statistics |

## Claude Code Integration

This repo includes a `CLAUDE.md` that auto-loads project context into Claude Code sessions. The `knowledge/` directory serves as a self-growing knowledge base — every new session automatically has access to all equipment specs, doctrine, and scenario data.
