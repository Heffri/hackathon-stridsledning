# Abstract Data Model for Simulation

> System internals use abstract parameterized types. Demo layer maps to real equipment names.

## Asset

```
Asset:
  id:                   string        # unique identifier
  type:                 enum          # fighter | sam_long | sam_mid | sam_short | shorad_missile | spaag | aew | uav_loyal | uav_recon | ew_ground | ew_airborne | sensor_civilian
  display_name:         string        # real-world name for demo (e.g., "Gripen E")
  position:             {lat, lng}    # current position
  base_position:        {lat, lng}    # home base / deployment site
  status:               enum          # ready | airborne | engaged | relocating | rearming | damaged | destroyed
  ammo:                 object        # weapon_type → remaining_count
  effective_range_km:   float         # max engagement range
  min_range_km:         float         # minimum engagement range (dead zone)
  altitude_ceiling_km:  float         # max engagement altitude
  target_types:         list<string>  # what it can engage: ballistic, cruise, fighter, uav_large, uav_small, fpv
  mobility:             enum          # static | mobile | airborne
  radar_on:             bool          # radar emitting (relevant for SEAD risk)
  radar_exposure_s:     int           # cumulative seconds radar has been on
  time_to_ready_s:      int           # seconds until available (rearm, relocate, scramble)
  sortie_endurance_s:   int           # for aircraft: time on station before RTB
  kill_probability:     object        # target_type → Pk (0.0-1.0)
  cost_per_engagement:  float         # abstract cost unit per shot
  unit_value:           float         # abstract value of this asset (for loss calculation)
```

## Threat

```
Threat:
  id:                   string
  type:                 enum          # ballistic | cruise_subsonic | cruise_supersonic | fighter | uav_male | uav_small | fpv | loitering | sead_arm
  position:             {lat, lng}
  heading_deg:          float         # 0-360
  speed_mps:            float         # meters per second
  altitude_m:           float
  rcs_m2:               float         # radar cross section
  threat_level:         enum          # critical | high | medium | low
  time_to_impact_s:     float         # estimated time to reach defended area
  target_id:            string?       # what it's heading toward (if known)
  guidance_type:        enum          # gps | gps_ins | ins | active_radar | ir | beam_riding | fiber | unguided
  ecm:                  enum          # none | basic | advanced
  maneuvering:          bool          # is it performing evasive maneuvers
  quantity:             int           # for swarms: number of individual units
  value:                float         # estimated threat value / damage potential
  detected_by:          list<string>  # which sensor(s) detected it
  track_quality:        enum          # tentative | firm | precise
```

## Assignment (Decision Output)

```
Assignment:
  id:                   string
  threat_id:            string
  asset_id:             string
  weapon_type:          string        # specific weapon to use
  pk_estimate:          float         # estimated probability of kill
  time_to_engage_s:     float         # seconds until weapon reaches threat
  opportunity_cost:     float         # what capability is consumed
  priority_score:       float         # optimizer output score
  status:               enum          # proposed | approved | executing | completed | aborted
  rationale:            string        # human-readable explanation for commander
```

## DefendedArea

```
DefendedArea:
  id:                   string
  name:                 string        # e.g., "Stockholm Metro", "Gotland"
  position:             {lat, lng}
  radius_km:            float
  priority:             enum          # critical | high | medium
  value:                float         # strategic value score
  replaceability:       enum          # irreplaceable | hard | medium | easy | expendable
  replacement_cost:     float         # abstract cost to rebuild
  replacement_time_s:   int           # seconds to restore capability (0 = can't)
  can_evacuate:         bool          # can personnel/critical items be moved?
  evacuation_time_s:    int           # seconds to evacuate if applicable
  hardened:             bool          # underground / blast-resistant?
  has_redundancy:       bool          # backup node exists elsewhere?
  defense_cost_limit:   float         # max abstract cost worth spending to defend
  current_defense_posture: enum       # full | reduced | evacuating | conceded
```

## SimulationState

```
SimulationState:
  tick:                 int           # current time step
  time_s:               float         # elapsed simulation seconds
  assets:               list<Asset>
  threats:              list<Threat>
  assignments:          list<Assignment>
  defended_areas:       list<DefendedArea>
  events_log:           list<Event>   # chronological event log
  resource_forecast:    object        # projected ammo/asset availability over next N minutes
```

## Demo Name Mapping

| Abstract Type | Demo Display Name | Notes |
|---------------|-------------------|-------|
| fighter | Gripen E | Saab product, prioritize |
| sam_long | Patriot PAC-3 | Non-Saab but in Swedish inventory |
| sam_mid | IRIS-T SLM | German, recently ordered by Sweden |
| sam_short | IRIS-T SLS (RBS 98) | |
| shorad_missile | RBS 70 NG | Saab product |
| spaag | Lvkv 90 | Swedish, 40mm Bofors |
| aew | GlobalEye (S 106) | Saab product, our "host platform" |
| uav_loyal | F-series Wingman | Saab future concept |
| uav_recon | Forward Sensor UAV | "Torch" — expendable sensor node |
| sensor_civilian | Civilian AESA Weather Radar | Modified with data link, SEAD sponge |
| ew_ground | Ground EW Station | Abstract / generic |
| ew_airborne | Gripen E Arexis EW | Saab product (built-in) |
