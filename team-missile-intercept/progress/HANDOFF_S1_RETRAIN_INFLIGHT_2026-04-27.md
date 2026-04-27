# Handoff — S1 Retrain in Flight on 5950X

**Date**: 2026-04-27 ~14:15 UTC (decision deadline: 17:00 Finale)
**Status**: Training in progress on Chen's local 5950X desktop
**Audience**: Laptop PM session at venue, teammates, anyone who needs to know

---

## TL;DR

A new Blue model is being retrained right now on Chen's 5950X desktop with a redesigned reward function targeted at the PAC-spam regression we identified at 13:00. Training started ~14:11, projected completion ~15:02, will auto-push to GitHub on branch `train-s1-retrain-anti-pac-spam`. Plenty of buffer before 17:00 Finale.

If the new model works at venue, it becomes Plan A. If it doesn't, V4 stays as primary demo (no regression — V4 is unchanged on `final-demo`).

---

## Why we're doing this

The big-model PAC-spam diagnosis (see [BIG_MODELS_POSTMORTEM_zh.md](BIG_MODELS_POSTMORTEM_zh.md) + [V4_DISTRIBUTION_SHIFT_UPDATE_zh.md](V4_DISTRIBUTION_SHIFT_UPDATE_zh.md)) concluded:

- All megamodel stages (S1-S4) regressed into "open match by firing PAC-2/PAC-3 at drones"
- Root cause: doctrine reward over-shaping (head-on bonus + multipliers + 0.5/M spend penalty + 5000s episode horizon)
- V4 is the only viable Blue but its training distribution is fragile (Layout C + Red 150M / Blue 200M required, otherwise distribution shift)

Hypothesis: a redesigned reward function with **explicit PAC-on-drone penalty** + simpler shaping should produce a viable model.

## Training config

```
Branch:      train-s1-retrain-anti-pac-spam (off final-demo @ 4199c8c)
Worktree:    .claude/worktrees/s1-retrain/
Run dir:     team-missile-intercept/backend/rl/runs/blue_s1_retrain/
Hardware:    Ryzen 5950X (16C/32T), CPU-only training
n_envs:      30 (16 phys × 2 SMT, leave 2 for OS)
Cap:         72/32/128 (matches megamodel S1 for direct A/B)
Layout pool: C only
Red mode:    scripted only
Episode:     3000s
Budget:      Red 150M / Blue 200M
Steps:       1.5M HARD_CAP, no early-stop monitor
Save every:  200000
```

## Reward design changes vs megamodel S1

| Term | Megamodel S1 | S1 Retrain |
|---|---|---|
| `(HIT_TO_KILL, DRONE)` | 1.0× canonical | **−5.0 flat penalty** |
| `(HIT_TO_KILL, CRUISE_SUB)` | 1.0× | **−2.0** |
| `(LONG_SAM, DRONE)` | 1.0× | **−3.0** |
| `(LONG_SAM, CRUISE_SUB)` | 1.0× | **−1.0** |
| `(CIWS, DRONE)` | 1.0× canonical | **+0.05 bonus** (CIWS preference nudge) |
| Cheap-on-hard gambles (CIWS×ballistic etc.) | 2.0× / 1.5× multiplier | **+2.0 / +1.0 flat additive** |
| Anti-doctrine (SAM×drone 0.7×) | 0.7× | **0** (let spend penalty + AOE handle) |
| Head-on bonus | 0.5 (PAC × ballistic/HGV) | **0.5 (kept, same gating)** |
| Spend penalty | 0.5/M | **0.15/M** (between V4's 0.05 and megamodel's 0.5) |
| Base-weight scaling | n_initial / n_alive ×3 | **kept (V4 mirror)** |
| Dead-base zero-out | yes | **kept** |
| Drone leak weight | 2.0 | **4.0** (V4 CIWS-active emphasis) |
| Episode time | 5000s | **3000s** (Hack Day demo length) |
| Budget-aware modifier | 0.5x-2.0x | **dropped** |

## Runtime status (live as of writing)

```
Iter 1 (43s):   fps 709, 30720 steps logged
Iter 2 (~):     fps 547 (PPO update overhead)
Iter 3 (~):     fps ~500 stable
Projection:     1.5M @ 500 fps = 50 min wall → finish ~15:02
ep_rew_mean:    not yet (long episodes; first complete episode at ~500k steps)
Current step:   ~100k+
```

If fps stays at 500, full 1.5M takes ~50 min. If fps drops below 300 sustained, full run is ~85 min. Either way, training will be done well before 17:00.

