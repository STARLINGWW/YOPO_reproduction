# YOPO 复现模块总图：12 个模块 × 论文对照

更新：2026-10-13 ｜ 范围：YOPO 复现全部内容（YOPO-only 活动范围） ｜ 论文快照：[YOPO_author_version.pdf](../../artifacts/paper_sources/YOPO_author_version.pdf) ｜ 配套交互式预览：工作区根目录 `_sandbox/yopo-project-map-preview.html`（本地查看，未纳入仓库）

本图把整个复现分成 5 个阶段、12 个模块，每个模块给出“定位 → 本地实现 → 证据与结果 → 状态”，并标注论文对应位置，便于对照论文逐节阅读。运行代码没有被移动：`src、scripts、configs、ros2_ws、docker、tests、external、datasets、checkpoints、artifacts、reports` 仍是根目录运行兼容层，`plan / implement / report` 是新增的管理、导航和阅读入口（原因见[重构总计划](../../plan/00_charter/01_refactor_master_plan.md)）。

## 0. 模块总览

状态口径：YOPO-only 活动范围内 12 个模块全部收官（活动矩阵 1,500/1,500、终审 6 verified、all_verified=true）。参考[17] MPPI 于 2026-10-13 移出活动范围并归档；剩余为研究限制（DAgger 闭环收益独立验证、实机未复现）。

| 阶段 | 模块 | 论文对应 | 实现导航 | 状态 |
|---|---|---|---|---|
| ① 前置与协议 | 01 论文与源码审计 | 协议层（II 的数值语义） | [plan/01_paper_protocol](../../plan/01_paper_protocol/README.md) | 已完成 |
| ① 前置与协议 | 02 运行环境与通信 | III（实验环境） | [implement/03 ROS2运行时](../../implement/03_ros2_runtime/README.md) | 已完成 |
| ② 数据、代价与轨迹 | 03 场景与数据生成 | II-B / III | [implement/04 Isaac仿真](../../implement/04_isaac_sim/README.md) | 已完成 |
| ② 数据、代价与轨迹 | 04 距离场与轨迹代价 | II-A | [implement/01 核心算法](../../implement/01_core_algorithm/README.md) | 已完成 |
| ② 数据、代价与轨迹 | 05 五次多项式轨迹 | II-A | [implement/01 核心算法](../../implement/01_core_algorithm/README.md) | 已完成 |
| ③ 网络与学习 | 06 YOPO 网络与运动原语 | II-A | [implement/01 核心算法](../../implement/01_core_algorithm/README.md) | 已完成 |
| ③ 网络与学习 | 07 Guidance Learning 训练 | II-B | [implement/02 训练流水线](../../implement/02_training_pipeline/README.md) | 已完成 |
| ④ 系统与规划 | 08 在线候选选择与规划 | II-A（推理） | [implement/03 ROS2运行时](../../implement/03_ros2_runtime/README.md) | 已完成 |
| ④ 系统与规划 | 09 控制器与 Isaac 闭环 | III-C（本地仿真替代实机） | [implement/04 Isaac仿真](../../implement/04_isaac_sim/README.md) | 已完成 |
| ⑤ 评估与收尾 | 10 专家与基线对照 | III-A、III-B | [implement/05 基线](../../implement/05_baselines/README.md) | 已完成（MPPI 已移出活动范围并归档） |
| ⑤ 评估与收尾 | 11 DAgger 聚合微调 | 论文外的本地扩展 | [implement/02 训练流水线](../../implement/02_training_pipeline/README.md) | 已完成（微调完成；闭环收益仍为研究限制） |
| ⑤ 评估与收尾 | 12 验收与成果 | III（图表与结论） | [implement/06 验证](../../implement/06_validation/README.md)、[implement/07 可视化](../../implement/07_visualization/README.md) | 已完成（终审 6 verified） |

## 1. 按论文章节读复现

论文分节：I. Introduction ｜ II. Method（A. One-stage Planner，B. Training Strategy）｜ III. Experiment（A. Training Strategy Validation，B. Simulated Comparison，C. Real-world Experiment）｜ IV. Conclusions。方法逐项对照见[论文方法与本地实现逐项对照](../02_method/01_paper_to_code.md)。

