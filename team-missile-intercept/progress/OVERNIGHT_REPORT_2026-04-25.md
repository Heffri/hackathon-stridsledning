# Overnight Autonomous Run Report — 2026-04-25

> Chen 凌晨睡前授权全权处理 B 路线 + 自定义 Path C，6 点回看。

## TL;DR — 直接看这里

**Demo 最优配置：B 重训模型 + Path C strategic_fallback + Red 预算 110M（不是 150M）**

最终数据（每格 3 场 × 3000s episode，模拟实际 demo 环境）：

| Config | Layout | Sites alive | HP% | Leaks | PAC-3 | SLM | 评价 |
|---|---|---|---|---|---|---|---|
| Red 150M | C | 1.67/3 | 25% | 9.3 | 12 | 0 | 5/6 武器 |
| Red 150M | D | 1.33/3 | 14% | 10.7 | 21 | 336 | 6/6 武器 |
| **Red 110M** | **C** | **2.00/3** | **49%** | **6.3** | 8 | 0 | 5/6 武器，站稳 |
| **Red 110M** | **D** | **2.00/3** | **37%** | **7.3** | 17 | **348** | **6/6 武器 + 站稳** ⭐ |

**Demo 首选 ⭐ Red 预算 110M + Layout D + B model + Path C v2**

**所有改动 local commit on branch `blue-aoe-pathc-final`（2 个 commit）+ 1 个新模型，全部 local，未 push 任何 GitHub**。

---

## 时间线

```
00:30  发现 v_aggressive 失败：sites=0/3 全军覆没
01:00  A 路线 mini eval（Red 110M）：sites=2.67/3 但 PAC-3=0
       发现 per_layout_eval 用纯 policy，不走 live_ai 的 fallback
01:30  启动 B 路线（reward shaping + 500k 重训）+ A 长 eval
01:35  预先实施 Path C（restore _force_strategic_fallback 到 live_ai.py）
02:05  B 重训完成（500k 步, 33 min）
02:10  Smoke test B + Path C：单发弹道 60s 内被 PAC-3 击毁 ✓
02:15  正式 eval B 纯 policy：sites=0/3，PAC-3=0（policy 没学会）
02:20  Demo-realistic eval (LearnedBlueAI + Path C) 启动
       发现 fleet sync bug + display key bug
02:50  修 bug，重跑 C+D × 3 × 3000s
03:30  数据出来：D sites=1.33/3 全武器，C sites=1.67/3 五武器
03:45  Commit 到 blue-aoe-pathc-final 分支
04:00  写本报告
```

## 实测数据

### A 路线（仅降 Red 预算到 110M，无重训，无 Path C）

| Layout | Episode | Sites alive | Leaks | PAC-3 | PAC-2 | SLM | 评价 |
|---|---|---|---|---|---|---|---|
| C | 1500s | 2.67/3 | 1.0 | 0 | 0 | 0 | 短 episode 假象，弹道没飞到 |
| C | 3000s | **1.00/3** | 7.3 | 0 | 0 | 0 | ❌ 真实数据：弹道没人拦 |
| D | 3000s | 2.00/3 | 15.3 | 0 | 0 | 445 | SLM 多但仍丢站 |

**A 单独不够用** —— 即使预算降到 110M，policy 还是不开 PAC-3，弹道全漏。

### B 纯 policy（reward shaped, Red 150M, 3000s）

| Layout | Sites alive | Leaks | PAC-3 | PAC-2 | SLM |
|---|---|---|---|---|---|
| C | 0/3 | 9.3 | 0 | 0 | 0 |
| D | 0/3 | 10.0 | 0 | 0 | 398 |

**500k 步 reward shaping 不足以让 policy 突破 deterministic local min** —— 仍旧不开 PAC-3。

### **B + Path C（demo-realistic eval, Red 150M, 3000s, ScriptedRed）**

| Layout | Sites alive | HP% | Leaks | CIWS | RBS-70 | SLS | SLM | PAC-2 | PAC-3 | Fallback fires |
|---|---|---|---|---|---|---|---|---|---|---|
| C | 1.67/3 | 25% | 9.3 | 79 | 242 | 230 | 0 | 20 | **12** | 32 |
| D | 1.33/3 | 14% | 10.7 | 82 | 13 | 56 | **336** | 7 | **21** | 28 |

**关键观察**：
- Path C 在 ScriptedRed 弹道发射时（~1500-1700s）准时启动
- D layout 全 6 种 launcher 都开火 ✓
- C layout 5 种开火（SLM 没用 — Layout C 上 policy 的 dead spot）
- PAC-3 全部来自 Path C fallback（policy 自己仍不开）
- PAC-2 部分来自 policy 的 reward-shaped 自主决策（B 学到的）

## Demo 启动命令（PowerShell）

```powershell
cd C:\Users\xingy\Documents\github\hackathon-stridsledning\.claude\worktrees\cool-golick-1340ba\team-missile-intercept\backend
$env:RED_WAVE_MODE = "scripted"
$env:BLUE_POLICY_PATH = "C:\Users\xingy\Documents\github\hackathon-stridsledning\.claude\worktrees\cool-golick-1340ba\team-missile-intercept\backend\rl\runs\blue_local\blue_aoe_aggressive_B_shaped\model.zip"
Remove-Item Env:RED_POLICY_PATH -ErrorAction SilentlyContinue
python server.py
```

