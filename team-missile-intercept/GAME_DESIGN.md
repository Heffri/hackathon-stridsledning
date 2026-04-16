# Game Design — AI vs AI Missile Intercept

## Core Concept

Two AIs fight over a defended base. Red AI launches missiles/drones to destroy the base. Blue AI selects and guides interceptors to defend it. Both AIs operate within realistic physics constraints and limited budgets.

## AI Control Levels

The key differentiator: each weapon type has a different level of AI control, creating a tactical depth ladder.

### Red Force — Guidance Hierarchy

Each weapon type gives Red AI a different degree of mid-flight control, from "fire and forget" to full real-time maneuvering.

#### Level 1: Pre-Programmed (Suicide Drone / Shahed-136)
- **Before launch**: Red AI sets a complete flight plan — waypoints, altitudes, and pre-programmed evasive maneuvers (e.g., "at waypoint 3, jink left 30° for 2 seconds")
- **After launch**: No changes possible. The drone follows its programmed trajectory exactly.
- **AI challenge for Red**: Must predict Blue's likely intercept patterns and program evasion in advance
- **AI challenge for Blue**: Easiest to intercept — trajectory is predictable once characterized
- **Maneuverability**: 2G max
- **Speed**: 45 m/s

#### Level 2: Pre-Programmed + Fast (Ballistic Missile)
- **Before launch**: Red AI sets the ballistic trajectory, plus a fixed number of terminal maneuvers (e.g., 1-3 course corrections in the last 30 seconds). Maneuver timing and magnitude are locked at launch.
- **After launch**: No changes. Follows pre-set arc with pre-set terminal maneuvers.
- **Design intent**: Upgraded Shahed — still pre-programmed but much faster, making the intercept window very short
- **AI challenge for Red**: Must decide terminal maneuvers blind (doesn't know which interceptor Blue will use)
- **AI challenge for Blue**: Very fast (Mach 6), predictable arc but short reaction time. Only PAC-3 MSE can catch it.
- **Maneuverability**: 1G correction (terminal phase only)
- **Speed**: 2,000 m/s terminal

#### Level 3: Waypoint-Adjustable (Subsonic Cruise Missile)
- **Before launch**: Red AI sets initial flight plan with waypoints
- **During flight**: Red AI can modify waypoints — insert new waypoints, change target approach angle, alter altitude. But this is NOT real-time stick-and-rudder control. Red AI issues a new waypoint plan, and the missile follows it.
- **Planning requirement**: Red AI must "think ahead" — the waypoint change takes effect over the next several seconds as the missile turns toward the new path. Red AI should consider: "If I reroute through this corridor, will Blue have time to reposition?"
- **AI challenge for Red**: Strategic re-routing to exploit gaps in Blue defenses, approach from unexpected angles
- **AI challenge for Blue**: Can't rely on initial trajectory prediction — need to continuously track and re-assess
- **Maneuverability**: 2G (wide turns only, not agile)
- **Speed**: 260 m/s

#### Level 4: Terminal Takeover (Stealth Subsonic Cruise Missile)
- **Cruise phase**: Same as Level 3 (waypoint-adjustable). Red AI can modify the approach route.
- **Terminal phase trigger**: When the missile crosses a geographic boundary (the sea strait on the Boreal Passage map, or within ~30 km of target), Red AI gains **full real-time control**.
- **Terminal phase**: Red AI directly commands maneuvers every tick — jinking, altitude changes, evasive spirals. Still constrained by physics (low G-limit, speed doesn't change much).
- **Design intent**: The geographic trigger creates tension — Blue watches the missile cross the sea knowing it's about to "wake up." Stealth (low RCS 0.01 m²) means late detection, compressing Blue's reaction window further.
- **Why terminal-only, not full real-time**: (1) Differentiates from HGV which has full control, (2) creates meaningful geography, (3) realistic — real stealth cruise missiles activate terminal seekers late
- **Maneuverability**: 3G (slightly better than standard cruise, but still not agile)
- **Speed**: 260 m/s
- **RCS**: 0.01 m² (10× stealthier than standard cruise)

#### Level 5: Full Real-Time Control (Hypersonic Glide Vehicle)
- **Full AI control from launch**: Red AI commands the HGV every simulation tick. Can execute skip-glide maneuvers, lateral jinks, altitude changes, dive-pull-up sequences — anything within physics limits.
- **Speed-maneuver tradeoff**: Every maneuver bleeds speed. A hard 8G turn at Mach 5 might drop speed to Mach 4. This creates a strategic choice: maneuver now to dodge an interceptor, but become easier to catch for the next one.
- **AI challenge for Red**: Must balance evasion vs speed preservation. Over-maneuvering makes the HGV vulnerable. Under-maneuvering means it gets intercepted.
- **AI challenge for Blue**: Hardest target. Unpredictable trajectory, extreme speed. Requires multiple interceptors or perfect timing.
- **Maneuverability**: 8G max (but costs speed proportional to G-force)
- **Speed**: 1,700 m/s initial, degrades with maneuvers
- **Speed bleed formula**: `speed_loss_per_second = (current_g / max_g) * bleed_rate` where bleed_rate ~ 50 m/s per second at max G [tunable]

### Blue Force — Guidance Hierarchy

Blue AI plays dual roles: **strategic commander** (decides what to fire at what) AND **guidance computer** (steers the interceptor to the target).

#### Unguided: Lvkv 90 (CIWS / 40mm Bofors)
- **Before firing**: Blue AI predicts the target's trajectory over the next ~3 seconds and computes a firing solution (lead angle, burst timing, fuse programming for airburst).
- **After firing**: The burst is ballistic — 10 rounds fly on a fixed path. No course correction. The airburst fuse detonates at the pre-programmed distance.
- **If the target maneuvers after the burst is fired**: Miss.
- **Design intent**: Cheapest option ($2K) but requires accurate prediction. Great vs pre-programmed targets (Shahed, ballistic terminal). Risky vs maneuvering targets.
- **Effective range**: 4 km
- **Time of flight**: Near-instant (~3 seconds at max range)

#### AI-Guided: RBS 70 NG (Short-range SAM)
- **Blue AI controls the missile in real-time** via laser beam riding
- AI must keep the missile on the target's bearing — adjusts aim point every tick
- **Proportional Navigation** or direct pursuit — AI chooses the guidance strategy
- Limited speed (Mach 2) means it can't chase fast targets well
- Short range (9 km) means late engagement
- **Key feature**: Passive (no radar) — invisible to enemy. No SEAD vulnerability.
- **AI challenge**: Guide a Mach 2 missile to hit a potentially maneuvering target

#### AI-Guided: IRIS-T SLS / RBS 98 (Short-range SAM+)
- **Blue AI controls in real-time** — IR imaging seeker
- Same IRIS-T missile as the AAM variant, ground-launched with short booster
- Slower than SLM (Mach 2 vs Mach 3) and shorter range (12 km vs 40 km)
- **60G maneuverability** — most agile interceptor in the arsenal (thrust vector control)
- **Niche**: Terminal-phase "knife fight" vs maneuvering targets. If a stealth cruise missile or HGV gets close and starts jinking, the SLS's 60G can out-turn anything.
- **AI challenge**: Short range means late launch — Blue AI must guide it perfectly in a compressed timeframe

#### AI-Guided: IRIS-T SLM (Medium-range SAM)
- **Blue AI controls in real-time** — acts as the missile's guidance computer
- Faster (Mach 3) and more maneuverable (40G) than RBS 70
- Longer range (40 km) — earlier engagement opportunity
- Blue AI can use advanced guidance laws: proportional navigation, augmented PN, predictive intercept
- **AI challenge**: Balance fuel/energy (steep maneuvers cost speed) while achieving intercept

#### AI-Guided: Patriot PAC-2 GEM+ (Long-range SAM)
- **Blue AI controls in real-time**
- Fastest conventional interceptor (Mach 5)
- Blast-fragmentation warhead (20m kill radius) — doesn't need direct hit
- 70 km range — earliest possible engagement
- **AI challenge**: Very fast closure rate means tiny margin for guidance errors

#### AI-Guided: Patriot PAC-3 MSE (Hit-to-Kill)
- **Blue AI controls in real-time**
- Kinetic kill — must score a near-direct hit (0.3m kill radius)
- Extreme maneuverability (50G) compensates for tiny kill radius
- **The only interceptor that can stop a ballistic missile in terminal phase**
- **AI challenge**: Hardest guidance problem. Must hit a Mach 6 target within 0.3 meters using a Mach 5 interceptor. This is the pinnacle Blue AI skill test.

### Control Level Summary

| Level | Red Weapons | Red AI Control | Blue Weapons | Blue AI Control |
|-------|-------------|----------------|--------------|-----------------|
| Pre-programmed | Drone, Ballistic | Set before launch, no changes | CIWS (Lvkv 90) | Predict trajectory, fire ballistic burst |
| Waypoint-adjustable | Cruise (subsonic) | Modify waypoints mid-flight | — | — |
| Terminal takeover | Stealth cruise | Waypoints + real-time terminal | — | — |
| Full real-time | HGV | Direct control every tick | RBS 70, IRIS-T SLS, IRIS-T SLM, Patriot | Direct guidance every tick |

---

## Economy System

### Blue Force (Defender)

**Base HP**: The defended installation has hit points. When HP reaches 0, Blue loses.
- Base HP: 1000 [tunable]
- Damage per threat type:
  - Drone: 50 damage
  - Cruise missile (subsonic): 200 damage
  - Stealth cruise missile: 200 damage
  - Ballistic missile: 500 damage
  - Hypersonic glide vehicle: 300 damage

**Starting Budget**: Blue starts with a fixed budget to purchase interceptors.
- Starting funds: $50,000,000 [tunable]
- Interceptor costs (see WEAPON_SPECS.md for details):
  - CIWS burst: $2,000
  - RBS 70 Bolide: $175,000
  - IRIS-T SLS: $500,000
  - IRIS-T SLM: $1,000,000
  - Patriot PAC-2 GEM+: $3,000,000
  - Patriot PAC-3 MSE: $4,000,000

**Loadout Decision**: Blue AI must decide how to spend its budget before the game starts. This is a strategic layer:
- All CIWS? Cheap but only works at 4 km range — anything fast gets through
- All Patriot? Can stop anything but runs out after 12 shots
- Mixed loadout? Best strategy — but what mix?

### Red Force (Attacker)

**Starting Budget**: Red starts with a fixed budget to purchase threats.
- Starting funds: calculated as a ratio of Blue's budget [tunable, e.g., 0.8× to 1.2×]
- Threat costs:
  - Drone (Shahed): $30,000
  - Subsonic cruise missile: $1,500,000
  - Stealth cruise missile: $2,500,000
  - Supersonic cruise missile: $3,000,000
  - Ballistic missile: $3,000,000
  - Hypersonic glide vehicle: $10,000,000

**Attack Planning**: Red AI must decide:
- What mix of weapons to buy
- When to launch each wave
- What trajectories/waypoints to program
- How to allocate real-time control attention (HGV and stealth cruise terminal need active piloting)

### Win Conditions

| Outcome | Condition |
|---------|-----------|
| **Red wins** | Blue base HP reaches 0 |
| **Blue wins** | Red exhausts all weapons and Blue base survives |
| **Draw** | Both sides exhaust resources, Blue base damaged but alive |

### Economic Balance Levers [Tunable]

| Parameter | Effect |
|-----------|--------|
| Red/Blue budget ratio | Higher = harder for Blue |
| Base HP | Higher = more forgiving for Blue |
| Threat damage values | Higher = each leak is more costly |
| Interceptor costs | Market pricing creates natural cost-effectiveness pressure |

---

## Implementation Notes

### Red AI Decision Layers

1. **Strategic (pre-game)**: Budget allocation — how many of each weapon type to buy
2. **Operational (per-wave)**: Launch timing, wave composition, approach routes
3. **Tactical (real-time)**: Guide HGV, adjust cruise missile waypoints, take over stealth cruise terminal phase

### Blue AI Decision Layers

1. **Strategic (pre-game)**: Budget allocation — interceptor loadout composition
2. **Operational (per-threat)**: Which interceptor to fire at which threat, launch timing
3. **Tactical (real-time)**: Missile guidance — proportional navigation, lead pursuit, or custom guidance for each interceptor in flight

### Physics Constraints — Hard Rules

Every missile and projectile in the simulation is a physical body subject to:

1. **G-limit**: Each weapon has a hard max G (e.g., IRIS-T SLS = 60G, HGV = 8G). The AI cannot exceed this, period.
2. **Speed bleed from maneuvers**: Turning costs kinetic energy. Higher G = more speed loss. Formula: `speed_loss = drag_factor * G_applied * dt`. A hard 8G turn at Mach 5 will noticeably slow the missile.
3. **Fuel / range limit**: Each weapon has finite fuel. When fuel runs out, the missile becomes ballistic (no more thrust, only gravity and drag). No infinite-range missiles.
4. **Gravity**: Always -9.81 m/s² on Z. Affects all objects at all times.
5. **Drag**: Quadratic drag with altitude-dependent air density. Faster = more drag. Lower altitude = denser air = more drag.
6. **Speed cap**: No weapon can exceed its rated max speed. Thrust is limited.
7. **Kill radius**: Intercept is determined by closest approach distance vs kill radius. No probability dice.
8. **Ground collision**: Any missile that touches terrain = instant destruction. See Terrain section.
9. **CIWS is ballistic**: Rounds follow a fixed trajectory after firing. No mid-course correction.

### Terrain

The arena has a **heightmap** — terrain is solid and has elevation.

- **Sea/water**: Elevation 0. The strait between north and south landmasses.
- **Landmasses**: Variable elevation — flat coastal areas, hills, ridges.
- **Ground collision**: `if entity.pos.z < terrain_height(entity.pos.x, entity.pos.y) → destroyed`. Missiles cannot tunnel underground.
- **Terrain following**: Cruise missiles that fly at 50m altitude must actually follow terrain contours. If terrain rises above their flight altitude, they either climb or crash.
- **Tactical implications**:
  - Mountains can block low-altitude approach routes
  - Valleys can provide cover for terrain-following missiles
  - Red AI must plan cruise missile routes that avoid high terrain
  - Blue AI should consider where terrain forces missiles to climb (easier intercept)

**Implementation**: 2D heightmap grid (e.g., 512x512), bilinear interpolation for any (x,y) query. Three.js renders it as a displacement-mapped plane.

### AI Multitasking Rules

- **Blue AI**: No attention limit. Can simultaneously make strategic decisions (which weapon to fire) AND guide all in-flight interceptors. The AI is both the commander and every missile's guidance computer at once.
- **Red AI**: No attention limit (for now). Can simultaneously control all HGVs and stealth cruise missiles in terminal phase. If this causes balance issues, we add attention slots later.
- **Concurrency**: Both AIs evaluate every tick. Each AI can issue commands to all its active weapons in a single tick.