## Deviations from the original prompt

1. **Run dir path**: prompt assumed `rl/runs/blue_local/blue_s1_retrain/`. `train.py` actually writes to `rl/runs/blue_s1_retrain/` (no `blue_local` parent). Dropdown registration adjusted to match real path. Functionally identical, just a path difference.

2. **Cap revert**: prompt's verification expected `(72, 12)` obs shape. Final-demo branch has `MAX_THREATS=120`. Worker reverted env.py caps to 72/32/128 to match training requirements. **Note for the laptop PM session**: this means `env.py` on this branch has cap-72, NOT cap-120. The live_ai adapter handles cross-cap deployment so demo runs at cap-120 env on final-demo via standard adapter.

3. **Tensorboard + tqdm + rich added to requirements**: SB3's progress callback needs them. Worker installed during setup.

4. **Train launch via `Start-Process`** instead of inline Bash (worker session timeout would have killed inline). Process detached from Claude Code, monitored via separate file polling.

## When training completes

Worker will:
1. Verify model loads (`python -c "...MaskablePPO.load(...).observation_space..."`)
2. Edit `server.py` BLUE_AI_MODELS (add `s1_retrain` slot)
3. Edit `frontend/index.html` (add dropdown option)
4. Edit `rl/env.py` (commit the reward changes)
5. `git add` + commit + `git push origin train-s1-retrain-anti-pac-spam`

Auto-pushed branch: **`train-s1-retrain-anti-pac-spam`**

## Venue testing flow (for the laptop PM session)

```powershell
# After training completes (~15:02-15:30 expected)
cd <demo worktree on laptop>
git fetch origin
git checkout train-s1-retrain-anti-pac-spam   # or merge into a local test branch
cd team-missile-intercept\backend
python server.py
```

Browser test:
- Blue: **RL S1 Retrain (anti-PAC-spam)**
- Layout: **C**
- Budget: Red **150M** / Blue **200M** (must manually set!)
- Red: **Scripted 3-Chain**
- Start Match → first match should NOT show PAC-spam

What to look for:
- ✓ CIWS engages drones in opening 30-drone wave
- ✓ PAC-3 / PAC-2 NOT firing on drones
- ✓ PAC-3 head-on intercepts ballistic / HGV in later waves
- ✓ 3/3 bases alive at end (or at least 2/3)

## Decision tree at venue

| S1 Retrain test result | Demo Plan A |
|---|---|
| Clear PAC-spam fix, all-base survival | **Switch to S1 Retrain** for demo. New narration: "we caught a reward bug at 13:00, retrained on local hardware, here's the result" — strong evidence-of-iteration story for jury Q3/Q4 |
| Slightly better than megamodel but still some PAC misuse | **Stay on V4 + Layout C + 150M/200M**. Mention S1 Retrain in Q&A as "we tried but more time needed" |
| Worse or broken | **Stay on V4**. S1 Retrain becomes unmentioned debug evidence |

V4 stays the safety net — it's untouched on `final-demo`.

## Files locations after push

After worker auto-pushes, on `train-s1-retrain-anti-pac-spam` branch:

```
team-missile-intercept/backend/rl/env.py                              # reward + spend changes
team-missile-intercept/backend/rl/runs/blue_s1_retrain/model.zip      # final model
team-missile-intercept/backend/rl/runs/blue_s1_retrain/training.log   # full log
team-missile-intercept/backend/rl/runs/blue_s1_retrain/launch_cmd.txt # exact CLI
team-missile-intercept/backend/rl/runs/blue_s1_retrain/pip_freeze.txt # deps
team-missile-intercept/backend/server.py                              # +s1_retrain slot
team-missile-intercept/frontend/index.html                            # +dropdown option
```

## Risks / open issues

1. **Training might not converge** — 1.5M cold start at cap-72 may be insufficient. ep_rew_mean trajectory will tell us. If still flat at 1.5M, model behavior likely random in spots.

2. **Reward design might have unforeseen bugs** — the new doctrine penalty terms haven't been A/B tested. Best mitigation is venue browser eyeball.

3. **5950X power state** — if Chen's desktop drops to power-saving mid-training, fps could plummet. Worker is monitoring.

4. **Push might fail** — if Chen's desktop loses network, model is on disk but not on GitHub. Worker should retry; if persistent failure, Chen can SCP / manual upload.

---

End of handoff. Next update: when training completes + branch pushed.
