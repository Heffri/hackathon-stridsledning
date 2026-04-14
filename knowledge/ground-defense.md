# Ground-Based Air Defense Systems — Technical Parameters

## MIM-104 Patriot PAC-2/PAC-3

| Parameter | Value | Notes |
|-----------|-------|-------|
| Manufacturer | Raytheon (US) | Non-Saab, but in Swedish inventory |
| Swedish acquisition | 2021-2022 | |
| Role | Long-range, ballistic missile defense | |
| **PAC-3 MSE Missile** | | |
| Range (vs TBM) | ~20-35 km (PAC-3), ~35-60 km (PAC-3 MSE) | |
| Range (vs air-breathing) | ~70 km (PAC-3), ~100+ km (PAC-3 MSE) | |
| Altitude | Up to 24 km (PAC-3), up to 40 km (PAC-3 MSE) | |
| Speed | Mach 5+ | |
| Guidance | Track-via-missile + active radar terminal (Ka-band) | Hit-to-kill for PAC-3 |
| **PAC-2 GEM+ Missile** | | |
| Range | ~160 km vs aircraft | |
| Altitude | Up to 25 km | |
| Guidance | Semi-active radar homing + TVM | Blast-fragmentation warhead |
| **AN/MPQ-65 Radar** | | |
| Type | C-band PESA (AN/MPQ-65A upgraded to AESA) | |
| Range | ~180 km | |
| Tracks | 100-125+ simultaneous | |
| Coverage | 360° with rotation | |
| **Battery composition** | | |
| Launchers per battery | Up to 8 | |
| Missiles per launcher | 16 (PAC-3) or 12 (PAC-3 MSE) | |
| Total per battery | Up to 128 PAC-3 or 96 PAC-3 MSE | |
| Other vehicles | Radar, engagement control station, antenna mast group, EPP | |
| Reload time | 30+ minutes per launcher [est] | |
| Mobility | Semi-mobile (hours to relocate) | |
| Unit cost per missile | ~$4M (PAC-3 MSE) | |

### Kill Probability (estimated)
| Target | Pk |
|--------|-----|
| Ballistic missile (TBM) | 0.80-0.90 (PAC-3, shoot-shoot) |
| Cruise missile | 0.85 |
| Fighter aircraft | 0.85 (PAC-2 GEM+) |
| Large UAV | 0.80 |
| Small UAV / FPV | Very low — not designed for this |

### Simulation Parameters
```
patriot_pac3:
  type: sam_long
  missile_speed_mps: 1700     # Mach 5
  range_max_km: 70
  range_min_km: 3
  altitude_max_m: 40000
  altitude_min_m: 60
  reload_time_s: 1800         # 30 min per launcher
  missiles_per_launcher: 12   # PAC-3 MSE (16 for PAC-3)
  launchers_per_battery: 8
  radar_range_km: 180
  radar_on_required: true     # SEAD vulnerability
  mobility: semi_mobile
  relocate_time_s: 10800      # ~3 hours
  pk:
    ballistic: 0.85
    cruise_subsonic: 0.85
    cruise_supersonic: 0.70
    fighter: 0.85
    uav_large: 0.80
    uav_small: 0.10           # not designed for this
  cost_per_missile: 400       # abstract units (expensive!)
  unit_value: 5000            # high value asset
```

---

## IRIS-T SLM (Surface Launched Medium-range)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Manufacturer | Diehl Defence (Germany) | |
| Swedish order | 7 systems, ~90B SEK, 2028+ delivery | |
| Role | Medium-range air defense | |
| **Missile** | | |
| Range | ~40 km | |
| Altitude | Up to 20 km | |
| Speed | Mach 3 | |
| Guidance | IR imaging seeker + datalink midcourse | |
| **TRML-4D Radar** | | (see sensors-c2.md) |
| Detection range | ~250 km | |
| Tracks | 1,500 simultaneous | |
| **System composition** | ~7 vehicles per battery | |
| - TRML-4D radar vehicle | 1 | |
| - Command post vehicle | 1 | |
| - Launcher vehicles (SX45 8x8) | 3 (8 missiles each) | |
| - Reload/maintenance vehicles | 2-3 | |
| Missiles per launcher | 8 | |
| Total ready per battery | 24 | |
| Crew | ~20-25 personnel | |
| Reload time | ~15-20 minutes [est] | |
| Mobility | Mobile (wheeled) | |
| Relocate time | ~30-60 minutes [est] | |
| Combat record | Ukraine: 99% reported kill rate | |
| Unit cost per missile | ~$500K [est] | |

### Simulation Parameters
```
iris_t_slm:
  type: sam_mid
  missile_speed_mps: 1020     # Mach 3
  range_max_km: 40
  range_min_km: 1
  altitude_max_m: 20000
  altitude_min_m: 10
  reload_time_s: 1200         # 20 min
  missiles_per_launcher: 8
  launchers_per_battery: 3    # confirmed: 3 per battery = 24 missiles
  radar_range_km: 250
  radar_on_required: true
  mobility: mobile
  relocate_time_s: 2400       # 40 min
  pk:
    cruise_subsonic: 0.90
    cruise_supersonic: 0.60
    fighter: 0.80
    uav_large: 0.90
    uav_small: 0.50
    loitering: 0.75
  cost_per_missile: 50        # abstract units
  unit_value: 2000
```

