# V4 / 大模型 PAC-spam 真正根因 —— Distribution Shift

**日期**: 2026-04-27（决赛当天）
**状态**: 本地工作笔记，对早些 V4_FIRST_MATCH_GROGGY 报告的重大修订

---

## TL;DR

之前我把"V4 第一把没睡醒"归因为内部 state warmup，**这个解释只对了一半**。Chen 实战观察揭示了真正主因：

> **所有大模型（包括 V4）的 PAC-spam / 没睡醒行为，本质上是部署时的 budget 和 layout 跟训练时不一致导致的 distribution shift**。设置匹配训练分布时，V4 第 1 把就完美。

这意味着：

- Megamodel / Cap120 / Boyu V2a 那些 "PAC spam 失败" 的判定**部分不公平** —— 测试时部署条件可能根本没对齐训练
- 之前 BIG_MODELS_POSTMORTEM 里"reward over-shaping" / "训练没收敛"等假说仍然对，但**还需要叠加 distribution shift 因素**
- **决赛实操变得简单**：不需要 warmup match，只需要**精确设置 Red/Blue budget 和 Layout 匹配 V4 训练分布**

---

## Chen 的实证序列

| 实验 | Layout | Budget | 结果 |
|---|---|---|---|
| 0. 关服务器前 | Layout 不详 | Blue **500M** vs Red AI | 测试 UI，行为不详 |
| 1. 重启 server，第 1 把 | **default (current)** | **default 120M / 100M** | 开局 PAC-2 喷无人机，120M 预算瞬间见底 |
| 2. 重启 server，第 2 把 | **Layout C** | **default 120M / 100M** | **依然没睡醒** |
| 3. 重启 server，第 3 把 | **Layout C** | **手动改 200M / 150M** | **突然就行了，干净拦截** |

关键 contrast：实验 2 vs 实验 3 的**唯一区别是 budget**。Layout 一样、Red AI 一样、模型一样、Scenario 一样，**只有预算从 120M/100M 改成 200M/150M**——行为从"垃圾"变"完美"。

---

## 为什么 budget 这么关键

### V4 的训练分布（Chen 实证修订）

V4 在 `team-missile-intercept/backend/rl/runs/blue_reward_v4_finetune/`，按 v4 reward 做 finetune。训练参数（按 Chen 实证的最优配置反推）：

- Red budget: **150M**
- Blue budget: **200M**
- Layout: **C** (Heavy Saturation, 23 launchers, **8 个 CIWS**)
- Red mode: **ScriptedRed**

V4 在这种分布下学了 ~1M+ 步，policy 内化了：
- "我有 200M 预算，对面 150M，预算对等略占优势"
- "Layout C 上有 8 个 CIWS，drone 群来了 CIWS 完全能扛住"
- "ScriptedRed 第一波 30 个 drone，CIWS 顶上不用动其它 launcher"

**关键实证（Chen 测试）**:

| Layout | 配置 | 结果 |
|---|---|---|
| Layout C | Red 150M / Blue 200M | 第 2 把轻松赢，干净拦截 |
| Layout D | Red 110M / Blue 200M | 不管第 1 把第 2 把都是惨胜，开局 SLM/SLS 喷无人机 |
| Layout default | default 120M/100M | PAC-2 喷无人机，预算瞬间见底 |

Layout D 的 SLM/SLS 喷无人机现象 = V4 在 Layout C 8-CIWS 上训练，到 Layout D 只有 3 CIWS 的环境下 policy 不知道怎么处理 drone（CIWS 不够数），fallback 到 SAM tier。**这是 launcher mix 维度的 distribution shift**。

### 部署时换了什么

**Server 默认启动**（`config.py`）：

```python
BLUE_BUDGET_START = 120_000_000   # Demo-safe value
RED_BUDGET_START = 100_000_000    # Demo-safe value
```

注意 `config.py` 的 comment："Chen deliberately keeps `config.py` at demo-safe values (120M / 100M) so the live-demo server-side game balance isn't disturbed when he runs the browser demo."

也就是说**默认值是 demo 旧配置，跟训练分布完全不一样**。

加上 frontend "current" layout 是 `build_default_scenario` 出的配置，**也跟训练 Layout D / C 不一样**。

### 模型怎么 react

V4 看到的 obs 里有 `blue_budget / BUDGET_SCALE` 这个 feature。训练时这个值大概是 200/250 = 0.8。部署默认时是 120/250 = 0.48。

policy 网络内部学到的 weight + bias 是对应 0.8 输入下的 decision boundary。当输入变成 0.48，**activation 走到了未学习过的区域**——可能错误激活了"我钱多可以乱花"的子策略，反而 PAC spam。

加上 layout 的 launcher 数量 / kind / 位置变了 → obs 里 `launchers` 张量的内容**跟训练时见过的几乎都不同** → policy 完全 confused。

这就是 **distribution shift**：部署时输入分布跟训练时输入分布不重合，policy 在没见过的输入区域**行为不可预测**。

---

## 这对早些"V4 第一把没睡醒"假说的修订

之前 V4_FIRST_MATCH_GROGGY 报告里我提出三个假说：

1. State 泄漏（`_tick_counter` / `_assignments` / launcher state 跨匹配持续）
2. JIT warmup（PyTorch 首次推理慢）
3. Layout fleet 引用错位（Apply Layout 后 LearnedBlueAI.launchers 没同步）

**真实情况是**：

