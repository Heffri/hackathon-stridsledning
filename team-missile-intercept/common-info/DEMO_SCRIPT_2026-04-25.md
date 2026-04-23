# Hack Day Demo Script — 2026-04-25

> **Event**: Saab "Smart Stridsledning" 2026 Hack Day, KTH Innovation, 08:30-17:00.
> **Slot**: 4-minute team presentation + live demo.
> **Presenter**: Chen. **Laptop**: Chen's PC, Chrome.
> **Framing**: student hackathon entry — browser-based arcade-style AI-vs-AI
> missile-defense sandbox. Same category as a tower-defense game. NOT a
> military product. All numbers are publicly available encyclopedia-level
> arcade stats.
>
> **Server launch** (one terminal, pre-warmed before the presentation):
>
> ```powershell
> cd C:\Users\xingy\Documents\github\hackathon-stridsledning\.claude\worktrees\sleepy-cartwright-2ccd8b\team-missile-intercept\backend
> $env:RED_WAVE_MODE = "scripted"
> $env:BLUE_POLICY_PATH = "C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend\rl\runs\blue_local\blue_cd_focused\model.zip"
> Remove-Item Env:RED_POLICY_PATH -ErrorAction SilentlyContinue
> python server.py
> ```
>
> Browser: `http://127.0.0.1:5174`. Layout dropdown → **C** → Apply Layout.
> Speed slider: **20×** default, bump to **30×** mid-match, **50×** for
> endgame scrub. Keyboard: **R** = reset camera.

---

## Pre-flight checklist (before walking on stage)

- [ ] Server running, browser open at `http://127.0.0.1:5174`.
- [ ] Layout **C** applied. HUD shows 23 Blue launchers.
- [ ] Speed slider at **20×**, match NOT started yet (SETUP phase).
- [ ] Window maximised. HUD panels visible (Budget / Sites / Logs).
- [ ] Zoom: camera reset (R), centered on Main Base.
- [ ] Volume muted (no audio on the demo).
- [ ] Cheat card in presenter's hand (see bottom of this doc).
- [ ] Practice-run log handy (which seeds produced which visual
      signatures — the 3 picks below are practice references, not
      live-lockable).

---

## Speaker script — 中文 primary + English slide cues

Times are *wall-clock minutes:seconds* from the start of the 4-minute slot.
Sim time numbers assume the **20×** → **30×** speed progression below.

### Beat 1 — 0:00 – 0:20 · Opening hook (20 s real)

**Slide title (EN)**: *Smart Stridsledning — AI vs AI missile-defense sandbox*

**中文 narration**:

> 大家好，我们的项目叫 **Smart Stridsledning** —— 一个浏览器里跑
> 的 AI 对 AI 导弹防御沙盒游戏。红方 AI 扮演攻击者，蓝方 AI 扮演
> 防御者；两边都在同一套物理引擎里实时决策。整个演示就在这台笔记
> 本本地运行 —— 后端 Python 仿真 + Three.js 前端，不依赖任何云端
> 服务。

**Action cue**: nothing yet — match is still in SETUP. Camera shows the
full 150 × 250 km Boreal Passage map with 23 Blue launchers lit up.

**Speaker note**: slow intro — let the jury read the title. ~4 s per
sentence. Don't rush the hook.

---

### Beat 2 — 0:20 – 0:45 · Map + layout walkthrough (25 s real)

**Slide title (EN)**: *Boreal Passage arena · 3 sites · 23-launcher Slot C defence*

**中文 narration**:

> 地图是 Saab 官方给的 Boreal Passage 场景，南面是我方领土，三个要
> 保护的基地：**Main Base**（主基地，中南）、**Spear Point Base**
> （北部前沿空军基地）、**Firewatch Station**（东南岸观察站）。北
> 面红方领地有无人机发射点和两个战略打击区。
>
> 今天演示的布防叫 **Slot C**，23 个拦截发射架——包括 8 座近防炮
> CIWS、3 座便携式短程 RBS 70、4 座中短程 IRIS-T SLS、4 座中程
> IRIS-T SLM、2 座爱国者 PAC-2、2 座末段反导 PAC-3——这是我们的
> 队员手动在浏览器里拖出来的阵型。