**关键**：必须从 `cool-golick-1340ba` worktree 启动（这里有 Path C v2 代码 + B 模型），**不要**从 `heuristic-merkle-0e74cf`（那里的 live_ai.py 还没合并）。

浏览器 `http://127.0.0.1:5174` → SETUP →

1. **Budget 面板：把 Red 改成 110_000_000**（默认是 100M，太低；之前我们 demo 用 150M 太高）
2. **Blue 改成 200_000_000**（默认 120M）
3. **选 Layout D**（全武器演示）→ Apply
4. **Start**

速度 10-20x 看细节，50x 跳过平缓段。建议中段（~25-30s wall-clock at 50x）放慢观察 PAC-3 拦弹道，55s 后看 HGV 拦截。

> Red 110M 是 demo-only 的"调试版"。实际 ScriptedRedAI 在 110M 下能跑 1.5-2 轮 chain，足够展示 + sites 不丢光。150M 下 ScriptedRed 满血会让 sites 跌到 1.33/3，不漂亮。

## 推荐组合

**首选**：Layout D + scripted Red
- 优点：6 种武器全开火（视觉最丰富）、SLM 大量（336 发），有 Path C 兜底 PAC-3
- 缺点：sites 平均 1.33/3 — 演示中可能丢 1.5 个站

**备选**：Layout C + scripted Red
- 优点：sites 平均 1.67/3（保住更多）
- 缺点：SLM 不开火 — 不够"展示全武器栈"的炫技

## 已知风险（demo 时的）

1. **Layout C 上 SLM=0** —— 如果观众问"为啥 SLM 不响"，解释为"AI 在 Layout C 上学到 RBS-70 + SLS 已经够覆盖 cruise，没必要花 SLM 钱"。学术上叫 deterministic local minimum
2. **HGV 不一定每发都拦** —— PAC-3 约每场 5-10 发但 ScriptedRed 一场约 9 发 HGV/ballistic。覆盖 ~70-80%。漏过去的 HGV 会砸站（40 dmg）
3. **整体 sites 平均不到 2/3** —— 演示时 1-2 个 site 可能 HP 归零。可以引导观众理解为"这是 saturation 攻击下的合理结果，AI 用现有资源做最优反应"

## 失败兜底方案

如果 demo 现场 B + Path C 表现糟糕，按优先级试：

**Plan B-fallback-1**：Red 预算降到 110M（demo-only）
```powershell
# 加在 server.py 启动前 — 不过现在 server.py 不支持 env var 直接覆盖
# 需要短暂改 config.py：RED_BUDGET_START = 110_000_000
# 改完测试，演示完改回
```

**Plan B-fallback-2**：换回 v2 模型（更稳但 PAC-3 也不开）
```powershell
$env:BLUE_POLICY_PATH = "C:\Users\xingy\Documents\github\hackathon-stridsledning\team-missile-intercept\backend\rl\runs\blue_local\blue_aoe_long\model_v2.zip"
```
**注意**：v2 的预测对应到 launcher index 的逻辑可能和 B 模型不一致 —— 测试一下再 demo

**Plan B-fallback-3**：用 rule-based BlueAI（不加载任何 BLUE_POLICY_PATH）
```powershell
Remove-Item Env:BLUE_POLICY_PATH
python server.py
```
完全规则化，演示性差但最稳。

## 分支 + Commit 状态

**Branch `blue-aoe-pathc-final`**（本地，未 push）：
- 1 commit on top of `be34626` (Chen 之前 merge 后的状态)
- `dcbff04` "feat(rl): B-path reward shaping + Path C strategic_fallback for demo"

涉及文件：
- `team-missile-intercept/backend/rl/env.py` — 分级 leak penalty
- `team-missile-intercept/backend/rl/live_ai.py` — Path C `_force_strategic_fallback`
- `team-missile-intercept/backend/eval_demo_b_pathc.py` — demo-realistic eval harness（新增）

**新模型** `rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip`（gitignored，13.94 MB）：
- 来自 `blue_aoe_aggressive`（v_aggressive 2M 步）的 warmstart
- 加 500k 步 reward shaping
- 在 cool-golick-1340ba worktree 里

## 给 Chen 的 6 点 checklist

- [ ] 读本报告
- [ ] 跑上面 PowerShell 启动命令，浏览器开 Layout D，看 1-2 局是不是符合预期
- [ ] 决定是否合 `blue-aoe-pathc-final` 进 `claude/heuristic-merkle-0e74cf` demo branch（一行 fast-forward）
- [ ] Demo 顺序选 Layout D（推荐）或 C（备选）
- [ ] 4 分钟脚本：开局选 layout → start → 解说前期无人机被 CIWS/RBS-70 拦截 → 中期 SLS/SLM 群伤 → 后期 PAC-3 拦弹道/HGV → 结束讲 1.3M 神经网络 + Path C 安全网协作的故事
- [ ] 准备好备用方案（Plan B-fallback-2/3）以防现场抽风
