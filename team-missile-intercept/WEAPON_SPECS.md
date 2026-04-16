# Weapon Specifications & Cost-Effectiveness Reference

> Data sourced from xingyi-rts/knowledge/ (manufacturer data, public domain).
> Values marked [est] are reasonable estimates where exact data is unavailable.

## Blue Force — Interceptors

### Summary Table

| Sim Type | Real-World Analog | Speed | Max G | Kill Radius | Range | USD/Shot | Abstract Cost |
|----------|-------------------|-------|-------|-------------|-------|----------|---------------|
| CIWS | Lvkv 90 (40mm Bofors 3P, 10-round burst) | 1,000 m/s (projectile) | N/A | 5m (airburst) | 4 km | ~$2,000 | 2 |
| Short-range SAM | RBS 70 NG (Bolide) | 680 m/s (Mach 2) | 20G [est] | 8m (frag) | 9 km | ~$175,000 [est] | 18 |
| Short-range SAM+ | IRIS-T SLS (RBS 98) | 400 m/s (Mach 2 avg) | 60G | 10m (frag) | 12 km | ~$500,000 | 50 |
| Medium-range SAM | IRIS-T SLM | 1,020 m/s (Mach 3) | 40G | 15m (frag) | 40 km | ~$1,000,000 | 100 |
| Long-range SAM | Patriot PAC-2 GEM+ | 1,700 m/s (Mach 5) | 25G | 20m (blast-frag) | 70 km | ~$3,000,000 | 300 |
| Hit-to-kill | Patriot PAC-3 MSE | 1,700 m/s (Mach 5) | 50G | 0.3m (kinetic) | 60 km | ~$4,000,000 | 400 |

### Detailed Parameters

#### CIWS — Lvkv 90 (40mm Bofors L/70)
- Rate of fire: 300 rpm
- Ammunition: Bofors 3P programmable (airburst / impact / proximity)
- Rounds per engagement: ~10 (burst)
- Total ammo: 144 rounds (~14 engagements before resupply)
- Effective range: 4 km (air targets)
- Altitude ceiling: 3,000 m
- Tracking radar: PS-95, 14 km detection
- Mobility: Tracked (CV90 chassis), very fast to relocate
- Cost per round: ~$200
- **Cost per engagement: ~$2,000**
- Source: ground-defense.md

#### Short-range SAM — RBS 70 NG (Saab)
- Missile: Bolide
- Speed: Mach 2 (680 m/s) — Saab official
- Range: >9 km — Saab official
- Altitude: 0–5,000 m — Saab official
- Guidance: Laser beam riding (passive, no radar emission)
- Reload time: <5 seconds — Saab official
- Deployment: Man-portable or vehicle-mounted
- Night capable: Yes (thermal imager, 8–12 µm)
- **Key advantage: SEAD-immune (no radar emission)**
- Cost per missile: ~$175,000 [est] — estimated from MANPAD class, Bolide is advanced laser-guided
- Source: ground-defense.md (Saab official datasheet values)

#### Medium-range SAM — IRIS-T SLM (Diehl Defence)
- Speed: Mach 3 (1,020 m/s)
- Range: 40 km
- Altitude: 10 m – 20,000 m
- Guidance: IR imaging seeker + datalink midcourse
- Radar: TRML-4D (250 km detection, 1,500 simultaneous tracks)
- Missiles per launcher: 8
- Launchers per battery: 3 (24 missiles ready)
- Reload time: ~20 min
- Combat record: 99% reported kill rate in Ukraine
- Cost per missile: ~$1,000,000 (SLM version with larger booster, estimated from IRIS-T SLS ~$500K baseline)
- Source: ground-defense.md

