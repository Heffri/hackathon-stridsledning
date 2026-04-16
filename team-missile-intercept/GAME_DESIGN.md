# Game Design — AI vs AI Missile Intercept

> ⚠️ **This is the full final product design.**
> The first playable MVP we're building is a simplified subset — see **[DEMO_PLAN.md](DEMO_PLAN.md)**.

## Core Concept

Two AIs fight over a defended base. Red AI launches missiles/drones to destroy the base. Blue AI selects and guides interceptors to defend it. Both AIs operate within realistic physics constraints, limited magazines, and finite budgets. Every weapon is a physical body subject to G-limits, fuel burn, and speed-bleed from maneuvering.

---

## AI Control Levels

Each weapon type gives its controlling AI a different degree of control, creating a tactical depth ladder.

### Red Force — Five-Tier Guidance Hierarchy

#### Level 1 — Pre-Programmed (Suicide Drone / Shahed-136)
- **Before launch**: Red AI sets full flight plan — waypoints, altitudes, pre-programmed evasive maneuvers
- **After launch**: No changes possible. Drone follows programmed trajectory exactly.
- **Speed**: 45 m/s, **Max G**: 2

#### Level 2 — Pre-Programmed + Fast (Ballistic Missile)
- **Before launch**: Red AI sets ballistic trajectory + fixed number of terminal maneuvers
- **After launch**: No changes. Follows pre-set arc with pre-set terminal maneuvers.
- **Design intent**: Upgraded Shahed — still pre-programmed but Mach 6 with short intercept window
- **Maneuverability**: 1G correction (terminal only)
- **Speed**: 2,000 m/s terminal

#### Level 3 — Waypoint-Adjustable (Subsonic Cruise Missile)
- **Before launch**: Red AI sets initial flight plan
- **During flight**: Red AI can modify waypoints — reroute, change approach angle, alter altitude. NOT real-time stick-and-rudder; the AI issues a new plan and the missile follows it.
- **Planning requirement**: Red AI must think ahead — waypoint changes take effect over several seconds as the missile turns
- **Speed**: 260 m/s, **Max G**: 2

#### Level 4 — Terminal Takeover (Stealth Subsonic Cruise Missile)
- **Cruise phase**: Waypoint-adjustable (same as Level 3)
- **Terminal phase trigger**: When missile crosses the sea strait on the Boreal Passage map (or within ~30 km of target), Red AI gains **full real-time control**
- **Terminal phase**: Red AI commands maneuvers every tick — jinks, altitude changes, evasive spirals
- **Design intent**: The geographic trigger creates tension. Stealth (RCS 0.01 m²) means late detection, compressing Blue's reaction window.
- **Speed**: 260 m/s, **Max G**: 3 (terminal)

#### Level 5 — Full Real-Time Control (Hypersonic Glide Vehicle)
- **Full AI control from launch**: Red AI commands the HGV every tick. Skip-glide, lateral jinks, altitude changes, dive-pull-up — anything within physics limits.
- **Speed-maneuver tradeoff**: Every maneuver bleeds speed via drag. Hard 8G turn at Mach 5 noticeably slows the missile.
- **Strategic tension**: Over-maneuver → slow → easier to intercept next time. Under-maneuver → caught by current interceptor.
- **Speed**: 1,700 m/s initial (degrades), **Max G**: 8

### Blue Force — Dual Role (Commander + Guidance Computer)

Blue AI simultaneously plays strategic commander (which weapon to fire at which threat) AND acts as the guidance computer living inside each in-flight interceptor (adjusting thrust/direction every tick).

#### Unguided Ballistic — Lvkv 90 CIWS (40mm Bofors 3P)
- **Before firing**: Blue AI predicts target trajectory ~3 seconds ahead, computes lead angle + 3P fuse programming (airburst timing)
- **After firing**: Round is ballistic. No course correction. Airburst detonates at pre-programmed distance.
- **If target maneuvers after burst is fired**: Miss.
- **Great vs pre-programmed targets** (Shahed, ballistic terminal). Risky vs maneuvering targets.

#### AI-Guided Real-Time — RBS 70, IRIS-T SLS, IRIS-T SLM, PAC-2, PAC-3
- **Blue AI controls each missile in real-time** every tick
- Can implement proportional navigation, lead pursuit, or custom guidance laws
- Respects each missile's physical limits (G, speed, fuel)
- PAC-3 MSE is the ultimate guidance challenge: must score <0.3m miss distance at Mach 10+ closure rates for kinetic kill

---

## Core Mechanics

### Physics — Hard Rules

Every projectile is a physical body subject to:

1. **G-limit**: Hard max per weapon (e.g., IRIS-T SLS = 60G, HGV = 8G). AI cannot exceed.
2. **Speed cap**: No weapon exceeds its rated max speed.
3. **Gravity**: Always -9.81 m/s² on Z axis.
4. **Drag**: Quadratic, with altitude-dependent air density. Faster + lower altitude = more drag.
5. **Speed bleed from maneuvers**: Turning trades kinetic energy. Formula: `speed_loss_per_s = bleed_coefficient * (G_applied / max_G)²`. Tuned per weapon so that a sustained max-G turn visibly slows the missile.
6. **Ground collision**: Any entity whose Z drops below terrain height is destroyed instantly.

