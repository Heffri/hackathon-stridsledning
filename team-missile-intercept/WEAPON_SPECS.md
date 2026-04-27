# Weapon Specifications — Full Reference

> This document is the arsenal spec reference. All 6 interceptors and
> all 6 threat kinds listed below are active in the shipped sim. All
> weapon names and stats are encyclopedia-level values used as arcade
> game-balance numbers.
>
> Data sourced from `common-info/source-data/knowledge/` (manufacturer
> datasheets, public-domain reference notes). Values marked `[est]` are
> reasonable estimates where exact data is unavailable. Reload times
> over 60 s are scaled by 1/10 for demo pacing (see `GAME_DESIGN.md`
> for the scaling rule).
>
> The single source of truth for runtime values is
> `backend/sim/types.py` and `backend/sim/world.py`. Where this file's
> prose drifted from the runtime during the 2026-04-19 cleanup pass,
> the prose was rewritten to match the runtime. Specifically:
> HGV cruise_speed (5,831 m/s / Mach 17), ballistic cruise_speed
> (4,459 m/s / Mach 13), HGV KE-bleed constant `_HGV_BLEED_RATE`
> (120 m/s/s at max G with quadratic `(G/Gmax)²` scaling), and the
> proximity-damage falloff is linear in code
> (`(1 - dist / prox_radius)`, not quadratic).

---

## Blue Force — Interceptors

### Performance Table

| Weapon | Real Analog | Speed | Max G | Range | Fuel (s) |
|--------|-------------|-------|-------|-------|----------|
| CIWS (per round) | Lvkv 90 (40mm Bofors 3P) | 1,000 m/s | N/A (ballistic) | 4 km | 4s |
| Short-range SAM | RBS 70 NG (Bolide) | 680 m/s (Mach 2) | 20G [est] | 9 km | 13s |
| Short-range SAM+ | IRIS-T SLS (RBS 98) | 400 m/s (Mach 2 avg) | 60G | 12 km | 30s |
| Medium-range SAM | IRIS-T SLM | 1,020 m/s (Mach 3) | 40G | 40 km | 39s |
| Long-range SAM | Patriot PAC-2 GEM+ | 1,700 m/s (Mach 5) | 25G | 70 km | 41s |
| Hit-to-kill | Patriot PAC-3 MSE | 1,700 m/s (Mach 5) | 50G | 60 km | 35s |

### Damage Table

| Weapon | Direct Hit Dmg | Prox Max Dmg | Prox Radius | Kill Mechanism |
|--------|----------------|--------------|-------------|----------------|
| CIWS (per round) | 15 | 8 | 5m | 3P programmable airburst fragments |
| RBS 70 NG | 40 | 20 | 8m | HE-fragmentation (Bolide) |
| IRIS-T SLS | 50 | 25 | 10m | 11.4 kg HE-fragmentation |
| IRIS-T SLM | 50 | 25 | 15m | HE-fragmentation |
| PAC-2 GEM+ | 80 | 40 | 20m | Blast-fragmentation |
| PAC-3 MSE | **200** | **5** | 0.3m | Kinetic kill (no warhead) |

**Damage formula (runtime, `backend/sim/world.py`):**
```
if dist < radius_direct (per-weapon; e.g. 0.3m for PAC-3 kinetic):
    damage = damage_direct
elif dist < radius_prox:
    damage = max(1, round(damage_prox * (1 - dist / radius_prox)))
else:
    damage = 0
```

Falloff is **linear** (not the quadratic `(1 - d/r)²` originally sketched)
because combining real-warhead fuse radii (5–20 m) with the Euler-0.05 s
PN's typical 20–80 m CPA left almost every hit at 1–2 dmg. The current
runtime scales `radius_prox` up per-weapon (see `INTERCEPTOR_SPECS` in
`types.py`) and uses linear falloff with a `max(1, …)` floor so the
"direct vs prox" design intent still reads in a 1–3 shot kill pattern.
Flagged for Emil review — see header drift note.

**Key design note — PAC-3 MSE:**
PAC-3 is a pure kinetic kill vehicle with no warhead. On direct hit: devastating (200 dmg, one-shots anything). On near-miss: almost nothing (5 dmg). This forces Blue AI to achieve perfect guidance — PAC-3 is the "sniper" of the arsenal.

### Economy Table