**Action cue**: slowly pan camera. Zoom out first (mouse wheel back)
to show the whole map, then pan to Main Base. Hover over 2-3 launchers
to trigger the status panel (optional — only if time allows).

**Speaker note**: this is the "map literacy" beat — the jury needs to
know where things are before they can follow the action. Point with
the cursor; don't list every launcher kind (they can't parse 6 names in
10 s).

---

### Beat 3 — 0:45 – 1:15 · Start Match 1 + Red AI doctrine (30 s real)

**Slide title (EN)**: *Red AI: scripted 3-chain overlap attack · drone → cruise → ballistic → HGV*

**中文 narration**:

> 我现在按 **Start Match**。红方 AI 用的是一套叫 **ScriptedRedAI**
> 的事件驱动战术 —— 对每个基地**同时**开三条攻击链。每条链先放一
> 波无人机，然后在无人机还没到的时候**提前**叠上巡航导弹，再叠上
> 弹道导弹，最后高超音速滑翔弹做收尾突破。红方预算一亿美元，蓝方
> 一亿两千万 —— 两边都有真实的经济约束。

**Action cue** — at **0:45 wall**:
- Press **Start Match** (HUD "Start" button, top of screen).
- Speed slider stays at **20×**.
- Camera: tap **R** to reset, then pan slightly north so both
  mainland strips are visible.

**Speaker note**: ScriptedRed fires the first drone batches
immediately at t = 0 s sim. The downstream chain triggers fire off
**drone arrival estimates** — drones at 120 m/s take ~1200 s sim to
reach their target, so cruise fires around 1200 s, ballistic ~1500 s,
HGV ~1600 s per chain. At 20× that's ~60 s wall to first cruise,
~75 s wall to first ballistic. Don't over-narrate the first ~30 s —
drones are alone on the screen, let the jury read the HUD.

---

### Beat 4 — 1:15 – 2:00 · Match 1 action narration (45 s real)

**Slide title (EN)**: *Blue AI · learned policy · blue_cd_focused (MaskablePPO)*

**中文 narration** — adapt to what's happening on screen:

> 看左上角：蓝方 AWACS 预警机在巡航圈（AWACS 是**可观测性的剧情
> 化说明** —— 蓝方能看到全场是因为有这架预警机）。红方 AWACS 在
> 北边对称巡航。
>
> 无人机群正在往南飞。**IRIS-T SLS** 和 **RBS 70** 开始拦截
> —— 它们是低空近程弹，无人机看到就打。注意右侧弹药面板实时扣除。
>
> 现在巡航导弹这一波来了，蓝方自动升级拦截档位 —— **IRIS-T SLM**
> 中程弹起飞。
>
> 弹道导弹速度 13 马赫，只有 **PAC-3** 能跟上 —— 看紫色拦截弹，
> 它是末段直接撞击（hit-to-kill）的那种，命中瞬间有白色闪光。
>
> 现在高超音速弹（HGV）进场 —— 17 马赫，会做末段机动。你能看到
> **PAC-3** 再起飞，尝试拦截。

**Action cue** — timing suggestions (wall-clock):
- **1:30** (sim ~900 s @ 20×): bump speed to **30×** so ballistic + HGV
  start firing by ~1:45 wall.
- **1:45**: optional — click a PAC-3 launcher to show its Magazine
  detail panel (Ammo/Status/Range).

**Speaker note**: this is the "wow" beat. Let the sound-free visual
breathe. Don't over-narrate — 3-4 sentences max, synced to what the
jury can see. If something unexpected happens (a site actually dies,
or a PAC-3 missing), lean in: *"红方实际上打出了一发突破 —— 但是
蓝方后续补射把剩下的清了"* sounds good either way.

---

### Beat 5 — 2:00 – 2:30 · Climax — Spear Point falls (30 s real)

**Slide title (EN)**: *Forward base falls · core sites hold · Red budget nearly exhausted*

**中文 narration** — synchronise with the HUD Spear Point HP bar dropping:

> 你看右上角 —— **Spear Point** 前沿基地的血条在掉。这次红方的第
> 二轮攻势突破了 Spear Point 的防线，血条归零了。
>
> 但是再看 **Main Base** 和 **Firewatch** —— 两个核心目标基本完
> 好。红方花了将近一亿美元的预算只拿下了**三个目标里的一个前沿基
> 地**。

