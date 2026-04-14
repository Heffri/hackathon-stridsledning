# Air Assets — Technical Parameters

> Parameters for simulation. Sources: public domain, manufacturer data. Mark [est] for estimated values.

## Gripen E (JAS 39E)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Role | Multirole 4.5-gen fighter | Single-seat (E), twin-seat (F) |
| Length | 15.2 m | |
| Wingspan | 8.6 m | |
| Max speed | Mach 2.0 (~2,120 km/h) | At altitude |
| Supercruise | Mach 1.1 (A2A loadout), Mach 1.2 demonstrated | Confirmed |
| Service ceiling | 15,200 m (50,000 ft) | |
| Combat radius | 800+ km; 1,300 km with 6x AAMs | |
| Ferry range | ~4,000 km | With external tanks |
| Range (internal fuel) | ~2,500 km one-way | |
| Internal fuel | 3,400 kg | 40% more than Gripen C |
| MTOW | 16,500 kg | |
| Empty weight | ~8,000 kg | |
| Max G load | +9G / -3G | |
| Engine | GE F414G (98 kN with A/B) | Single engine |
| Hardpoints | 10 (8 external + 2 wingtip) | |
| Max external load | 5,300 kg | |
| Radar | Raven ES-05 AESA (Leonardo), X-band | Repositioner-mounted (swashplate) |
| Radar field of regard | ±100° (200° total) | +40° per side vs fixed AESA |
| Radar detection range | ~200-300 km (target RCS dependent) | 222 km cited in some databases |
| Radar tracks | Classified | Not publicly disclosed |
| Data link | TIDLS (Swedish), Link 16 compatible | Bidirectional with GlobalEye |
| RCS | ~1 m² [est] | Reduced signature design |
| Turnaround time | 10 min (quick-turn goal), 15-25 min (Saab official) | 1 tech + 5 crew |
| Road base capable | Yes | Core Gripen design philosophy |
| Unit cost | ~$85M | |

### Typical Air-to-Air Loadout
- 7x Meteor (BVR) + 2x IRIS-T (WVR, wingtip) + gun (typical)
- 8x Meteor + 2x IRIS-T (max A2A confirmed by Saab)
- 1x 27mm Mauser BK-27 cannon (internal)
- Drop tank on centerline for extended range

### Simulation Parameters
```
gripen_e:
  type: fighter
  speed_max_mps: 589          # Mach 2.0
  speed_cruise_mps: 265       # Mach 0.9
  ceiling_m: 15200
  combat_radius_km: 1300      # with 6x AAMs
  turnaround_s: 600           # 10 minutes
  scramble_time_s: 300        # 5 min from alert [est]
  endurance_combat_s: 7200    # ~2 hrs on station [est]
  ammo:
    meteor: 7                  # BVR (typical); max 8
    iris_t: 2                  # WVR
    cannon_rounds: 120
  pk:
    fighter: 0.85              # with Meteor [est]
    cruise_missile: 0.70       # [est]
    uav_large: 0.90            # [est]
    uav_small: 0.30            # guns only [est]
  rcs_m2: 1.0
  cost_per_sortie: 50000      # abstract units
  unit_value: 8500             # abstract (proportional to $85M)
```

---

## MBDA Meteor (BVRAAM)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Type | Beyond Visual Range Air-to-Air Missile | |
| Propulsion | Ramjet (throttleable ducted rocket) | Key advantage: sustained energy |
| Length / Diameter | 3.7 m / 178 mm | Confirmed |
| Weight | 190 kg | Confirmed |
| Speed | Mach 4+ | |
| Max range | >200 km (head-on, co-altitude) | Confirmed by MBDA |
| No-Escape Zone | ~60+ km (geometry-dependent) | Largest NEZ of any AAM in service |
| Guidance | Inertial + datalink midcourse, active radar terminal | |
| Warhead | Blast-fragmentation, impact/proximity fuze | |
| Key feature | Maintained end-game energy | Ramjet allows throttling to conserve fuel |
| Silent Attack | Yes — GlobalEye can provide midcourse updates | Gripen stays radar-silent |
| Unit cost | ~$2M+ [est] | |

### Simulation Parameters
```
meteor:
  type: bvr_missile
  speed_mps: 1360             # Mach 4
  range_max_km: 200           # confirmed >200 km
  range_nez_km: 60
  pk_vs_fighter: 0.85         # [est]
  pk_vs_cruise_missile: 0.70  # [est]
  guidance: active_radar_terminal
  datalink: true              # can receive midcourse updates
  cost: 200                   # abstract units
```

---