| Weapon | Magazine | Inter-shot | Full Reload | USD/shot |
|--------|----------|------------|-------------|----------|
| CIWS (round) | 24 per box, 6 boxes | 0.2s (300 rpm) | 5s box swap, 30s full resupply | $200 |
| RBS 70 NG | 1 per rail | 5s | 5s (same as inter-shot) | $175,000 |
| IRIS-T SLS | 4 per launcher | 3s [est] | 60s | $500,000 |
| IRIS-T SLM | 8 per launcher | 5s [est] | 120s | $1,000,000 |
| PAC-2 GEM+ | 4 per launcher | 10s [est] | 180s | $3,000,000 |
| PAC-3 MSE | 12 per launcher | 10s [est] | 180s | $4,000,000 |

---

### Detailed Parameters — Blue

#### CIWS — Lvkv 90 (40mm Bofors L/70)
- Rate of fire: 300 rpm → 5 rounds/second → ~0.2s between rounds
- Ammunition: Bofors 3P programmable (airburst / impact / proximity modes)
- Per engagement: 10-round burst (~2 seconds of firing)
- Box magazine: 24 rounds
- Total onboard: 144 rounds (6 boxes = 14 engagements)
- Box swap: 5 seconds
- Full resupply: 30 seconds (scaled from 300s)
- Effective range: 4 km air targets
- Altitude ceiling: 3,000 m
- Projectile is **unguided ballistic** — AI predicts target trajectory, fires burst on lead angle
- Fuel timer: 4 seconds (projectile self-destructs after 4s if no impact)
- Cost per round: $200; **per engagement: ~$2,000**
- Source: ground-defense.md

#### Short-range SAM — RBS 70 NG (Saab Bolide)
- Speed: Mach 2 (680 m/s) — Saab official
- Range: >9 km — Saab official
- Altitude: 0–5,000 m — Saab official
- Guidance: Laser beam riding (passive, no radar emission) — SEAD-immune
- Magazine: 1 rail, manual reload in <5s (Saab official)
- Fuel: 13 seconds
- Direct hit: 40 dmg (Bolide HE-frag warhead, direct impact)
- Proximity: 20 dmg in 8m radius
- Night capable: thermal imager (8–12 µm)
- Cost per missile: ~$175,000 [est]
- Source: ground-defense.md (Saab official datasheet)

#### Short-range SAM+ — IRIS-T SLS / RBS 98 (Diehl Defence)
- Missile: IRIS-T AAM ground-launched with short booster
- Speed: Mach 2 (~400 m/s average)
- Range: 12 km
- Altitude: up to 8,000 m
- Guidance: IR imaging seeker (all-aspect, 360° engagement)
- **Maneuverability: 60G** — thrust vector control. Most agile interceptor.
- Warhead: 11.4 kg HE-fragmentation
- Magazine: 4 per launcher, ~3s inter-shot [est]
- Full reload: 60s (scaled from 600s)
- Fuel: 30 seconds
- Direct hit: 50 dmg; Prox: 25 dmg in 10m radius
- Cost per missile: ~$500,000 ($430K-560K per threats.md)
- **Niche**: Terminal "knife fight" vs maneuvering targets within 12 km
- Source: ground-defense.md, air-assets.md

#### Medium-range SAM — IRIS-T SLM (Diehl Defence)
- Speed: Mach 3 (1,020 m/s)
- Range: 40 km
- Altitude: 10 m – 20,000 m
- Guidance: IR imaging seeker + datalink midcourse
- Radar: TRML-4D (250 km detection, 1,500 simultaneous tracks)
- Magazine: 8 per launcher, ~5s inter-shot [est]
- Full reload: 120s (scaled from 1200s)
- Fuel: 39 seconds
- Direct hit: 50 dmg; Prox: 25 dmg in 15m radius
- Combat record: 99% reported kill rate in Ukraine
- Cost per missile: ~$1,000,000 (SLM with larger booster, est)
- Source: ground-defense.md

#### Long-range SAM — Patriot PAC-2 GEM+ (Raytheon)
- Speed: Mach 5 (1,700 m/s)
- Range: ~70 km vs TBM, ~160 km vs aircraft (sim uses 70 km)
- Altitude: up to 25,000 m
- Guidance: Semi-active radar homing + TVM
- Warhead: Blast-fragmentation (larger frag pattern than IRIS-T)
- Magazine: 4 per launcher (PAC-2 variant), ~10s inter-shot [est]
- Full reload: 180s (scaled from 1800s)
- Fuel: 41 seconds
- Direct hit: 80 dmg; Prox: 40 dmg in 20m radius
- Cost per missile: ~$3,000,000 [est]
- Source: ground-defense.md

