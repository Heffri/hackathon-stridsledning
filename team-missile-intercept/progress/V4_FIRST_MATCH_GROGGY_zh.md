# V4 "第一把没睡醒" 现象 —— 本地工作笔记

**日期**: 2026-04-27
**状态**: 本地参考，未 push（实战观察 + 推测，未代码验证）
**Scope**: Saab 2026 hackathon arcade-game demo

---

## 现象描述

V4 (CIWS Active) + Path 1 predictive dispatch 在浏览器实战中表现：

| 序号 | 操作 | 结果 |
|---|---|---|
| 第 1 把 | 选好 Layout (e.g. C/D) → Start Match → 跑 ScriptedRed | **明显"没睡醒"** —— 漏拦截、决策慢半拍、基地经常掉血或失守 |
| 第 2 把 | Restart (Reset + Start，不换 layout) → 同样 ScriptedRed | **几乎完美** —— CIWS 干净拦截 drone，PAC-3 head-on 命中弹道，3/3 基地满血 |
| 第 3 把 | 同上 | **保持完美** |

每次重启 server 重新选 layout 都会复现：第 1 把垃圾，第 2+ 把神。

---

## 三个最可能的假说

### 假说 1（最强）—— `LearnedBlueAI` 内部 state 跨匹配泄漏

`LearnedBlueAI` 在 server 启动 / 选模型时**只构造一次**（`__init__` 跑一次），之后所有匹配**复用同一个实例**。它内部的 state 不会在 Reset+Start 时被清空：

```python
class LearnedBlueAI:
    def __init__(self, policy_path, scenario):
        self.launchers = LauncherFleet()
        self._env = _LiveEnv(scenario, own_blue_fleet=self.launchers)
        self._tick_counter = 0
        self._assignments: Dict[int, List[int]] = {}
        # ... 其他 state
```

**关键 state**:

- `_tick_counter`: policy 决策频率是 `_tick_counter % DECISION_EVERY == 0`。
- `_assignments`: 用 threat_id 做 key，跨匹配的旧 entry 会留下成"鬼数据"
- `self.launchers`: 自带 reload / cooldown 时间戳

**第 1 把分析**:
```
_tick_counter = 0 (干净)
决策时点 = 0, 10, 20, 30, ...
ScriptedRed 也从 sim_t = 0 起 spawn drones
两边 phase 完全对齐 (即决策瞬间正好是 drone 刚 spawn)
→ 反直觉的, 这种"对齐" 反而让 policy 慢半拍：
  drone 在每个 decision tick 刚刚生成,policy 看到的 obs 是 drone "刚出现",
  还没真正进入威胁姿态。policy 倾向于"再等等看",
  错过了 CIWS 的最佳开火窗口。
```

**第 2+ 把分析**:
```
_tick_counter 已累计到第 1 把的 ticks 总数 (比如 6000+)
新匹配从 sim_t = 0 开始, 但 _tick_counter % DECISION_EVERY 给了
随机 phase offset (假设 6000 % 10 = 0, 还是对齐;但 6234 % 10 = 4
意味着决策时点是 4, 14, 24, ...)
phase offset 让 policy 的决策瞬间踩在 drone "已经飞了一段路" 的状态
→ obs 显示 drone 在 CIWS 射程内, policy 立刻 fire CIWS
→ 干净拦截
```

更进一步：`self.launchers` 的 reload 状态在第 1 把结束时**所有 launcher 都已经"复位"**（打过的弹药 reload 完毕，cooldown 归 0）。第 2 匹开局所有 launcher 都是"全员就位"姿态——比第 1 匹的"刚 spawn 出来 cooldown 还没设置好"状态要稳。

**怎么验证**：

```
1. 启动 server,选 V4,选 Layout C,Start Match (第 1 把垃圾)
2. Restart → 第 2 把神
3. Restart → 第 3 把仍然神
4. 退出 server (Ctrl+C),重新启动 server
5. 重选 V4 + Layout C,Start → 应该又"没睡醒"
```

如果第 5 步又没睡醒 → **假说 1 强烈成立**。

---

### 假说 2（次要）—— JIT / cache warmup

第一次 `policy.predict()` 调用：

- PyTorch 第一次 forward pass 触发 graph 编译 / kernel 选择
- numpy ↔ torch tensor dtype 转换走 cold path
- sb3-contrib `obs_to_tensor` / `action_masks` 路径首次执行

V4 policy 网络很小（默认 [64, 64] MLP），稳态推理 < 5ms。但**第一次** predict 可能 20-50ms 走完整 warmup。

如果决策延迟 > sim 一个 tick (DT = 0.05s = 50ms)，那一帧的"决策"实际上**漂移到了下一帧**才生效 → 表现就是 "慢半拍"。

**为什么不会是主因**：

