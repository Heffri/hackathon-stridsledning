# Big-Model Demo Failure — Postmortem

**Date**: 2026-04-27
**Author**: PM session
**Scope**: Saab 2026 hackathon arcade-game demo. All numbers below are gameplay balance constants, not real weapon/system data.

---

## TL;DR

All our "big" RL Blue models (Boyu V2a / Cap120 / Megamodel) regressed during pre-Finale demo testing into a shared failure mode: **opening the match by firing PAC-2 / PAC-3 (≈$5M each) at incoming drones (≈$30K each)** — a 1:166 cost-exchange catastrophe. The only Blue model that competes with the original hand-written rule heuristic (`sim/blue_ai.py`) is **V4 (CIWS Active) + the Path 1 predictive-dispatch rule layer in `live_ai.py`**. Arguably the rule heuristic generalizes even better.

The Red side has one bright spot: the new **Red Trainee v2** discovered a non-obvious **bait-and-saturate** strategy that no part of the reward function explicitly encoded. This is the cleanest piece of evidence-of-learning we have, and it should anchor the Finale narration.

---

## 1. The shared failure — "PAC-spam syndrome"

| Model | Trained at cap | Steps | Demo behaviour |
|---|---|---|---|
| Boyu V2a | 96/24/128 | unknown (sufficient) | Opens with PAC-2/PAC-3 against the 30-drone first wave |
| Cap120 | 120/60/160 | 2.5M cold-start (did not converge) | Same, more random |
| Megamodel | 72/32/128 | ~5M curriculum | Same, with more "confidence" |
| **V4** | 30/15/40 | 1M+ finetune | **Correct** — CIWS handles drones, PAC reserved for ballistic / HGV |

PAC-3 unit cost ≈ $5M, drone ≈ $30K → cost-exchange 1:166. Burning a budget on PAC-3-vs-drone in the opening is essentially self-inflicted defeat.

---

## 2. Per-model diagnosis

### 2.1 Megamodel — reward over-shaping

Trained with very aggressive doctrine reward shaping:

- `(CIWS, ballistic): 2.0` multiplier → bonus when cheap interceptor kills hard target
- `head_on_weight = 0.5` → +50% reward when PAC head-on intercepts ballistic
- `spend penalty 0.5/M` → significant per-fire cost (10× the V4 spend penalty)
- `base_weight × 3` when only 1 base alive → leak penalty triples

Doing the math:
- **PAC-3 head-on hit on ballistic** = +7.5 reward (highest event reward in the table)
- **CIWS killing 30 drones** = 30 × 0.029 ≈ +0.87 (low margin)

The policy learned "PAC-vs-ballistic is the big-ticket trade; CIWS-vs-drone is marginal", and tilted toward **firing PAC early** to hunt for the big payoff. Combined with a strong spend penalty (doing nothing also costs you), the model preferred **fire-now-think-later** behaviour even when the only threats on screen were drones.

Worker's own note in the training report: *"the displayed reward is dominated by leak-penalty magnitude, not necessarily by quality of decisions"*. Training `ep_rew_mean` plateaued around -1170 across all 4 stages — **the curriculum did not converge in any meaningful sense**.

### 2.2 Cap120 — undertrained

2.5M steps, cold-start at cap-120/60/160:

- Action mask = 60 × 121 = **7260 dims** vs V4's 15 × 31 = 465 dims (15.6× larger)
- CPU-bound, 74 fps × 24 envs = 1776 transitions/sec
- 2.5M steps / 1776 fps ≈ 1400 wall-seconds — far short of what's needed for an action space this large to converge
- Training log: `ep_rew_mean: 135k=-1110 → 1M=-1060 → flatlined ~-1070 through 2.5M`

Policy is in late-exploration / early-exploitation phase — has not consolidated a stable strategy. The opening PAC-spam is leftover random exploration bias.

### 2.3 Boyu V2a — machine-dependent regression + load-loading folklore

The most interesting case:

**On Boyu's own machine**: reportedly *"stronger than V4 unmodified"*
**After we synced to 4 teammates**: only 2/4 could even load the model successfully; on the 2 that could load, demo behaviour was poor (PAC-spam pattern).

Most likely causes (in probability order):

1. **Boyu may have been running the rule-based heuristic, not V2a** — same silent-fallback bug we've all hit at one time or another:
   - Operator selects the model in the dropdown
   - Server tries `LearnedBlueAI(model_path)` → fails internally (e.g. numpy pickle issue)
   - Server falls back to `BlueAI()` (the rule heuristic) without flagging it loudly enough
   - Operator sees correct-looking behaviour and concludes "the model is strong"
   - When other teammates try to load the model deliberately, the underlying load failure surfaces.