---

## IRIS-T SLS (Surface Launched Short-range) / RBS 98

| Parameter | Value | Notes |
|-----------|-------|-------|
| Missile | IRIS-T air-to-air missile, ground-launched | |
| Range | ~12 km | |
| Altitude | Up to 8 km | |
| Speed | Mach 2 (~400 m/s average) | Slower than SLM |
| Guidance | IR imaging seeker | 360° engagement capability |
| Launcher | Vehicle-mounted VLS, 4 or 8 missiles | |
| Mobility | Mobile | |
| Role | Short-range protection of ground units & IADS sites | |

### Simulation Parameters
```
iris_t_sls:
  type: sam_short
  missile_speed_mps: 400      # Mach 2 (average)
  range_max_km: 12
  range_min_km: 1
  altitude_max_m: 8000
  missiles_per_launcher: 4
  reload_time_s: 600          # 10 min [est]
  mobility: mobile
  relocate_time_s: 600
  pk:
    cruise_subsonic: 0.80
    fighter: 0.70
    uav_large: 0.85
    uav_small: 0.60
    loitering: 0.75
    fpv: 0.50
  cost_per_missile: 40
  unit_value: 800
```

---

## RBS 70 NG (Saab)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Manufacturer | Saab | Saab product — highlight in demo |
| Missile | Bolide | |
| Range | ~8 km (Bolide), 9 km [some sources] | |
| Altitude | Up to 5 km | |
| Speed | Mach 2.2+ (Bolide, supersonic from launch) | |
| Guidance | Laser beam riding | Operator-guided, jam-resistant |
| Deployment | Tripod (man-portable) or vehicle-mounted | |
| Night capability | Yes (UTAOS thermal sight) | |
| Time to fire | ~30 seconds from ready state | |
| Crew | 2-3 operators | |
| Key advantage | Passive (laser beam riding = no radar emission) | SEAD-immune |

### Simulation Parameters
```
rbs_70_ng:
  type: shorad_missile
  missile_speed_mps: 750      # Mach 2.2+
  range_max_km: 8
  range_min_km: 0.2
  altitude_max_m: 5000
  missiles_ready: 1           # single rail, manual reload
  reload_time_s: 15           # fast reload, single missile
  mobility: mobile
  relocate_time_s: 300        # very mobile, 5 min
  radar_on_required: false    # PASSIVE — laser beam riding
  pk:
    helicopter: 0.80
    uav_large: 0.70
    uav_small: 0.50
    loitering: 0.60
    fpv: 0.30
    fighter: 0.30             # difficult target
    cruise_subsonic: 0.40
  cost_per_missile: 15        # abstract units (relatively cheap)
  unit_value: 200
```

---

## Lvkv 90 (Luftvärnskanonvagn 90)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Platform | CV90 chassis | |
| Main weapon | 40mm Bofors L/70 autocannon | |
| Rate of fire | 300 rounds/min | |
| Effective range (air) | 4 km | |
| Max range | ~12.5 km [theoretical] | |
| Ammunition | Bofors 3P programmable | Airburst, impact, proximity modes |
| Ammo capacity | 24-round box magazines | |
| Radar | PS-95 search/track | 360° coverage |
| Radar detection range | ~14 km | |
| Radar tracks | Up to 6 simultaneous | |
| Fire control | Automatic tracking, lead computation | |
| Mobility | Tracked, accompanies armored units | |
| Shoot on move | No (short halt required) | |
| Crew | 3 | |
| Cost per round | ~$200 [est] | 3P programmable rounds |

### Bofors 3P Ammunition
- **Programmable fuze**: Set mode electronically at muzzle exit
- **Airburst**: Detonates at computed distance — optimal vs drones/UAVs
- **Impact**: Direct hit fuze for harder targets
- **Proximity**: Detonates near target based on sensor
- **Pre-fragmented**: Tungsten pellets for wide kill pattern

### Simulation Parameters
```
lvkv_90:
  type: spaag
  weapon: cannon_40mm
  rate_of_fire_rpm: 300
  range_max_km: 4             # effective vs air
  range_min_km: 0.1
  altitude_max_m: 3000
  ammo_capacity: 144          # est ~6 box magazines of 24 rounds
  ammo_per_engagement: 10     # burst of 10 rounds [est]
  reload_time_s: 300          # ammo resupply [est]
  radar_range_km: 14          # PS-95 confirmed
  radar_on_required: true     # PS-95 for search
  mobility: tracked_mobile
  relocate_time_s: 120        # very fast, tracked vehicle
  pk:                         # per burst (not per round)
    fpv: 0.70                 # excellent with 3P airburst
    uav_small: 0.65
    loitering: 0.60
    helicopter: 0.60
    uav_large: 0.50
    cruise_subsonic: 0.20     # fast crossing target
    fighter: 0.05             # very hard, last resort
  cost_per_engagement: 2      # abstract units (very cheap!)
  unit_value: 600
```