### Fuel System — Two Types

**Type A: Thrust-Powered (Fuel Timer)**
Applies to: CIWS rounds, RBS 70, IRIS-T SLS, IRIS-T SLM, PAC-2, PAC-3, drones, all cruise missiles.

- `fuel_seconds = range_max / cruise_speed` (see WEAPON_SPECS.md for values)
- Each tick: `fuel -= dt` (constant burn, regardless of maneuvering)
- Maneuvers don't burn extra fuel — but because turning ≠ straight-line progress, a maneuvering missile covers less ground per second of fuel spent
- **When fuel = 0**: engine cuts → rapid deceleration from drag → self-destruct (ground collision or speed < minimum threshold)

**Type B: Gravity/Kinetic-Driven (No Fuel Timer)**
Applies to: Ballistic missiles, HGV.

- No fuel countdown. These enter the simulation already in terminal/coast phase.
- Operate on initial kinetic energy + gravity. Cannot generate thrust.
- Maneuvers bleed SPEED (not fuel) via the same formula as above.
- When speed drops below critical threshold (~500 m/s for HGV, ~300 m/s for ballistic) → loss of aerodynamic control → crash.
- Gravity always acts — they're falling toward Earth by definition.
- **Implication**: HGV can still reach target with fuel = 0. It's a pure energy-management game.

### HP & Damage System

Every threat has **HP**. Every interceptor has two damage values — **direct hit** and **proximity**.

**Damage calculation** (per closest-approach event):
```
if dist < direct_hit_radius (typically 0.5m, or 0.3m for PAC-3):
    damage = direct_hit_damage
elif dist < prox_radius:
    damage = prox_damage * (1 - dist / prox_radius)²
else:
    damage = 0
```

**When target HP ≤ 0**: destroyed.

See WEAPON_SPECS.md for full HP and damage tables.