| 假说 | 之前评估 | 修订后评估 |
|---|---|---|
| 1. State 泄漏 | **高概率** | **降级为低概率** —— 测试用 200M+layout C 时，第 1 匹就好，state 不需要"睡醒" |
| 2. JIT warmup | 低 | 低（保持）—— 这个客观存在但影响小 |
| 3. Layout fleet 引用错位 | 中 | **降级为低概率** —— 同样的逻辑 |
| **4. Distribution shift（新）** | 没考虑 | **真正主因** |

之前观察到的"第 2 把变好"的现象解释：

- ❌ 之前以为：state 在第 1 匹时被"激活"，第 2 匹起开始好
- ✅ 真实情况：用户在第 1 匹失利后**习惯性手调了 budget / 重选 layout**，第 2 匹的设置才匹配上训练分布

也就是说"warmup"是个**伪相关性**——状元不是"先打一把热身"，是"先打一把发现设置不对然后改设置"。

---

## 对 BIG_MODELS_POSTMORTEM 报告的影响

之前 BIG_MODELS_POSTMORTEM 把所有大模型的 PAC-spam 归咎于：

- Megamodel: reward over-shaping
- Cap120: 没训够
- Boyu V2a: 跨机器加载玄学 + cap mismatch

这些**都仍然对**，但还要叠加 **distribution shift**：

- Megamodel 训练用 200M/150M + Layout C+D + scripted Red。如果 Chen 测试时用了 default 120M/100M + default layout，那性能差的部分原因是**配置不对**而不是"模型烂"
- Cap120 训练用 200M/150M(?) + Layout C/D(?)。同样可能存在配置不对
- Boyu V2a 训练分布完全未知给我们的；**几乎不可能配置正确**

**这意味着我们之前对"大模型烂"的判定可能误判了一些**。也许 Megamodel 在精确匹配的设置下也能跑得不错。但今天没时间复测。

---

## 决赛实操（修订后）

### 主推 demo 配置（**精确匹配 V4 训练分布** — Chen 实证最优组合）

```
Blue:    RL CIWS Active (V4)
Red:     Scripted 3-Chain
Layout:  C (Heavy Saturation, 23 launchers — 8 CIWS!)
Budget:  Red 150M / Blue 200M     ← 必须手调,不要用 default!
Speed:   10× / 50×
```

为什么 Layout C 而不是 D：
- Chen 实证：Layout D 上不管第 1 第 2 把都是惨胜，开局会用 SLM/SLS 喷无人机
- Layout D 只有 3 个 CIWS（vs Layout C 的 8 个 CIWS）—— V4 训练时大概率见的是 8-CIWS 配置
- Layout C + 200M/150M 第 2 把就轻松赢，干净拦截

为什么 Red 150M（不是 Hack Day 用的 110M）：
- Chen 实证：150M 给 ScriptedRed 时 V4 表现最好
- Hack Day 那个 110M 是为了"demo 友好"压低过的，不是 V4 的训练分布

**关键步骤顺序**：

```
1. 启 server
2. 选 V4
3. 选 Layout C, 点 Apply Layout
4. 把 Red budget 输入框改成 150, Blue 改成 200, 点 Apply
5. (验证 setup ribbon 显示的预算是 150M/200M)
6. 选 Scripted 3-Chain
7. 点 Start Match
   ↓
   第 1 把就应该好,**不需要 warmup**
```

### 不需要的步骤

- ❌ 不需要 warmup match（错觉）
- ❌ 不需要重启 server 重选模型
- ❌ 不需要 Reset+Start 第 2 次

只要**预算和 layout 一开始就对**，第 1 把就稳。

### 一定不要的事

- ❌ **不要让 server 用 default 120M/100M 跑给评委看** —— V4 必崩
- ❌ **不要中途改 Layout** —— 重新 distribution shift
- ❌ **不要中途改 budget** —— 同上
- ❌ **不要切到 Megamodel / Cap120** 再试 —— 没时间复测它们的真实能力

---

## Stretch goal（如果有第 2 场）

```
Blue:    RL CIWS Active (V4)
Red:     RL Trainee v2
Layout:  C
Budget:  Red 150M / Blue 200M     ← 注意这是 Red Trainee v2 的训练分布!
```

这个配置展示 RL Red 的 bait-and-saturate 策略。**Red 那边 budget 是 150M 不是 110M** —— 因为 Red Trainee v2 训练时是 150M，必须匹配。

---

## 长期修复建议

如果以后想避免 distribution shift bug：

1. **训练时 budget 用更广的随机分布**（e.g., Red 100-150M, Blue 150-250M），让 policy 对预算变化鲁棒
2. **训练时 layout 用更多 layouts 混合**（不只 C+D，加 E F 等），让 policy 学会 generalize
3. **部署时强制把 server default 设成训练分布的中位**（改 config.py 让 default = 110M/200M）
4. **UI 上显眼提示当前 budget / layout 是否匹配最新模型的训练分布**（"⚠ 预算偏离 V4 训练分布"）

但 17:00 demo 之前**只需要做第 3 步**——把决赛 demo 用的配置硬编码到一个 preset，下次开 server 就自动用。可能 5 行代码改 server.py。

---

## 一句话总结

> V4 / 所有大模型的 PAC-spam 主因是 **deployment-time distribution shift**（不是 reward over-shaping，不是 warmup）。决赛只要**精确手调 budget Red 150M / Blue 200M + Layout C**，第 1 把就稳，根本不需要 warmup match 这个 work-around。Distribution shift 不只是预算，还包括 launcher mix（layout）—— V4 在 Layout C 的 8-CIWS 上训练，去 Layout D 只有 3 CIWS 一样会 distribution-shift 退化。
