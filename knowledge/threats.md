# Threat Profiles & Engagement Data

> Generic adversary profiles for simulation. NOT tied to any specific nation.
> Label as "Red Force" or "Adversary" in all user-facing text.

## Threat Type Profiles

### 1. 4th-Gen Fighter (Generic)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Examples (internal ref only) | Su-30 class, J-11 class | Never show in demo |
| Max speed | Mach 2.0-2.5 | |
| Combat speed | Mach 0.85-1.2 | |
| Service ceiling | 15,000-18,000 m | |
| Combat altitude | 5,000-12,000 m | |
| RCS (by subtype) | Su-27/30 class: ~15 m², MiG-29 class: ~5 m², F-16 class: ~1.2-5 m² | |
| RCS (4.5-gen w/ shaping) | 0.5-1.5 m² | Typhoon ~0.5-1.2, Rafale ~0.5-1.0 |
| BVR weapons range | 80-160 km | R-77: 80 km base, 110-160 extended; AIM-120D: ~165 km |
| ECM | External pods (DRFM-based), noise/repeater/transponder | Effective jamming at 25+ nm |

```
threat_4gen_fighter:
  type: fighter
  speed_cruise_mps: 280
  speed_max_mps: 660          # Mach 2
  altitude_m: 10000
  rcs_m2: 5.0
  ecm: basic
  weapons_range_km: 120
  threat_level: high
  value: 80
```

### 2. 5th-Gen Stealth Fighter (Generic)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Examples (internal ref only) | Su-57 class | |
| Max speed | Mach 1.6-2.0 | |
| Supercruise | Mach 1.2-1.8 | Without afterburner |
| Service ceiling | 15,000-20,000 m | |
| RCS (full stealth, frontal X-band) | F-22 class: ~0.0001 m², F-35 class: ~0.005 m² | |
| RCS (partial stealth) | Su-57 class: 0.1-0.5 m² | |
| BVR weapons range | ~150-200 km | Internal weapons bays |
| ECM | Integrated EW suite, LPI radar, sensor fusion | Networked data links |

```
threat_5gen_fighter:
  type: fighter
  speed_cruise_mps: 290
  speed_max_mps: 600
  altitude_m: 12000
  rcs_m2: 0.005             # F-35 class; use 0.0001 for F-22 class
  ecm: advanced
  weapons_range_km: 180
  threat_level: critical
  value: 120
```

### 3. Subsonic Cruise Missile

| Parameter | Value | Notes |
|-----------|-------|-------|
| Examples (internal ref only) | Kalibr-class, Tomahawk-class | |
| Speed | Mach 0.7-0.9 (~800 km/h) | |
| Cruise altitude | 15-100 m (sea-skimming) or 50-300 m (terrain following) | |
| Terminal altitude | 2-5 m (sea-skimming) | Hides in sea clutter |
| RCS (stealthy, e.g. JASSM) | 0.01-0.05 m² | |
| RCS (conventional) | 0.1-1.0 m² | |
| Range | 300-2,500 km | |
| Guidance | INS + TERCOM + GPS/GLONASS + terminal seeker | |
| Maneuvering | Limited (terminal pop-up possible) | |
| Warhead | 400-500 kg HE or submunitions | |

```
threat_cruise_subsonic:
  type: cruise_subsonic
  speed_mps: 260
  altitude_m: 50              # terrain following
  rcs_m2: 0.08
  ecm: none
  maneuvering: false
  threat_level: high
  value: 30
  quantity: 1                 # often comes in salvos
```

### 4. Supersonic / Hypersonic Cruise Missile

| Parameter | Value | Notes |
|-----------|-------|-------|
| Examples (internal ref only) | BrahMos-class, Zircon-class | |
| Speed (supersonic) | Mach 2.0-3.0 | |
| Speed (hypersonic) | Mach 5+ | |
| Cruise altitude | 10,000-14,000 m | |
| Terminal altitude | 4-15 m (sea-skimming) | For anti-ship variants |
| RCS | 0.1-1.0 m² | Larger body than subsonic |
| Reaction time | Very short | 2-3x size of subsonic = larger IR signature |

```
threat_cruise_supersonic:
  type: cruise_supersonic
  speed_mps: 900              # Mach ~2.7
  altitude_m: 14000           # high cruise, terminal dive
  rcs_m2: 0.15
  ecm: basic
  threat_level: critical
  value: 50
```

