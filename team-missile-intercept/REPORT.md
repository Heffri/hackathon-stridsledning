# Milestone B 实现报告

## 已完成内容

### 后端 (Python, 1010 行)

| 文件 | 行数 | 说明 |
|------|------|------|
| `backend/requirements.txt` | 3 | fastapi 0.115, uvicorn 0.30, numpy 1.26 |
| `backend/sim/__init__.py` | 0 | 包标识 |
| `backend/sim/config.py` | 44 | 所有可调参数集中 (arena 150×150×40 km, DT=0.05s, 15Hz stream, PN gain=4) |
| `backend/sim/types.py` | 150 | `Team`/`ThreatType`/`InterceptorType` enum、`ThreatSpec`/`InterceptorSpec` dataclass、`EntityState`、`Explosion`、`WaveSpec`，以及 drone/cruise_sub + CIWS/short_sam/med_sam 的 spec 表 |
| `backend/sim/physics.py` | 119 | 重力、二次阻力、加速度/速度 cap、**True Proportional Navigation** (N=4)、semi-implicit Euler 积分、闭合式 closest-approach 距离计算 |
| `backend/sim/entities.py` | 172 | `Threat` (航路点跟踪 + 高度保持 + 阻力) 和 `Interceptor` (PN 制导 + 沿速度方向推进到 max_speed + 重力 + 阻力) |
| `backend/sim/world.py` | 181 | 世界 tick：推进威胁 → 推进拦截弹 → 每 tick CPA 二元命中判定 → 基地命中 → 清理死亡实体 → 生成 snapshot JSON |
| `backend/sim/red_ai.py` | 83 | 3 波定时刷怪脚本 (T+2s 3 drones → T+35s 2 cruise → T+75s 4 drones + 1 cruise)。每种威胁从与自身速度匹配的距离刷新 (drone 15km, cruise 40km) |
| `backend/sim/blue_ai.py` | 84 | 基于规则的拦截弹选择：drone → SHORT_SAM > CIWS > MED_SAM；cruise → MED_SAM > SHORT_SAM。当威胁进入 `max_range × 1.1` 时发射，按 threat_id → interceptor_id 跟踪分配关系 |
| `backend/sim/scenarios.py` | 40 | 组装 World + RedAI + BlueAI，每 tick 依次调用，snapshot 包含 wave 状态和 log |
| `backend/server.py` | 173 | FastAPI + WebSocket。`SimRunner` 在 asyncio task 中以 1/15s 周期推进 + 广播全量 JSON；接受 `start/pause/reset/speed` 命令；静态文件服务 `/` 和 `/static/*` |
| `backend/test_pn.py` | 63 | 独立 PN 验证脚本（已跑通：med_sam 从 30km 外追一个 cruise_sub 在 24.5s 命中，脱靶距离 71.4m） |

### 前端 (HTML/CSS/JS, 482 行)

| 文件 | 行数 | 说明 |
|------|------|------|
| `frontend/index.html` | 63 | 单页，Three.js ES-modules importmap (unpkg CDN, 0.160.0)，HUD 结构 |
| `frontend/style.css` | 106 | HUD 毛玻璃面板、按钮、速度滑块、log 列、连接状态指示 |
| `frontend/js/scene.js` | 109 | Three.js 场景、透视相机、OrbitControls、环境光 + 方向光、150×150 km GridHelper、地面 plane、蓝方基地 cylinder marker、北方指示 marker、world→scene 坐标变换 (X=东, Y=北, Z=上 → X,Y=上,Z=-北，整体 ×0.001 缩放到 km) |
| `frontend/js/entities.js` | 166 | `EntityMesh` (彩色椎体 + 缓冲几何尾迹 60 点 + 速度矢量朝向)、`EntityRegistry` (snapshot 同步创建/销毁/更新)、爆炸白色球体 scale-up + fade |
| `frontend/js/hud.js` | 60 | 绑定 Start/Pause/Reset 按钮和 speed slider、更新 T/wave/intercepts/leaked/active 数字、渲染 Red/Blue AI log |
| `frontend/js/main.js` | 47 | 启动场景、打开 WebSocket (自动重连)、render loop 中消费最新 snapshot |