| 论文位置 | 论文讲什么 | 对应模块 | 从哪读起 |
|---|---|---|---|
| 摘要 + I | 一阶段规划器 + Guidance Learning 动机 | 06、08 | [方法对照](../02_method/01_paper_to_code.md) §1–§2 |
| II-A | 运动原语、单次前向预测偏移与评分、ESDF 梯度、推理流程 | 04、05、06（方法）、08（推理） | [方法对照](../02_method/01_paper_to_code.md) §2–§3、§5 |
| II-B | 训练策略：两条梯度联合训练 | 07（执行）、04（监督信号） | [方法对照](../02_method/01_paper_to_code.md) §4 |
| III-A | Table I：网络 vs 专家（代价、时延） | 10 | [专家50步比较](../03_training/03_专家50步比较.md) |
| III-B | Table II / Fig.7：TopoTraj、MPPI、Agile 仿真对比 | 10、12 | [权重批量对照实验](../04_evaluation/02_权重批量对照实验.md)、[复现状态总览](../01_status/02_复现状态总览.md) |
| III-C | 实机平台实验 | 09（本地为仿真闭环） | 差异 D11、[ROS2基线迁移记录](../04_evaluation/06_ROS2基线迁移记录.md) |
| IV | 结论与展望 | — | 差异索引 §3 |

## 2. 12 个模块逐项说明

### 01 论文与源码审计（① 前置与协议，已完成）

固定 YOPO main 分支源码为正式主线，保留 YOPO-Simple 官方参考；逐条记录论文与源码在评分符号、候选筛选、场景来源上的差异，并据此锁定数值语义。差异清单已把正式语义固定为：main 正代价评分、训练配置 `unselect=0`、Isaac 程序化森林替代 Flightmare；无法完全复现的部分保持显式记录。

入口：[external/audit_sources/main](../../external/audit_sources/main)、[external/audit_sources/YOPO-Simple](../../external/audit_sources/YOPO-Simple)、[configs/paper_aligned.json](../../configs/paper_aligned.json)、[configs/reproduction_protocol.json](../../configs/reproduction_protocol.json)、[原论文与源码差异审计](../02_method/03_原论文与源码差异审计.md)。

### 02 运行环境与通信（① 前置与协议，已完成）

训练与规划节点运行在 Ubuntu 22.04 Docker / ROS2 Humble，场景与物理使用 Windows 原生 Isaac Sim；ROS2 承载深度图、里程计、目标、轨迹与仿真时钟，并处理消息过期、旧结果覆盖与时钟回跳。运行时准入通过（yopo / topotraj / agile 三个后端）；最终展示飞行 216 条轨迹全部被接受、213 条应用、0 条过期或覆盖。

入口：[compose.yaml](../../compose.yaml)、[ros2_ws/src/yopo_runtime](../../ros2_ws/src/yopo_runtime)、[trajectory_buffer.py](../../src/yopo_sim/trajectory_buffer.py)、[job_guard.py](../../src/yopo_sim/job_guard.py)、[runtime_validation.json](../../benchmarks/protocol_v1/runtime_validation.json)、[plan/02_environment_ros2](../../plan/02_environment_ros2/README.md)。

### 03 场景与数据生成（② 数据、代价与轨迹，已完成）

Isaac 程序化森林按固定地图种子生成树木、灌木与地面，随机采样自由空间位姿并渲染深度图（采集 160×90，训练重采样为 160×96、深度裁剪 20 m 归一化），并生成点云、占据体素与 SDF 逐帧校验。训练 20 张地图 / 100,000 样本；验证 4 / 10,000；测试 4 / 10,000；地图种子 100–119、1000–1003、2000–2003 按地图切分，避免同图泄漏。

入口：[prepare_dataset.py](../../scripts/prepare_dataset.py)、[collect_isaac_shard.py](../../scripts/collect_isaac_shard.py)、[forest.py](../../src/yopo_repro/forest.py)、[isaac_full_v1/validation.json](../../datasets/isaac_full_v1/validation.json)。

### 04 距离场与轨迹代价（② 数据、代价与轨迹，已完成）