**Key design consequence — PAC-3 MSE:**
- Direct hit: 200 dmg (one-shots any target)
- Proximity: only 5 dmg in 0.3m radius (it's a kinetic body, no warhead)
- Forces Blue AI to guide PAC-3 with extreme precision. A near-miss is nearly wasted.

**Alternative tactic — blast-frag stacking:**
- Ballistic missile has 80 HP
- 2× PAC-2 GEM+ proximity hits (40 each) = 80 dmg → guaranteed kill
- But uses $6M instead of $4M for PAC-3 direct hit
- Tradeoff: higher success probability vs higher cost

### Magazine & Reload System

Every launcher has:
- **Magazine capacity**: max missiles ready to fire
- **Inter-shot cooldown**: seconds between consecutive shots from the same launcher
- **Full reload**: seconds to refill an empty magazine (after all inter-shot shots used up)

Both Blue and Red are subject to magazine/reload. Red cannot zerg-rush by dumping entire budget at t=0 — the launchers physically can't fire that fast.

See WEAPON_SPECS.md for full magazine and reload values.

### Time Scaling — ÷10 Rule for Long Reloads

To fit realistic strategic dynamics into a 4-minute demo, we apply:

**Short timers (<60s)**: kept at real-world values
- Inter-shot cooldowns, box magazine swaps, RBS 70 reload, etc.

**Long timers (>60s)**: scaled ÷10
- Patriot reload: 1800s real → 180s sim
- IRIS-T SLM reload: 1200s real → 120s sim
- Missile flight, physics, and combat timing all run at **real time**. Only out-of-combat logistics are accelerated.

Rationale: At 1x game speed, a Mach 5 missile takes the realistic ~40 seconds to fly 70 km. Observers can see the engagement clearly. But a 30-minute Patriot reload doesn't fit in a demo, so we compress those out-of-combat timers only.

**Optional UI speed slider**: 0.5x / 1x / 2x / 5x / 10x globally accelerates everything (physics + clocks proportionally). Useful for debugging (10x) or slow-mo showcase (0.5x).

### Terrain

The arena has a **heightmap** — terrain is solid and has elevation.

- **Sea/water**: elevation 0 (the strait between north and south landmasses on the Boreal Passage map)
- **Landmasses**: variable elevation — coastal plains, hills, ridges
- **Ground collision**: `if entity.pos.z < terrain_height(entity.pos.x, entity.pos.y) → destroyed`
- **Terrain following**: Cruise missiles at 50m altitude must follow terrain contours; if terrain rises above, they either climb or crash
- **Tactical implications**:
  - Mountains can block low-altitude approach routes
  - Valleys provide cover for terrain-following cruise missiles
  - Red AI must plan routes that avoid high terrain
  - Red AI can exploit low valleys to delay detection by Blue

**Implementation**: 2D heightmap grid (e.g., 512×512), bilinear interpolation for arbitrary (x,y) queries. Three.js renders it as a displacement-mapped plane.

### AI Multitasking

- **Blue AI**: No attention limit. Simultaneously makes strategic decisions AND guides all in-flight interceptors.
- **Red AI**: No attention limit (for now). Can simultaneously control all HGVs and stealth-cruise terminal-phase missiles.
- Both AIs evaluate every tick. Each can issue commands to all its active weapons in a single tick.
- If Red-side multitasking becomes a balance issue, we'll add attention slots later.

---

## Economy System

### Blue Force (Defender)

**Base HP**: Defended installation has hit points. HP = 0 → Blue loses.
- Starting base HP: 1,000 [tunable]
- Damage per threat type impact:
  - Drone: 50
  - Cruise missile (subsonic/stealth): 200
  - Supersonic cruise: 250
  - Ballistic missile: 500
  - Hypersonic glide vehicle: 300

**Starting Budget**: $50,000,000 [tunable]
- Blue spends this on interceptor loadout before the game starts
- Mid-game: if budget remains, Blue can "buy" additional missiles to load into empty launchers (subject to reload CD)

**Loadout Decision** (pre-game strategy):
- All CIWS? Cheap but only 4 km range — fast threats get through
- All Patriot? Can stop anything but thin magazine
- Mixed loadout? Best strategy, but what mix?

### Red Force (Attacker)

**Starting Budget**: calculated as a ratio of Blue's budget (e.g., 0.8–1.2×) [tunable]

**Attack Planning**:
- What mix of weapons to buy
- When to launch each wave (limited by launcher reload CDs)
- What trajectories/waypoints to program
- How to allocate real-time control attention (HGV, stealth-cruise terminal)

**No opening zerg**: Magazine/reload limits mean Red cannot fire entire arsenal at t=0. Even with unlimited budget, HGV launcher can only fire 1 every 360s, drones only 5 per minute per launcher.

### Win Conditions

| Outcome | Condition |
|---------|-----------|
| **Red wins** | Blue base HP reaches 0 |
| **Blue wins** | Red budget = 0 AND all Red weapons spent AND Blue base HP > 0 |
| **Draw** | Both sides exhausted, Blue base damaged but alive |

### Balance Levers [Tunable]

| Parameter | Effect |
|-----------|--------|
| Red/Blue budget ratio | Higher = harder for Blue |
| Base HP | Higher = more forgiving for Blue |
| Threat damage values | Higher = each leak more costly |
| Interceptor costs | Market pricing creates cost-effectiveness pressure |
| Reload scaling factor | Lower = more strategic depth, longer games |

---

## Real-Time Status Display (HUD)

Frontend shows live data for every active missile:

**Per-entity panel** (click to focus, or hover for tooltip):
- Type + team
- Current speed (m/s + Mach equivalent)
- Current G-load (live computed from acceleration magnitude)
- Fuel remaining (seconds + % bar) — or "gravity-driven" tag for ballistic/HGV
- HP (bar with numeric)
- Target (if any) + predicted intercept point
- Distance to target

**Global side panel** — scrollable list of all active entities with key stats (type, HP, fuel, speed).

**AI decision log** — scrolling text showing:
- "SLS #3 launched at Cruise #2 — cost ratio 0.33, 60G guidance engaged"
- "PAC-3 #1 direct hit on Ballistic #1 — 200 damage, target destroyed"
- "CIWS burst missed Drone #5 — target maneuvered after round was fired"

**Score panel**:
- Blue base HP
- Blue budget remaining + ammo counts per launcher
- Red budget remaining + launcher status (ready / reloading)
- Running cost totals (spent vs destroyed-target-value)

**Playback controls**:
- Start / Pause / Reset
- Speed slider: 0.5x / 1x / 2x / 5x / 10x

---

## Implementation Notes

### AI Decision Layers

**Red AI:**
1. Strategic (pre-game): Budget allocation — weapon mix
2. Operational (per-wave): Launch timing, wave composition, approach routes
3. Tactical (real-time): Guide HGV, adjust cruise waypoints, take over stealth-cruise terminal phase

**Blue AI:**
1. Strategic (pre-game): Budget allocation — interceptor loadout
2. Operational (per-threat): Weapon selection, launch timing based on cost-exchange + HP math
3. Tactical (real-time): Guidance law per in-flight interceptor (PN, lead pursuit, or custom)

### Physics Implementation Summary

- Coordinate system: X=east, Y=north, Z=up, meters
- Arena: 150 km × 150 km × 40 km high
- Timestep: dt=0.05s
- WebSocket streaming: 15 fps state snapshots
- Integration: Euler (adequate at 20 Hz physics for this scale)
- Guidance: True Proportional Navigation (N=4) as the default, AI may choose others
- Kill check: per-tick closest-approach distance calculation
- Terrain check: per-tick heightmap lookup + ground collision

### File Structure (unchanged from initial plan)

See PLAN.md for full directory layout.

### Key Tunable Parameters

All balance numbers in this doc should live in a single `backend/sim/config.py` for easy adjustment during playtesting:
- Base HP, damage values
- Budgets (Blue/Red)
- Reload scaling factor
- Speed bleed coefficients
- Drag coefficients per weapon type
- Terminal-takeover distance threshold