#### Short-range SAM+ — IRIS-T SLS / RBS 98 (Diehl Defence)
- Missile: IRIS-T air-to-air missile, ground-launched with short booster
- Speed: Mach 2 (~400 m/s average) — slower than SLM due to smaller booster
- Range: 12 km
- Altitude: up to 8,000 m
- Guidance: IR imaging seeker (all-aspect, 360 deg engagement)
- **Maneuverability: 60G** — confirmed, thrust vector control. Most agile interceptor in the arsenal.
- Warhead: 11.4 kg HE-fragmentation
- Launcher: Vehicle-mounted VLS, 4 missiles per launcher
- Reload time: ~10 min
- Cost per missile: ~$500,000 ($430K-560K per threats.md)
- **Niche**: Short range but hyper-agile. Best choice vs maneuvering targets within 12 km. The 60G capability means it can turn tighter than any threat in the sim.
- Source: ground-defense.md, air-assets.md (IRIS-T AAM specs)

#### Long-range SAM — Patriot PAC-2 GEM+ (Raytheon)
- Speed: Mach 5 (1,700 m/s)
- Range: ~160 km vs aircraft, ~70 km vs TBM
- Altitude: up to 25,000 m
- Guidance: Semi-active radar homing + TVM
- Warhead: Blast-fragmentation
- Radar: AN/MPQ-65 C-band (180 km detection, 100+ tracks)
- Requires active radar (SEAD vulnerability)
- Cost per missile: ~$3,000,000 [est]
- Source: ground-defense.md

#### Hit-to-kill — Patriot PAC-3 MSE (Lockheed Martin)
- Speed: Mach 5+ (1,700 m/s)
- Range: ~60 km vs TBM, ~100 km vs air-breathing
- Altitude: up to 40,000 m
- Guidance: Track-via-missile + Ka-band active radar terminal
- Kill mechanism: Direct kinetic hit (no warhead explosion)
- 12 per launcher (vs 4 PAC-2 per launcher)
- **Only interceptor in Swedish inventory for ballistic missile terminal defense**
- Cost per missile: ~$4,000,000
- Source: ground-defense.md (confirmed)

### Blue Ammo Budget (Demo Scenario)

| Type | Count | Total Value (USD) | Rationale |
|------|-------|-------------------|-----------|
| CIWS (bursts) | 14 | ~$28,000 | 144 rounds ÷ 10/burst |
| Short-range SAM (RBS 70) | 16 | ~$2,800,000 | 2 launchers × 8 |
| Short-range SAM+ (IRIS-T SLS) | 8 | ~$4,000,000 | 2 launchers × 4 |
| Medium-range SAM (IRIS-T SLM) | 12 | ~$12,000,000 | Partial battery (2 launchers × 6) [est] |
| Long-range SAM (PAC-2 GEM+) | 4 | ~$12,000,000 | Limited Patriot inventory |
| Hit-to-kill (PAC-3 MSE) | 2 | ~$8,000,000 | Scarce, save for ballistic |
| **Total inventory** | **56** | **~$38,828,000** | |

---

## Red Force — Threats

### Summary Table

| Sim Type | Real-World Analog | Speed | Max G | RCS | Altitude | USD/Unit | Abstract Value |
|----------|-------------------|-------|-------|-----|----------|----------|----------------|
| Suicide drone | FPV / Shahed-136 mix | 45 m/s | 2G | 0.2 m² | 500 m | ~$30,000 | 3 |
| Subsonic cruise missile | Kalibr-class | 260 m/s | 2G | 0.08 m² | 50 m | ~$1,500,000 | 150 |
| Stealth cruise missile | JASSM-ER / Kh-101 class | 260 m/s | 3G | 0.01 m² | 50 m | ~$2,500,000 [est] | 250 |
| Supersonic cruise missile | BrahMos/Zircon-class | 900 m/s | 4G | 0.15 m² | 14,000 m | ~$3,000,000 [est] | 300 |
| Ballistic missile (terminal) | Iskander-class SRBM | 2,000 m/s | 1G | 0.5 m² | 35,000 m entry | ~$3,000,000 | 300 |
| Hypersonic glide vehicle | Kinzhal/DF-ZF class | 1,700 m/s | 8G | 0.1 m² [est] | 25,000 m | ~$10,000,000 [est] | 1,000 |

### Detailed Parameters