训练用的环境评价器：平滑代价（高阶导数平方积分）、碰撞代价（SDF 指数罚）与目标偏差，对轨迹直接给出数值与梯度。MapBank 把候选变换到世界系查询地图，梯度为格点 + 差分实现（数值指导梯度，另有 `minimum(g,1)` 裁剪，见差异 D4）。网络评测与专家重建共用同一套原版目标函数；代价数值与梯度即 Guidance Learning 的训练监督。

入口：[main_cost.py](../../src/yopo_repro/main_cost.py)、[maps.py](../../src/yopo_repro/maps.py)、[ros2_ws/src/yopo_math_reference](../../ros2_ws/src/yopo_math_reference)、[ros2_ws/src/yopo_expert_core](../../ros2_ws/src/yopo_expert_core)。

### 05 五次多项式轨迹（② 数据、代价与轨迹，已完成）

把当前状态 (p, v, a) 与候选终端状态 (p_T, v_T, a_T) 连成五次多项式，让网络输出的 9 个终端参数变成任意时刻可求值的连续轨迹。训练时为全部 15 个候选各生成一条多项式；推理时只对选中候选生成正式轨迹（差异 D7）。

入口：[quintic.py](../../src/yopo_repro/quintic.py)、[primitive_utils.py](../../external/audit_sources/main/flightpolicy/yopo/primitive_utils.py)。

### 06 YOPO 网络与运动原语（③ 网络与学习，已完成）

ResNet18 编码深度，与 3×5 运动原语网格、速度、加速度和目标方向融合，共享 1×1 卷积头一次输出 15 个候选（9 个轨迹参数 + 1 个代价评分），隐藏特征 64 维。“Only Plan Once”指单阶段网络完成一次规划更新，而不是整段飞行只规划一次。

入口：[policy.py](../../src/yopo_repro/policy.py)、[yopo_policy.py](../../external/audit_sources/main/flightpolicy/yopo/yopo_policy.py)。

### 07 Guidance Learning 训练（③ 网络与学习，已完成）

一次更新：网络输出 15 个候选 → 生成 15 条多项式 → 地图计算真实代价与梯度 → 轨迹分支接收代价梯度、评分分支回归代价（`L = mean(J) + 10 × SmoothL1(score, J.detach())`）→ 联合反向传播。三个随机种子各 50 轮 × 312,500 步、batch 16、Adam 1.5e-4 从头训练，逐轮严格审计全部通过；seed0 最优验证总损失 ≈ 0.02293。

入口：[train_scratch.py](../../scripts/train_scratch.py)、[checkpoints/formal_main_v1_seed0](../../checkpoints/formal_main_v1_seed0)、[training_audit.json](../../checkpoints/formal_main_v1_seed0/training_audit.json)、[方法对照](../02_method/01_paper_to_code.md) §3。

### 08 在线候选选择与规划（④ 系统与规划，已完成）

在线推理只用深度、状态与目标：对 15 个候选按预测评分 argmin（正代价语义），生成五次多项式并采样位置/速度/加速度/偏航，经 ROS2 发布。按消息时间与实测延迟决定应用时刻；过期轨迹与旧结果在缓冲层被丢弃，观测量到达即重新规划。

入口：[main_planner.py](../../ros2_ws/src/yopo_runtime/yopo_runtime/main_planner.py)、[protocol_node.py](../../ros2_ws/src/yopo_runtime/yopo_runtime/protocol_node.py)。

### 09 控制器与 Isaac 闭环（④ 系统与规划，已完成）

参考轨迹 → 位置/速度外环 → SO3 姿态控制 → 电机推力与力矩分配（含电机响应滞后）→ PhysX 刚体积分；飞行中不直接设置位置或速度。自训练 seed0 展示飞行：成功、航迹 24.641 m、最小净空 1.188 m、终点误差 0.099 m、跟踪 RMSE 0.116 m、最大接触力 0 N；物理步长 2 ms、控制步长 10 ms。

