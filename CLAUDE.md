# Smart Stridsledning — Saab Hackathon 2026

## Repo Structure

This repo contains two separate projects:

- `team-missile-intercept/` — **Team project**: 3D AI vs AI missile interception
- `xingyi-rts/` — **Xingyi's personal project**: RTS-style air defense decision support

## Team Project: Missile Intercept

3D missile interception simulation. Red AI launches threats (hypersonic, cruise, ballistic, drones), Blue AI selects interceptors and computes real-time physics-based intercept solutions. Not probability — actual trajectory math.

## Xingyi's RTS Project

Full IADS decision support system with knowledge base in `xingyi-rts/knowledge/`:
- `air-assets.md` — Gripen E/F, GlobalEye, Meteor, IRIS-T
- `ground-defense.md` — Patriot, IRIS-T SLM/SLS, RBS 70, Lvkv 90
- `threats.md` — 11-tier threat classification with cost-exchange ratios
- `doctrine.md` — 13 sections: 3-layer response, GlobalEye protection, CAP rotation
- `scenario.md` — 5-wave demo scenario on Saab's Boreal Passage map
- `data-model.md` — Abstract parameterized data model
- `sensors-c2.md` — Radar specs, AESA trade-offs, burn-through formula

## Event Info

- **Hack Day**: April 25, 08:30-17:00, KTH Innovation
- **Grand Finale**: April 27, 16:30-20:30
- **Presentation**: 4 minutes per team
- **API**: OpenRouter ($50 credit, Google Gemini). NEVER commit API keys.