### 5. Tactical Ballistic Missile (TBM)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Speed — SRBM terminal | Mach 4-8 (~1.5-3 km/s) | |
| Speed — MRBM terminal | Mach 8-15 (~3-5 km/s) | |
| Apogee — SRBM | 50-150 km | |
| Apogee — MRBM | 150-500 km | |
| Terminal phase start | ~60 km altitude | Atmosphere thickens, drag significant |
| RCS (warhead/RV) | 0.01-0.1 m² | Classified, conical low-RCS design |
| Trajectory | Ballistic (predictable but extremely fast) | |
| Countermeasures | Decoys, MaRV, penetration aids | Decoys slow faster than warheads below 60 km |
| Only interceptor | Patriot PAC-3 (in Swedish inventory) | |

```
threat_tbm:
  type: ballistic
  speed_terminal_mps: 2000    # Mach ~6
  altitude_apogee_m: 150000
  rcs_m2: 0.5
  ecm: none
  threat_level: critical
  value: 100
```

### 6. MALE/HALE UAV (Medium/High Altitude, Long Endurance)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Examples (internal ref only) | MQ-9 class, Bayraktar TB2 class | |
| Speed | 150-300 km/h (40-80 m/s) | Slow |
| Altitude | 3,000-15,000 m | |
| RCS | 0.5-3 m² | Relatively large |
| Endurance | 24-40 hours | |
| Weapons | Precision guided munitions, ISR payloads | |
| Vulnerability | Easy to shoot down once detected | |

```
threat_uav_male:
  type: uav_male
  speed_mps: 60
  altitude_m: 7000
  rcs_m2: 1.0
  ecm: none
  maneuvering: false
  threat_level: medium
  value: 15
```

### 7. Small Tactical UAV / Reconnaissance Drone

| Parameter | Value | Notes |
|-----------|-------|-------|
| Speed | 50-150 km/h (15-40 m/s) | |
| Altitude | 100-3,000 m | |
| RCS | 0.01-0.1 m² | Very small |
| Endurance | 1-4 hours | |
| Role | ISR, target designation | |
| Challenge | Hard to detect, not worth expensive missiles | |

```
threat_uav_small:
  type: uav_small
  speed_mps: 30
  altitude_m: 500
  rcs_m2: 0.01
  ecm: none
  threat_level: low
  value: 2
  quantity: 5                 # often in groups
```

### 8. FPV / Kamikaze Drone

| Parameter | Value | Notes |
|-----------|-------|-------|
| Speed | 50-180 km/h (15-50 m/s) | |
| Altitude | 0-500 m (typical 30-150 m) | Extremely low |
| RCS | 0.001-0.01 m² (-30 to -20 dBsm) | Dielectric materials, tiny |
| Range | 10-30 km | |
| Mass | 0.3-5 kg | |
| Warhead | 0.5-3 kg shaped charge or frag | |
| Cost | $300-$500 | |
| Endurance | 15-45 minutes | |
| Operational wave size | Up to 117 drones (Ukraine Op Spider Web) | |
| Monthly scale | 50,000+ FPV/month (Ukraine theater, both sides) | |
| Detection challenge | Very small RCS, low speed (clutter), low alt, plastic/carbon fiber | |

```
threat_fpv:
  type: fpv
  speed_mps: 40
  altitude_m: 50
  rcs_m2: 0.005
  ecm: none
  maneuvering: true           # highly agile
  threat_level: low           # individually
  value: 0.5
  quantity: 20                # swarm attacks
```

### 9. Loitering Munition (Shahed-class)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Speed | 140-185 km/h (~45 m/s) | Slow, piston engine |
| Service ceiling | 4,000 m | |
| Attack altitude | Very low (below conventional radar) | |
| RCS | 0.01-0.1 m² | Honeycomb structure for RCS reduction |
| Wingspan / Length | 2.5 m / 3.5 m | |
| Mass | ~200 kg | |
| Range | 1,500-2,500 km | Strategic range |
| Warhead | ~40-50 kg HE | |
| Cost | $20,000-$50,000 | |
| Challenge | Cheap, numerous, strategic range | |
| Engagement | IRIS-T SLS, RBS 70, Lvkv 90 all effective | |

```
threat_loitering:
  type: loitering
  speed_mps: 45
  altitude_m: 1000
  rcs_m2: 0.2
  ecm: none
  maneuvering: false
  threat_level: medium
  value: 5
  quantity: 10                # often in waves
```