**总计**: 14 个实现文件 + requirements.txt + test_pn.py ≈ 1500 行代码。

## 启动命令

```bash
cd "C:/Users/xingyi chen/Documents/GitHub/hackathon-stridsledning/team-missile-intercept/backend"
pip install -r requirements.txt
python server.py
# 浏览器打开 http://localhost:8000/
```

验证物理引擎（不启动 server）:
```bash
cd backend && python test_pn.py
```

## 验证清单（浏览器应能看到的现象）

打开 http://localhost:8000/ 后：

1. **初始场景** — 深蓝天空，30×30 网格地面（150km × 150km），中央偏南有一个蓝色圆柱（蓝方基地），北边有一个黄色小球（方位指示）。左下角右下角 HUD，"disconnected" 变 "connected"。
2. **点击 Start 按钮** — `T` 计数开始走。
3. **T+2s (Wave 1)** — 3 个红色椎体从北边 15km 处出现，缓慢（45 m/s）向基地飞。日志 "Wave 1: Drones launched"。
4. **T+3-5s** — 蓝方 AI 发现威胁进入 short_sam 9km 射程，3 枚黄色椎体从基地弧形发射（初始速度 340 m/s，加速到 680 m/s），PN 制导弯向 drone。
5. **T+10-15s** — 白色球状爆炸在空中出现，尾迹保留。intercepts 计数 +3，active threats 归零。
6. **T+35s (Wave 2)** — 2 枚更亮的红色椎体从 40km 处出现（260 m/s subsonic cruise），med_sam 发射（max speed 1020 m/s）。
7. **T+50-60s** — med_sam 完成 2 次拦截。
8. **T+75s (Wave 3)** — 4 drones + 1 cruise 同时刷新，蓝方 AI 并行多目标处理。
9. **速度滑块** — 拖到 5.0x，整个模拟按 5 倍速推进（物理步数增加，不是插帧）。
10. **Pause 按钮** — 冻结模拟时间；再点 Start 恢复。
11. **Reset 按钮** — 清零所有实体和计数，回到 T=0。

**烟雾测试结果**（后端独立运行 180 秒）: 10 威胁刷新，9 次拦截成功，0 次漏过基地。墙钟时间 1.00 秒（sim 加速 ~180×）。

## 做了的技术决策

几个在文档里没明确、需要自己拍板的点：