入口：[unified_quad.py](../../src/yopo_sim/unified_quad.py)、[physx_vehicle.py](../../src/yopo_sim/physx_vehicle.py)、[run_ros2_navigation.py](../../scripts/run_ros2_navigation.py)、[run_navigation.py](../../scripts/run_navigation.py)、`artifacts/ros2_flights/showcase_formal_main_v1_seed0_20260926_014921/metrics.json`（外部归档：完整飞行记录与逐架次证据见 report/06_migration）。

### 10 专家与基线对照（⑤ 评估与收尾，待闭合：MPPI 300 槽）

三层对照：专家重建（scaled_gd50 / mma50_evaluations）在独立测试集比较候选质量；TopoTraj 与 Agile Autonomy 接入冻结协议；官方与本地权重在 Simple / main 栈 × 3 场景 × 2/4/6 m/s 的 36 架次同场景对照。

离线 1 万样本：本地 seed0 平均代价 ≈0.0231、最优候选 ≈0.0179，优于官方 0.0296 / 0.0220 与随机初始化 0.0823 / 0.0396；本地平均代价弱于 mma50（0.0215），最优候选优于两个专家重建。权重对照 36 架次：30 成功 / 4 超时 / 2 碰撞。参考[17] MPPI 于 2026-10-13 移出活动范围：身份/全文与旧方案归档于 report/90_archive/mppi 与 plan/90_decisions/archive_mppi。

入口：[network_comparison_trained_seed0.json](../../artifacts/expert/network_comparison_trained_seed0.json)、[expert_variants.json](../../configs/expert_variants.json)、[protocol.json](../../benchmarks/protocol_v1/protocol.json)、[专家50步比较](../03_training/03_专家50步比较.md)、[权重批量对照实验](../04_evaluation/02_权重批量对照实验.md)、[官方权重 vs 自训练权重对照](../04_evaluation/01_official_vs_selftrained.md)、[MPPI参考17身份与可得性（归档）](../90_archive/mppi/05_MPPI参考17身份与可得性.md)。

### 11 DAgger 聚合微调（⑤ 评估与收尾，待闭合：闭环收益未验证）

用基础 seed0 权重在新地图闭环飞行，收集策略实际访问的观测与位姿，聚合成分片数据集后从 seed0 最佳权重微调 10 轮。33 架次（18 成功 / 15 超时）、11 个分片、新增 7,620 样本、67,260 步微调完成；闭环收益尚未独立验证，微调权重未进入正式活动矩阵。

入口：[aggregation_manifest.json](../../datasets/isaac_dagger_v1/aggregation_manifest.json)、[dagger result.json](../../checkpoints/dagger_main_v1_seed0/result.json)、[DAgger聚合与微调方案](../03_training/02_DAgger聚合与微调方案.md)。

### 12 验收与成果（⑤ 评估与收尾，待闭合：终审矩阵 1500/1800）

机械验收审计逐项核对证据链；成果包括全局飞行视频、轨迹总览图、成功率-速度图与延迟/安全/平滑度统计表；文档链接与命令证据审计通过。终审 6 verified、all_verified=true（YOPO-only 活动范围；活动矩阵 1,500/1,500）。

入口：[final_acceptance_audit.json](../../artifacts/environment/final_acceptance_audit.json)、[global_trajectory.mp4](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_trajectory.mp4)、[global_overview.png](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_overview.png)、[figure_7_success_vs_speed.png](../../artifacts/paper_figures/figure_7_success_vs_speed.png)、[table_i_expert_vs_network.md](../../artifacts/paper_figures/table_i_expert_vs_network.md)、[table_ii_latency_safety_smoothness.md](../../artifacts/paper_figures/table_ii_latency_safety_smoothness.md)、[完成验收与成果路径](../90_archive/01_完成验收与成果路径.md)、[演示程序与权重飞行验证命令](../05_visualization/01_演示程序与权重飞行验证命令.md)。

## 3. 与原文的已知差异索引

以下差异均有代码证据，完整明细与行号见[逐项对照报告](../02_method/02_YOPO笔记与本地复现逐项对照_2026-10-08.md)与[原论文与源码差异审计](../02_method/03_原论文与源码差异审计.md)；分节级对照见[方法对照文档](../02_method/01_paper_to_code.md) §6。