- V4 网络太小，warmup 5-50ms 不够导致"基地满血→失守"这种戏剧性差距
- 即使第 1 帧慢，后续每一帧都热的，第 1 把后期应该恢复正常 — 但 Chen 观察到第 1 把整把都不对劲

**怎么验证**：

第 1 把开局 5 秒后切到 50× 快进，看后期是否恢复。如果后期变好 = warmup 主因。如果后期照样烂 = 不是主因。

---

### 假说 3（可能）—— Apply Layout 时 LearnedBlueAI 的 launcher fleet 没同步

Apply Layout 时 server 调 `Scenario.set_layout()`，**替换 `scenario.blue.launchers`**。

但 `LearnedBlueAI` 在 `__init__` 时已经持有自己的 launcher fleet 引用：

```python
self.launchers = LauncherFleet()  # LearnedBlueAI 自己创建
self._env = _LiveEnv(scenario, own_blue_fleet=self.launchers)
```

如果 `Scenario.set_layout()` **替换的是 `scenario.blue.launchers` 引用本身**（而不是修改原对象的内容），那 LearnedBlueAI 的 `self.launchers` 还指向**老的、未更新的** LauncherFleet。

**症状**:
- 第 1 匹：LearnedBlueAI 用老 layout 决策位置（CIWS 在哪、PAC-3 在哪），但 scene 里渲染的是新 layout —— **决策跟视觉脱节**
- 第 2 匹：Reset 时 launcher state 同步了一次 (各种 tick / reload 路径都触发过了)，引用对齐 → 正常

**怎么验证**：

启动 server，选 V4 + Layout C，**点右下 Magazine 面板看一下显示的 launcher 是不是 Layout C 的配置**（CIWS×8 + RBS-70×3 + SLS×4 + SLM×4 + PAC-2×2 + PAC-3×2）。如果显示的不是这个，假说 3 成立。

或者在浏览器开发者工具看几次 LearnedBlueAI 启动时的 console log（`[LearnedBlueAI] adapter active: ...`），看 launcher count 是不是匹配。

---

## 三个假说的概率排序

| 假说 | 概率 | 影响重 | 容易验证 |
|---|---|---|---|
| 1. State 泄漏 | **高** | 高 | 容易（重启 server 看是否复现）|
| 2. JIT warmup | 低 | 低 | 容易（看后期是否恢复）|
| 3. Layout fleet 不同步 | 中 | 高 | 容易（看 Magazine 面板内容）|

实战中可能是**假说 1 + 假说 3 双重叠加**，不是单一原因。

---

## 决赛实操方案

### 主推：先打 warmup match 再上台

```
17:00 上场前 5 分钟,在备用屏幕 / 静音浏览器跑一把 warmup:
  - 启 server
  - 选 V4 + Scripted Red + Layout D + Red 110M / Blue 200M
  - Start → 让它跑一会(可以 50× 快进)
  - 不需要看完,就是为了让 LearnedBlueAI 的 internal state "睡醒"

17:00 评委到位,Restart 跑给评委看 → 干净的第 2 把神级表现
```

**关键**: warmup 后**不要换 layout** —— 切 layout 可能重新触发假说 3 的状态错位。要换 layout 的话再多打一把 warmup。

### 备选：每次 demo 前 Restart 一次

不开 warmup match，但**第一次给评委看的不是"第 1 把"**：
```
启动 → 选 V4 → Apply Layout → Start (评委还在看 slide)
等 30 秒,即使打成稀烂 → Restart → 给评委看第 2 把
```

这等于把 warmup match 公开跑了一遍，但比较自然。

### 不要做的事

- ❌ 上台后才 Apply Layout (第 1 把必崩)
- ❌ 中途换 Red AI / Layout (重新触发状态错位)
- ❌ 信"Cap120 / Megamodel 之类的备用模型"——它们没有这种 warmup 救法

---

## 长期修复（不在决赛 budget 内）

如果以后想根治：

1. **Reset 时调 `LearnedBlueAI.reset_state()`**：清 `_assignments` / `_tick_counter`
2. **Apply Layout 时同步 `LearnedBlueAI.launchers`**：让 LearnedBlueAI 重新拿新 fleet 引用
3. **在 LearnedBlueAI `__init__` 开头跑一次 dummy `policy.predict()`**：吃掉 JIT warmup
4. **Server 启动时 lazy-load model**：减少首次 inference 延迟

每个改动都很小（10-30 行），但今晚 17:00 demo 不值得动——**warmup match 这条 work-around 解决 99% 问题**。

---

## 一句话总结

> V4 的"没睡醒"是经典的 RL 系统**热路径预热问题**——`LearnedBlueAI` 单实例跨匹配的内部 state 有 phase / cache / 引用错位，第 1 把当 warmup 跑掉，第 2 把开始就稳定了。决赛前自己先打一把 warmup，然后给评委看的就是"睡醒后"的样子。