2. **Training cap (96/24/128) ≠ deployment cap (was 30/15/40, now 120/60/160 after the cap-120 expansion)**:
   - Boyu trained at 96 against a Blue env at 30
   - After cap expansion to 120, the adapter (`live_ai.LearnedBlueAI._adapt_obs_for_model`) handles the shape mismatch by slicing
   - The adapter's behaviour can drift between numpy / pytorch versions (Boyu pickled under numpy 2.x, we unpickle under 1.26 with a compat shim — works but is not bit-for-bit guaranteed)
   - The model sees observations subtly different from training distribution → behavioural regression

3. **Cross-machine Python environment differences**:
   - Of 4 teammates: 2 load it, 2 cannot
   - The 2 who fail probably have a different sb3-contrib / numpy / pickle protocol than Boyu
   - This is exactly why the EPYC training run pinned `numpy==1.26.4` rigidly

**Likely composite truth**: Boyu's local "strong V2a" was probably the rule heuristic running silently (cause 1). Once we sync to teammates, the actual V2a load surfaces, and where it loads, the cap-mismatch adapter degrades behaviour (cause 2).

---

## 3. Why V4 wins

V4 = `blue_reward_v4_finetune` (CIWS Active variant), trained at cap-30/15/40 with simple v4 reward:

- Intercept: `+ threat_value / 1e6` (no multipliers)
- Leak: HGV ×8 / ballistic ×6 / cruise ×3 / **drone ×4** (deliberate drone-leak emphasis)
- Spend penalty: `× 0.05` (weak — does not dominate the gradient)

**No head-on bonus, no doctrine multiplier, no budget-aware modifier**. The policy directly learned "intercept = reward, leak = penalty, drones leaking is especially expensive" — simple, blunt, generalizes well.

