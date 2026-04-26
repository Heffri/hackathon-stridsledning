# PM Handoff — Post-Hack-Day → Pre-Finale

> Hack Day (2026-04-25 08:30) is done. Finale on 2026-04-27 16:30.
> This handoff covers everything done from Hack Day eve through
> 2026-04-26 morning, current branch state, what's broken, what's
> left to try.

## TL;DR — 30 second read

**Demo state**: stable, shipped on `final-demo` branch. Model =
`blue_aoe_aggressive_B_shaped` (2.3 M warmstart + 500 k reward
shaping). Plus Path C strategic_fallback in `live_ai.py` plus Path 1
predictive dispatch (PAC-3 fires pre-emptively at incoming
ballistic/HGV before strict range gate).

**For Hack Day demo we used**: Layout D + Red 110M + Blue 200M +
ScriptedRed. Sites 2/3 alive average, all 6 launchers fire on D.

**Post-Hack-Day "for fun" experiment**: cap expanded 30/15/40 →
120/60/160 with backward-compat adapter in live_ai.py. Then trained
fresh 120-cap model overnight (`blue_120_v4_path2_scratch`). Result:
**flopped** — 2.5 M / 10 M steps, fps 74 (CPU-bound), ep_rew_mean
flat at -1070. Wired into dropdown but quality is suspect.

**Open immediate question**: did Chen actually try the cap120 model
in browser yet? (Last message: he was just about to.) Result of
that eyeball test directs the next step.

---

## Branch + worktree map

### Branches (all on origin)

| Branch | Tip | What it has |
|---|---|---|
| **`final-demo`** | `a232886` | **Production demo**. Has cap-120 + adapter + Path 1 + cap120 model in dropdown |
| `cap-120-experiment` | `e7e7287` | First cap expansion exploration (merged to final-demo via push) |
| `train-120-v4-path2` | `bb77301` | Overnight training branch with v2/v3/v4 reward stack + Path 2 loose mask. Not merged to final-demo (training results were poor) |
| `path1-predictive-dispatch` | `1485681` | Path 1 predictive dispatch (merged to final-demo) |
| `blue-aoe-pathc-final` | `e9c6ce8` | Original Hack Day demo polish (B-shaped + Path C). Older, superseded by final-demo |

### Worktrees (local)

| Worktree | Branch | Use |
|---|---|---|
| `cool-golick-1340ba` | final-demo | **Chen's demo worktree** — runs server.py from here |
| `admiring-fermat-5b34d4` | train-120-v4-path2 | Overnight training output dir |
| `optimistic-sanderson-420b4b` | cap-120-experiment | Earlier capacity-expansion work |
| `heuristic-merkle-0e74cf` | claude/heuristic-merkle-0e74cf | Pre-Hack-Day demo state |
| Main `hackathon-stridsledning` | red-ai | Messy with uncommitted RL WIP — DO NOT touch |

---

## What we did (chronological)

### 1. Hack Day day-of (2026-04-25 morning)

Chen was preparing for 08:30 Hack Day. Demo using B_shaped (3.3 M
cumulative steps, B-path tiered leak penalty in env.py reward,
warmstarted from blue_aoe_long/model_v2.zip). Plus Path C
`_force_strategic_fallback` in `live_ai.py` so PAC-3 fires when
policy ignores ballistic / HGV.

