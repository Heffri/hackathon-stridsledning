# Swedish Air Defense Doctrine & Engagement Logic

> Principles for realistic decision-making in the simulation.

## 1. Layered Defense Principle

Swedish air defense operates in concentric layers. Each layer handles specific threat bands:

```
Layer 0: AEW&C (GlobalEye)     — Detect at 450-650 km, cue all layers
Layer 1: Fighter intercept      — Engage at 150-200 km (Meteor BVR)
Layer 2: Long-range SAM          — Engage at 40-70+ km (Patriot)
Layer 3: Medium-range SAM        — Engage at 15-40 km (IRIS-T SLM)
Layer 4: Short-range SAM         — Engage at 2-15 km (IRIS-T SLS, RBS 70)
Layer 5: SHORAD/SPAAG            — Engage at 0.5-4 km (Lvkv 90 gun)
```

**Key rule**: A threat should be engaged at the **outermost effective layer**. If it leaks through, the next layer picks it up. The system must track "leakers" and reassign.

## 2. Asset-Threat Matching Rules

### Cost-Exchange Ratio
Never use a high-value interceptor on a low-value target if alternatives exist:
- Patriot missile ($3-4M) should NOT engage a $500 FPV drone
- Lvkv 90 40mm rounds ($200/rd) ARE appropriate for FPV drones
- Gripen sortie (fuel + Meteor at $2M+) should target high-value threats

### Engagement Priority Matrix