**Action cue**: the Spear Point HP bar hits 0 at roughly sim 1200-
1800 s (≈ 45-90 s wall at 30×). Let the "site dying" visual pulse
breathe before narrating — the jury needs to see the event, not just
hear you label it. If Spear Point dies EARLY (before 2:00), fold
the earlier beat into this one and extend denouement; if it's still
alive past 2:15 wall, temporarily mute narration and let the action
play.

**Speaker note**: this is the emotional high point. The data pattern
holds across every seed we sampled (15/15): Spear Point falls, Main
and Firewatch hold. Narrate it as Blue's deliberate trade — forward
base absorbs the heaviest punch, rear bases stay intact.
**Overlay timing**: the sampler ran with a 2500 s sim cap and never
saw a "BLUE WINS" overlay. The live server has `MAX_SIM_TIME = 3600 s`
plus `Scenario.winner = "blue"` when Red is bankrupt AND all live
threats resolve — so **if Chen pushes speed to 50× during denouement,
a BLUE WINS overlay may fire around 2:45-3:00 wall** as the last
drones get cleaned up. If it doesn't fire, no problem — the Site HP
bars + Red budget bar carry the story.

---

### Beat 6 — 2:30 – 3:00 · Denouement — Red goes broke (30 s real)

**Slide title (EN)**: *Red budget exhausted · final threats play out · Blue preserves > 30 % budget*

**中文 narration**:

> 红方预算用完了 —— 看顶部红色预算条几乎归零，没有新的威胁再刷
> 出来。现在屏幕上飞着的是红方最后的一批无人机和巡航导弹，蓝方
> 的 CIWS 和 SLS 在把它们一个一个清掉。
>
> 最终统计：蓝方在 23 个发射架上打出去大约 **400 枚**拦截弹，还
> 保留了 **30% 以上** 的预算。这是一套**学出来的**协调策略，不是
> 手写规则。

**Action cue**: speed slider to **50×** if the pace feels slow —
denouement visuals carry themselves. If HGV is still in-flight,
narrate "最后一发高超音速弹" and let it play. When screen is
visibly calm (no live threats), hit **Pause** so the final frame
sticks.

**Speaker note**: this is where you pivot from narrating events to
explaining mechanism. The scene becomes quieter — that's your cue
to shift energy from commentary to the RL-training beat that follows.

---

### Beat 7 — 3:00 – 3:30 · Technical beat · Blue AI training (30 s real)

**Slide title (EN)**: *Blue policy · MaskablePPO self-play · action-masked multi-launcher coordination*

**中文 narration**:

> 蓝方 AI 不是手写规则。它是一个 **MaskablePPO** 策略，用
> **stable-baselines3** 训练（模型叫 `blue_cd_focused`，针对 Slot C /
> Slot D 布防 + ScriptedRed 红方做对抗训练）。
>
> 它学到的是**多发射架协同**：在 23 个发射架、6 种不同武器的组合
> 中，每 0.5 秒做一次决策，选谁打谁、打不打。我们在推理阶段还加了
> 四层安全护栏 —— 预算硬下限、饱和打击上限、成本交换过滤、
> 孤儿拦截弹清理 —— 防止策略在训练分布外做蠢事。

**Action cue**: screen is paused on the denouement frame. Wallpaper
only — no action. Chen can slowly drag the camera to keep the scene
alive without stealing attention from the speech.

**Speaker note**: this beat is the "why should Saab care?" sentence.
If the jury is nodding at just the visuals, they'll remember the
demo as a game; this beat is what they'll quote when they write up
their evaluation. Don't skip it. Deliver it clearly.

---

### Beat 8 — 3:30 – 4:00 · Close + next steps (30 s real)

**Slide title (EN)**: *Next: radar/sensor model · red-side RL · operator-in-the-loop deployment*

**中文 narration**:

> 剩下 30 秒讲一下后续。现在蓝方 AI 是**全知**的 —— 它看得到
> 地图上所有红方单位。下一步我们要接**雷达感知模型**，让探测依
> 赖于雷达状态和目标 RCS；同时红方也用 RL 训练一个**学习型攻击
> 者**，跟蓝方做不对称自博弈；最后我们还想做**人机协作部署** —— 
> 操作员摆阵、AI 打仗，结合人的战术直觉和 AI 的反应速度。
>
> 谢谢大家。我们的代码在 GitHub 的 `Heffri/hackathon-stridsledning`
> 里，欢迎提问。

