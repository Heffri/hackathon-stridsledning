# Cross-eval tournament — Red × Blue matrix

- Episodes per pair: **30**
- Seed list: 1000–1029 (30 seeds, shared across every pair)
- Episode time limit: 600s sim

## Results matrix

| Red \ Blue | rule | blue_ai_1m_2xpenalty |
|---|---|---|
| rule | R 0% / B 0% / D 100%<br/>len 1200 · dmg 65 · sites_dead 0.03 | R 0% / B 0% / D 100%<br/>len 1200 · dmg 80 · sites_dead 0.03 |
| red_20260421_234425 | R 0% / B 0% / D 100%<br/>len 1200 · dmg 69 · sites_dead 0.00 | R 0% / B 0% / D 100%<br/>len 1200 · dmg 71 · sites_dead 0.00 |

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
- Total site damage: 65.2 ± 28.1
- Red budget remaining: $0.7M mean
- Blue budget remaining: $79.3M mean
- Events (per-episode mean): intercepts 5.0 · leaks 1.7 · ground crashes 3.4
- Red spawn totals (all eps): drone: 330, cruise_sub: 240, ballistic: 120, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 344, pac_2: 120, pac_3: 118, iris_t_sls: 85, ciws: 47, rbs_70: 11
- Wall clock: 271.7s

### rule  vs  blue_ai_1m_2xpenalty

- Red spec: `rule`
- Blue spec: `rl/models/blue_ai_1m_2xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 0.03 ± 0.18
- Total site damage: 80.0 ± 31.1
- Red budget remaining: $0.7M mean
- Blue budget remaining: $54.0M mean
- Events (per-episode mean): intercepts 5.8 · leaks 2.4 · ground crashes 4.0
- Red spawn totals (all eps): drone: 330, cruise_sub: 240, ballistic: 120, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 689, pac_2: 228, iris_t_sls: 210, ciws: 145, pac_3: 122, rbs_70: 84
- Wall clock: 325.4s

### red_20260421_234425  vs  rule

- Red spec: `rl/runs/red_20260421_234425/model.zip`
- Blue spec: `rule`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 0.00 ± 0.00
- Total site damage: 69.0 ± 35.7
- Red budget remaining: $0.5M mean
- Blue budget remaining: $81.1M mean
- Events (per-episode mean): intercepts 8.3 · leaks 2.1 · ground crashes 0.6
- Red spawn totals (all eps): drone: 506, cruise_sub: 480, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 513, iris_t_sls: 174, pac_2: 106, pac_3: 92, rbs_70: 44, ciws: 13
- Wall clock: 514.2s

### red_20260421_234425  vs  blue_ai_1m_2xpenalty

- Red spec: `rl/runs/red_20260421_234425/model.zip`
- Blue spec: `rl/models/blue_ai_1m_2xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 0.00 ± 0.00
- Total site damage: 71.0 ± 28.8
- Red budget remaining: $0.2M mean
- Blue budget remaining: $53.2M mean
- Events (per-episode mean): intercepts 7.8 · leaks 2.6 · ground crashes 0.5
- Red spawn totals (all eps): drone: 776, cruise_sub: 480, hgv: 90
- Blue launch totals (all eps): iris_t_slm: 630, iris_t_sls: 330, pac_2: 196, rbs_70: 172, pac_3: 148, ciws: 4
- Wall clock: 557.1s