| # | 主题 | 论文/笔记描述 | 本地实际 |
|---|---|---|---|
| D1 | 评分符号与选择 | 负评分 −J，在线 argmax | 正代价 J、ReLU 输出、SmoothL1(score, J)、argmin |
| D2 | 候选筛选 | 轨迹损失只训练筛选后的候选 | `unselect=0`，全部 15 候选都贡献轨迹损失 |
| D3 | 损失合成 | 两条梯度相加 | `mean(J) + 10 × mean(SmoothL1)`，带权重而非无权重求和 |
| D4 | 梯度来源 | 真实代价的精确导数 | 格点查询 + 差分梯度，另有 `minimum(g,1)` 单边裁剪与参数范数裁剪 |
| D5 | 轨迹时域 | 固定 2 s | 训练 T=2×4/6≈1.333 s；在线 T=8/v，4 m/s 时为 2 s |
| D6 | 规划/控制频率 | 15 Hz 规划、50 Hz 控制 | 相机名义 15 Hz，控制 100 Hz，物理 500 Hz；异步接受率不能等同名义频率 |
| D7 | 在线解码范围 | 解码全部 15 条候选 | 正式 MainPlanner 先 argmin 再只解码所选端点（训练 `decode_all` 才全解码） |
| D8 | 重规划起点 | 每次用测得的位置/速度/加速度 | 有效旧轨迹存在时从旧参考在当前时刻的 p/v/a 续接，否则用观测 p/v 与零初始加速度 |
| D9 | 数据与场景 | Flightmare 数据、论文设备 | Isaac 程序化森林、自生成 100K/10K/10K；结论按“等效条件实验”表述 |
| D10 | 专家标签 | 需要专家生成标签再训练 | 训练器不加载专家缓存；专家仅用于离线比较 |
| D11 | 实机实验 | III-C 实机飞行 | 本地为 Isaac + ROS2 仿真闭环，实机未复现 |

## 4. 状态边界与活动矩阵分解

YOPO-only 活动矩阵 1,500/1,500（622 成功 / 624 碰撞 / 254 超时），五个活动模型各 300 槽：

| 模型 | 成功 | 超时 | 碰撞 | 说明 |
|---|---:|---:|---:|---|
| YOPO seed0 | 184 | 74 | 42 | 本地自训练权重 |
| YOPO seed1 | 163 | 87 | 50 | 本地自训练权重 |
| YOPO seed2 | 174 | 90 | 36 | 本地自训练权重 |
| TopoTraj | 71 | 2 | 227 | 外部基线，已准入 |
| Agile Autonomy | 30 | 1 | 269 | 外部基线，已准入 |
| MPPI（参考[17]） | — | — | — | 已移出活动范围并归档（见 benchmarks/archive、report/90_archive/mppi） |

阅读时不要越界解读：

- 参考[17] MPPI 的 300 槽按用户决定（2026-10-13）移出活动范围；不是数据丢失。
- 终审 `all_verified=true`：6 项验收全部 verified；MPPI 不再是验收项。
- DAgger 微调已完成，但现有证据不支持“微调一定改善闭环成功率”。
- 实机实验（论文 III-C）未复现；飞行结论均来自 Isaac 仿真闭环。
- 训练完成 ≠ 所有飞行成功；verified 只表示该项有证据。
- 权威状态源：[report/01_status](../01_status/README.md)、[复现状态总览](../01_status/02_复现状态总览.md)、[status_overview.json](../../artifacts/environment/status_overview.json)、[final_acceptance_audit.json](../../artifacts/environment/final_acceptance_audit.json)。

## 5. 推荐阅读路径

- 看结论：先读 [01_status](../01_status/README.md) 和[复现状态总览](../01_status/02_复现状态总览.md)。
- 对照论文读：从本图 §1 进入[论文方法与本地实现逐项对照](../02_method/01_paper_to_code.md)，再按模块（§2）点进 implement 导航。
- 看成果与复跑：从 [05_visualization](../05_visualization/README.md)、[99_artifact_index](../99_artifact_index/README.md) 和[演示程序与权重飞行验证命令](../05_visualization/01_演示程序与权重飞行验证命令.md) 进入。
- 想按代码模块读：从 [implement/README](../../implement/README.md) 进入 8 个代码模块的代码地图。
