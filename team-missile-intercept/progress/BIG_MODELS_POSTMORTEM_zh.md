# 大模型在决赛 demo 实战的失败 —— 复盘报告

**日期**: 2026-04-27
**作者**: PM session
**Scope**: Saab 2026 hackathon arcade-game demo. 所有数字均为游戏平衡常数，非真实武器/系统数据。

---

## TL;DR

我们的大 RL 模型（Boyu V2a / Cap120 / Megamodel）在最新 demo 实战中**全部表现出"开局乱扔 PAC-2 / PAC-3 打无人机"的退化行为**。最终决赛 demo 唯一能跟原版规则脚本（heuristic / sim/blue_ai.py）一较高下的蓝方模型只有 **V4 (CIWS Active)** + Path 1 predictive dispatch 这套老组合。某种意义上 heuristic 的泛用性甚至比所有 RL 大模型都强。

红方那边新训的 Red Trainee v2 学到了一种**反直觉的"骗弹"策略**：不直接 spam HGV，而是开局发 27 发便宜弹道引诱蓝方耗尽 PAC 预算，然后用剩余预算造大量无人机淹没基地。这是 RL 训练真正涌现的一个亮点（即使整体模型质量不理想）。

---

## 1. 共同失败 — "PAC-spam 综合症"

| 模型 | 训练 cap | 训练步数 | demo 行为 |
|---|---|---|---|
| Boyu V2a | 96/24/128 | 未知（充足）| 开局狂发 PAC-2/PAC-3 打 30 个 drone |
| Cap120 | 120/60/160 | 2.5M cold start (没收敛) | 同上，更随机 |
| Megamodel | 72/32/128 | ~5M curriculum | 同上，但更"自信"地浪费 |
| V4 | 30/15/40 | 1M+ finetune | **正常**——CIWS 主管 drone，PAC 留给弹道/HGV |

PAC-3 单价 $5M，drone 单价 $30k —— **效费比 1:166**。开局把预算砸 PAC 上等于自杀。

---

## 2. 各模型失败原因诊断

### 2.1 Megamodel —— Reward over-shaping

训练用了非常激进的 doctrine reward：

- `(CIWS, ballistic): 2.0` multiplier  → 偷弹道命中爆奖励
- `head-on bonus 0.5`  → PAC 迎头打弹道 +50% 奖励
- `spend penalty 0.5/M`  → 单次 fire 罚分严重
- `base-weight × 3`  → 死光剩 1 个基地时 leak 罚分 ×3

数学算出来：**PAC-3 head-on 命中弹道 = +7.5**（最高奖励）；**CIWS 打 30 个 drone = +0.87**（30 × 0.029）。policy 学到"PAC 拦弹道是大单生意，CIWS 是边际",倾向于**优先 fire PAC** 等待"大单"。

加上 spend penalty 让"什么都不做"也是亏的（无奖励但有 time 流逝），policy 倾向于**早 fire 早爆赏**，结果开局看见 drone 也想"赌一把"用 PAC 打。

报告里 worker 自己写："the displayed reward is dominated by leak-penalty magnitude, not necessarily by quality of decisions" —— 训练 ep_rew_mean 从头到尾平在 -1170，**根本没收敛**。

### 2.2 Cap120 —— 没训够

2.5M 步 cold start at cap-120/60/160：

- Action space 60 × 121 = 7260 维 —— 比 V4 的 15 × 31 = 465 维大 **15.6 倍**
- CPU-bound，74 fps × 24 envs = 总 1776 transitions/sec
- 2.5M / 1776 ≈ 1400 sec —— 远不够大动作空间收敛
- 报告里：`ep_rew_mean went 135k=-1110 → 1M=-1060 → flatlined ~-1070 through 2.5M`

policy 处于**探索末期 / 开发早期**的状态，没真正学到稳定策略。开局乱扔 PAC 是探索阶段未消解的随机偏好。

### 2.3 Boyu V2a —— 跨机器降智 + 加载玄学

最有意思的案例：

**Boyu 自己机器上**：报告"比原版 V4 还强"
**我们 4 人同步后**：只有 2/4 人能正常加载，且加载后 demo 行为差，开局乱扔 PAC

可能原因（按概率排）：