1. **坐标系缩放**。Three.js 的 Y 轴是屏幕的"上"，跟模拟器 Z=上 冲突。选择在前端做坐标变换：`(sim_x, sim_y, sim_z) → (scene_x=(x-base_x), scene_y=z, scene_z=-(y-base_y))` 并整体乘 0.001 从米换成公里。这样相机数值在 O(100) 而不是 O(1e5)，避免 z-fighting。
2. **威胁刷新距离按速度归一化**。文档的 scenario 写 "从北边 edge"，但 drone 45 m/s 从 140km 外飞到基地要 50 分钟，demo 不可能看到。改为 drone 在 15km 外刷新（仍在 SHORT_SAM 9km × 1.1 margin 外，蓝方需要等它进入射程），cruise 在 40km 外刷新（MED_SAM 边缘）。在 red_ai.py 里分威胁类型算 spawn_y。
3. **PN 制导实现**。用 True PN 标准形式 `a_cmd = N * V_c * (omega × r_hat)`，其中 `omega = (r × v_rel) / |r|²`。对迎头几何稳定。额外在 closing speed < 100 m/s 时给 LOS 方向 80 m/s² 的推进，防止横向穿越几何下 PN 输出趋零。
4. **阻力系数**。没有实测数据，按"drone 阻力大、cruise 中、拦截器各有不同"手工调：drone=1e-5, cruise_sub=5e-6, CIWS=2e-5, short_sam=1e-5, med_sam=6e-6。配合 `cap_speed(max_speed)` 硬 clip 保证不超速。
5. **加速度上限**。`cap_accel(max_g * 9.81)`。额外在 config.py 有 `MAX_ACCEL=600 m/s²` 全局 cap（暂未使用，保留接口）。
6. **WebSocket 推送**。15fps 全量 JSON snapshot。前端一次只处理最新一帧（丢弃任何队列积压），所以不会卡。服务端 `asyncio.Queue(maxsize=8)` 订阅端，溢出直接丢。
7. **启动时 server 默认不 running**。连上 WebSocket 就开始收空状态，点 Start 才真正推进物理。避免页面刷新时模拟被跑完一半。
8. **基地命中半径 250m**。威胁到基地 250m 内即"漏过"（leaked +=1，生成爆炸），强制让威胁终止，不让一堆死 drone 永远飘在基地上空。
9. **尾迹长度 60 点 @ 15fps = 4 秒**。够看出弧度，不占 GPU。
10. **CIWS 在规则里**但现在的 2 种威胁（drone/cruise_sub）几乎从不在 4km CIWS 射程内被首选——优先级把 CIWS 放在 SHORT_SAM 之后作为 fallback。后期加更近距离的威胁后它会被触发。
11. **爆炸视觉**。白球 scale 从 1 到 18，opacity 从 0.9 到 0，1 秒生命周期。在 `entities.js` 里用 performance.now() 驱动，不依赖 server 时钟。

## 遗留的 TODO / 已知问题

1. **第 3 波有 1 个 cruise 有时漏过**。Blue AI 对同一个 cruise 连续发射了 8 枚 med_sam 都没命中（见 blue_log 尾部）。推测原因：cruise 飞低空 (60m)，med_sam 弧形高空飞过来，到末端时速度向量几乎垂直向下，几何差。应对：要么加一个 launch-direction prediction（预测拦截点反推发射方向），要么把 cruise 的 cruise_alt 提到 500+m 符合真实飞行剖面。当前做法能看，但不完美。
2. **Blue AI 无限弹药**。按 DEMO_PLAN 故意延后。
3. **线性 Euler 积分**在高 G 转弯时有少量能量漂移。在 demo 尺度看不出来；上 RK4 是后期事。
4. **Reset 按钮**重建 Scenario 对象但不清空前端已有 mesh，等下一次 snapshot 的 entity reconcile 来清。有一帧"上一局实体 + 下一局新实体"重叠，肉眼几乎不可见。
5. **前端 `_exKeys` Set 去重**用 `t.toFixed(3) + pos` 作 key，理论上两次爆炸精确在同一位置同一 tick 会合并成一次。概率极低，不修。
6. **阻力系数未在真空/高空模型化**。目前 `drag = -k*|v|*v` 用常数 k。实际上 50m 巡航和 25km 高度的空气密度差 25 倍。Milestone C 加高度密度模型。
7. **视角默认位置**（camera 在基地上空南侧 95km 远）正好能看到战场全貌。如果以后加更高空的 HGV，相机要往后拉。
8. **没有 README 更新**。`team-missile-intercept/README.md` 当前是占位符，应写一个简短"如何运行"+指向 REPORT.md 的链接。

## 给下一个 session 的建议（按优先级）