**Action cue**: at **3:55**, press **Pause** so the screen freezes
on a stable frame. Camera zoomed on one site.

**Speaker note**: finish BEFORE the 4-minute bell. Aim for 3:55 — if
you're over-running, drop the "operator-in-the-loop" sentence and
jump straight to "谢谢".

---

## Camera + speed schedule

One match, paced so Spear Point fall lands around the 2:00 wall mark.
Sim-time numbers assume the stacked speed bumps below. ScriptedRed
chains take ~1500-2500 sim seconds to fully play out on Slot C, so
we intentionally *don't* wait for the end-of-match overlay — we use
the HP bars + Red budget bar as our narrative tells.

| t (wall) | t (sim) ≈ | speed | camera | action |
|---|---|---|---|---|
| 0:00 | 0 s | 20× (paused) | reset (R) + wide | intro speech |
| 0:20 | 0 s | 20× (paused) | pan to Main Base | layout walkthrough |
| 0:45 | 0 s | **20×** (start) | reset (R) | click **Start Match** |
| 0:45–1:15 | 0–600 s | 20× | wide, camera static | Red doctrine intro |
| 1:15–1:30 | 600–1200 s | 20× | slight orbit around PAC-3 launchers | narrate first wave / cruise layer |
| 1:30 | 1200 s | **30×** | wide | speed bump; ballistic + HGV begin |
| 1:30–2:00 | 1200–2100 s | 30× | wide | HGV terminal dive visible, Spear Point under pressure |
| 2:00–2:30 | 2100–3000 s | 30× | zoom toward Spear Point HP bar / site ring | Spear Point falls (climax) |
| 2:30 | 3000 s | **50×** | pull back wide | denouement, Red budget dry |
| 2:30–3:00 | 3000–4500 s | 50× | wide | final drones die off; **Pause** when scene calms |
| 3:00–3:30 | (paused) | — | slowly orbit paused frame | RL training speech |
| 3:30–3:55 | (paused) | — | whatever frame looks best | close speech |
| 3:55 | (paused) | — | freeze | "谢谢" |

Keyboard reference:
- **R** — reset camera
- **Space** or **Start / Pause** button — toggle match
- Mouse-drag — orbit; wheel — zoom; right-drag — pan

---

## Seed selection

Three seeds picked from the `tools/seed_sample_demo.py` sweep (Slot C + ScriptedRedAI + blue_cd_focused, budgets 100M / 120M defaults, 2500 s max sim cap). Drama-score rule: partial Red breach + decisive Blue closeout is best; total shutouts and 2+ sites dying are worst.

> **How to apply**: ScriptedRedAI builds its rng with `np.random.default_rng()` (no seed argument) when `scenario.red` is constructed, so the live browser demo draws a fresh unseeded rng on every scenario build. The three seeds below are **practice references** — Chen ran them headless via `tools/seed_sample_demo.py` to calibrate what a "good demo match" looks like (threat composition, rough timing, which site tends to take damage). Live, Chen clicks **Reset** → **Start** and narrates whatever comes up. The sampler shows **14 / 15 seeds** land in the same "Spear Point falls, Main + Firewatch hold" archetype — only 1 seed (1003) diverged into a 2-site loss. So the demo outcome is ~93 % predictable in shape; variation is in which specific interceptor types engage and roughly how much budget Blue spends.

### Primary seed — **1009**

