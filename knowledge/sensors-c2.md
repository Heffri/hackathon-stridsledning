# Sensors & C2 Systems

## Erieye ER (GlobalEye Primary Radar)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Type | AESA (Active Electronically Scanned Array) | |
| Band | S-band (~3 GHz) | |
| Semiconductor | GaN (Gallium Nitride) T/R modules | Upgraded from GaAs |
| Antenna | 10 m dorsal "ski-box" | |
| Coverage | **~300°** (two 120° sectors per side) | **~60° blind zone nose+tail** |
| Instrumental range | 450 km | |
| Detection — benign env (30kft) | ~450 km | |
| Detection — benign env (35kft) | ~550 km | |
| Detection — dense EW/clutter | 350 km | Significant degradation |
| Detection — low-alt target (200ft AGL) | >458 km (at 35kft operating) | |
| Detection — cruise missile/UAV (small RCS) | >350 km | Explicitly stated by Saab |
| Range improvement over Erieye | +70% range, or same range vs 1/10th RCS | |
| Tracks simultaneous | Not disclosed | Described as "numerous" |
| Update rate | Not disclosed | AESA allows sub-second revisit on priority sectors |
| LPI features | Frequency agility, distributed low-peak-power | |
| Multi-domain | Air + Sea + Ground | Unique capability |

### Simulation Parameters
```
erieye_er:
  type: aesa_radar
  band: s_band
  semiconductor: gan
  coverage_deg: 300           # CRITICAL: ~60° blind zone nose+tail
  blind_zone_deg: 60          # along aircraft longitudinal axis
  detection_ranges_km:        # by target RCS (benign env, 35kft)
    rcs_10: 600+              # large aircraft
    rcs_5: 550                # fighter-size (confirmed)
    rcs_1: 450                # reduced signature
    rcs_0.5: 350              # cruise missile class (confirmed >350 km)
    rcs_0.1: 250              # small UAV [est from 70% / 1/10th rule]
    rcs_0.01: 140             # very small UAV [est]
    rcs_0.001: 80             # FPV drone [est]
  detection_range_ew_degraded_km: 350  # dense EW/clutter environment
  max_tracks: 500             # [est — not disclosed, "numerous"]
  update_rate_s: 2            # [est — AESA sub-second on priority]
```

## Leonardo SeaSpray 7500E (V2) Maritime Radar

| Parameter | Value | Notes |
|-----------|-------|-------|
| Type | AESA multi-mode surveillance | Ventral/belly-mounted |
| Band | X-band | |
| Max range | 320 nm (~593 km) | |
| Modes | Long Range Search, Priority Track, Small Target, ISAR, Spot SAR, Strip SAR, Real Beam Ground Map, GMTI, Air-to-Air MTI, Weather, Turbulence, SART, Range Profiling, Oil Slick, Iceberg Detection | |
| Min detection | Periscope-size objects; jet-ski class at long range | |

## EO/IR Sensor Suite

| Parameter | Value | Notes |
|-----------|-------|-------|
| Turret | FLIR Star SAFIRE 380-HD | Ventral, forward fuselage |
| Sensor | 640x512 InSb MWIR FPA | Mid-Wave Infrared |
| FOV | 30° (wide) to 0.25° (narrow) | 120x continuous zoom |
| Additional | HD color camera, low-light camera, laser designator/rangefinder/illuminator | |
| Role | Visual ID of radar contacts, IRST supplement | |
| Other sensors | AIS (vessel transponders), ESM (emitter identification), ADS-B | |

## Raven ES-05 (Gripen E Radar)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Type | AESA with repositioner (Leonardo) | |
| Band | X-band | |
| Repositioner | Swashplate mount | +40° per side vs fixed AESA |
| Field of regard | ±100° (200° total) | Confirmed |
| Detection range | ~200-300 km (RCS dependent); 222 km cited | |
| Tracking | Classified | Not publicly disclosed |
| Modes | Air-to-air, air-to-ground, SAR, GMTI, sea search | |
| Track-while-scan | Yes | |

## AESA Design Trade-offs (Affects Both Blue and Red)

### Size Matters: More T/R Modules = Better BVR