1. **Boyu 实际从未真正启动 V2a，跑的是 heuristic（rule-based）**
   - 跟 Chen 之前遇到过的 "selected cap120 but server fell back to rule" 同款 bug
   - 选模型 → 模型加载失败（silently）→ server 默认回退 rule
   - heuristic 行为 perfectly fine，Boyu 以为"模型很强"
   - 我们这边 trying to load his actual model 才暴露 bug

2. **训练 cap (96/24/128) ≠ demo cap (原本 30/15/40 → 120/60/160)**
   - Boyu 训练时 demo cap 是 30，他训练 96 vs Blue cap-30 (现已被 cap-120 expansion 吞掉)
   - cap 升级到 120 后 adapter 路径触发：env 切到 120/60/160，模型 96/24/128 通过 adapter slice 处理
   - adapter 路径在不同 numpy / pytorch 版本下行为可能微妙不同（Boyu 用 numpy 2.x pickle 我们 1.26 unpickle，shim 兜底但不保证 100% 一致）
   - 模型实际看到的 obs 跟它训练时见的不完全一样 → 行为退化

3. **跨机器 Python 环境差异**
   - 4 人电脑：2 人能加载，2 人加载失败
   - 加载失败那 2 人的 sb3-contrib / numpy 版本可能跟 Boyu 训练时不一致
   - 这正是为什么我们这次 EPYC 训练严格 pin `numpy==1.26.4`

**真相组合**：很可能 Boyu 自己机器上跑的实际是 rule（猜测 1），他的 V2a 加载本身就有问题；同步给我们后 V2a 偶尔能 load 上但 adapter 输入分布漂移导致行为差（猜测 2）。

---

## 3. 为什么 V4 胜出？

V4 = blue_reward_v4_finetune (CIWS Active)，训练在 30/15/40 cap，简单 v4 reward：

- 拦截事件：`+ threat_value / 1e6`（无 multiplier）
- Leak：HGV ×8 / ballistic ×6 / cruise ×3 / **drone ×4**（特意提高 drone 防漏）
- Spend penalty：`× 0.05`（弱，不主导）

**没有 head-on bonus，没有 doctrine multiplier，没有 budget-aware modifier**。policy 直接学"intercept 给奖、leak 罚分、drone 漏掉特别痛"——简单粗暴，泛化好。

**加上 live_ai.py 的 Path 1 predictive dispatch**：PAC-3 / PAC-2 在弹道 / HGV 的轨迹**预计**会进入射程时**提前**升空（不等严格 88 km 射程门），让迎头拦截命中率大幅提升。这条规则**在所有蓝 model 跑 demo 时都激活**，所以即使 policy 没学好"何时 fire PAC"，规则层兜底正确决策。

V4 的优势 = 简单 reward + 充足训练 + 规则层兜底 = **稳**。

---

## 4. 跨蓝模型综合排名

| 模型 | demo 表现 | 备注 |
|---|---|---|
| **Heuristic (rule)** | 极佳 | 手写规则 + Path 1/Path C 全套，最稳 |
| **V4 + Path 1** | 极佳 | RL policy 行为正常 + 规则兜底，跟 heuristic 几乎平 |
| Cap120 | 差 | 没训够，开局 PAC spam |
| Boyu V2a | 不稳 | 加载玄学 + 跨机器行为差异 |
| Megamodel | 最差 | over-shaped reward 导致 PAC spam |

**结论**：决赛 demo 上 V4 ≈ heuristic。整体上 heuristic 的泛用性甚至更强（不依赖训练分布，对各种 Red 配置都稳）。

---

## 5. Red AI —— 涌现的"骗弹"策略

新训的 Red Trainee v2 是这次最有意思的 RL 成果（**虽然整体模型质量不理想**）。它学到的策略**完全没人编码**：

### 5.1 老 Red 的弱智 spam（已修复）

之前 Red 模型的 bug：

- `red_env._winner` 在**任何一个**基地死了就 return "Red wins" → episode 提前 terminated
- Reward 只看 leak damage 绝对值（HGV ~80 dmg vs drone ~10 dmg）
- 没有 cost 概念

→ policy 学到"开局 spam 最贵单价 / 最高 leak damage 的 HGV 直到打死 1 个基地"。简单粗暴的 hill climbing。

### 5.2 Red Trainee v2 的"骗弹"策略

我们这次修了 `_winner` bug（必须**全部** 3 个基地死才算 Red 赢），并重写了 reward：