1. **（最优先）修 cruise 漏网问题**。两个方向：(a) 在 `blue_ai.py` 计算简单 lead angle，不只是 `threat.pos - base` 作为 initial_dir，而是加上 threat velocity × time_to_intercept；(b) 提 cruise cruise_alt 到 500m，同时降低 MED_SAM 的弧形发射角（initial_dir 的 Z 分量从 1000 降到 300）。建议先试 (b)，更简单。
2. **加 HP/damage 系统**。按 WEAPON_SPECS.md 的 direct_hit_radius/prox_radius/damage 值。最小改动：`EntityState` 加 `hp` 字段，`world.step` 里把二元命中改成"按公式减 HP，HP ≤ 0 才 alive=False"。打开 PAC-3-vs-ballistic 这类"直接命中 200 伤害一击必杀，擦边仅 5 伤害"的战术深度。
3. **加弹药/装弹 CD**。引入 `launcher.py`，每种拦截器有 magazine + inter-shot CD + full reload。强制 blue_ai 做资源决策。
4. **引入剩余 3 种拦截器 + 3 种威胁**：IRIS-T SLS (60G 刀战)、PAC-2、PAC-3；supersonic cruise、ballistic terminal、HGV。这些解锁 WEAPON_SPECS 的 cost-exchange 矩阵。
5. **Red AI Level 2/3**：ballistic 的固定弧线 + 末端机动，cruise 的航路点修正。Level 4/5 (stealth terminal, HGV full control) 是更大改动，放到 Milestone D。
6. **Per-entity 状态面板**：鼠标点椎体，右侧显示 type/speed/G/HP/fuel/target/time-to-intercept。UI 骨架已有，改 entities.js 加 raycaster 和一个 #status-panel div 即可。
7. **地形高度图**：加 terrain.py + frontend/js/terrain.js，用 `knowledge/scenario.md` 的 Boreal Passage 高度图。为 Level 4 "过海峡触发末端控制" 做准备。
8. **经济系统 + 胜负条件**：base_hp、Red/Blue 预算、游戏结束判定。让它成为真正的"游戏"而不是演示。

## 备注：未做的事（主动延后，不是遗漏）

按 DEMO_PLAN.md 表格："HP、燃料、弹匣、地形、经济、stealth/HGV/ballistic、Red Levels 2-5、per-entity panel、AI decision log 面板、seeker cone、cost-exchange 计算" — 全部未实现，为 Milestone C+ 保留。此 Milestone B 交付物只覆盖"核心循环能跑通"，完全符合 DEMO_PLAN 的界定。

---

# Milestone B+ Update — 立体化改造

目标：把"3D 渲染的 2D 战斗"升级成真正使用 Z 轴的立体战场。重点是 VLS 垂直发射、弹道导弹高空俯冲、巡航导弹末端 pop-up，以及突出 3D 感的默认相机视角。

## 代码变化摘要

| 文件 | 变化行数 | 核心逻辑变化 |
|------|---------|--------------|
| `backend/sim/types.py` | +25 | 新增 `ThreatType.BALLISTIC`、`InterceptorType.LONG_SAM` 枚举；在 `THREAT_SPECS` / `INTERCEPTOR_SPECS` 中加入对应 spec（ballistic 1800 m/s / kill_radius 70m / 颜色 `#ff8020`；LONG_SAM 1700 m/s / 25G / 70km / kill_radius 90m / 颜色 `#ffec40`） |
| `backend/sim/entities.py` | 重写 (+180/-45) | `Threat.__init__` 对 ballistic 走单独分支计算初始下冲向量；`Threat.step` 按类型分派：ballistic 用重力主导 + 1G 横向修正 + 无高度保持；cruise_sub 在 <5km/<1.5km 水平距离处把目标高度抬升到 600m/150m（末端 pop-up）。`Interceptor.__init__` 对 SHORT_SAM/MED_SAM/LONG_SAM 三种 SAM 启用 VLS 初始垂直速度矢量；`Interceptor.step` 新增 boost phase：前 1.5s 禁用 PN，仅做强上推 + 重力 + 阻力；boost 结束后切换到 PN，且 sustain thrust 方向改为 LOS-to-target（避免 PN 与垂直推力互相打架）。Interceptor.step 签名加 `t_now` 参数 |
| `backend/sim/world.py` | +1/-1 | `inter.step()` 调用传入 `self.t` 以支持 boost-phase 判定 |
| `backend/sim/red_ai.py` | +29 | 新增常量 `BALLISTIC_SPAWN_Y=base_y+40km` / `BALLISTIC_SPAWN_Z=35km`；Wave 4 (T+120s) 单发 ballistic；Wave 5 (T+150s) 高低空混合（1 ballistic + 2 drones + 1 cruise）。`threats` 元组从 `(kind, (x,y))` 扩展到 `(kind, (x,y,z))` 对 ballistic 类型 |
| `backend/sim/blue_ai.py` | +6 | `RULES` 新增 `BALLISTIC: [LONG_SAM]`；不放 fallback，宁可漏过也不浪费 SHORT/MED SAM |
| `frontend/js/scene.js` | +14/-7 | 相机默认位置 `(18, 25, 55)`、OrbitControls target `(0, 6, -30)`，形成从南偏东、中高空向北俯视略仰视的视角，让 35km 高空 ballistic 明显落在地平线上方 |

