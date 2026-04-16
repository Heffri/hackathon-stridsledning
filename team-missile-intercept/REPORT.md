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
