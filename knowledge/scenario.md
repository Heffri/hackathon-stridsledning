# Demo Scenario: Multi-Wave Mixed Threat Attack

> A realistic asymmetric scenario designed to showcase the decision support system's
> ability to optimize resource allocation across multiple threat types and time horizons.
>
> All adversary forces labeled **"Red Force"** — no specific nation named.

## Scenario Overview

**Setting:** Coastal Sweden, defending a mixed military-civilian area including:
- 1x Air base (Gripen home, fixed infrastructure)
- 1x Strategic C2 node (fixed)
- Mobile IADS assets (can relocate)

**Blue Force starting disposition:**

| Asset | Quantity | Location | Status |
|-------|----------|----------|--------|
| GlobalEye (S 106) | 1 | Orbiting 200 km west, 35,000 ft | Airborne, full sensors |
| Gripen E | 6 | Air base (4 alert, 2 maintenance) | 4 ready, 2 unavailable |
| Patriot PAC-3 MSE | 1 battery (8 launchers, 96 missiles) | Defending air base | Ready |
| IRIS-T SLM | 2 batteries (24 missiles each) | Positions Alpha and Bravo | Ready |
| IRIS-T SLS | 3 launchers (4 missiles each) | Escorting SAM sites | Ready |
| RBS 70 NG | 4 teams | Dispersed around defended area | Ready |
| Lvkv 90 | 3 vehicles | Mobile patrol | Ready |
| EW Ground Station | 1 | Forward position | Ready (optional module) |

**Red Force attack plan** (unknown to Blue at start — revealed progressively):

5 waves designed to exhaust Blue resources through cost asymmetry and SEAD.

---

## Wave Timeline

### Wave 1: Attrition / Reconnaissance (T+0)

**Intent:** Force Blue to activate radars, consume medium-range interceptors, map IADS positions.

| Threat | Qty | Speed | Altitude | RCS | Guidance | From |
|--------|-----|-------|----------|-----|----------|------|
| Shahed-136 loitering munition | 40 | 45 m/s | 500-1000 m | 0.1 m² | **GPS only** | East, spread across 60 km front |
| Orlan-10 recon UAV | 4 | 30 m/s | 3,000 m | 0.1 m² | GPS + operator | Behind Shahed wave |

**Detection timeline:**
- GlobalEye detects Shahed wave at ~200 km → **~74 min warning**
- Orlan-10 detected at ~250 km (higher altitude, same RCS)

**Optimal Blue response (what the system should recommend):**

1. **EW layer (if available):** Activate GPS jamming toward east. Shahed guidance degrades — many will miss their programmed targets by hundreds of meters to kilometers.

2. **Evasion layer:** Calculate which Shaheds target mobile assets (SAM sites from last known positions). Recommend relocation for those sites. Shaheds have no seeker — they'll hit empty ground.

3. **Triage:** Of the 40 Shaheds, determine which ones are on course for **fixed** high-value targets (air base, C2 node). Only those need kinetic intercept.

4. **Engage with cheapest effector:** Lvkv 90 + RBS 70 for Shaheds approaching defended areas. **NOT** IRIS-T SLM (save for Wave 3).

5. **Orlan-10:** Must be engaged — cannot allow recon UAVs to map IADS positions. But engage with **cost-appropriate passive/cheap assets only**:
   - **RBS 70 NG** (laser beam riding = no radar emission, no position betrayal) — ideal
   - **MANPADS** from forward infantry positions away from SAM sites
   - **Gripen cannon** if CAP fighters are nearby
   - **Forward patrol IFVs** with autocannon (cheap, expendable positions)
   - **NOT** IRIS-T SLM or Patriot — cost overkill and reveals SAM radar positions

**Trap to avoid:** Spending 24 IRIS-T SLM missiles on Shaheds, leaving nothing for the cruise missiles in Wave 3.

---

### Wave 2: SEAD Probe (T+15 min)

**Intent:** Destroy any radars that turned on during Wave 1. Suppress IADS for the main strike.

| Threat | Qty | Speed | Altitude | RCS | Guidance | From |
|--------|-----|-------|----------|-----|----------|------|
| Su-34 (strike) | 2 | 280 m/s | 10,000 m | 10 m² | N/A (launch platform) | 300 km east |
| Kh-31P ARM | 4 | 900 m/s | 12,000→diving | 0.08 m² | **Anti-radiation** (homes on radar) | Launched by Su-34 at 150 km |