新增测试脚本：
- `backend/test_ballistic.py` — 60 行独立 Python 脚本：生成 ballistic + LONG_SAM 并离线推进 30 秒，打印 Z 轴轨迹。当前输出：t=16.8s 拦截成功，miss 距离 86m，拦截点 Z=10.7km。
- `backend/test_full_scenario.py` — 运行完整场景 200 秒，打印最终 stats。当前输出：spawned=15 intercepts=15 leaked=0（所有 5 波都全部拦截）。

## 启动命令

不变：
```bash
cd "C:/Users/xingyi chen/Documents/GitHub/hackathon-stridsledning/team-missile-intercept/backend"
pip install -r requirements.txt
python server.py
# 浏览器打开 http://localhost:8000/
```

离线验证（不启动 server）：
```bash
cd backend && python test_ballistic.py     # ballistic + LONG_SAM 拦截
cd backend && python test_full_scenario.py # 完整 5 波场景
```

## 验证清单（浏览器应能看到的 Z 轴表现）

1. **默认视角** — 打开页面即看到偏南偏上的视角。基地在视野偏下方，地平线在画面中间，天空占上半屏，地面网格延伸向画面深处。这让高空 ballistic 不会"从屏幕顶部之外"出现。
2. **Wave 1 (T+2s) — VLS 垂直发射**：SHORT_SAM 从基地几乎垂直窜上天（1.5 秒内到 ~400-500m 高度），然后才明显向北弯向 drone。尾迹呈标志性的"L 形"。
3. **Wave 2 (T+35s) — Cruise pop-up**：60m 贴地巡航的 cruise 在距离基地 5km 时抬升到 600m，1.5km 处下探到 150m；Wave 2 的 2 枚 med_sam 因 pop-up 后几何匹配改善，全部命中。
4. **Wave 3 (T+75s) — 多目标并行** + pop-up：4 drones + 1 cruise。原 REPORT 提到的"cruise 漏网"问题应已解决（测试显示 0 leak）。
5. **Wave 4 (T+120s) — Ballistic**：橙色 (`#ff8020`) 弹道导弹从基地正北 40km、Z=35000m 点亮。初始下冲速度 1800 m/s，重力作用下明显抛物线俯冲。与此同时，LONG_SAM (亮黄色 `#ffec40`) 从基地垂直窜上，在 ~10km 高度与 ballistic 相遇爆炸。整个拦截过程清晰显示 Z 轴上的 3D 几何。
6. **Wave 5 (T+150s) — 高低空夹击**：1 个 ballistic（上方）+ 2 drones（800m）+ 1 cruise（60m，末端 pop-up）。视觉上四个高度层同时在场。
7. **Z 坐标分层观察**：Start 之后的任意时刻，你应该能在画面里看到：地表附近的 drone（~800m）、低空贴地的 cruise（60-600m）、中空飞行的 SAM 拦截弹（几 km）、天上砸下来的 ballistic（35km→地面）。这是"3D 战斗"的关键视觉凭证。
8. **相机控制**：OrbitControls 保留；鼠标拖拽可以从俯视转侧视、远近缩放，验证战场确实是立体的而不是平面。