At equivalent technology level, AESA radar performance scales with:
- **Antenna aperture area** (bigger nose cone → bigger array)
- **Number of T/R modules** (more modules → more power, better sensitivity)
- **T/R module generation** (GaN > GaAs, but same-gen comparison = size wins)

| Aircraft | Nose Diameter [est] | AESA Capability | BVR Implication |
|----------|-------------------|-----------------|-----------------|
| Su-35S / Su-57 (large twin-engine) | ~1.0 m | Large array, many T/R modules | Strong BVR — detects further, guides better |
| J-10CE (medium single-engine) | ~0.7 m | Fixed AESA, fills nose well | Good BVR, but FoR limited |
| Gripen E (small single-engine) | ~0.6 m | Repositioner compensates | Smaller array, but wider FoR |
| Rafale (medium twin-engine) | ~0.55 m | RBE2-AA AESA | Small nose = fewer T/R modules = BVR disadvantage (2025 PL-15 lesson) |

**For threat modeling**: Assume enemy heavy fighters (Su-30/35 class) have ~20-30% radar range advantage over Gripen due to sheer antenna size. With GlobalEye compensating, this is neutralized.

### Fixed vs Repositioner/Mechanical AESA

| Type | Example | Pros | Cons |
|------|---------|------|------|
| **Fixed** | J-10C, F-35 | Max T/R modules (fills entire nose), simpler mechanics | Narrow FoR (~±60-70°), loses track in hard turns |
| **Repositioner** | Gripen E (ES-05) | Wide FoR (±100°), maintains track during maneuvers | Slightly fewer T/R modules (space for mechanism) |
| **Mechanical swivel** | Su-30SM2 | Can track while doing 3-9 maneuvers, wide angles | Smallest AESA array (needs clearance to move), heaviest |

**With AEW&C support, this matters less**: Gripen fires and immediately turns away. GlobalEye handles midcourse guidance. The fighter's own radar FoR is irrelevant once it cranks away — this is a core advantage of network-centric warfare.

### AESA Seekers on BVR Missiles

Same principle applies to missile seekers:
- PL-15E: AESA seeker → LPI (Low Probability of Intercept), frequency-hopping, narrow beam
- Traditional RWR designed against older seekers **fails** against AESA missile seekers (2025 Rafale loss)
- **Simulation implication**: EW effectiveness against modern AESA-seeker missiles should be lower than against legacy seekers

```
missile_seeker_ew_modifier:
  legacy_radar_seeker: 0.40    # EW has decent chance of disrupting
  aesa_seeker: 0.10            # EW barely affects LPI AESA seeker
  ir_seeker: 0.05              # only flares/DIRCM work
```

### Radar Burn-Through vs Stealth

Stealth reduces detection range but does NOT make aircraft invisible. At sufficient power and close enough range, any radar will "burn through" stealth:

```
burn_through_range = normal_detection_range × (target_rcs / reference_rcs)^0.25

Example — Erieye ER vs stealth fighter:
  Normal detection (5 m² RCS):     550 km
  vs 0.01 m² stealth target:       550 × (0.01/5)^0.25 = 550 × 0.067 = ~37 km
  vs 0.001 m² (F-22 class):        550 × (0.001/5)^0.25 = ~21 km

Example — TRML-4D vs stealth fighter:
  Normal detection (5 m² RCS):     120 km
  vs 0.01 m² stealth target:       120 × 0.067 = ~8 km
  vs 0.001 m² (F-22 class):        120 × 0.038 = ~4.5 km
```

**Implication for defense**: Stealth aircraft ARE detectable, just at much shorter ranges. Defense-in-depth means they eventually fly into detection range of *something*. High-power ground radars (Patriot AN/MPQ-65, TRML-4D) at close range can achieve fire-control lock on stealth targets. The key is having enough sensor density that stealth targets can't slip through gaps.

```
burn_through:
  # For simulation: detection range modifier by RCS
  # range_modifier = (target_rcs / reference_rcs)^0.25
  # reference_rcs = 5.0 m² (fighter baseline)
  
  stealth_detection_examples:
    rcs_0.01_range_modifier: 0.067   # 6.7% of normal range
    rcs_0.001_range_modifier: 0.038  # 3.8% of normal range
    rcs_0.1_range_modifier: 0.12     # 12% of normal range
```