**Plus the `live_ai.py` Path 1 predictive dispatch**: PAC-3 / PAC-2 launch when ballistic / HGV is *predicted* to enter range (not when it's already there) — solving the "Mach-13 is too close by the time it crosses the strict 88km gate" problem. Path 1 fires from the rule layer regardless of what the policy decides, so even if the policy doesn't choose to engage, the rule layer provides the guaranteed-correct ballistic/HGV intercept.

V4's edge = simple reward + sufficient training + rule-layer safety net = **stable, generalizable**.

---

## 4. Blue model leaderboard

| Model | Demo performance | Note |
|---|---|---|
| **Heuristic (rule)** | Excellent | Hand-written rules + Path 1/Path C, the most stable |
| **V4 + Path 1** | Excellent | RL policy behaviour is correct + rule-layer safety net; near-tie with heuristic |
| Cap120 | Bad | Undertrained, opens with PAC spam |
| Boyu V2a | Unstable | Cross-machine load failures + behavioural regression after cap mismatch |
| Megamodel | Worst | Over-shaped reward → consistent PAC spam |

**Conclusion**: For the Finale demo, V4 ≈ heuristic. The heuristic arguably generalizes better (no training-distribution dependency, robust across Red configurations).

---

## 5. Red AI — the emergent "bait" strategy

The new **Red Trainee v2** is the most interesting RL outcome from this round (**despite the overall model quality being modest**). It learned a strategy that no part of the reward function explicitly described:

### 5.1 Old Red — naive HGV spam (now fixed)

Pre-fix bug pair:

- `red_env._winner` returned "red wins" if **any single** base hit 0 HP → episodes terminated as soon as one base died, so the policy never learned to plan for full takedown.
- Reward only counted leak damage in absolute terms (HGV ~80 dmg vs drone ~10 dmg). No cost awareness.

Result: the old Red learned "open with the highest-damage / highest-survivability threat (HGV) until one base goes down". Naive hill-climbing.

### 5.2 Red Trainee v2 — bait-and-saturate

In this round we fixed the `_winner` bug (Red wins **only when all 3 military bases are dead**) and rewrote the reward:

- Cost-asymmetric drain bonus (Blue overpaying to kill cheap Red threats → Red rewarded)
- Cost-asymmetric loss penalty (Red's expensive kit killed by cheap Blue counter → Red penalized)
- HGV evasion bonus (only fires when an HGV genuinely dodged a PAC, gated by `_hgv_recently_maneuvered` tracker)
- Base-weight scaling on leak (killing the last base = 3× reward)

After the curriculum R1a → R1d (vs rule Blue → B_shaped → V4 → Boyu V2a), the policy converged to this counterintuitive strategy:

```
Phase 1 — Bait (opening):
  Spawn ~27 cheap ballistic missiles (~$1.5M each, total ~$40M)
   ↓
  Blue, alarmed, throws PAC-3 / PAC-2 to intercept all of them
   PAC-3 unit cost = $5M
   Worst case: 27 × $5M = $135M of Blue budget consumed

Phase 2 — Economic exhaustion:
  Blue: $200M − $135M = $65M remaining
  Red:  $150M − $40M  = $110M remaining
   ↓ Red is now richer in absolute terms

Phase 3 — Saturation:
  Red converts $110M into drones at $30K each → up to 3666 drones
   (real cap is much lower due to spawn-rate / launcher constraints,
    but still hundreds of drones)
   ↓
  Blue no longer has budget for interceptors
   ↓
  Drones overwhelm the remaining 2 bases → Red wins
```

This is **genuine RL emergent behaviour** — economic-layer cost-asymmetry exploitation. **The reward function did not encode "use cheap ballistic to bait expensive interceptors and follow up with drone saturation."** The policy derived the strategy on its own from the cost-asymmetric drain reward.

### 5.3 Why this is the demo highlight

The Finale jury scores on 4 dimensions (1-10 each):

- **Q1**: How clearly did the team explain *what process* they're improving? → Multi-objective resource allocation under cost constraints, with concrete examples
- **Q2**: How critical is the process? → Resource allocation is canonical
- **Q3**: Ceiling impact of a really good RL solution? → "RL discovers strategies humans don't program"
- **Q4**: Impact of *this* demo? → **The bait-and-saturate strategy IS the evidence**

Narrating Red Trainee v2's opening 27-ballistic burst followed by drone saturation will land harder than any architecture slide. *"This bait-and-saturate logic emerged from reinforcement-learning training. We did not program it. The agent discovered cost-asymmetric warfare on its own."*

---

## 6. Lessons learned (for the next training run)

1. **Simpler reward beats complex reward.** Doctrine multipliers, head-on bonuses, and budget-aware modifiers are *hand-coded reward shaping biases* — and they routinely backfire because the policy maximises *reward*, not your intended behaviour. Megamodel is the cautionary tale.

2. **Training cap should match what you can afford to train.** Cap-120's 7260-dim action space takes far more than 2.5M steps to converge cold-start. V4's cap-30 / 465-dim action space generalised stably with 1M finetune steps. Small cap + sufficient training > big cap + rushed training.

3. **Pin dependency versions across all teammate machines.** `numpy==1.26.4`, `torch==2.5.x`, `sb3-contrib==2.8.0`, locked. Boyu V2a's cross-machine regression is the cautionary tale.

4. **Be skeptical of "the model is strong" reports.** If the server log doesn't print "adapter active" or "loaded learned policy" when the model is selected, the rule heuristic may be silently driving instead. Boyu's local "V2a is stronger than V4" report is most likely this exact failure mode.

5. **The rule layer (`live_ai.py` Path C / Path 1) is the demo lifeline.** RL policies are unreliable on their own; the rule layer guarantees correct critical decisions (PAC-3 vs ballistic, CIWS-saturation against drones). **Don't try to encode all doctrine into reward** — write it as a rule layer; that's strictly more controllable.

6. **Training Red AI on its own gives the most interesting RL output.** Red Trainee v2 is the round's clearest evidence of RL discovering a non-obvious strategy. Future iterations should invest more time on Red AI training (the adversarial side) rather than stacking yet more Blue variants.

---

## 7. Final demo configuration

```
Blue:    RL CIWS Active (V4) + Path 1 predictive dispatch (active in live_ai.py)
Red:     Scripted 3-Chain
Layout:  D (Forward HGV Hunter, 19 launchers)
Budget:  Red 110M / Blue 200M
Speed:   10× to narrate key moments, 50× to skip lulls
```

Optional stretch (second match if time allows):

```
Blue:    RL CIWS Active (V4)
Red:     RL Trainee v2 (cost-aware bait-and-saturate)
Layout:  C
[Narration: Show off Red's emergent strategy. Blue may lose; the
 story is "look what RL discovered on its own".]
```

Do **not** use Megamodel, Cap120, or Boyu V2a in the Finale demo.
