# Cross-eval tournament — Red × Blue matrix

- Episodes per pair: **30**
- Seed list: 1000–1029 (30 seeds, shared across every pair)
- Episode time limit: 600s sim

## Results matrix

| Red \ Blue | rule | blue_ai_1m_2xpenalty |
|---|---|---|
| rule | R 0% / B 0% / D 100%<br/>len 1200 · dmg 76 · sites_dead 0.03 | R 0% / B 0% / D 100%<br/>len 1200 · dmg 92 · sites_dead 0.03 |
| red_20260421_205051 | R 0% / B 0% / D 100%<br/>len 1200 · dmg 186 · sites_dead 1.17 | R 0% / B 0% / D 100%<br/>len 1200 · dmg 182 · sites_dead 0.93 |
| red_20260421_234425 | R 0% / B 0% / D 100%<br/>len 1200 · dmg 269 · sites_dead 1.37 | R 10% / B 0% / D 90%<br/>len 1193 · dmg 276 · sites_dead 1.67 |

_Cell legend:_ `R% / B% / D%` is Red wins / Blue wins / draws over the n episodes. `len` = mean episode length in decisions (1 decision = 0.5s sim). `dmg` = mean total HP damage across all sites. `sites_dead` = mean count of sites with HP=0.

## Per-pair detail

### rule  vs  rule

- Red spec: `rule`
- Blue spec: `rule`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 0.03 ± 0.18
- Total site damage: 75.8 ± 21.1
- Red budget remaining: $45.7M mean
- Blue budget remaining: $79.4M mean
- Events (per-episode mean): intercepts 5.0 · leaks 1.9 · ground crashes 3.1
- Red spawn totals (all eps): drone: 330, cruise_sub: 240, ballistic: 120, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 347, pac_2: 120, pac_3: 116, iris_t_sls: 93, ciws: 35, rbs_70: 10
- Wall clock: 425.7s

### rule  vs  blue_ai_1m_2xpenalty

- Red spec: `rule`
- Blue spec: `rl/models/blue_ai_1m_2xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 0.03 ± 0.18
- Total site damage: 92.0 ± 18.7
- Red budget remaining: $45.7M mean
- Blue budget remaining: $54.9M mean
- Events (per-episode mean): intercepts 5.9 · leaks 2.7 · ground crashes 3.5
- Red spawn totals (all eps): drone: 330, cruise_sub: 240, ballistic: 120, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 666, pac_2: 228, iris_t_sls: 211, pac_3: 121, ciws: 101, rbs_70: 83
- Wall clock: 517.3s

### red_20260421_205051  vs  rule

- Red spec: `rl/runs/red_20260421_205051/model.zip`
- Blue spec: `rule`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 1.17 ± 0.59
- Total site damage: 186.0 ± 10.7
- Red budget remaining: $0.4M mean
- Blue budget remaining: $70.5M mean
- Events (per-episode mean): intercepts 8.6 · leaks 6.0 · ground crashes 0.2
- Red spawn totals (all eps): cruise_sub: 571, hgv: 211, drone: 32, ballistic: 7
- Blue launch totals (all eps): iris_t_slm: 596, ciws: 259, iris_t_sls: 181, pac_3: 127, pac_2: 125, rbs_70: 55
- Wall clock: 531.2s

### red_20260421_205051  vs  blue_ai_1m_2xpenalty

- Red spec: `rl/runs/red_20260421_205051/model.zip`
- Blue spec: `rl/models/blue_ai_1m_2xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 0.93 ± 0.25
- Total site damage: 181.8 ± 7.2
- Red budget remaining: $0.4M mean
- Blue budget remaining: $40.4M mean
- Events (per-episode mean): intercepts 8.1 · leaks 5.5 · ground crashes 1.2
- Red spawn totals (all eps): cruise_sub: 523, hgv: 210, drone: 149, ballistic: 33
- Blue launch totals (all eps): iris_t_slm: 749, iris_t_sls: 260, pac_2: 240, ciws: 209, pac_3: 191, rbs_70: 144
- Wall clock: 586.5s

### red_20260421_234425  vs  rule

- Red spec: `rl/runs/red_20260421_234425/model.zip`
- Blue spec: `rule`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 1.37 ± 0.49
- Total site damage: 269.3 ± 10.6
- Red budget remaining: $0.0M mean
- Blue budget remaining: $79.8M mean
- Events (per-episode mean): intercepts 7.4 · leaks 8.2 · ground crashes 0.0
- Red spawn totals (all eps): drone: 472, cruise_sub: 388, hgv: 240, ballistic: 1
- Blue launch totals (all eps): iris_t_slm: 569, ciws: 254, iris_t_sls: 98, pac_2: 98, pac_3: 98, rbs_70: 19
- Wall clock: 781.6s

### red_20260421_234425  vs  blue_ai_1m_2xpenalty

- Red spec: `rl/runs/red_20260421_234425/model.zip`
- Blue spec: `rl/models/blue_ai_1m_2xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **3** (10.0%) · Blue **0** (0.0%) · Draw **27** (90.0%)
- Episode length: 1193.1 ± 21.6 decisions
- Sim time: 596.5 ± 10.8 s
- Sites destroyed: 1.67 ± 0.66
- Total site damage: 275.8 ± 12.6
- Red budget remaining: $0.0M mean
- Blue budget remaining: $69.6M mean
- Events (per-episode mean): intercepts 7.1 · leaks 9.1 · ground crashes 0.0
- Red spawn totals (all eps): drone: 474, cruise_sub: 390, hgv: 240
- Blue launch totals (all eps): iris_t_slm: 592, iris_t_sls: 261, rbs_70: 221, pac_2: 120, pac_3: 98, ciws: 96
- Wall clock: 683.8s
