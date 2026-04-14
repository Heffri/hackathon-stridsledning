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

## 6. Ammunition Management

Ammunition is finite. The system must:

1. **Track remaining rounds** for every asset
2. **Project depletion time** based on current engagement rate
3. **Recommend conservation**: If ammo drops below threshold, suggest:
   - Switch to guns (Lvkv 90) for low-value targets
   - Request fighter rearmament sortie
   - Redistribute coverage from well-stocked units
4. **Rearm priority**: Which unit to rearm first based on coverage gap analysis

## 7. Scramble Decision Logic

When to scramble fighters vs. rely on ground-based defense:

| Factor | Favor Scramble | Favor Ground SAM |
|--------|---------------|-----------------|
| Threat distance | Far (>100 km, time to intercept) | Close (<50 km, SAM already covers) |
| Threat type | Fighters, bombers (need BVR) | Missiles, drones (SAM effective) |
| Fighter availability | Many ready | Few remaining |
| Threat quantity | Small number (manageable) | Large swarm (SAM more efficient) |
| Airfield threat | Airfield NOT threatened | Airfield under threat (scramble to save aircraft) |

## 8. Forward Planning (Look-Ahead)

The system should NOT be purely reactive. It must:

1. **Predict resource state** N minutes into the future
2. **Identify coverage gaps** that will emerge after engagements
3. **Recommend pre-positioning**: Move mobile units to fill predicted gaps
4. **Reserve management**: Keep a strategic reserve (e.g., 2 Gripen on ground alert) for unexpected threats
5. **Wave analysis**: If detecting multi-wave attacks, conserve resources for subsequent waves

## 9. Rules of Engagement (Simplified for Sim)

1. AEW&C (GlobalEye) is NEVER a combatant — it detects and coordinates only
2. Fighters may engage only targets classified as hostile (not "unknown")
3. SAMs engage automatically within their assigned sectors unless overridden
4. Commander can override any automated assignment
5. Civilian aircraft corridors must be respected (no engagement in designated safe lanes)

## 10. Swedish Dispersed Operations Concept

Gripen is designed for dispersed operations:
- Can operate from road bases (straight highway segments)
- Turnaround time: ~10 minutes (refuel + rearm by conscript crew of 5-6)
- Multiple road bases reduce single-point-of-failure risk
- Simulation should model multiple dispersed bases, not just one main airfield

## 11. Network-Centric Warfare

All assets share a common operational picture via data links:
- GlobalEye → all units: fused track data
- Gripen ↔ Gripen: cooperative targeting (one detects, another shoots)
- GlobalEye → Meteor: mid-course guidance (Silent Attack — Gripen doesn't need own radar)
- Ground SAM sites share track data with fighter control

**"Silent Attack" concept**: Gripen fires Meteor while radar-silent. GlobalEye provides target updates via data link. Target cannot detect the launching fighter. This is a KEY Saab selling point — highlight in demo.