## 技术决策

1. **Ballistic 初始方向用 `normalize(target - start) + (0, 0, -0.25)` 而非规范示例的 `(0, -0.3, -1)`**。原因：在 40km 北 + 35km 高的刷新点上，`(0, -0.3, -1)` 归一化后水平速度只有 517 m/s，配合 26 秒下落时间仅能向前飞 10 km，会落在距基地 30km 的地方（远远偏离）。改用"瞄准基地 + 额外 0.25 垂直偏置"后，ballistic 在 t≈16.8s 被 LONG_SAM 成功拦截，几何戏剧性 + 拦截可行性兼得。
2. **Ballistic 的 `drag_k = 2e-6`**。选值基于：空气密度在 10km+ 高空比海平面薄 ~4x，使用比 cruise_sub (5e-6) 低 2-3 倍的系数；同时让终端速度 ~1800 m/s 不会被阻力显著衰减。实测 20 秒下落速度从 1800 → 1830（重力微增），符合"Mach 5.5 再入"观感。
3. **Ballistic `max_g = 1`**。规范要求。实测 1G 横向修正对于 20+ 秒弹道只能累计 ~2km 位移，不足以大幅调整落点，但足够让弹道弯向基地（demo 用足够）。
4. **Cruise pop-up 阈值固定 5km/1.5km，高度 600m/150m**。未做可调参数。5km 是肉眼可见"开始爬升"的距离，1.5km 是俯冲命中基地最后一击。实测 Wave 2/3 全部 cruise 命中（之前 REPORT 里 Wave 3 漏 1 枚 cruise 的问题因此解决）。
5. **VLS boost 1.5s 固定**。规范要求。实测 MED_SAM 在 1.5s 结束时到达 ~400m altitude，SHORT_SAM 到 ~300m。视觉上足够突出"垂直爬升"阶段。
6. **Boost 期间仅做强上推 + 重力 + 阻力，不做 PN**。实现时让 boost 阶段的目标速度是 `0.7 × max_speed` 沿（0.2 水平 + 1.0 垂直）方向，加速度上限临时放大到 `1.5 × max_g`（允许更"暴力"的垂直爬升）。
7. **Post-boost 关键修正：sustain thrust 改为沿 LOS-to-target 方向**，而非沿当前速度方向。这是实现 VLS 过程中踩到的核心坑：如果仍沿速度方向加速，当 boost 结束时速度是垂直的，加速度也会强化垂直方向，PN 的横向修正追不上——结果是 MED_SAM 拉成一个 25km 高的巨大弧线才转向目标，演示时间已经结束。改成沿 LOS 方向后，PN 和推力协同工作，SHORT_SAM 对远端 drone 的拦截时间从 >60s 降到 27s。
8. **Wave 4 只放 1 发 ballistic**。ballistic 刷新耗费 CPU/视觉预算大，1 发足够看到拦截效果；多发会堆积渲染。
9. **Wave 5 的 ballistic 从 `base_x - 4000` 位置刷新**（非正北），制造一个侧向偏移，测试 LONG_SAM 对非正上方来袭目标的拦截能力。
10. **LONG_SAM 发射时机**：Blue AI 的现有逻辑"当威胁进入 `max_range × 1.1` 立即发射"对 ballistic 已经足够——ballistic 刷新时 3D 距离 53km < 77km 阈值，当 tick 就发射。规范要求"不等"，自然满足。
11. **相机参数**：位置 `(18, 25, 55)`、target `(0, 6, -30)`，对应世界坐标 18km 东、25km 高、向南 55km，注视点在基地北方 30km、高度 6km。这个组合让 35km 高空 ballistic 从画面上方 1/3 处进入视野并向下画弧线。若需更夸张立体感可把 target.y 调到 8-10。

## 已知问题 / 遗留 TODO