#### Hit-to-kill — Patriot PAC-3 MSE (Lockheed Martin)
- Speed: Mach 5+ (1,700 m/s)
- Range: ~60 km vs TBM, ~100 km vs air-breathing (sim uses 60 km)
- Altitude: up to 40,000 m
- Guidance: Track-via-missile + Ka-band active radar terminal
- **Kill mechanism: pure kinetic hit, no warhead**
- Magazine: 12 per launcher, ~10s inter-shot [est]
- Full reload: 180s (scaled from 1800s)
- Fuel: 35 seconds
- **Direct hit: 200 dmg — one-shots anything** (kinetic transfer at Mach 10+ closure)
- Proximity: only 5 dmg in 0.3m radius (kinetic body, no frag)
- **Only interceptor capable of ballistic missile terminal-phase intercept**
- Cost per missile: ~$4,000,000
- Source: ground-defense.md (confirmed)

### Blue Ammo Budget (Starting Loadout Example)

| Type | Launchers | Mag | Total | Total Value | Rationale |
|------|-----------|-----|-------|-------------|-----------|
| CIWS bursts | — | — | 14 | ~$28,000 | 144 rounds ÷ 10/burst |
| RBS 70 (rails) | 2 | 1 | 2 (then reload) | — | Cheap continuous coverage |
| IRIS-T SLS | 2 | 4 | 8 | ~$4,000,000 | Max-agility niche |
| IRIS-T SLM | 2 | 8 | 16 | ~$16,000,000 | Medium-range workhorse |
| PAC-2 GEM+ | 1 | 4 | 4 | ~$12,000,000 | Long-range/fast-target |
| PAC-3 MSE | 1 | 12 | 12 | ~$48,000,000 | Ballistic/HGV terminal |

*This is one possible loadout. Blue AI can reallocate within its budget.*

---

## Red Force — Threats

### Performance Table

| Weapon | Real Analog | Speed | Max G | HP | RCS | Altitude | Fuel (s) |
|--------|-------------|-------|-------|-----|-----|----------|----------|
| Suicide drone | Shahed-136 | 45 m/s | 2G | 10 | 0.2 m² | 500–1000 m | 4000 |
| Subsonic cruise | Kalibr-class | 260 m/s | 2G | 30 | 0.08 m² | 50 m | 600 |
| Stealth cruise | JASSM-ER / Kh-101 | 260 m/s | 3G | 30 | 0.01 m² | 50 m | 600 |
| Supersonic cruise | BrahMos-class | 900 m/s | 4G | 40 | 0.15 m² | 14,000 m | 180 |
| Ballistic (terminal) | Iskander / DF-17 class | 4,459 m/s (Mach 13) | 1G | 80 | 0.5 m² | 35,000→0 m | **gravity** |
| Hypersonic glide | Kinzhal / DF-ZF | 5,831 m/s (Mach 17) | 8G | 60 | 0.1 m² [est] | 35,000 m | **gravity** |

**Gravity-driven** means no fuel timer — ballistic and HGV operate on kinetic energy and altitude trade:
- Maneuvers bleed speed (not fuel). HGV runtime formula (`entities.py`): `speed_loss = _HGV_BLEED_RATE * (G_applied / max_G)² * dt` where `_HGV_BLEED_RATE = 120 m/s/s` at `G_applied = max_G = 8 G`.
- When speed drops below the stall floor (`_HGV_STALL_SPEED = 500 m/s` for HGV) → HGV loses lift, is marked dead, ground-sweep picks up the wreck.
- Cannot generate thrust — once launched, they coast on initial energy.

### Economy Table

| Weapon | Launcher Capacity | Inter-shot | Full Reload | USD/unit |
|--------|-------------------|------------|-------------|----------|
| Shahed | 5 per trailer | 30s | 60s (scaled from 600s) | $30,000 |
| Subsonic cruise | 4 per launcher | 10s | 180s (scaled from 1800s) | $1,500,000 |
| Stealth cruise | 4 per launcher | 10s | 180s (scaled from 1800s) | $2,500,000 |
| Supersonic cruise | 2 per launcher | 15s | 120s (scaled from 1200s) | $3,000,000 |
| Ballistic | 2 per launcher | 60s | 120s (scaled from 1200s) | $3,000,000 |
| Hypersonic glide | 1 per carrier | — | 360s (scaled from 3600s) | $10,000,000 |

**Red Force reload scaling prevents opening-shot zerg rush**: buying all HGVs at t=0 doesn't help if the carrier can only fire one at a time with a 6-minute reload.

---

### Detailed Parameters — Red