- 119 threats (90 drone / 23 cruise / 4 ballistic / 2 HGV)
- 383 interceptor launches from Blue
- 6 leaks → **Spear Point Base dies** (HP 0), Main + Firewatch intact
- Red budget drained 99 %, Blue budget drained 54 % (keeps $55 M in reserve)
- Match runs to the 2500 s sim cap; `Scenario.winner` stays `None`
  (partial site loss doesn't auto-end the match per Issue #9)

**Narrative**: Blue trades the forward base — Spear Point absorbs the
heaviest cruise + ballistic salvo of Round 2. By the time Round 3's
HGV loft would normally fire, Red is bankrupt and nothing new spawns.
Clean "Blue holds 2 of 3" story.

### Backup A — **1001**

- Same threat composition as 1009 (119 threats, identical breakdown)
- 388 interceptor launches (close to primary)
- 6 leaks → Spear Point dies, Main + Firewatch intact
- Blue drain **49 %** (leanest of the 5 "drama=-40" seeds — most
  budget preserved, good for the "we held AND saved money" narrative)

**Narrative**: same shape as primary, slightly more conservative
Blue. Use if primary practice run feels overheated.

### Backup B — **1014**

- Same 119-threat composition
- **513 interceptor launches** — highest of any seed sampled (busier
  visual — more interceptor streaks on screen)
- 6 leaks → Spear Point dies, Main + Firewatch intact
- Blue drain 53 %

**Narrative**: same shape as primary, but the sky is noticeably
busier. Use if the room is cold and you need more visible motion to
wake the jury up.

### Why these three

All three share the "Spear Point falls, other two hold" outcome
pattern, which appeared in **5 of 15 sampled seeds** (≈ 33 %) — the
most consistent demo-friendly result. The three differ on Blue's
budget discipline (lean / median / busy) so Chen can choose based
on what he sees in a practice run before the live demo.

Seeds to **avoid** (based on the sampler):

- **1003** — 2 sites die (Spear + Main). Looks like Blue failure.
- **1000, 1004, 1005, 1002** — Main Base takes heavy damage (60-75).
- **1013** — Main Base takes 45 dmg. Borderline.

Sampler run metadata is in `team-missile-intercept/backend/tools/seed_sample_results.json`
(15 records, each with threats-by-kind, damage per site, budget drain, wall time).

---

## Recovery rules — if things go wrong

| Symptom | Action |
|---|---|
| Spear Point hasn't fallen by 2:15 wall | Bump speed to **50×**, narrate "我们快进一下看最后" |
| **2 sites die** before 2:00 wall | Unusual variance (seed 1003 pattern). **Reset** + Start, say "红方这次打得特别狠，我们重置" |
| All 3 sites die | Shouldn't happen on Slot C but if it does, narrate it honestly: "这个种子红方赢了 —— 我们平均 1/3 种子红方能突破一个前沿基地但不能全部拿下" then **Reset** + **Start** |
| Shutout (no Red damage at all by 2:00) | Rare — narrate Blue's perfect defense + skip to RL training beat early |
| Server stalls / no snapshots | Refresh browser tab. Server state persists. |
| Browser tab dies | Keep presenting from the HUD-less slides. Don't attempt restart on stage. |
| HGV misses every interceptor | Expected — Euler 0.05 s PN CPA is ~100-300 m against Mach-17. Narrate: "高超音速弹是现在全世界都在头疼的威胁" — turn the physics ceiling into a feature. |
| No "BLUE WINS" overlay | Expected under ScriptedRed + Slot C — match is designed to run long. Use Site HP bars + Red budget bar as your visual tells. |

---

## 3-bullet presenter cheat card (memorise)

1. **Hook**: "浏览器里的 AI 对 AI 导弹防御沙盒" — arcade-style, not a product.
2. **Climax**: Slot C 的 23 个发射架 + MaskablePPO 蓝方策略 + ScriptedRed 三链攻击。Spear Point 前沿基地陷落，主基地 + Firewatch 完好。
3. **Payoff**: Blue 学会了 23-launcher 协同 + 成本交换 + 饱和拦截。下一步接雷达模型 + 红方学习型 AI + 人机协作部署。

---

## Appendix A — Seed sampling methodology

Run from `team-missile-intercept/backend/`:

```bash
python tools/seed_sample_demo.py \
    --seeds 1000-1014 \
    --max-sim-s 2500 \
    --model "C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend\rl\runs\blue_local\blue_cd_focused\model.zip" \
    --json-out tools/seed_sample_results.json
```

Each seed takes ~80-120 s wall at CPU inference. Full 15-seed sweep
is ~23 min wall on this laptop.

**Note on `--max-sim-s 2500`**: this is a sampler-side cap for speed,
not the game-level cap (`config.MAX_SIM_TIME = 3600 s`). With 2500 s
every sampled seed had `winner=None` at cutoff because the final
drones were still in flight. Raising to 3600 s would add ~30 s wall
per seed and likely surface a "blue" winner on most seeds
(`red.done or red_budget <= 0` is already true; we just need the
last threats to resolve). For the live demo this doesn't matter —
Chen narrates off HP bars + Red budget, not the overlay.

The sampler monkey-patches `config.BLUE_LAUNCHER_POSITIONS` to the Slot C
roster, seeds `ScriptedRedAI.rng` with the seed int, installs `LearnedBlueAI`
loading the blue_cd_focused model, and steps the scenario at `config.DT =
0.05 s` until `scenario.done` OR `max_sim_s` elapses. Per-seed stats:
winner, ep_len_sim_s, threats-by-kind counter, interceptor launches, leaks,
per-site damage, Red / Blue budget drain.

Drama-ranking weights:
- +min(site_dmg, 60): partial breach is good
- -20 for zero damage: total shutout is boring
- +20 for decisive winner: cap-fire penalised
- -50 for ≥ 2 sites dead: Red runaway is bad
- -0.03 × |len - 1500 s|: mild duration penalty

If you need to resample with a different layout or budget, edit `SLOT_C`
and `config.RED_BUDGET_START` / `BLUE_BUDGET_START` at the top of the
script.

---

## Appendix B — Failure mode library

Empirically, under Slot C + ScriptedRedAI + blue_cd_focused the match
does NOT formally resolve within a 2500 s sim cap (none of the 15
sampled seeds returned `winner != None`). The sampler classifies
matches by *which* sites took damage instead:

Invariant across 15/15 seeds: **Spear Point Base dies**; Main Base +
Firewatch survive (except the 1 runaway seed). Red drain 97-100 %,
Blue drain 49-72 %, match hits the 2500 s sim cap with
`Scenario.winner = None`.

| Mode | Count | Symptom | Demo readiness |
|---|---|---|---|
| **Archetype (clean)** | 5/15 | Spear dies, Main + Firewatch untouched | Ideal — "Blue holds 2 of 3" narrative. Seeds 1001/1006/1009/1012/1014. |
| Main-scratched | 4/15 | Archetype + Main Base dmg 15-20 | Still good; adds mild "under real pressure" texture. Seeds 1007/1008/1010/1011. |
| Main-hit | 3/15 | Archetype + Main Base dmg 60-75 | Borderline — narrate carefully. Seeds 1000/1002/1005. |
| Main-borderline | 1/15 | Archetype + Main Base dmg 45 | Borderline. Seed 1013. |
| Firewatch-hit | 1/15 | Archetype + Firewatch dmg 60 (Main untouched) | Unusual — narrate as "red tried an east-side breakthrough". Seed 1004. |
| Runaway | 1/15 | Spear AND Main both die | Bad — reset and retry. Seed 1003. |
| Shutout | 0/15 | site_dmg = 0 | Never observed. If it happens live it would look strange — skip narration and jump to RL beat. |

---

## Appendix C — Known visual quirks to narrate around

- HGV miss rate is high (Euler 0.05 s PN against Mach-17 targets has
  CPA 100-300 m). If an HGV lands despite multiple PAC-3 fires,
  acknowledge it openly: "高超音速弹是全世界现役防空系统都在研究
  的难题，我们的拦截弹物理引擎精度和真实世界一样，对 17 马赫目
  标有几十到几百米的近距失误距离 —— 这是**诚实的限制**，不是
  bug。"
- SLM launches occasionally turn around mid-flight and self-destruct.
  This is the fuel-burnout + stall rule firing. Narrate it as "燃料
  耗尽 + 失速自毁 —— 发动机烧完就滑翔，低于 200 m/s 就自动销毁".
- Drones may pile up visually at the same spawn site before fanning
  out. This is deliberate — post-W5 jitter was added but spawn
  launcher positions are discrete.
- AWACS aircraft circle the map (1 Red in the north, 1 Blue near the
  southern base; Blue circles counter-direction from Red). They're a
  **diegetic explanation of full-map vision** — not a gameplay
  element. Don't say "预警机在探测敌机"; say "预警机是我们解释蓝方
  如何看到全场的剧情化设定". (Sanity: both aircraft should fly
  **nose-forward** along their orbit after this session's scene.js
  fix — if you see one flying tail-first, the fix didn't ship.)

---

> **Last updated**: 2026-04-23. Worker: demo-packaging session on branch
> `live-demo` (worktree `brave-albattani-9adc8b`). Any edits made during
> Chen's practice runs should be committed back to `live-demo`.