## IRIS-T (WVR / Short-Range AAM)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Type | Within Visual Range / Dogfight missile | |
| Propulsion | Solid rocket | |
| Length | 2.94 m | |
| Weight | 87.4 kg | |
| Speed | Mach 3 | |
| Range | ~25 km max, effective ~15 km | |
| Guidance | Imaging infrared seeker | All-aspect |
| Off-boresight | ±90° (with HMS cueing) | Confirmed |
| G capability | 60G | Confirmed, thrust vector control |
| Warhead | 11.4 kg HE-Fragmentation | Confirmed |
| Seeker detail | InSb two-colour, 128x2 linear array + scanning mirror | Imaging IR |
| Length / Diameter | 2.9 m / 127 mm | |
| Unit cost | ~$400K [est] | |

### Simulation Parameters
```
iris_t_aam:
  type: wvr_missile
  speed_mps: 1020             # Mach 3
  range_max_km: 25
  range_effective_km: 15
  pk_vs_fighter: 0.90         # within envelope [est]
  pk_vs_uav: 0.85             # [est]
  guidance: imaging_ir
  cost: 40                    # abstract units
```

---

## GlobalEye AEW&C (S 106)

> See also: `sensors-c2.md` for detailed sensor specs

| Parameter | Value | Notes |
|-----------|-------|-------|
| Platform | Bombardier Global 6000/6500 | |
| Endurance | >12 hours | Saab official product sheet |
| Cruise speed | Mach 0.85 / ~904 km/h | |
| Max speed | 1,110 km/h | |
| Operating altitude | Up to 51,000 ft (15,545 m) | Service ceiling 16,000 m |
| Engines | 2x Rolls-Royce BR710 (~14,750 lbf each) | |
| Flight crew | 2 pilots | |
| Mission crew | Up to 9 systems managers | |
| C2 consoles | 5 operator workstations | |
| Total onboard | Up to 11 | |
| Range (base airframe) | >6,000 nm (11,110 km) | |
| Primary radar | Erieye ER AESA | Dorsal "plank" |
| Detection (fighter, 30kft) | ~450 km | |
| Detection (fighter, 35kft) | ~550 km | |
| Detection (cruise missile/UAV) | >350 km (small RCS) | Confirmed by Saab |
| Coverage | **~300°** (60° blind zone nose+tail) | Critical for sim |
| Maritime radar | Leonardo SeaSpray 7500E | |
| EO/IR | Yes | |
| GMTI | Yes | Ground moving target indication |
| AIS | Yes | Ship identification |
| Multi-domain | Air + Sea + Ground simultaneously | Only AEW&C with this capability |
| C2 role | Battle management + data link node | Not just sensor |
| Unit cost | ~$300M+ [est] | |

### Simulation Parameters
```
globaleye:
  type: aew
  speed_cruise_mps: 251       # Mach 0.85
  ceiling_m: 16000            # 52,493 ft
  endurance_s: 43200          # >12 hours (Saab official)
  coverage_deg: 300           # 60° blind zone nose+tail!
  detection_range_fighter_km: 550   # at 35kft, benign env
  detection_range_cruise_km: 350    # confirmed by Saab
  detection_range_fighter_ew_km: 350 # degraded in EW/clutter
  detection_range_uav_small_km: 140 # [est]
  tracks_simultaneous: 500          # [est — not disclosed]
  can_guide_meteor: true
  combatant: false            # NEVER engages directly
  unit_value: 30000           # extremely high value asset
```

---

## Loyal Wingman (Saab UCAV Concept)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Status | R&D, 2.6B SEK contract (2025-2027) | Saab-funded |
| Config | Single-engine, blended wing-body, dorsal intake | Low-observable |
| Speed | Supersonic (specific Mach not disclosed) | Confirmed concept |
| Role | BVR air-to-air, sensor carrier | Gripen E/F wingman |
| Weapons | Internal bays (types/capacity undisclosed) | Stealth priority |
| Autonomy | AI-directed, human-supervised | Helsing Centaur integration |
| Demonstrator flight | Planned 2027 (stated Singapore Airshow 2026) | |
| Decision milestone | Before 2030 | |
| Collaboration | Saab + Airbus exploring joint program | Gripen E + Eurofighter |
| Note | Skeldar is Saab's VTOL naval ISR UAV — unrelated | |

### Simulation Parameters (Placeholder)
```
loyal_wingman:
  type: uav_loyal
  speed_cruise_mps: 250       # [est]
  endurance_s: 14400          # 4 hrs [est]
  ammo:
    iris_t: 2                  # [est]
  pk_vs_fighter: 0.60         # lower than manned [est]
  expendable: true
  cost_per_unit: 500          # much cheaper than Gripen
  unit_value: 500
```