#### Suicide Drone — Shahed-136
- Speed: ~45 m/s (~185 km/h cruise)
- Altitude: 500–1,000 m (below conventional radar coverage)
- RCS: 0.2 m² (honeycomb RCS reduction)
- **HP: 10** (fragile composite airframe)
- Warhead: 30–50 kg HE
- Guidance: GPS/GLONASS + INS (baseline, Level 1 pre-programmed control)
- Mass: ~200 kg
- Launcher: 5-tube trailer
- Fuel: 4000s (more than enough for arena crossing)
- Cost: $30,000 (production average; export prices vary $70K–290K)
- **Role**: Cheap saturation weapon. 10 HP means CIWS airburst or RBS 70 frag one-shots it.
- Source: threats.md

#### Subsonic Cruise Missile — Kalibr-class
- Speed: Mach 0.7–0.9 (~260 m/s)
- Cruise altitude: 50 m (terrain following — hides below radar horizon)
- RCS: 0.08 m²
- **HP: 30** (moderate structure)
- Warhead: 400–500 kg HE
- Guidance: INS + TERCOM + GPS + active radar terminal (Level 3 waypoint-adjustable)
- Launcher: 4-tube (ship, submarine, or ground)
- Fuel: 600s
- Cost: ~$1,500,000
- Source: threats.md

#### Stealth Cruise Missile — JASSM-ER / Kh-101 class
- Speed: Mach 0.7–0.9 (~260 m/s) — same as subsonic cruise
- Cruise altitude: 50 m (terrain following)
- **RCS: 0.01 m²** — 8× stealthier than Kalibr. Late detection.
- **HP: 30** (same structure as subsonic, just stealthier coating)
- Maneuverability: 3G (slightly better than standard for terminal evasion)
- Guidance: INS + GPS + terminal IR/radar seeker (Level 4 — terminal AI takeover after crossing sea strait)
- Launcher: 4-tube
- Fuel: 600s
- Cost: ~$2,500,000 [est]
- **Key threat**: Stealth (late detection) + terminal real-time AI control
- Source: threats.md (RCS), estimates for other parameters

#### Supersonic Cruise Missile — BrahMos-class
- Speed: Mach 2.7 (~900 m/s)
- Cruise altitude: 14,000 m (terminal dive to low altitude)
- RCS: 0.15 m²
- **HP: 40** (larger, more robust airframe)
- Guidance: Active radar seeker (Level 3 waypoint-adjustable)
- Launcher: 2-tube truck
- Fuel: 180s
- Cost: ~$3,000,000 [est] (BrahMos ~$2.73M public data)
- Source: threats.md

#### Ballistic Missile — Iskander / DF-17 class (terminal phase)
- Terminal speed: Mach 13 (~4,459 m/s) — matches public terminal velocity of modern MaRV / heavy-RV designs (Iskander upgrade, DF-17 depressed-trajectory test)
- Entry altitude: 35,000 m (simulation enters at this point, skipping boost phase; Milestone I floors reentry at ≥ 20 km on far-north spawn)
- RCS: 0.5 m² (reentry vehicle, conical low-RCS design)
- **HP: 80** (hardened RV designed to survive reentry heating)
- Maneuverability: 1G correction (terminal phase only, very limited)
- Trajectory: Pre-programmed ballistic arc + pre-programmed maneuvers (Level 2 — no post-launch control)
- **No fuel system** — gravity-driven. Speed bleeds from maneuvers and drag.
- Launcher: 2 missiles per TEL
- Cost: ~$3,000,000 (real $1-5M)
- **Only PAC-3 MSE can intercept**
- Source: threats.md

#### Hypersonic Glide Vehicle — Kinzhal/DF-ZF class
- Initial speed: Mach 17 (~5,831 m/s)
- Altitude: 25,000–40,000 m (skip-glide trajectory; Milestone I floors reentry at ≥ 30 km on far-north spawn)
- **Maneuverability: 8G max** — `Threat.override_maneuver(turn_dir, g_load)` hook is the Red AI control input (Milestone I); default flight is straight-line toward the pre-selected target
- RCS: ~0.1 m² [est]
- **HP: 60** (hardened but control surfaces are fragile)
- **No fuel system** — gravity/kinetic-driven. Maneuvers bleed speed aggressively.
- Runtime speed bleed (`entities.py`): `speed_loss_per_s = _HGV_BLEED_RATE * (G_applied / max_G)²` with `_HGV_BLEED_RATE = 120 m/s/s` at max G
- When speed < `_HGV_STALL_SPEED` (500 m/s) → HGV can no longer generate sufficient lift → crashes
- Launcher: 1 per carrier (MiG-31 analog)
- Cost: ~$10,000,000 [est] — Kinzhal ~$10M+ reported
- **Hardest target**: speed + maneuverability combination
- **Strategic tension**: Red AI must balance evasion (maneuver = safer now) vs speed preservation (easier to intercept next)
- Source: threats.md (partial), estimates for HGV

