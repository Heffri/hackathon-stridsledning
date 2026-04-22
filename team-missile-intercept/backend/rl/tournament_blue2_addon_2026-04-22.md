# Cross-eval tournament — Red × Blue matrix

- Episodes per pair: **30**
- Seed list: 1000–1029 (30 seeds, shared across every pair)
- Episode time limit: 600s sim

## Results matrix

| Red \ Blue | blue_ai_1m_1xpenalty |
|---|---|
| red_20260421_205051 | R 0% / B 0% / D 100%<br/>len 1200 · dmg 194 · sites_dead 0.70 |
| red_20260421_234425 | R 17% / B 0% / D 83%<br/>len 1188 · dmg 278 · sites_dead 1.70 |

_Cell legend:_ `R% / B% / D%` is Red wins / Blue wins / draws over the n episodes. `len` = mean episode length in decisions (1 decision = 0.5s sim). `dmg` = mean total HP damage across all sites. `sites_dead` = mean count of sites with HP=0.

## Per-pair detail

### red_20260421_205051  vs  blue_ai_1m_1xpenalty

- Red spec: `rl/runs/red_20260421_205051/model.zip`
- Blue spec: `rl/models/blue_ai_1m_1xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **0** (0.0%) · Blue **0** (0.0%) · Draw **30** (100.0%)
- Episode length: 1200.0 ± 0.0 decisions
- Sim time: 600.0 ± 0.0 s
- Sites destroyed: 0.70 ± 0.47
- Total site damage: 194.0 ± 20.4
- Red budget remaining: $0.5M mean
- Blue budget remaining: $41.8M mean
- Events (per-episode mean): intercepts 8.0 · leaks 5.9 · ground crashes 1.1
- Red spawn totals (all eps): cruise_sub: 527, drone: 319, hgv: 210, ballistic: 28
- Blue launch totals (all eps): iris_t_slm: 633, iris_t_sls: 280, pac_2: 240, rbs_70: 210, pac_3: 204, ciws: 5
- Wall clock: 895.3s

### red_20260421_234425  vs  blue_ai_1m_1xpenalty

- Red spec: `rl/runs/red_20260421_234425/model.zip`
- Blue spec: `rl/models/blue_ai_1m_1xpenalty/model.zip`
- Episodes: 30
- Winner breakdown: Red **5** (16.7%) · Blue **0** (0.0%) · Draw **25** (83.3%)
- Episode length: 1188.0 ± 27.6 decisions
- Sim time: 594.0 ± 13.9 s
- Sites destroyed: 1.70 ± 0.75
- Total site damage: 278.5 ± 15.0
- Red budget remaining: $0.0M mean
- Blue budget remaining: $70.2M mean
- Events (per-episode mean): intercepts 6.1 · leaks 9.1 · ground crashes 0.0
- Red spawn totals (all eps): drone: 474, cruise_sub: 390, hgv: 240
- Blue launch totals (all eps): iris_t_slm: 552, rbs_70: 313, iris_t_sls: 257, pac_2: 120, pac_3: 100, ciws: 1
- Wall clock: 965.1s