**Detection timeline:**
- GlobalEye detects Su-34 at ~550 km → **~15 min before ARM launch range**
- Kh-31P detected at launch, ~150 km away → **~2.5 min to impact**

**Optimal Blue response:**

1. **CRITICAL:** If any SAM radar was left on from Wave 1, **shut it down NOW**. Kh-31P homes on radar emissions.

2. **Radar management:** TRML-4D at positions Alpha/Bravo should already be off (post Wave 1 engagement). If not, immediate shutdown + relocate.

3. **GlobalEye provides SA:** Blue doesn't need ground radar to track Su-34. GlobalEye tracks them from 550 km and shares via TIDLS.

4. **Scramble Gripen?** Su-34 at 300 km, within Meteor range from CAP position. **Yes** — scramble 2 Gripen to intercept. Silent Attack: Gripen fires Meteor using GlobalEye track data, no own-radar emission.

5. **Kh-31P defense:** If ARM is inbound to a radar site → radar already off + unit relocated → ARM hits empty ground. IRIS-T SLS *can* intercept ARM if detected, but it's Mach 2.5 and small — difficult shot.

**Trap to avoid:** Turning SAM radars back on to "defend against the Su-34" — that's exactly what the ARMs are homing on.

---

### Wave 3: Main Strike (T+20 min)

**Intent:** Precision strike on air base and C2 node while IADS is suppressed.

| Threat | Qty | Speed | Altitude | RCS | Guidance | Target |
|--------|-----|-------|----------|-----|----------|--------|
| Kalibr (3M-14) cruise missile | 8 | 260 m/s | 30-50 m (terrain following) | 0.08 m² | **GPS/INS + active radar terminal** | Air base (4), C2 node (4) |

**Detection timeline:**
- GlobalEye detects at ~350 km (small RCS, confirmed Saab range for cruise missiles)
- Low altitude + terrain following → ground radar detection much shorter (~40-60 km)
- **~22 min from GlobalEye detection to impact**

**Optimal Blue response:**

1. **This is why we saved IRIS-T SLM ammunition.** Kalibr is the real threat — it has terminal active radar seeker, cannot be evaded or EW'd easily at terminal phase.

2. **GPS/INS midcourse IS jammable** — if EW is still active, Kalibr midcourse accuracy degrades, but terminal radar seeker kicks in at ~20 km and homes independently.

3. **Engagement plan:**
   - IRIS-T SLM (Positions Alpha/Bravo): Primary interceptor. Must turn TRML-4D back on to engage. Accept SEAD risk — this is worth it.
   - Patriot: Reserve for leakers or if Kalibr count exceeds SLM capacity.
   - Gripen (if airborne from Wave 2): Can attempt BVR intercept on cruise missiles, but very difficult (small, low, fast crossing target).

4. **Radar management dilemma:** Must turn on TRML-4D to engage Kalibr, but Wave 2 Su-34 may still be in area. System must calculate: is SEAD threat neutralized (Gripen intercepted Su-34?) before recommending radar activation.

5. **Resource math:** 8 Kalibr, assume Pk 0.9, shoot-shoot doctrine = 16 IRIS-T SLM needed. We have 48 total (2 batteries × 24). Comfortable margin — but only because we didn't waste them on Shaheds.

---

### Wave 4: Ballistic Strike (T+22 min)

**Intent:** Simultaneous with Wave 3. Crater the air base runway to prevent Gripen recovery/rearm.

| Threat | Qty | Speed | Altitude | RCS | Guidance | Target |
|--------|-----|-------|----------|-----|----------|--------|
| Iskander-M (9M723) | 2 | 2000 m/s terminal | Apogee 100 km | 0.05 m² | **INS + terminal optical/radar** | Air base runway |

**Detection timeline:**
- GlobalEye may detect launch plume / boost phase
- Terminal phase: ~60 seconds from reentry to impact
- **Extremely short reaction time**

**Optimal Blue response:**

1. **Only Patriot PAC-3 MSE can engage.** No other system reaches ballistic targets.
2. Shoot-shoot (2 interceptors per target) → 4 PAC-3 MSE expended (of 96). Acceptable.
3. **Simultaneously:** Alert Gripen pilots — if runway is cratered, divert to road bases.
4. **Forward planning:** After this wave, assess runway status. If damaged, switch all Gripen ops to dispersed road bases.

**System insight:** Even if Patriot intercepts both Iskanders, the system should proactively recommend dispersing Gripen to road bases as a precaution. This is "thinking ahead."

---

