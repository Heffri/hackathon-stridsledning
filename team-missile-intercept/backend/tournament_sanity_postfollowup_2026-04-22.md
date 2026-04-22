# Cross-eval tournament — Red × Blue matrix

- Episodes per pair: **30**
- Seed list: 1000–1029 (30 seeds, shared across every pair)
- Episode time limit: 1200s sim

## Results matrix

| Red \ Blue | rule | blue_ai_1m_2xpenalty |
|---|---|---|
| rule | R 0% / B 0% / D 100%<br/>len 2401 · dmg 65 · sites_dead 0.03 | R 0% / B 3% / D 97%<br/>len 2393 · dmg 88 · sites_dead 0.03 |
| red_20260421_234425 | R 0% / B 0% / D 100%<br/>len 2401 · dmg 102 · sites_dead 0.00 | R 0% / B 0% / D 100%<br/>len 2401 · dmg 120 · sites_dead 0.07 |

_Cell legend:_ `R% / B% / D%` is Red wins / Blue wins / draws over the n episodes. `len` = mean episode length in decisions (1 decision = 0.5s sim). `dmg` = mean total HP damage across all sites. `sites_dead` = mean count of sites with HP=0.

## Per-pair detail

### rule  vs  rule

- Red spec: `rule`
- Blue spec: `rule`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 2401.0 ± 0.0 decisions
- Sim time: 1200.0 ± 0.0 s
- Sites destroyed: 0.03 ± 0.18
- Total site damage: 65.2 ± 28.1
- Red budget remaining: $0.7M mean
- Blue budget remaining: $70.5M mean
- Events (per-episode mean): intercepts 14.8 · leaks 1.7 · ground crashes 3.4
- Red spawn totals (all eps): drone: 330, cruise_sub: 240, ballistic: 120, hgv: 90
- Blue launch totals (all eps): ciws: 592, iris_t_slm: 579, rbs_70: 140, pac_2: 120, pac_3: 118, iris_t_sls: 96
- Wall clock: 467.3s

### rule  vs  blue_ai_1m_2xpenalty

- Red spec: `rule`
- Blue spec: `rl/models/blue_ai_1m_2xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **1** (3.3%) · Draw **29** (96.7%)
- Episode length: 2393.3 ± 42.2 decisions
- Sim time: 1196.2 ± 21.1 s
- Sites destroyed: 0.03 ± 0.18
- Total site damage: 88.2 ± 34.5
- Red budget remaining: $0.7M mean
- Blue budget remaining: $0.5M mean
- Events (per-episode mean): intercepts 17.3 · leaks 3.1 · ground crashes 4.0
- Red spawn totals (all eps): drone: 330, cruise_sub: 240, ballistic: 120, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 1150, iris_t_sls: 533, pac_2: 361, rbs_70: 346, pac_3: 256, ciws: 145
- Wall clock: 595.3s

### red_20260421_234425  vs  rule

- Red spec: `rl/runs/red_20260421_234425/model.zip`
- Blue spec: `rule`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 2401.0 ± 0.0 decisions
- Sim time: 1200.0 ± 0.0 s
- Sites destroyed: 0.00 ± 0.00
- Total site damage: 101.5 ± 38.2
- Red budget remaining: $0.2M mean
- Blue budget remaining: $70.6M mean
- Events (per-episode mean): intercepts 24.8 · leaks 4.5 · ground crashes 0.6
- Red spawn totals (all eps): drone: 770, cruise_sub: 480, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 725, ciws: 676, rbs_70: 508, iris_t_sls: 273, pac_2: 106, pac_3: 92
- Wall clock: 963.2s

### red_20260421_234425  vs  blue_ai_1m_2xpenalty

- Red spec: `rl/runs/red_20260421_234425/model.zip`
- Blue spec: `rl/models/blue_ai_1m_2xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 2401.0 ± 0.0 decisions
- Sim time: 1200.0 ± 0.0 s
- Sites destroyed: 0.07 ± 0.25
- Total site damage: 119.5 ± 27.3
- Red budget remaining: $0.1M mean
- Blue budget remaining: $0.1M mean
- Events (per-episode mean): intercepts 26.8 · leaks 7.1 · ground crashes 0.5
- Red spawn totals (all eps): drone: 907, cruise_sub: 480, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 1152, rbs_70: 772, iris_t_sls: 665, pac_2: 328, pac_3: 248, ciws: 245
- Wall clock: 1382.5s
