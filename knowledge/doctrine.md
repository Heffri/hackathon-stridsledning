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
| GPS/GNSS only (Shahed-136) | **High** | Jamming degrades CEP from 20m to 500m+; spoofing can redirect entirely |
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

## 6. GlobalEye Protection Doctrine

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
| PL-15 (reference) | 145 km (exhibition data) | Unknown — India-Pakistan incident suggests longer | N/A (not in theater) |

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

**Lessons from India-Pakistan (2025 India–Pakistan conflict):**
- Indian pilots trusted PL-15 exhibition data (145 km) as hard limit
- Pakistani F-16s (with AIM-120C-5) engaged at distances Indians believed safe
- RWR/MAWS warnings came "too late" by Indian pilot accounts
- **Takeaway**: Always assume enemy range is 15-20% beyond what you think it is

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

## 7. Ammunition Management

Ammunition is finite. The system must:

1. **Track remaining rounds** for every asset
2. **Project depletion time** based on current engagement rate
3. **Recommend conservation**: If ammo drops below threshold, suggest:
   - Switch to guns (Lvkv 90) for low-value targets
   - Request fighter rearmament sortie
   - Redistribute coverage from well-stocked units
4. **Rearm priority**: Which unit to rearm first based on coverage gap analysis

## 8. Scramble Decision Logic

When to scramble fighters vs. rely on ground-based defense:

| Factor | Favor Scramble | Favor Ground SAM |
|--------|---------------|-----------------|
| Threat distance | Far (>100 km, time to intercept) | Close (<50 km, SAM already covers) |
| Threat type | Fighters, bombers (need BVR) | Missiles, drones (SAM effective) |
| Fighter availability | Many ready | Few remaining |
| Threat quantity | Small number (manageable) | Large swarm (SAM more efficient) |
| Airfield threat | Airfield NOT threatened | Airfield under threat (scramble to save aircraft) |

## 9. Forward Planning (Look-Ahead)

The system should NOT be purely reactive. It must:

1. **Predict resource state** N minutes into the future
2. **Identify coverage gaps** that will emerge after engagements
3. **Recommend pre-positioning**: Move mobile units to fill predicted gaps
4. **Reserve management**: Keep a strategic reserve (e.g., 2 Gripen on ground alert) for unexpected threats
5. **Wave analysis**: If detecting multi-wave attacks, conserve resources for subsequent waves

## 10. Rules of Engagement (Simplified for Sim)

1. AEW&C (GlobalEye) is NEVER a combatant — it detects and coordinates only
2. Fighters may engage only targets classified as hostile (not "unknown")
3. SAMs engage automatically within their assigned sectors unless overridden
4. Commander can override any automated assignment
5. Civilian aircraft corridors must be respected (no engagement in designated safe lanes)

## 11. Swedish Dispersed Operations Concept

Gripen is designed for dispersed operations:
- Can operate from road bases (straight highway segments)
- Turnaround time: ~10 minutes (refuel + rearm by conscript crew of 5-6)
- Multiple road bases reduce single-point-of-failure risk
- Simulation should model multiple dispersed bases, not just one main airfield

## 12. Network-Centric Warfare

All assets share a common operational picture via data links:
- GlobalEye → all units: fused track data
- Gripen ↔ Gripen: cooperative targeting (one detects, another shoots)
- GlobalEye → Meteor: mid-course guidance (Silent Attack — Gripen doesn't need own radar)
- Ground SAM sites share track data with fighter control

**"Silent Attack" concept**: Gripen fires Meteor while radar-silent. GlobalEye provides target updates via data link. Target cannot detect the launching fighter. This is a KEY Saab selling point — highlight in demo.
