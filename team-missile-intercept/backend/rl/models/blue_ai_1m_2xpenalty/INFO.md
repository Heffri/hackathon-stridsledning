# blue_ai_1m_2xpenalty

PPO MaskablePPO Blue-side policy.

## Training
- Steps: 1,000,000 (scratch, no resume)
- n_envs: 8
- Device: cuda (RTX 5070)
- Red opponent: `red_mode=training_random`, `difficulty=mixed`
- Wall time: ~85 min

## Reward shaping
- Intercept: `+SITE_LEAK_DAMAGE[kind] * 2`
- Leak: `-damage * 2`
- Cost-efficiency penalty: `max(0, (interceptor_cost - threat_cost) / $1M) * 2.0`
- Terminal: `+100` blue win, `-100` red win, `0` draw
- Per-decision: weak `-spent/1e6 * 0.05` efficiency term

## Eval (20 matches each)

### red_mode=demo_fixed
| Policy | Win | Reward | Fires | HP |
|---|---|---|---|---|
| hold | 0/20 (0%) | -478.3 | 0 | 120 |
| random | 19/20 (95%) | +324.2 | 97.3 | 213 |
| closest | 19/20 (95%) | +300.8 | 121.2 | 210 |
| trained (det) | 18/20 (90%) | +263.2 | 107.0 | 205 |
| trained (stoch) | 19/20 (95%) | +313.0 | 97.5 | 211 |

### red_mode=training_random difficulty=hard
| Policy | Win | Reward | Fires | HP |
|---|---|---|---|---|
| hold | 0/20 (0%) | -498.7 | 0 | 113 |
| random | 13/20 (65%) | +107.6 | 82.6 | 171 |
| closest | 13/20 (65%) | +75.7 | 111.3 | 164 |
| trained (det) | 13/20 (65%) | +72.3 | 104.5 | 162 |
| trained (stoch) | 13/20 (65%) | +91.0 | 90.5 | 166 |

## Notes
- Matches random/closest baselines but doesn't beat them — 1M steps insufficient on this env.
- Fewer fires than closest heuristic (97 vs 121) → better ammo efficiency.
- `COST_DIFF_WEIGHT=2.0` suspected of biting exploration too hard when cheaper
  launcher not in range; `blue_ai_1m_1xpenalty` is the follow-up experiment.