#### Suicide Drone — Shahed-136 / Loitering Munition
- Speed: ~45 m/s (~185 km/h cruise)
- Altitude: 500–1,000 m (below conventional radar)
- Service ceiling: 4,000 m
- RCS: 0.01–0.1 m² (honeycomb RCS reduction)
- Range: 1,500–2,500 km (strategic range)
- Warhead: 30–50 kg HE
- Guidance (baseline): GPS/GLONASS + INS — jammable
- Guidance (upgraded Geran-2): GPS/INS + camera/AI (NVIDIA Jetson Orin) — partially jam-resistant
- Mass: ~200 kg
- Cost: $20K–50K production; actual $70K–290K (export pricing varies)
- **Sim cost: ~$30,000** (production average)
- Typical deployment: Swarms of 10+
- Source: threats.md

#### Subsonic Cruise Missile — Kalibr-class
- Speed: Mach 0.7–0.9 (~260 m/s)
- Cruise altitude: 50 m (terrain following) — hides below radar horizon
- Terminal: possible pop-up maneuver
- RCS: 0.08 m² (stealthy variant)
- Range: 300–2,500 km
- Guidance: INS + TERCOM + GPS/GLONASS + active radar terminal
- Warhead: 400–500 kg HE
- Cost: $1–2M
- **Sim cost: ~$1,500,000**
- Source: threats.md

#### Stealth Cruise Missile — JASSM-ER / Kh-101 class
- Speed: Mach 0.7–0.9 (~260 m/s) — same as subsonic cruise
- Cruise altitude: 50 m (terrain following)
- RCS: **0.01 m²** — 8× stealthier than standard Kalibr. Late detection.
- Range: 500–2,500 km
- Guidance: INS + GPS + terminal IR/radar seeker
- Maneuverability: 3G (slightly better than standard, terminal evasion)
- **Terminal takeover**: Red AI gains real-time control in final ~30 km
- Cost: $1.5–3.5M (JASSM-ER ~$1.5M, Kh-101 ~$3M+)
- **Sim cost: ~$2,500,000** [est]
- **Key threat**: Combination of stealth (late detection) + terminal AI control makes it dangerous despite slow speed
- Source: threats.md (stealthy RCS values), general estimates

#### Supersonic Cruise Missile — BrahMos/Zircon-class
- Speed: Mach 2.7 (~900 m/s)
- Cruise altitude: 14,000 m (terminal dive to low altitude)
- RCS: 0.15 m²
- Guidance: Active radar seeker
- Very short reaction time for defenders
- Cost: ~$2.73M (BrahMos public data), Zircon likely $5–10M
- **Sim cost: ~$3,000,000** (benefit of the doubt, use BrahMos range)
- Source: threats.md

#### Ballistic Missile — Iskander-class SRBM
- Terminal speed: Mach 6 (~2,000 m/s)
- Apogee: ~150 km
- Terminal phase: begins ~60 km altitude
- RCS: 0.01–0.1 m² (conical low-RCS reentry vehicle)
- Trajectory: Ballistic (extremely fast, predictable arc)
- Countermeasures: Decoys, MaRV capability
- Range: 400–500 km
- Only interceptor in Swedish inventory: Patriot PAC-3 MSE
- Cost: $1–5M
- **Sim cost: ~$3,000,000**
- Source: threats.md

#### Hypersonic Glide Vehicle — Kinzhal/DF-ZF class
- Speed: Mach 5+ (~1,700 m/s)
- Altitude: 25,000–40,000 m (skip-glide trajectory)
- Maneuverability: HIGH (8G+) — can change course unpredictably
- RCS: ~0.1 m² [est] — slender, high-speed body
- Guidance: INS + terminal seeker [est]
- **Hardest target in simulation**: combines speed of ballistic with maneuverability
- Cost: Very expensive, limited production
- **Sim cost: ~$10,000,000** [est] — benefit of the doubt, based on Kinzhal being modified Iskander
- Source: threats.md (partially), estimates for HGV

---

## Cost-Exchange Ratio Matrix

The AI computes this in real-time to decide whether an engagement is cost-justified.