### 10. SEAD/Anti-Radiation Missile (ARM)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Examples (internal ref only) | HARM/AARGM class | |
| Speed | Mach 2-3 | |
| Range | 80-150 km | |
| Guidance | Home-on-jam / anti-radiation seeker | Locks onto radar emissions |
| RCS | 0.05-0.1 m² | |
| Counter | Shut down radar + relocate | |

```
threat_sead_arm:
  type: sead_arm
  speed_mps: 900
  altitude_m: 12000           # high launch, diving terminal
  rcs_m2: 0.08
  threat_level: high          # threatens entire IADS
  value: 40
  homing_on: radar_emission   # targets active radars
```

---

## RCS Reference Table

| Target Category | Typical RCS (m²) | dBsm | Erieye ER Detection (km) [est] |
|-----------------|-------------------|------|--------------------------------|
| Large bomber (non-stealth) | 10-100 | +10 to +20 | 600+ |
| 4th-gen fighter (clean) | 3-15 | +5 to +12 | 450-550 |
| 4.5-gen fighter | 0.5-1.5 | -3 to +2 | 350-450 |
| 5th-gen stealth (frontal) | 0.0001-0.01 | -40 to -20 | 30-140 |
| 5th-gen partial stealth (Su-57) | 0.1-0.5 | -10 to -3 | 250-350 |
| Cruise missile (stealthy) | 0.01-0.05 | -20 to -13 | 140-220 |
| Cruise missile (conventional) | 0.1-1.0 | -10 to 0 | 250-350 |
| Large UAV (MALE) | 0.1-1.0 | -10 to 0 | 250-350 |
| Small tactical UAV | 0.001-0.01 | -30 to -20 | 50-140 |
| Loitering munition | 0.01-0.1 | -20 to -10 | 140-250 |
| FPV drone | 0.001-0.01 | -30 to -20 | 50-140 |
| Ballistic missile RV | 0.01-0.1 | -20 to -10 | 140-250 |

**Note**: RCS varies with aspect angle, frequency band, external stores, and surface treatments. Values are typically frontal-aspect, X-band estimates.

---

## Cost-Exchange Ratio Reference

### Real Interceptor Costs (USD)

| System | Interceptor | Cost per Shot |
|--------|-------------|---------------|
| Patriot PAC-3 MSE | PAC-3 MSE | $3.7-4.7M |
| IRIS-T SLM | IRIS-T (med range) | $1.0-4.4M |
| IRIS-T SLS | IRIS-T (short range) | $430K-560K |
| Meteor | MBDA Meteor | ~$2M+ |
| NASAMS | AIM-120 AMRAAM | $1.1-1.2M |
| Gepard/Lvkv 90 | 35-40mm burst | $1K-2K per engagement |

### Real Threat Costs (USD)

| Threat | Unit Cost |
|--------|-----------|
| FPV drone | $300-500 |
| Shahed-136 loitering munition | $20K-50K |
| Subsonic cruise missile | $1-2M |
| Short-range ballistic missile | $1-5M |
| 4th-gen fighter | $30-80M |

### Cost-Exchange Ratio Matrix

| Scenario | Interceptor $ | Target $ | Ratio | Verdict |
|----------|--------------|----------|-------|---------|
| Patriot vs FPV drone | $4M | $500 | 8,000:1 | **NEVER** |
| Patriot vs Shahed-136 | $4M | $50K | 80:1 | **NEVER** (at scale) |
| SM-2 class vs Houthi drone | $2M | $2K | 1,000:1 | **UNSUSTAINABLE** |
| IRIS-T SLS vs Shahed-136 | $500K | $50K | 10:1 | **MARGINAL** |
| Lvkv 90 burst vs FPV | $1-2K | $500 | 2-4:1 | **OPTIMAL** |
| Patriot vs cruise missile | $4M | $1.5M | 2.7:1 | **ACCEPTABLE** (HVA defense) |
| Patriot vs TBM | $4M | $3M | 1.3:1 | **FAVORABLE** |
| Meteor vs 4th-gen fighter | $2M | $50M | 0.04:1 | **EXCELLENT** |

### Key Saturation Principle

100x Shahed-136 ($5M total) forces $400M+ in Patriot interceptors if no lower-cost alternatives exist. **Mixed salvos** (cheap drones + expensive cruise missiles) force defenders to either:
1. Expend premium interceptors on cheap targets, OR
2. Accept hits while triaging

**Decision rules:**
- Cost ratio > 20:1 against low-value targets → **mandate cheaper alternative**
- Interceptor inventory depletion is a strategic objective for attacker → **reserve management critical**
- Tiered response: match interceptor cost to threat value