### Wave 5: Exploitation / Second Attrition (T+30 min)

**Intent:** Exploit any gaps created by Waves 1-4. If Blue wasted ammo on Shaheds, this wave finishes the job.

| Threat | Qty | Speed | Altitude | RCS | Guidance | From |
|--------|-----|-------|----------|-----|----------|------|
| Shahed-136 (second wave) | 20 | 45 m/s | 500 m | 0.1 m² | GPS only | East |
| Su-35S (air superiority) | 4 | 300 m/s | 12,000 m | 5 m² | N/A (platform) | 400 km east |
| R-37M (ultra-long-range AAM) | 4 | 1800 m/s | 25,000 m | 0.05 m² | Active radar | Targeting GlobalEye |

**Critical threat:** R-37M targeting GlobalEye. Range ~200+ km against large RCS target (GlobalEye is huge). Loss of GlobalEye = loss of situational awareness = catastrophic.

**Optimal Blue response:**

1. **Protect GlobalEye.** The R-37M threat means GlobalEye must increase standoff distance or the Su-35S must be intercepted before launch. Scramble remaining Gripen for fleet defense.

2. **Shahed Wave 2:** Same playbook as Wave 1 — EW + evade + Lvkv 90 for what reaches defended areas. By now Blue should be experienced with the pattern.

3. **Air battle:** 4 Gripen vs 4 Su-35S. Gripen advantage: Silent Attack via GlobalEye, Meteor's superior NEZ. But must engage before Su-35 reaches R-37M launch range against GlobalEye.

4. **Resource assessment:** System should display current ammo state across all assets. If IRIS-T SLM stocks are low (bad decisions earlier), recommend conservation. If healthy (good decisions earlier), normal engagement.

---

## Scoring / Assessment Criteria

The demo can show two runs of the same scenario:

### Run A: Naive Approach (no decision support)
- Wave 1: Operator panics, fires 30 IRIS-T SLM at Shaheds → ammo nearly depleted
- Wave 2: Radars still on → 2 TRML-4D destroyed by Kh-31P
- Wave 3: No SLM left, only Patriot → forced to use $4M missiles on cruise missiles
- Wave 4: Patriot partially depleted → only 1 Iskander intercepted
- Wave 5: No air picture (GlobalEye not protected) → blind

**Result:** Air base destroyed, C2 damaged, 60% IADS losses.

### Run B: With Decision Support System
- Wave 1: EW degrades Shaheds, mobile assets evade, Lvkv 90 handles rest → 0 SLM expended
- Wave 2: Radars already off, Gripen intercepts Su-34 via Silent Attack → 0 losses
- Wave 3: Full IRIS-T SLM stock available → all 8 Kalibr intercepted
- Wave 4: Patriot intercepts both Iskander, Gripen dispersed to road bases proactively
- Wave 5: GlobalEye protected, Su-35S engaged at range → air superiority maintained

**Result:** All defended assets intact, ammunition reserves healthy, IADS fully operational.

---

## Key Demo Talking Points

1. **"The system saved 30 IRIS-T SLM missiles by recommending 'don't shoot' for Wave 1"** — shows cost-exchange intelligence
2. **"It recommended radar shutdown 2 minutes before the ARMs arrived"** — shows SEAD awareness
3. **"It reserved the right ammunition for the right threats"** — shows forward planning
4. **"It recommended protecting GlobalEye before the long-range AAM threat materialized"** — shows looking ahead
5. **Soft kill → Evade → Hard kill** — three-layer response is more sophisticated than just a weapon-target matcher

## Simulation Parameters for This Scenario

### Map Area
- Defended area center: ~58.5°N, 17.5°E (generic coastal Sweden, Gotland vicinity)
- Threat axis: East (over Baltic Sea)
- Map extent: ~400 km × 300 km

### Timing
- Total scenario duration: ~35-40 minutes simulated time
- Time acceleration: suggest 4-10x for demo playback
- Key decision points at T+0, T+15, T+20, T+22, T+30

### Difficulty Scaling
If time permits, scenario parameters can be adjusted:

| Parameter | Easy | Medium | Hard |
|-----------|------|--------|------|
| Wave 1 Shahed count | 20 | 40 | 80 |
| Wave 3 Kalibr count | 4 | 8 | 16 |
| Wave 4 Iskander count | 1 | 2 | 4 |
| SEAD timing | +5 min gap | Overlapping | Simultaneous |
| EW available | Yes | Yes | No |
| Blue Gripen count | 8 | 6 | 4 |