**Formula**: `cost_ratio = interceptor_cost / threat_cost`
- Ratio < 1.0 → Excellent (interceptor cheaper than threat)
- Ratio 1.0–5.0 → Acceptable (defending high-value assets)
- Ratio 5.0–20.0 → Marginal (only if protecting critical infrastructure)
- Ratio > 20.0 → Unacceptable (find a cheaper option or accept the hit)

### Full Matrix (USD-based)

| | CIWS ($2K) | RBS 70 ($175K) | SLS ($500K) | SLM ($1M) | PAC-2 ($3M) | PAC-3 ($4M) |
|---|---|---|---|---|---|---|
| **Drone ($30K)** | 0.07 | 5.8 | 16.7 | 33 | 100 | 133 |
| **Cruise Sub ($1.5M)** | 0.001 | 0.12 | 0.33 | 0.67 | 2.0 | 2.7 |
| **Stealth Cruise ($2.5M)** | — | 0.07 | 0.20 | 0.40 | 1.2 | 1.6 |
| **Cruise Super ($3M)** | — | — | — | 0.33 | 1.0 | 1.3 |
| **Ballistic ($3M)** | — | — | — | — | 1.0 | 1.3 |
| **Hypersonic ($10M)** | — | — | — | — | 0.30 | 0.40 |

- Ratio < 1.0 = favorable. Ratio > 20 = unacceptable. "—" = cannot engage.

### Key Decision Rules (for Blue AI)

1. **Drones → CIWS first** (ratio 0.07). Short SAM only if CIWS unavailable or out of range.
2. **Subsonic cruise → IRIS-T SLM** (ratio 0.67). CIWS as last-ditch close-in backup.
3. **Stealth cruise → IRIS-T SLS or SLM** (ratio 0.20–0.40). SLS's 60G agility ideal vs maneuvering terminal phase, but 12 km range means late engagement.
4. **Supersonic cruise → Patriot PAC-2 or SLM** (ratio 0.33–1.0). Needs fast interceptor.
5. **Ballistic → PAC-3 MSE only** (ratio 1.3). Only system that can intercept Mach 6 terminal.
6. **Hypersonic → PAC-2 or PAC-3** (ratio 0.30–0.40). Excellent cost ratio but extremely hard to hit.
7. **Never fire Patriot at a drone** — cost ratio 100:1+, the #1 rule the AI must enforce.

### Saturation Attack Economics

| Attack Composition | Total Red Cost | Naive Blue Response Cost | Smart Blue Response Cost |
|-------------------|----------------|--------------------------|--------------------------|
| 20× drones | $600,000 | $3.5M (20× short SAM) | $40,000 (14× CIWS + 6× CIWS) |
| 5× drones + 2× cruise sub | $3,150,000 | $4.5M (mixed) | $1,010,000 (5× CIWS + 2× med SAM) |
| 10× drones + 1× ballistic | $300,000 + $3M | $23.5M (naive: Patriot on drones) | $4,020,000 (10× CIWS + 1× HTK) |

**Core demo point**: Smart AI saves >80% in interceptor costs vs naive response.

---

## Abstract Unit Conversion

For internal simulation, 1 abstract unit ≈ $10,000 USD (rough).

This is approximate — the abstract system preserves cost RATIOS while keeping numbers manageable:

| Real USD | Abstract Units |
|----------|---------------|
| $2,000 | 0.2 |
| $30,000 | 3 |
| $175,000 | 18 |
| $500,000 | 50 |
| $1,500,000 | 150 |
| $3,000,000 | 300 |
| $4,000,000 | 400 |
| $10,000,000 | 1,000 |

---

## Sources

- Ground defense specs: `xingyi-rts/knowledge/ground-defense.md` (Saab datasheets, Raytheon, Diehl)
- Threat profiles: `xingyi-rts/knowledge/threats.md` (public domain estimates, CSIS, defense analysis)
- Air assets: `xingyi-rts/knowledge/air-assets.md` (MBDA, Saab, Leonardo)
- Cost-exchange framework: `xingyi-rts/knowledge/threats.md` (Real Interceptor Costs section)
- Full source citations: `xingyi-rts/knowledge/SOURCES.md`