1. **VLS boost 阶段尾迹在 1.5s 内会从原点拉出一条很短的垂直线**，因为 trailPoints 只采样 15fps × 1.5s ≈ 22 个点。视觉够看，但不如 SAM 稳态飞行阶段的尾迹飘逸。可在前端增加 boost-phase 期间的尾迹插值。
2. **Ballistic 刷新后 1-2 帧内 Blue AI 就打出 LONG_SAM**，没有"发现 → 评估 → 决策"的节奏感。若要体现 C2 决策时间可在 blue_ai 里加一个 0.5-1s 的 detection delay。
3. **Wave 5 的 ballistic 如果 LONG_SAM 在 Wave 4 的 ballistic 上消耗且未命中，第二枚 ballistic 仍会分配 LONG_SAM（目前无弹药追踪）**。Milestone C+ 引入 magazine 后需要处理"LONG_SAM 弹匣打空就漏 ballistic"的情况。
4. **当 ballistic 落点在基地北 10+ km**（未被拦截时），当前 `leaked` 计数逻辑只在距基地 250m 内触发，所以远落的 ballistic 会一直到撞地 Z=0 才 alive=False，但不计 leaked。UI 显示上不会弹 leak 日志。可接受。
5. **VLS boost 的上推加速度上限放到了 `1.5 × max_g`**，比 spec 的 `max_g` 高 50%。是为了让垂直爬升更戏剧化；如果要严格遵守 max_g，可以把这个 1.5 倍改回 1.0，代价是爬升更慢、初期 Z 轴观感没那么震撼。
6. **scene.js 默认视角对于只关心低空 drone 的玩家来说偏高**。如果后续 demo 专门做近程防御演示，这个视角需要再往下拉。目前是"覆盖所有高度"的折中。
7. **test_pn.py 的 MED_SAM 命中时间从原 24.5s 延长到 27.25s**。boost phase 浪费了 1.5s 加之 post-boost 需要 turn-around。miss 距离从 71m 改善到 16.6m（因为新 sustain-thrust 方向让终端几何更好）。整体净收益正向。
8. **Ballistic 下落速度比真实 Iskander (Mach 6 ~2040 m/s) 略低 (1800 m/s)**。保留空间给未来的 HGV (Mach 5+ 机动性 8G) 和真正 Mach 6 ballistic 终端阶段。

## 给下一个 session 的建议（按优先级）

1. **加 HP/damage 系统（最优先）**。现在拦截是二元"在 kill_radius 内就死"。按 WEAPON_SPECS.md 的 direct_hit / prox / prox_radius 三档实现，让 PAC-3 的"200 直接伤害 / 5 擦边伤害"反差真正成立。预期改动：`EntityState` 加 `hp` 字段，`world.step` 的命中逻辑里按公式减 HP，只有 HP≤0 才 `alive=False`。
2. **引入 supersonic cruise + stealth cruise**。二者都是 ~260-900 m/s、低空 14km+ 高空混合，和当前的 subsonic cruise 形成三层差异。代码成本很低（复制 CRUISE_SUB spec，调 speed/alt/rcs），但能显著增加 demo 武器多样性。
3. **Magazine / 装弹 CD**。LONG_SAM 一个发射架 4 发、120s 装弹。引入后 Wave 4/5 必须权衡"ballistic 来了是否开火"。可以把 `InterceptorSpec` 加 `magazine_size + reload_s`，`blue_ai` 维护每种武器的剩余数和下次可用时间。
4. **HGV (Level 5 红方 AI)**。真正的实时规避机动。需要在 Threat 里加"侦测附近 interceptor → 侧向规避"逻辑。但 HGV 也需要 kinetic energy bleed 机制（机动 → 速度下降 → 最终滑落）。是较大改动，留给 Milestone D。
5. **Per-entity 状态面板 + AI decision log 面板**。用 Raycaster 点击实体显示详情。UI 框架已在，改 entities.js 加 click handler 和一个 `#status-panel` div 即可。这对 4 分钟 demo 的"透明度"评分帮助很大。