Demo config:
- Layout D (3 CIWS, 6 RBS-70, 4 SLS, 3 SLM, 1 PAC-2, 2 PAC-3)
- Red budget 110M (110 M is "demo-friendly", lower than the v3
  spec'd 150 M but lets sites stay alive)
- Blue budget 200 M
- ScriptedRed 3-chain
- Episode time 3000 s

All went OK. Demo ran. We don't know if Chen advanced to Finale.

### 2. Capacity expansion (post-Hack-Day evening)

For Boyu's V2/V2a (96/24/128 cap) to load, env had to grow. Decided
to expand:
- `MAX_THREATS` 30 → 120
- `MAX_LAUNCHERS` 15 → 60
- `MAX_INTERCEPTORS` 40 → 160
- `MAX_SITES` 10 (unchanged)

Plus backward-compat adapter in `live_ai.py` `LearnedBlueAI`:
- `_adapt_obs_for_model` slices env's bigger tensors to model's
  expected shape
- `_adapt_action_for_env` remaps model's hold sentinel + pads
  action vector to env's bigger MAX_LAUNCHERS

All previously-trained models (B_shaped at 30/15/40, Boyu V2 at
96/24/128) load and play via the adapter.

Done in worker `cap-120-experiment` branch, pushed to final-demo.

### 3. Path 1 — predictive strategic dispatch

Inside `_force_strategic_fallback` (live_ai.py LearnedBlueAI), the
range check changed from "strict in-range" to "trajectory enters
range within fuel_s - 3 s". So PAC-3 fires earlier on incoming
Mach-7 ballistic / Mach-13 HGV instead of waiting for them to
cross the strict 88 km gate.

Math: solve `|threat_pos + t·threat_vel - launcher_pos| = R` for
earliest `t > 0`. Fire if `0 < t_enter < fuel_s - 3.0`.

Smoke confirmed: ballistic at 240 km out gets PAC-3 launched at
t=0.05s, killed at t=37s.

### 4. Overnight training: blue_120_v4_path2_scratch

Goal: train a fresh policy at 120 cap with reward improvements
(v2/v3/v4 reward stack: spend×10, time penalty, terminal HP/budget
split, weighted sites, drone leak ×4) plus Path 2 loose action
mask (fires allowed at 3× max_range so policy can learn pre-emptive
launches).

Configuration:
- 24 envs (12 cores × 2 SMT on 5950X)
- `--device cuda` (RTX 5070, sm_120)
- 10 M steps target, checkpoint every 500 k
- Episode 3000 s
- Red 150 M / Blue 200 M / scripted Red / layouts C+D
- No warmstart (cap mismatch with old 30-cap models)

**Result**: 2.5 M / 10 M steps in 9.5 h. fps was **74** (CPU sim
was the bottleneck, not GPU — RTX 5070 sat at 4-9 % util the whole
run). ep_rew_mean went 135k=-1110 → 1M=-1060 → flatlined ~-1070
through 2.5M. **Reward never went positive**. Policy didn't
clearly learn anything useful.

Worker auto-stopped at 2.5M, copied model, wrote report at
`progress/TRAIN_120_V4_PATH2_REPORT.md`.

### 5. Wired model into UI dropdown

Two-file edit (caught after Chen pointed out it wasn't showing):
- `backend/server.py` line 37: added `("cap120", "RL 120-cap (scratch, 2.5M)", ...)`
- `frontend/index.html` line 78: added `<option value="cap120">`

Frontend dropdown options are **hardcoded HTML**, not dynamically
generated from BLUE_AI_MODELS. Both files must be edited in sync.
This was a misstep — only edited server.py first, dropdown didn't
update, had to push a second commit.

---

## What went wrong (lessons for next time)

1. **fps projection off by 13×**. Estimated ~1000 fps for 120-cap
   on RTX 5070; got 74. Reason: action-mask + range-check is
   `O(MAX_LAUNCHERS × MAX_THREATS)` — at 60×120 = 7 200 ops per
   tick per env vs 15×30 = 450 (16× more). Times 24 envs over
   Python's GIL + SubprocVecEnv IPC overhead = CPU-bound. GPU sat
   idle. **Next time**: project fps ~1/15× the 30-cap baseline,
   not 1×.

2. **PyTorch 2.5+ doesn't support GTX 1080 (Pascal sm_61)**. Chen's
   dual-GPU plan (train on 1080, game on 5070) was killed by this.
   PyTorch 2.4 supports Pascal but doesn't support Blackwell
   (sm_120). Can't have both. Result: Chen never got to use the
   1080 for training — drove gaming on 1080 instead.

3. **Frontend dropdown is hardcoded HTML**. Adding a model means
   editing both `server.py::BLUE_AI_MODELS` AND
   `frontend/index.html` `<option>` list. I forgot the second.
   **Could be future-proofed**: have JS read model list from server
   API + populate dropdown dynamically. Out of scope for now.

4. **Training fresh-from-scratch with bigger network is slow**.
   Without warmstart, 2.5 M steps on a 120-cap PPO from random
   init is barely past "explore phase". Needs 5-10 M+ to stabilise.
   We don't have that wall-clock budget on current hardware.

5. **Boyu V2/V2a load but don't play well**. Distribution shift
   (different game balance at training) makes them spam PAC-3 at
   drones from start. Adapter unblocks LOAD, not BEHAVIOUR.

6. **`world.t > 2500s` heuristic** added to ScriptedRed `done`
   logic during Hack Day to fix "Red sits with $300 k, match
   draws" bug — works but is hacky. Real fix is a proper
   trigger-queue cleanup. Out of scope unless the 2500 s threshold
   ever conflicts with a longer training episode.

---

## Open items / what's next

### Immediate (Chen will discover)

- **Eyeball cap120 model in browser** — Chen was about to try this
  when context ran out. Likely outcome: it plays poorly (per the
  flat reward trajectory). If so:
  - Don't deploy as primary
  - Either delete from dropdown or leave as "experimental reference"
  - Decide whether to try training again with different config

### Pre-Finale options (2026-04-26 to 04-27 16:30)

| Option | Effort | Risk | Payoff |
|---|---|---|---|
| **A. Stick with B_shaped + Path C** for Finale | 0 | none | proven stable demo |
| **B. Retrain at 60-cap** (smaller network, fewer ops, faster fps, can warmstart from B_shaped via weight padding) | high | medium | possible better policy |
| **C. Re-run cap120 with longer wall clock** (don't touch architecture, just give it more steps; need 36+ h on current CPU) | moderate | medium-high | might learn but might still flatline |
| **D. Tune Path 1 + Path C harder** for cleaner "all 6 weapons fire visibly" demo | low | low | better Finale visuals, no model change |
| **E. Train Red AI** instead of Blue (e.g., a smarter scripted Red, or a learned Red AI) | high | high | makes Finale less predictable |

Chen's preference is unknown but he sounded relaxed about the
cap-120 experiment as "for fun" not critical. Default: option A,
maybe with option D polish.

### Hardware notes (read before next training)

- **PyTorch tied to single GPU at a time**: 2.5+ supports 5070 +
  most modern but NOT 1080. 2.4 supports 1080 but NOT 5070. Pick
  one architecture per training run.
- **CPU is bottleneck for 120-cap PPO** on this machine — GPU
  upgrades won't help. Need to either drop cap or accept slow fps.
- **Game on 1080, train on 5070** if both wanted simultaneously
  (display cable into 1080). Not tested in practice — Windows GPU
  routing chaos may need NVIDIA Control Panel work.

### Code debt

- `eval_demo_b_pathc.py` is hand-written demo eval, lives in
  backend/. Useful but ad-hoc. Could be folded into per_layout_eval.
- `_path_c_fallback_snippet.py` may still be in worker tree — was
  scratch file. If found, delete.
- Frontend hardcoded model list (`index.html`) — see lesson #3.
- Many `.runlog` files untracked in cool-golick worktree (cleanup
  candidate).

---

## Quick reference

### Demo PowerShell (current production)

```powershell
cd C:\Users\xingy\Documents\github\hackathon-stridsledning\.claude\worktrees\cool-golick-1340ba\team-missile-intercept\backend
python server.py
```

Browser → SETUP →
- Budget: Red `110_000_000`, Blue `200_000_000`
- Layout: D (or C as backup)
- AI: Blue dropdown → "RL Aggressive (AOE shaped)" (= B_shaped + Path C)
- Red dropdown → "Scripted 3-Chain"
- Apply Layout → Start Match
- Speed 10-20× to watch, 50× to fast-forward

### Available Blue AI dropdown options

```
rule       → Heuristic (rule-based, no NN)
blue1      → RL Cautious 2x leak penalty (legacy 1M)
blue2      → RL Balanced 1x leak penalty (legacy 1M)
aoe        → RL Aggressive AOE shaped (B_shaped, demo primary) ⭐
v3         → RL Site-Priority weighted (reward v2 finetune)
v4         → RL CIWS Active (reward v4 finetune)
boyu_v2    → RL Boyu V2 (96-cap, distribution-shifted)
boyu_v2a   → RL Boyu V2a (96-cap, distribution-shifted)
cap120     → RL 120-cap scratch 2.5M (NEW, untested in browser, likely poor)
```

### Key paths

- Demo model: `team-missile-intercept/backend/rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip`
- New cap120 model: `team-missile-intercept/backend/rl/runs/blue_local/blue_120_v4_path2_scratch/model.zip` (also in cool-golick worktree)
- Overnight training report: `team-missile-intercept/progress/TRAIN_120_V4_PATH2_REPORT.md`
- Hack Day report: `team-missile-intercept/progress/OVERNIGHT_REPORT_2026-04-25.md`
- This file: `team-missile-intercept/progress/HANDOFF_POST_HACK_DAY_2026-04-26.md`

### Critical file edit points

| To do | Edit | Notes |
|---|---|---|
| Add Blue AI model | `backend/server.py::BLUE_AI_MODELS` + `frontend/index.html` `<option>` list | TWO files |
| Add Red AI model | `backend/server.py::RED_AI_MODELS` + `frontend/index.html` red-ai-select options | TWO files |
| Tweak threat speed | `backend/sim/types.py::THREAT_SPECS[X].cruise_speed` | Affects training distribution |
| Tweak interceptor | `backend/sim/types.py::INTERCEPTOR_SPECS[X]` | Same |
| Tweak reward | `backend/rl/env.py::_reward_from_events` | Training only |
| Tweak action mask | `backend/rl/env.py::_build_action_mask` | Training affects RL behavior |
| Inference behavior | `backend/rl/live_ai.py` (Path C, Path 1, adapter) | Live demo only |

### NVIDIA driver state (Chen's machine)

- 581.80 installed (covers both 5070 + 1080)
- `nvidia-smi` shows both cards
- PyTorch 2.5+ uses 5070 only (sm_120) — emits Pascal warning, ignore
- 1080 functionally unused for training; can be used for display + gaming if monitor cable is plugged into it (untested)
- Some Windows GPU routing chaos observed when monitor on 1080 — games still pull 5070. NVIDIA Control Panel + Windows graphics-prefs may need tuning.

### git aliases / common commands

```bash
# Sync local to origin
cd <worktree>
git fetch origin
git pull --ff-only origin final-demo

# Push to final-demo without merge
git push origin <branch>:final-demo

# Find a worktree's branch
git worktree list

# What's on branch X but not Y
git log --oneline X ^Y
```

---

## What I'd say to a fresh PM session

> "Hack Day's done, demo's stable on final-demo. Last night we
> tried a fun experiment (cap expansion + fresh training) — model
> is wired into the dropdown as 'cap120' but Chen never finished
> eyeballing it before context ran out.
>
> Chen's last action was Ctrl+Shift+R to refresh the browser and
> select cap120. Ask him: did you try it? What did you see?
>
> Default plan: Finale demo uses B_shaped + Path C + Layout D + Red
> 110M, same as Hack Day. Anything else is icing. We have
> 04-26 + most of 04-27 for iteration but no need to risk the
> stable demo for marginal gains.
>
> Don't trust 1000 fps projections for big-cap training; the
> overnight run was 13× slower than estimated. CPU sim is the
> bottleneck."