- Cost-asymmetric drain reward（让 Blue 用 PAC 杀 cheap threat → Red 加分）
- 反向 penalty（HGV 被 CIWS 打掉 → Red 减分）
- HGV evasion bonus（HGV 真的躲过 PAC 才给）
- Base-weight scaling（killing the last base ×3 reward）

policy 经过 R1a → R1d 的 curriculum，对手是 rule Blue → B_shaped → V4 → Boyu V2a，学到这个**反直觉策略**：

```
开局发 27 发便宜弹道（每发 ~$1.5M, 总 ~$40M）
   ↓
Blue 看到弹道,激进发 PAC-3 / PAC-2 拦截
   每枚 PAC-3 = $5M, PAC-2 = $1M
   假设 Blue 用 PAC-3 全拦: 27 × $5M = $135M
   ↓
Blue 200M − 135M = 剩 $65M
Red 150M − 40M = 剩 $110M
   ↓
Red 用 110M 制造无人机 (每个 $30k = 3666 个潜在 drone)
   实际受 spawn rate / launcher 限制少很多,但仍数百个
   ↓
Blue 没钱拦, drone 淹没剩余 2 座基地 → Red 赢
```

这是**真正的 RL 涌现行为**——经济学层面的 cost asymmetry exploitation。**没有 reward 直接编码"打弹道骗 PAC 然后无人机海"这套战术**，是 policy 自己从 cost-asymmetric drain reward 推导出来的。

### 5.3 为什么这是亮点

决赛评分 4 个维度（each 1-10）：

- Q1: 我们解决的 process 多清楚 → "多目标资源分配" 有具体例子
- Q2: process 多关键 → 资金分配是普适问题
- Q3: 真正好方案的影响上限 → "RL 能涌现非显式策略"
- Q4: 我们 demo 的实际影响 → **这个骗弹策略是直接 evidence**

narration 把 Red Trainee v2 的开局 27 弹道 + 后续 drone 海**讲一段**，比一切 slide 都有冲击力。"This bait-and-saturate logic emerged from training. We did NOT program it."

---

## 6. 经验教训（下次训练改进方向）

1. **Reward 越简单越好**。Doctrine multiplier + head-on bonus + budget-aware modifier 这种"hand-coded reward 偏差"通常**反作用**——policy 找最大化路径，不一定对应你想要的行为。Megamodel 是反面教材。

2. **训练 cap 别贪大**。Cap-120 的 7260 维动作空间在 2.5M 步 cold start 上必然不收敛。V4 的 cap-30 / 465 维在 1M 步就稳定泛化，证明小 cap + 充足训练 > 大 cap + 仓促训练。

3. **跨机器加载必须 pin 依赖版本**。`numpy==1.26.4` + `torch==2.5.x` + `sb3-contrib==2.8.0` 严格固定。Boyu V2a 跨机器降智案例就是反面教材。

4. **学会怀疑"模型很强"的报告**。在浏览器选个模型，server log 没说"adapter active"或"loaded learned"就大概率是 rule fallback。Boyu 自报家门 V2a 比 V4 强，但他自己机器上很可能根本跑的是 rule。

5. **规则层 (live_ai.py Path C/Path 1) 是 demo 救命稻草**。RL policy 本身可能不可靠，规则层兜底关键决策（PAC-3 拦弹道、CIWS 群杀 drone）让 demo 行为可预测。**不要试图把所有 doctrine 编码到 reward 里**——直接规则层硬写更稳。

6. **Red AI 反向训练能涌现真有趣的策略**。Red Trainee v2 是这次最大收获，是说明文档里 evidence-of-learning 的硬证据。下次可以多花精力训 Red AI 而不是堆 Blue model。

---

## 7. 决赛 demo 配置（最终）

```
Blue: RL CIWS Active (V4) + Path 1 predictive dispatch (live_ai.py 已激活)
Red:  Scripted 3-Chain
Layout: D (Forward HGV Hunter, 19 launchers)
Budget: Red 110M / Blue 200M
Speed:  10× narrate, 50× skip lulls
```

可选 stretch：

```
Blue: RL CIWS Active (V4)
Red:  RL Trainee v2 (cost-aware bait-and-saturate)
Layout: C
[narration: 演示 Red 涌现策略,可能 Blue 输,但故事好]
```

不要用 Megamodel / Cap120 / Boyu V2a。