---

## Cost-Exchange Ratio Matrix

**Formula:** `cost_ratio = interceptor_cost / threat_cost`

- Ratio < 1.0 → Excellent (interceptor cheaper than threat)
- Ratio 1.0–5.0 → Acceptable (defending high-value assets)
- Ratio 5.0–20.0 → Marginal
- Ratio > 20.0 → Unacceptable (find cheaper option or accept hit)

### Matrix (USD-based, single shot)

| | CIWS ($2K) | RBS 70 ($175K) | SLS ($500K) | SLM ($1M) | PAC-2 ($3M) | PAC-3 ($4M) |
|---|---|---|---|---|---|---|
| **Drone ($30K)** | 0.07 ✅ | 5.8 ⚠️ | 16.7 ❌ | 33 ❌ | 100 ❌ | 133 ❌ |
| **Cruise Sub ($1.5M)** | 0.001 ✅ | 0.12 ✅ | 0.33 ✅ | 0.67 ✅ | 2.0 ✅ | 2.7 ✅ |
| **Stealth ($2.5M)** | — | 0.07 ✅ | 0.20 ✅ | 0.40 ✅ | 1.2 ✅ | 1.6 ✅ |
| **Cruise Super ($3M)** | — | — | — | 0.33 ✅ | 1.0 ✅ | 1.3 ✅ |
| **Ballistic ($3M)** | — | — | — | — | 1.0 ✅ | 1.3 ✅ |
| **Hypersonic ($10M)** | — | — | — | — | 0.30 ✅ | 0.40 ✅ |

"—" = cannot engage (too slow, out of range, or insufficient damage to kill before miss)

### HP vs Damage — Shots Needed to Kill

| Target (HP) | CIWS burst | RBS 70 | SLS | SLM | PAC-2 | PAC-3 |
|-------------|------------|--------|-----|-----|-------|-------|
| Drone (10) | 1 burst prox (8+) + 1 direct (15) | 1 prox (20) | 1 prox (25) | 1 prox (25) | 1 prox (40) | 1 direct (200) |
| Cruise Sub (30) | ~4 bursts prox | 2 prox (40) or 1 direct (40) | 2 prox (50) or 1 direct (50) | 2 prox (50) | 1 prox (40) | 1 direct (200) |
| Cruise Super (40) | — | 2 prox | 2 prox | 2 prox | 1 prox (40) | 1 direct |
| HGV (60) | — | 3 prox | 3 prox | 3 prox | 2 prox (80) | 1 direct |
| Ballistic (80) | — | — | 4 prox or 2 direct | 4 prox or 2 direct | 2 prox or 1 direct | 1 direct |

**Key tactical insight**: PAC-3 is ideal vs ballistic/HGV because:
1. Only weapon fast enough to catch ballistic terminal
2. Direct hit one-shots 80 HP target
3. But if it misses (prox 5 dmg), it's basically wasted — Blue AI must achieve pinpoint guidance

**Alternative tactic**: Stack 2× PAC-2 GEM+ on a ballistic/HGV — 2× prox (40) = 80 dmg, guaranteed kill via blast-frag fragment density.

---

## Abstract Unit Conversion (for internal simulation)

1 abstract unit ≈ $10,000 USD (rough scaling for manageable numbers)

| Real USD | Abstract |
|----------|----------|
| $2,000 | 0.2 |
| $30,000 | 3 |
| $175,000 | 18 |
| $500,000 | 50 |
| $1,000,000 | 100 |
| $1,500,000 | 150 |
| $2,500,000 | 250 |
| $3,000,000 | 300 |
| $4,000,000 | 400 |
| $10,000,000 | 1,000 |

---

## Sources

- Ground defense specs: `team-missile-intercept/common-info/source-data/knowledge/ground-defense.md` (Saab datasheets, Raytheon, Diehl)
- Threat profiles: `team-missile-intercept/common-info/source-data/knowledge/threats.md` (public domain, CSIS, defense analysis)
- Air assets: `team-missile-intercept/common-info/source-data/knowledge/air-assets.md` (MBDA, Saab, Leonardo)
- Cost-exchange framework: `team-missile-intercept/common-info/source-data/knowledge/threats.md`
- Full citations: `team-missile-intercept/common-info/source-data/knowledge/SOURCES.md`
