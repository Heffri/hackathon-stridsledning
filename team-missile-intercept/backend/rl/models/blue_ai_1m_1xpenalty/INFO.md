# blue_ai_1m_1xpenalty

PPO MaskablePPO Blue-side policy.

## Training
- Steps: 1,000,000 (scratch, no resume)
- n_envs: 8
- Device: cuda (RTX 5070)
- Red opponent: `red_mode=training_random`, `difficulty=mixed`
- Wall time: ~87 min

## Reward shaping
- Intercept: `+SITE_LEAK_DAMAGE[kind] * 2`
- Leak: `-damage * 2`
- Cost-efficiency penalty: `max(0, (interceptor_cost - threat_cost) / $1M) * 1.0`  ← half of v1 (2.0)
- Terminal: `+100` blue win, `-100` red win, `0` draw
- Per-decision: weak `-spent/1e6 * 0.05` efficiency term

## Eval (20 matches each)

### red_mode=demo_fixed
| Policy | Win | Reward | Fires | HP |
|---|---|---|---|---|
| hold | 0/20 (0%) | -478.3 | 0 | 120 |
| random | 19/20 (95%) | +338.8 | 97.3 | 213 |
| closest | 19/20 (95%) | +317.1 | 121.2 | 210 |
| trained (det) | 19/20 (95%) | +309.2 | 116.8 | 208 |
| trained (stoch) | 19/20 (95%) | +312.1 | 103.2 | 209 |

### red_mode=training_random difficulty=hard
| Policy | Win | Reward | Fires | HP |
|---|---|---|---|---|
| hold | 0/20 (0%) | -498.7 | 0 | 113 |
| random | 13/20 (65%) | +122.1 | 82.6 | 171 |
| closest | 13/20 (65%) | +90.6 | 111.3 | 164 |
| trained (det) | 13/20 (65%) | +103.7 | 99.9 | 166 |
| trained (stoch) | 13/20 (65%) | +112.2 | 90.8 | 169 |

## Comparison vs blue_ai_1m_2xpenalty (v1)

|  | v1 (W=2.0) | v2 (W=1.0) |
|---|---|---|
| demo det win rate | 90% | 95% |
| demo det reward | +263.2 | +309.2 |
| hard det reward | +72.3 | +103.7 |
| hard stoch reward | +91.0 | +112.2 |

Halving the cost-diff penalty let the agent fire more freely when only
an expensive interceptor was in range, improving all metrics without
sacrificing the "prefer cheap when available" preference.

## Notes
- Still at parity with random/closest baselines on win rate — 1M steps
  not enough to surpass simple heuristics on this env.
- Fewer fires than closest on both scenarios (105-117 vs 121 on demo,
  91-100 vs 111 on hard).
- Next experiment: curriculum (easy → mixed → hard) or longer training.