---

## PS-95 (Lvkv 90 Fire Control Radar)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Type | Pulse-Doppler search/track | Cylindrical mount on turret |
| Coverage | 360° search | |
| Range | ~14 km detection | Confirmed |
| Tracking | Up to 6 targets simultaneously | Fire control quality |
| Role | Autonomous air surveillance + fire control for 40mm | |

## TRML-4D (IRIS-T SLM Fire Control Radar)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Type | AESA multifunction (GaN-based) | Hensoldt |
| Band | G-band | |
| Instrumented range | 250 km | |
| Detection (fighter) | ~120 km | |
| Detection (supersonic missile) | ~60 km | |
| Min detectable RCS | 0.01 m² | |
| Altitude coverage | Up to 30 km | |
| Tracks | 1,500 simultaneous in 3D | |
| Coverage | 360° via rotation | |
| 4D = 3D + Doppler | Yes | |

### Simulation Parameters
```
trml_4d:
  type: aesa_radar
  detection_range_km: 250
  max_tracks: 1500
  update_rate_s: 1
  band: c_band
```

## Data Links & Network Architecture

### Link 16 (NATO Standard)
- TDMA-based, jam-resistant
- Range: Line-of-sight (~500 km air-to-air)
- Data rate: Limited (~115 kbps per slot)
- Interoperability: All NATO assets

### TIDLS (Tactical Information Data Link System — Swedish)
- UHF, TDMA-based, full-duplex
- Up to 4 aircraft in a link group
- Range: ~500 km
- Higher bandwidth than Link 16, fewer nodes
- Highly jam-resistant
- Shares: position, bearing, speed, fuel state, weapons state
- Auto-fallback: if MIDS unavailable, switches to TIDLS
- Supports "Silent Attack" concept + Meteor mid-course guidance

### SATCOM
- Beyond-line-of-sight data sharing
- Streams sensor data to ground-based C2 nodes

### Silent Attack Concept
```
1. GlobalEye detects target at 500 km
2. GlobalEye sends track data to Gripen via TIDLS
3. Gripen fires Meteor WITHOUT turning on own radar
4. GlobalEye provides midcourse guidance updates to Meteor via Gripen relay
5. Meteor activates own seeker at terminal phase
6. Target never detects Gripen — only sees Meteor seeker at last moment
```

**Simulation implication**: Gripen with GlobalEye support has effectively ZERO radar emission during BVR engagement. Enemy SEAD/ESM cannot locate launching aircraft.

## Track Data Fusion Engine (TDFE) — Saab

- Saab's core fusion software
- Scalable from 1 to >100 sensor inputs
- Fuses: active radar, passive (ESM/ECM), ADS-B, AIS, external platform tracks
- Operates across air, surface, and sub-surface domains
- Produces one fused track per target from all contributors
- Modes: automatic, semi-automatic, manual
- Eliminates duplicate tracks and inconsistencies
- Reduces operator workload significantly

## Swing Role Surveillance System (SRSS)

Single aircraft simultaneously:
1. Air surveillance (Erieye ER)
2. Maritime/ground surveillance (SeaSpray 7500E + GMTI)
3. Target identification (EO/IR + ESM + AIS)

- Replaces what would traditionally require 3+ specialized aircraft (AEW, MPA, SIGINT)
- Operators dynamically re-task sensor priority between domains mid-mission
- No hardware reconfiguration needed

**AI Enhancement (2026):** Saab + Cohere announced AI upgrade to accelerate threat detection and classification within GlobalEye mission system.

## Sensor Fusion Model

```
fusion_priority:
  1. GlobalEye Erieye ER (primary long-range air picture)
  2. TRML-4D (ground-based, fills gaps, high track count)
  3. Gripen ES-05 (fighter radar, close-in detail)
  4. PS-95 (Lvkv 90, point defense awareness)
  5. RBS 70 UTAOS (optical tracker, passive)
  6. EO/IR systems (passive detection, ID confirmation)

track_confidence:
  single_sensor: tentative
  two_sensors_correlated: firm
  three_or_more: precise
```