| Threat | Primary Response | Secondary | Avoid Using |
|--------|-----------------|-----------|-------------|
| Ballistic missile | Patriot PAC-3 | — | Everything else (can't reach it) |
| Cruise missile (subsonic) | IRIS-T SLM | Gripen intercept | Patriot (overkill), SPAAG (too fast) |
| Cruise missile (supersonic) | Patriot | Gripen (if enough warning) | Short-range (too fast) |
| Fighter aircraft | Gripen + Meteor | Patriot (if in range) | Short-range SAM |
| MALE/HALE UAV | IRIS-T SLM/SLS | Gripen (if nearby) | Patriot (waste) |
| FPV / small drone | Lvkv 90 (gun) | RBS 70 | Patriot, IRIS-T SLM |
| Loitering munition | Lvkv 90, IRIS-T SLS | RBS 70 | Patriot |
| SEAD/ARM missile | Radar shutdown + relocate | IRIS-T SLS (if detected) | Keep radar on |

## 3. Three-Layer Response Model (Soft Kill → Evade → Hard Kill)

Before committing kinetic interceptors, the system evaluates cheaper alternatives in order:

### Layer 1: Soft Kill (Electronic Warfare)

Use EW to degrade or defeat threat guidance without expending munitions.

**Guidance vulnerability table:**

| Guidance Type | EW Effectiveness | Notes |
|---------------|-----------------|-------|
| GPS/GNSS + INS (Shahed-136 baseline) | **High** | Jamming degrades CEP significantly; spoofing can redirect. INS drift accumulates |
| GPS/GNSS + INS + camera/AI (Shahed upgraded/Geran-2) | **Medium** | GPS jam still degrades midcourse, but camera/AI terminal guidance can correct — partial resistance |
| GPS/INS combo (cheap cruise missiles) | **Medium** | GPS denied → falls back to INS, drift accumulates over time |
| INS only | **None** | Pre-programmed, no external signal to jam |
| Active radar seeker (Kalibr terminal) | **Low-Medium** | Noise jamming possible but seeker designed to resist |
| IR imaging seeker (IRIS-T class) | **None** | Passive sensor, no emission to jam |
| Laser beam riding (RBS 70) | **None** | Friendly system, not jammable by design |
| Fiber-optic FPV | **None** | Physical link, no RF to jam |

**EW assets (abstract):**

```
ew_jammer:
  type: ew_ground | ew_airborne
  coverage_radius_km: 50         # [est, depends on power]
  effectiveness:                 # probability of degrading guidance
    gps: 0.80
    gps_ins: 0.50               # GPS denied, INS remains
    active_radar: 0.30
    ir: 0.0
    beam_riding: 0.0
    fiber: 0.0
  friendly_impact:               # also affects friendly GPS in coverage
    friendly_gps_degraded: true
    mitigation: directional_antenna | military_m_code
```

**Key constraint:** EW is area-effect — it degrades friendly GPS too. Mitigations:
- Directional jamming (beam toward threat axis)
- Friendly forces use military GPS M-code (jam-resistant)
- Zone planning: EW denial zone forward, clean GPS zone rear

**Decision rule:** If threat guidance_type is GPS-only and EW assets are available → apply EW first, potentially avoid kinetic engagement entirely.

### Layer 2: Evade (Relocate)

If the threat cannot track moving targets (no seeker), mobile assets can simply move.

**Evasion viability table:**

| Threat | Seeker | Can track movers? | Evade viable? |
|--------|--------|-------------------|---------------|
| Shahed-136 (GNSS) | None (pre-programmed coords) | **No** | **Yes** — drive away |
| Kalibr (terminal active radar) | Yes | Yes | No — it will follow |
| Iskander-M (terminal guided) | Yes | Yes | No |
| FPV (operator-guided) | Yes (camera) | Yes | No |
| SEAD/ARM (anti-radiation) | Yes (radar homing) | Tracks emission source | **Yes** — shut down radar and move |

**Evasion decision rule:**
```
IF threat.seeker == none AND target_asset.mobility != static:
  → RECOMMEND: evade (relocate asset)
  → COST: fuel only
  → REQUIREMENT: sufficient warning time (distance / threat_speed > relocate_time)
```

**Warning time calculation:**
```
warning_time = detection_range / threat_speed
relocate_time = asset.relocate_time_s

IF warning_time > relocate_time * 1.5:  # 50% safety margin
  → evasion_feasible = true
```

Example: Shahed at 150 km, speed 45 m/s → 55 min warning. IRIS-T SLM relocate 40 min → feasible with margin.

### Layer 3: Hard Kill (Kinetic Intercept)

Expend munitions only when soft kill and evasion are not viable or insufficient.

Apply cost-exchange rules from Section 2. Use cheapest effective interceptor.

### Combined Decision Flow

```
threat_detected:
  1. CAN EW DEGRADE IT?
     → guidance == gps/gnss → YES → apply EW
       → if EW success probability > 0.7 AND target is low-value:
           DONE (let it miss, save ammo)
       → if defending fixed HVA: continue to layer 3 as backup
     → guidance == active_radar/ir/fiber → NO → skip to layer 2

  2. CAN WE EVADE?
     → threat has no terminal seeker AND asset is mobile
       AND warning_time > relocate_time?
       → YES → relocate asset, let threat hit empty ground
     → NO → continue to layer 3

  3. HARD KILL (last resort)
     → apply cost-exchange rules
     → select cheapest effective interceptor
     → engage
```

---

## 4. Resilient Defense & Asset Value Assessment

### Principle: Defend What's Worth Defending

Rigid defense (protect everything at all costs) loses to attrition. Resilient defense accepts that some assets will be hit and optimizes for overall force survival.

**Defense ROI calculation:**
```
defense_cost = interceptors_expended + IADS_exposure_risk + opportunity_cost
asset_value  = replacement_cost + downtime_strategic_impact + political_cost

IF defense_cost > asset_value → RECOMMEND: evacuate or accept loss
IF defense_cost < asset_value → RECOMMEND: defend
```

### Resilience Hierarchy (Reduce Need for Defense)

Before spending interceptors, reduce the number of things that need defending:

| Strategy | Example | Effect |
|----------|---------|--------|
| **Mobilize** | Gripen → road bases, SAMs → relocate | No fixed target to hit |
| **Disperse** | Split one ammo dump into 5 small caches | Single strike can't destroy all |
| **Harden** | Underground C2 bunkers | Survives anything short of bunker-buster |
| **Make redundant** | Backup C2 nodes, mesh communications | Losing one node doesn't break the network |
| **Deceive** | Decoy emitters, inflatable SAM mockups | Red wastes munitions on fakes |

After applying these, the truly irreplaceable fixed targets shrink dramatically.

### Asset Replaceability Classification

| Category | Examples | Defense Priority |
|----------|----------|-----------------|
| **Irreplaceable** | GlobalEye ($300M, 3 in inventory), national C2 hub | Maximum — worth PAC-3 salvos |
| **Hard to replace** | Patriot battery, major radar site | High — defend with proportional force |
| **Replaceable (weeks)** | Grid substation, fuel depot | Medium — defend if cheap, accept loss if expensive |
| **Replaceable (days)** | Road base supplies, small generator | Low — relocate/disperse instead |
| **Expendable** | Decoys, forward observation posts | None — let them be hit |

### "Concede and Exhaust" Strategy

When Red commits disproportionate resources to destroy a low-value target:

```
Red launches 2x Iskander-M ($10M+ each) at a regional power substation ($2M)
  → Blue has no THAAD, Patriot Pk vs Iskander uncertain
  → Defense cost (4x PAC-3 MSE at $4M each = $16M) > asset value ($2M)
  → RECOMMEND: evacuate personnel, accept loss
  → RATIONALE: Red spent $20M to destroy $2M — unsustainable for Red at scale
  → FOLLOW-UP: deploy mobile generators, reroute grid
```

The system should recognize when **letting Red "win" a tactical exchange actually wins the strategic exchange**.

### Dynamic Protection Threshold

Protection level should adapt based on:

```
current_ammo_state:
  IF ammo_reserves > 70%: defend medium+ value targets
  IF ammo_reserves 30-70%: defend high+ value targets only
  IF ammo_reserves < 30%: defend irreplaceable targets only, conserve everything else

threat_tempo:
  IF multi-wave attack detected:
    → raise defense threshold (save ammo for later waves)
    → concede low-value targets in early waves
  IF single isolated threat:
    → normal threshold
```

### Swedish Doctrine Alignment

This approach aligns with Sweden's existing military philosophy:
- **Gripen road basing**: Don't give the enemy a juicy airfield target
- **Dispersed operations**: Spread assets so no single strike is decisive
- **Total defense concept (Totalförsvar)**: Civilian infrastructure has redundancy built in
- **Accepting losses to preserve combat power**: Better to lose a substation than a Patriot battery

---

## 5. SEAD/DEAD Evasion

Anti-radiation missiles (ARMs) home on radar emissions. Defense doctrine:

1. **Emit-and-move**: Radar on → detect → fire → radar off → relocate
2. **Radar rotation**: Alternate which sites emit. Never have all radars on simultaneously
3. **Emission time budget**: Track cumulative radar-on time. Above threshold → mandatory shutdown
4. **Decoy emitters**: (Future feature) Deploy dummy radar sources
5. **Close-in protection**: Every SAM site needs SHORAD escort (Lvkv 90, RBS 70) against ARMs that arrive after radar shutdown

**Simulation rule**: If an asset has `radar_on = true` for > threshold_seconds, SEAD threat probability increases proportionally.

## 6. Mixed Defense Group Composition

### Principle: No High-Value SAM Site Operates Alone

Every major SAM position needs layered local protection. The SAM site itself handles medium/long range threats — but it needs escorts to handle close-in threats (drones, ARMs, leakers) and to prevent recon UAVs from mapping its position.

### Standard Defense Group Templates

**Template A: Long-Range SAM Group (around Patriot)**
```
OUTER RING (3-5 km radius):
  1-2x IRIS-T SLM battery        — medium-range cover, catches what Patriot shouldn't waste ammo on
  2-3x Lvkv 90                   — 40mm 3P airburst vs drones, loitering munitions
  
INNER RING (within 1-2 km of Patriot):
  2x Lvkv 90                     — point defense, last line before anything reaches Patriot
  2-3x RBS 70 NG / IRIS-T SLS    — passive IR/laser engagement, no radar emission
  
CORE:
  Patriot PAC-3 battery           — fires only at ballistic missiles, supersonic cruise, high-value threats
  AN/MPQ-65 radar                 — on MINIMUM duty cycle (see Section 12.5)
```

**Template B: Medium-Range SAM Group (around IRIS-T SLM)**
```
ESCORT (1-3 km radius):
  1-2x Lvkv 90                   — point defense vs drones
  1-2x RBS 70 NG                 — passive engagement, no radar signature
  
CORE:
  IRIS-T SLM battery              — main engagement asset
  TRML-4D                         — burst scanning only (3s on, 30s off)
```

**Template C: Forward Patrol Group (front line screen)**
```
2-3x Lvkv 90                     — PS-95 radar for local awareness + 40mm 3P
2-3x RBS 70 NG / IRIS-T SLS      — passive missile engagement
2-4x IFV with autocannon          — cheap vehicles with VT/AHEAD-type ammo, no dedicated radar
                                    (e.g., CV90 variants with 30-40mm cannon)

Tasks:
  - Patrol designated sectors
  - Engage recon UAVs (Orlan-10 class) to prevent IADS mapping
  - Engage loitering munitions and FPV drones heading for rear areas
  - If facing threats too large to handle → report and withdraw
  - DO NOT engage with methods that reveal rear SAM positions
  - These groups are relatively expendable — they protect by being forward, not by being invulnerable
```

### Core Operating Principle

```
Forward patrol groups:  SCREEN — prevent recon, kill cheap targets, absorb first contact
Middle ring:            PROTECT — local defense of SAM sites, catch leakers
SAM sites:              ENGAGE — only fire at threats worth the ammo cost, minimum radar exposure
```

The decision support system manages this hierarchy: it should **never recommend Patriot engagement against a target that a forward Lvkv 90 can handle**, and it should **alert if a recon UAV is approaching a SAM site unengaged**.

---

## 7. GlobalEye Protection Doctrine

GlobalEye is the single most valuable Blue asset (~$300M, only 3 in Swedish inventory). Loss of GlobalEye = loss of situational awareness = cascading failure of entire IADS. Protection is absolute priority.

### 6.1 Network-Centric Engagement ("A Shoots, B Guides")

The data link architecture enables **separation of sensor and shooter**:

```
Detection:   GlobalEye Erieye ER detects target at 500+ km
Tracking:    GlobalEye maintains continuous track, shares via TIDLS
Launch:      Gripen fires Meteor — own radar OFF (Silent Attack)
Midcourse:   GlobalEye sends track updates → Gripen relays → Meteor adjusts
Terminal:    Meteor activates own active radar seeker at ~20 km from target
```

**Critical implications for simulation:**
- Gripen with GlobalEye support has ZERO radar emission during BVR engagement
- Enemy ESM/RWR cannot detect or locate the launching fighter
- Multiple Gripen can fire simultaneously using the same GlobalEye track
- Gripen can turn away ("crank") immediately after launch — GlobalEye maintains guidance
- If GlobalEye is lost mid-engagement, Meteor falls back to own seeker (reduced Pk, but not zero)

**System must model:**
```
engagement_mode:
  autonomous:    # fighter uses own radar — detectable, SEAD risk
    pk_modifier: 1.0
    radar_emission: true
  silent_attack: # GlobalEye provides guidance — undetectable
    pk_modifier: 0.95    # slight reduction from relay latency
    radar_emission: false
    requires: globaleye_track_quality >= firm
```

### 6.2 Continuous Escort (CAP Rotation)

GlobalEye must have fighter escort at ALL times. Specifically Gripen F (two-seat):

**Why Gripen F (two-seat):**
- Weapons Systems Officer (WSO) in rear seat can:
  - Offload tactical C2 tasks from GlobalEye operators
  - Manage loyal wingman drone formations (up to 3 drones per Gripen F)
  - Operate EW/ECM systems during defensive actions
  - Coordinate with GlobalEye crew on threat prioritization
- Pilot focuses purely on flying and weapons delivery

**Escort composition:**
```
globaleye_cap:
  escort_fighters: 3-4x Gripen F (two-seat)
  loadout_per_fighter:
    meteor: 4-6          # BVR (reduced from max to make room for tanks)
    iris_t: 2            # WVR
    drop_tanks: 2        # extended endurance critical
    cannon: full
  loyal_wingman: 3 per Gripen F  # 9-12 drones total in escort package
  rotation: seamless     # fresh pair takes over before current pair hits bingo fuel
  
  # Rotation math:
  # Gripen F endurance with drop tanks: ~3-4 hrs on station
  # Need 2 fighters on station at all times minimum
  # With transit time, need 3-4 fighters total in rotation cycle
  # Assumes 2+ road bases within range for recovery/rearm
```

### 6.3 Threat Response Escalation (Protect at All Costs)

When GlobalEye is under direct attack, response escalates through five levels:

**Level 1: Stand-off BVR Intercept (Normal)**
- Escort Gripen F engage incoming threats at maximum range
- Silent Attack via GlobalEye's own sensors
- Loyal wingman drones used as forward sensor/shooter nodes

**Level 2: Ground IADS Emergency Activation**
- If escort Gripen cannot handle threat volume:
- Ground SAM sites along GlobalEye's orbit path **force-activate radars**
- Accept SEAD exposure risk — GlobalEye survival outweighs SEAD risk
- IRIS-T SLM / Patriot engage any threats within their range

**Level 3: Active Missile Defense (Shoot the Missile)**
- Against incoming long-range AAMs (R-37M class):
- Escort Gripen and drones attempt to **intercept the incoming missile** with own weapons
- IRIS-T has 60G maneuverability — theoretically capable of engaging a maneuvering missile
- Low Pk per attempt, but multiple shooters improve odds

**Level 4: Drone Sacrifice + ECM**
- If escort missiles expended:
- WSO in Gripen F directs loyal wingman drones to:
  - Deploy chaff/flares in the path of incoming missile
  - Activate onboard ECM to jam missile's active radar seeker
  - Physically position themselves between missile and GlobalEye as decoys
  - Expendable drones are designed for this — each one costs a fraction of GlobalEye
- Gripen F simultaneously performs maximum ECM from Arexis suite

**Level 5: Manned Aircraft Self-Sacrifice (Last Resort)**
- If all drones expended and threat still inbound:
- Escort Gripen F pilots maneuver to draw incoming missiles away from GlobalEye
- Deploy own chaff/flares, maximize ECM, present themselves as more attractive target
- **Rationale**: 2 crew vs 11+ crew on GlobalEye + $300M asset + loss of entire air picture
- System should flag this as last resort but not exclude it from recommendations

```
globaleye_defense_escalation:
  level_1_bvr:
    trigger: threat detected heading toward GlobalEye
    action: escort engages at max range via Silent Attack
    cost: missiles only
  level_2_ground_iads:
    trigger: escort overwhelmed OR threat count > escort capacity
    action: activate ground SAM along orbit path, accept SEAD risk
    cost: SEAD exposure + SAM missiles
  level_3_missile_intercept:
    trigger: incoming AAM detected, closing fast
    action: escort + drones attempt to shoot down incoming missile
    pk_per_attempt: 0.15-0.30  # very difficult shot
    cost: escort missiles
  level_4_drone_sacrifice:
    trigger: escort missiles expended, threat still inbound
    action: WSO directs drones as ECM decoys / physical shields
    cost: drones destroyed (acceptable)
  level_5_manned_sacrifice:
    trigger: all drones gone, missile still inbound, no other option
    action: escort Gripen draws missile away from GlobalEye
    cost: potential loss of crew + fighter
    authorization: automatic (pre-authorized by escort role)
```

### 6.4 Standoff Distance Management

**Hard rule: GlobalEye stays outside enemy max weapon range + safety margin AT ALL TIMES.**

Known long-range air-to-air threats:

| Weapon | Published Range | Proven/Estimated Real Range | Required Standoff |
|--------|----------------|---------------------------|-------------------|
| R-37M | 300+ km (marketing) | ~200 km (Ukraine combat evidence, against large RCS) | **250+ km** |
| R-77-1 | 110 km | ~80-100 km effective | 150 km |
| PL-15E (reference) | 145 km (export spec) | ~200 km claimed (2025 Op Sindoor, Pakistani/RUSI claim — disputed by Indian/US analysts) | N/A (not in theater, but lesson applies) |

**Standoff calculation:**
```
min_standoff_km = max_enemy_weapon_range_proven * 1.15 + 30
  # 15% margin + 30 km buffer for unknowns

For R-37M: 200 * 1.15 + 30 = 260 km minimum standoff

# Additional factors:
# - GlobalEye RCS is HUGE (large business jet + 10m radar plank)
#   → enemy missiles get better Pk at range against large targets
# - R-37M specifically designed for AWACS/tanker hunting
# - NEVER trust published max range — it's marketing, not combat data
```

**Lessons from India-Pakistan (2025 Operation Sindoor):**
- Pakistani J-10CE reportedly fired PL-15E at Indian Rafale ("Godzilla 4") from ~200 km
  (Pakistani/RUSI claim; disputed by Indian analysts and US expert Michael Dahm)
- Indian intel assessed PL-15E max range at ~150 km (based on published export specs of 145 km)
- Rafale crew reportedly believed they were outside engagement envelope
- PL-15E's AESA seeker is LPI (Low Probability of Intercept) — Rafale's SPECTRA EW suite failed to provide adequate warning
- PL-15 lofts to high altitude, then dives at supersonic speed from above — worst angle for target's RWR
- Result: first-ever combat loss of a Rafale, first combat use of PL-15
- **Takeaway**: NEVER trust published/export weapon specs as actual max range. Assume 15-30% beyond what you think it is. Export specs may be deliberately conservative or the actual variant supplied may differ.

**GlobalEye orbit planning:**
```
orbit_constraints:
  min_distance_from_threat_axis: 260 km  # hard floor
  preferred_distance: 300 km             # comfortable margin
  orbit_orientation: perpendicular to threat axis
    # minimizes time spent with 60° blind zone toward enemy
  orbit_altitude: 35,000 ft              # maximize radar range
  orbit_pattern: racetrack
    # turns should keep threat axis within 300° radar coverage at all times
    # never turn nose/tail toward threat direction (blind zone!)
```

### 6.5 Emergency Retreat Procedure

If GlobalEye crew determines attack is imminent or escort is overwhelmed:

```
1. TURN AWAY — fly toward friendly territory immediately
   - Direction: toward nearest friendly IADS coverage
   - Max speed (Mach 0.85)

2. ALERT GROUND IADS — notify SAM sites along retreat path
   - SAM sites activate radars to create defensive corridor
   - Accept SEAD risk — GlobalEye survival is priority
   
3. SCRAMBLE REINFORCEMENTS — nearest available Gripen
   - Emergency scramble from closest road base / airfield
   - Directed to intercept threats pursuing GlobalEye
   - Priority: cut off low-altitude attackers that might sneak under radar

4. MAINTAIN SENSOR FUNCTION — keep Erieye ER operating during retreat
   - GlobalEye is still the primary sensor even while retreating
   - Rear-hemisphere coverage (within 300° arc) maintained
   - Continue feeding track data to all Blue assets

5. IF MISSILE INBOUND — execute defense escalation (6.3)
   - Escort enters protection mode
   - Ground IADS along path engages
```

**Low-altitude threat consideration:**
- Enemy fighters could attempt low-altitude approach under Erieye coverage floor
- Ground radar (TRML-4D) and Gripen look-down capability fill this gap
- Emergency scramble specifically tasks interceptors to sweep low-altitude corridors between GlobalEye and threat axis

### 6.6 Simulation Parameters

```
globaleye_protection:
  # Escort
  min_escort_strength: 2           # Gripen F on station at all times
  desired_escort_strength: 4       # with rotation
  drones_per_escort: 3             # loyal wingman per Gripen F
  escort_endurance_s: 12600        # ~3.5 hrs with drop tanks [est]
  rotation_overlap_s: 1800         # 30 min handover period

  # Standoff
  min_standoff_km: 260             # hard floor vs R-37M
  preferred_standoff_km: 300
  orbit_altitude_ft: 35000
  blind_zone_deg: 60               # nose+tail, never toward threat

  # Defense escalation thresholds
  level_2_trigger: escort_ammo_pct < 50 OR threat_count > 4
  level_3_trigger: incoming_missile_detected
  level_4_trigger: escort_ammo_pct == 0
  level_5_trigger: drones_remaining == 0 AND missile_still_inbound

  # Value (for defense ROI calculation)
  globaleye_value: 30000           # highest value asset in system
  globaleye_replaceability: irreplaceable
```

---

## 8. Ammunition Management

Ammunition is finite. The system must:

1. **Track remaining rounds** for every asset
2. **Project depletion time** based on current engagement rate
3. **Recommend conservation**: If ammo drops below threshold, suggest:
   - Switch to guns (Lvkv 90) for low-value targets
   - Request fighter rearmament sortie
   - Redistribute coverage from well-stocked units
4. **Rearm priority**: Which unit to rearm first based on coverage gap analysis

## 9. Fighter Operations: CAP Rotation ("Volley Fire")

### Concept: Continuous Air Presence via Rotation

Like musket-era volley fire — one line fires while others reload. The number of tiers scales with available aircraft: 3 tiers minimum (small force), 4-5 tiers for larger forces. Example with 4 tiers:

```
Tier 1: FRONT LINE (on station, engaging)
  ├── 3/4 air superiority loadout (Meteor + AMRAAM + IRIS-T)
  ├── 1/4 CAS/SEAD loadout (SDB + HARM/anti-radiation + self-defense AAM)
  └── Task: BVR intercepts, SEAD suppression, high-value target strikes

Tier 2: REAR PATROL (on station, defensive)
  ├── Pure air superiority loadout
  └── Task: intercept border-crossers (fighters, armed UAVs, helicopters),
            protect rear area, backup for Tier 1 if overwhelmed

Tier 3: INBOUND (en route to replace Tier 1)
  ├── Loadout configured based on CURRENT frontline situation
  │   (system recommends loadout based on active threats)
  └── Task: transit to Tier 1 position, assume station as Tier 1 returns

Tier 4: HOME BASE (just landed, rearming/refueling)
  ├── Quick turnaround: 15-25 min (Saab official)
  └── Task: rearm, refuel, crew rest (if available), prepare for Tier 3
```

### Rotation Cycle

```
Time 0:00   Tier 1 on station (2-4 fighters)
            Tier 2 on station (2 fighters)
            Tier 3 departing base
            Tier 4 rearming

Time 1:30   Tier 1 approaching bingo fuel / ammo expended
            Tier 3 arrives at Tier 1 position → becomes new Tier 1
            Old Tier 1 RTB → becomes Tier 4

Time 1:45   Old Tier 4 finished rearm → becomes new Tier 3 (departs)

Cycle continues indefinitely...
```

### High-Intensity Rotation Math

```
cap_rotation:
  tier_1_strength: 4           # front line
  tier_2_strength: 2           # rear patrol
  tier_1_endurance_s: 7200     # ~2 hrs on station with drop tanks
  turnaround_time_s: 1500      # 25 min (Saab official, conservative)
  transit_time_s: 1800         # ~30 min each way [est]
  
  # Minimum fleet for continuous Tier 1 + Tier 2:
  # Tier 1: 4 on station + 4 inbound + 4 rearming = 12
  # Tier 2: 2 on station + 2 rearming = 4
  # Total: ~16 fighters for 24/7 ops (not counting GlobalEye escort)
  # With 6 Gripen available (scenario): can sustain ~4-6 hrs before exhaustion
```

### Loadout Decision Logic

Tier 3 (inbound replacements) loadout should adapt to current situation:

| Front Line Situation | Recommended Tier 3 Loadout |
|---------------------|---------------------------|
| Enemy fighters active | Max BVR (7 Meteor + 2 IRIS-T) |
| Enemy fighters + SEAD needed | Mixed (4 Meteor + 2 AMRAAM + HARM + 2 IRIS-T) |
| Mainly drones/cruise missiles | Mixed BVR + gun focus |
| Enemy ground targets of opportunity | CAS heavy (SDB + Maverick + 2 Meteor self-defense) |
| Unknown / first sortie | Standard mixed BVR (5 Meteor + 2 AMRAAM + 2 IRIS-T) |

### Emergency Scramble vs Planned Rotation

| Situation | Action |
|-----------|--------|
| Planned rotation | Normal: Tier 3 departs on schedule |
| Tier 1 overwhelmed | Emergency: Tier 2 moves forward to support, Tier 4 (even if not fully armed) scrambles |
| Base under attack | **Emergency scramble ALL serviceable aircraft** — get them airborne before runway is hit |
| GlobalEye threatened | Divert nearest Tier 1/2 fighters to escort reinforcement |

### Emergency Base Dispersal

When intelligence indicates air base strike imminent:

```
1. SCRAMBLE: All flight-ready aircraft launch immediately
   - Even unarmed / partially armed — survival > loadout
   - Fly to pre-designated holding areas

2. DISPERSE: Ground vehicles and mobile SAM relocate away from base
   - Fuel trucks, ammo, maintenance equipment → pre-positioned road bases

3. RECOVER: Aircraft divert to road bases for rearm
   - Gripen road base capability is critical here
   - Multiple road bases = no single point of failure
   - 15-25 min turnaround at road base with prepared crew

4. RESUME: Continue CAP rotation from dispersed road bases
   - Longer transit times, but survivable
```

**2025 lesson (India-Pakistan):** Reports suggest Pakistani Erieye AEW&C may have been destroyed on the ground, not in the air. Reinforces: **never let high-value assets sit on a runway when attack is possible**.

## 10. Forward Planning (Look-Ahead)

The system should NOT be purely reactive. It must:

1. **Predict resource state** N minutes into the future
2. **Identify coverage gaps** that will emerge after engagements
3. **Recommend pre-positioning**: Move mobile units to fill predicted gaps
4. **Reserve management**: Keep a strategic reserve (e.g., 2 Gripen on ground alert) for unexpected threats
5. **Wave analysis**: If detecting multi-wave attacks, conserve resources for subsequent waves

## 11. Rules of Engagement (Simplified for Sim)

1. AEW&C (GlobalEye) is NEVER a combatant — it detects and coordinates only
2. Fighters may engage only targets classified as hostile (not "unknown")
3. SAMs engage automatically within their assigned sectors unless overridden
4. Commander can override any automated assignment
5. Civilian aircraft corridors must be respected (no engagement in designated safe lanes)

## 12. Swedish Dispersed Operations Concept

Gripen is designed for dispersed operations:
- Can operate from road bases (straight highway segments)
- Turnaround time: ~10 minutes (refuel + rearm by conscript crew of 5-6)
- Multiple road bases reduce single-point-of-failure risk
- Simulation should model multiple dispersed bases, not just one main airfield

## 13. Distributed Sensor Network & Network-Centric Warfare

### 12.1 Core Principle: Every Radar is a Sensor Node

The system does not depend on any single sensor. Every unit with a radar or sensor contributes to a shared picture via data links:

```
                    ┌─────────────────────────┐
                    │   TDFE Fused Picture     │
                    │  (one track per target)  │
                    └────────┬────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
   │ Tier 1  │         │ Tier 2  │         │ Tier 3  │
   │ Deep    │         │ Battle  │         │ Forward │
   │ Rear    │         │ Zone    │         │ Edge    │
   └─────────┘         └─────────┘         └─────────┘
   GlobalEye            TRML-4D             Recon UAVs
   (300 km behind)      Raven ES-05         Civilian AESA
                        PS-95               EO/IR sensors
```

**Every unit with a radar shares track data**, not just GlobalEye:
- Gripen ES-05 radar → shares tracks to network
- TRML-4D (IRIS-T SLM) → shares tracks
- PS-95 (Lvkv 90) → shares tracks
- RBS 70 UTAOS thermal sight → passive detection, shares bearing
- Recon UAVs → shares radar/EO tracks
- Civilian AESA weather radar (modified) → shares tracks

### 12.2 Tiered Sensor Architecture

**Problem:** GlobalEye at 300+ km standoff has degraded detection against small/low-altitude targets at the front line. Detection range drops with distance, altitude, and target size.

**Solution:** Layered sensor tiers, with expendable assets closest to enemy.

| Tier | Distance from Front | Assets | Expendability | Role |
|------|-------------------|--------|---------------|------|
| **Tier 3: Forward Edge** | 0-50 km | Recon UAVs, civilian AESA nodes, EO/IR posts | **Expendable** | "Torches" — illuminate the front line |
| **Tier 2: Battle Zone** | 50-150 km | Gripen (on CAP), TRML-4D, Lvkv 90 PS-95 | **Valuable but mobile** | Main engagement sensors, shoot-and-scoot |
| **Tier 1: Deep Rear** | 150-300+ km | GlobalEye, ground C2 | **Irreplaceable** | Fusion hub, deep look, C2 |

**Key insight:** The closer a sensor is to the front, the cheaper and more expendable it should be. GlobalEye provides the deep picture; forward UAVs provide the close picture. Together they cover all threat types and altitudes.

### 12.3 Forward Sensor UAVs ("Torches")

Deploy cheap radar/EO-equipped UAVs as forward sensor nodes:

```
recon_uav_sensor:
  type: uav_recon
  radar: small AESA or SAR (~30-50 km detection range) [est]
  eo_ir: yes
  data_link: yes — feeds tracks to TDFE
  endurance_s: 28800        # 8 hrs [est, MALE class]
  altitude_m: 5000-8000
  speed_mps: 50
  rcs_m2: 0.3-1.0
  cost: low (relative to GlobalEye)
  expendable: true          # expected to be shot down — plan for losses
  
  # Deployment:
  # 4-6 UAVs on rotating station along front line
  # spaced to overlap coverage
  # each feeds tracks to TDFE → GlobalEye → all Blue assets
  # if one is shot down, adjacent UAVs cover the gap
```

**What they provide that GlobalEye can't from 300 km:**
- Low-altitude detection (sea-skimming cruise missiles, FPV drones)
- Small RCS target detection at close range
- EO/IR identification (visual confirmation of threat type)
- Expendable radar emission (draws SEAD attention away from high-value radars)

**If shot down:** Expected. Replace with next drone in rotation. Each loss tells you something — the kill location reveals enemy fighter or SAM positions.

### 12.4 Civilian AESA Weather Radar Exploitation

**Concept:** Modern civilian AESA weather radars (compact types already deployed in parts of China and Europe) can be repurposed as low-cost IADS sensor nodes with data link modifications.

**Why this works:**
- AESA is AESA — the physics is the same whether it's tracking rain clouds or aircraft
- Modern weather AESA radars operate in C-band or X-band — same bands as military surveillance radars
- They already have sophisticated signal processing for clutter rejection
- They are CHEAP compared to military radars ($0.5-2M vs $20-50M+)
- They are numerous — many sites already exist throughout Swedish territory
- With data link integration, they become nodes in the TDFE fusion network

**What they CAN do (with modification):**
- Detect aircraft-sized targets at medium range (~50-100 km) [est]
- Detect large slow targets (Shahed, MALE UAV) at shorter range
- Provide track data (position + velocity) via data link
- Act as additional radiation sources (diluting SEAD targeting)

**What they CANNOT do:**
- Fire control quality tracking (not precise enough for missile guidance)
- Detect stealth targets (not enough power/sensitivity)
- Survive a dedicated attack (unhardened, fixed location)

**Strategic value as SEAD sponges:**

```
Scenario: Red launches 4x Kh-31P anti-radiation missiles
  
Without civilian radars:
  → ARMs home on TRML-4D and AN/MPQ-65 (your only emitters)
  → 2 high-value radars destroyed
  
With 20 civilian AESA nodes active:
  → ARMs see 22+ radiation sources across the spectrum
  → Kh-31P homes on the strongest / most "military-looking" signal
  → Civilian radars at full power attract ARMs away from military radars
  → Military radars operate at low power or intermittent mode
  → Even if 4 civilian nodes destroyed: $2-8M loss vs $40-100M+ for military radars
  → IADS intact, weather service loses a few nodes (replaceable in weeks)
```

**Operational concept:**
```
civilian_aesa_node:
  type: sensor_civilian
  radar_type: aesa_weather (modified)
  band: c_band or x_band
  detection_range_km: 80           # vs fighter-size target [est]
  detection_range_small_km: 30     # vs Shahed-class [est]
  track_quality: surveillance      # NOT fire control
  data_link: modified (feeds to TDFE)
  mobility: static (fixed installation)
  hardened: false
  cost: 50-200                     # abstract units (very cheap)
  expendable: true                 # acceptable loss
  sead_decoy_value: high           # attracts ARMs away from military radars
  
  # Operational modes:
  # - continuous: always on, maximum SA contribution, maximum SEAD attraction
  # - scheduled: on/off cycling synchronized with military radar schedule
  # - bait: deliberately high-power emission to attract ARMs
```

### 12.5 Integrated Radar Emission Management

Combining military radars, civilian nodes, and forward UAVs enables sophisticated emission control:

```
Radar emission schedule (per 60-second cycle):

T+0s:   Civilian AESA nodes: ON (continuous, full power)
         Forward UAVs: ON (radar + EO)
         GlobalEye Erieye: ON (always, but 300+ km from threat)
         TRML-4D: OFF
         AN/MPQ-65: OFF
         → Fused picture from civilian + UAV + GlobalEye = adequate SA

T+15s:  TRML-4D Alpha: ON (3-second burst scan)
         → High-quality track update, correlate with civilian data
T+18s:  TRML-4D Alpha: OFF (relocate if needed)

T+30s:  TRML-4D Bravo: ON (3-second burst scan)
T+33s:  TRML-4D Bravo: OFF

T+45s:  Continue cycle...

Fire control activation:
  → ONLY when engagement decision made
  → Minimum time on: fire, guide, shut down
  → Civilian radars remain on throughout (mask military emissions)
```

**Result:** Military radars are on for seconds per minute. Civilian radars and UAVs provide continuous SA. SEAD missiles see mostly civilian emissions. Military radar positions stay hidden until the moment of engagement.

### 12.6 Data Link Architecture Summary

```
data_link_network:
  backbone: TIDLS (Gripen ↔ GlobalEye, high bandwidth)
  nato_interop: Link 16 (broadcast to all NATO assets)
  ground: national air defense network (StriC / LuLIS)
  
  contributors:
    globaleye:     erieye_er + seaspray + eo_ir + esm → TDFE
    gripen:        es_05 + ew_suite → TIDLS → TDFE
    trml_4d:       360° ground surveillance → ground network → TDFE
    ps_95:         lvkv_90 local air picture → ground network → TDFE
    rbs_70_utaos:  passive thermal tracks → ground network → TDFE
    recon_uav:     radar + eo_ir → data link → TDFE
    civilian_aesa: modified weather radar → data link → TDFE
    
  fusion_output:
    → single recognized air picture for all Blue assets
    → track confidence: single_sensor (tentative) → two+ (firm) → three+ (precise)
    → every shooter can see every track
    → "any sensor to any shooter" architecture

  silent_attack:
    → GlobalEye detects → Gripen fires Meteor radar-silent
    → GlobalEye provides midcourse guidance via TIDLS relay
    → target cannot detect launching fighter
    → KEY Saab selling point — highlight in demo
```

### 12.7 Simulation Parameters

```
sensor_network:
  # Tier 3: Forward
  forward_uav_count: 4-6
  forward_uav_coverage_km: 50       # per UAV
  forward_uav_replacement_rate: 1 per 4 hours [est, attrition]
  civilian_aesa_count: 10-20        # across defended territory
  civilian_aesa_range_km: 80
  
  # Tier 2: Battle zone
  trml_4d_burst_duration_s: 3       # per scan cycle
  trml_4d_cycle_interval_s: 30      # between bursts
  trml_4d_emission_duty_pct: 10     # only 10% of time emitting
  
  # Tier 1: Deep rear
  globaleye_coverage: continuous (within 300° arc)
  
  # SEAD dilution factor
  military_emitters: 3-5            # TRML-4D + AN/MPQ-65
  total_emitters: 25-35             # military + civilian + UAV
  arm_targeting_dilution: 0.12-0.20 # probability ARM hits military radar
    # vs 1.0 without civilian nodes
```
