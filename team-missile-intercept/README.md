# Missile Intercept: AI vs AI

3D missile interception simulation where a Red AI launches attacks and a Blue AI selects and guides interceptors in real-time.

## Concept

- **Red AI** launches a variety of threats: hypersonic glide vehicles, cruise missiles, ballistic missiles, suicide drones
- **Blue AI** selects the optimal interceptor from its arsenal based on cost, Pk, and trajectory analysis, then computes a real-time intercept solution
- **NOT a dice-roll probability game** — actual physics-based trajectory computation: predict target path, compute lead angle, determine optimal launch time and intercept point
- Both AIs have **full situational awareness** (no fog of war)
- Only missiles and drones are modeled — no vehicles or launch platforms

## What You See

A 3D map view showing:
- Red missiles/drones flying in from one side
- Blue interceptors launching and maneuvering to intercept
- Real-time trajectory predictions, intercept points
- The AI's decision-making: which interceptor was chosen, why, and the computed intercept geometry

## Core Mechanics

### Red AI (Attacker)
- Selects from a weapons arsenal (hypersonic gliders, cruise missiles, ballistic missiles, cheap drones)
- Controls missile flight path in real-time (maneuvering, course changes)
- Goal: overwhelm Blue defenses, exploit cost asymmetry

### Blue AI (Defender)
- Analyzes incoming threat: type, speed, trajectory, predicted path
- Selects best interceptor from arsenal considering:
  - Cost-effectiveness (don't use expensive interceptors on cheap drones)
  - Probability of intercept (speed matching, maneuverability comparison)
  - Time-to-intercept (can we reach it in time?)
- Computes intercept solution: launch time, lead angle, intercept point
- Guides interceptor to target in real-time

### Physics Model
- 3D kinematics: position, velocity, acceleration
- Gravity, drag (simplified)
- Maneuverability limits (turn rate, G-load) per missile type
- Intercept geometry: proportional navigation or lead pursuit
- No black-box probability — interception succeeds or fails based on actual closest-approach distance

## Tech Stack

TBD — to be decided by team.

## Threat & Interceptor Types

### Red Arsenal (Threats)
| Type | Speed | Maneuverability | Difficulty |
|------|-------|----------------|------------|
| Suicide drone | Slow (~200 km/h) | Medium | Easy |
| Subsonic cruise missile | ~900 km/h | Low (terrain following) | Medium |
| Supersonic cruise missile | ~Mach 2-3 | Low | Hard |
| Ballistic missile (terminal) | ~Mach 5-8 | Very low (predictable) | Hard (speed) |
| Hypersonic glide vehicle | ~Mach 5+ | High (skip-glide, maneuvering) | Very Hard |

### Blue Arsenal (Interceptors)
| Type | Speed | Best Against | Cost |
|------|-------|-------------|------|
| Gun/CIWS burst | Instant (projectile) | Drones, slow missiles | Very Low |
| Short-range SAM | ~Mach 2-3 | Drones, cruise missiles | Low |
| Medium-range SAM | ~Mach 3-4 | Cruise missiles, fighters | Medium |
| Long-range SAM | ~Mach 5+ | Ballistic, high-altitude | High |
| Hit-to-kill interceptor | ~Mach 5+ | Ballistic (terminal phase) | Very High |
