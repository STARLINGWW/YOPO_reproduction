# 官方权重 vs 自训练权重对照

更新：2026-10-12 ｜ 论文对应：III-A（Table I 网络 vs 专家）、III-B（Table II 基线对比）｜ 证据来源：2026-09-26 批量闭环对照与 2026-10-08 离线对照的既有原始 JSON，未新增飞行

本文汇总两类权重的全部可核验对照：官方 YOPO-Simple epoch50 权重，与本地从头训练的三个正式种子（formal_main_v1）。结论只覆盖已记录的实验范围。

## 1. 对照对象与身份

| 类别 | 权重 | SHA256 | 说明 |
|---|---|---|---|
| 官方（原生 Simple 布局） | [external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth](../../external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth) | `09ec3109…229f` | 官方发布预训练权重，45,264,872 B |
| 官方（main 布局映射） | [checkpoints/official_epoch50_reference/best_policy.pth](../../checkpoints/official_epoch50_reference/best_policy.pth)（等同 [artifacts/expert/official_epoch50_policy_layout.pth](../../artifacts/expert/official_epoch50_policy_layout.pth)） | `7d5dc46f…a94e` | 7 个键名映射进 main 布局，张量不变，见 [official_checkpoint_mapping.json](../../artifacts/expert/official_checkpoint_mapping.json) |
| 自训练 seed0 | [checkpoints/formal_main_v1_seed0/best_policy.pth](../../checkpoints/formal_main_v1_seed0/best_policy.pth) | `af2ea0fa…f274` | 50 轮 / 312,500 步，随机初始化，最佳轮 50 |
| 自训练 seed1 | checkpoints/formal_main_v1_seed1/best_policy.pth | `908e79f6…94c8` | 最佳轮 47（哈希记录于 training_audit.json） |
| 自训练 seed2 | checkpoints/formal_main_v1_seed2/best_policy.pth | `eaf157f7…6c1d` | 最佳轮 50（哈希记录于 training_audit.json） |

官方权重不加载进训练器（`official_weights_loaded=false`），只用于部署与对照；自训练权重由本仓库完整审计链产生。

## 2. 离线对照（10,000 样本，Table I 口径）

独立测试集地图 2000–2003；网络候选与专家候选都由同一原版 C++ 目标函数评分，未根据测试结果调参。完整表见 [table_i_expert_vs_network.md](../../artifacts/paper_figures/table_i_expert_vs_network.md)与[专家50步比较](../03_training/03_专家50步比较.md)。

| 来源 | 平均候选代价 | 最优候选代价 | 与 scaled_gd50 最优一致率 |
|---|---:|---:|---:|
| 随机初始化 | 0.082267 | 0.039556 | 0.1486 |
| 自训练 seed0 | **0.023062** | **0.017855** | **0.2261** |
| 自训练 seed1 | 0.023073 | 0.017867 | 0.2238 |
| 自训练 seed2 | 0.023072 | 0.017882 | 0.2204 |
| 官方 epoch50 | 0.029614 | 0.021963 | 0.1521 |
| 专家 scaled_gd50（重建） | 0.024253 | 0.021824 | — |
| 专家 mma50（重建） | 0.021451 | 0.018753 | — |

读法：单看该离线集，自训练 seed0 相对官方平均代价低约 22.1%、最优候选低约 18.7%、一致率高约 7.4 个百分点；但自训练平均代价仍弱于 mma50 专家重建，最优候选优于两个专家重建。原论文绝对数字的场景、代价尺度、实现与硬件不同，不作为逐项数值复现声明。

## 3. 闭环对照（36 架次，场景 × 速度 × 栈）

设计：3 个程序化森林场景（简单 5002 / 中等 5004 / 困难 5001）× 3 档速度（2/4/6 m/s）× 4 个「栈 × 权重」组合；每格 1 架次、上限 120 s；判定为终点误差 <0.5 m 且速度 <0.2 m/s 连续 1 s 且无碰撞。全量原始记录见 [batch_summary.json](../../artifacts/weights_ab_demo/batch_summary.json)与 [batch_analysis.json](../../artifacts/weights_ab_demo/batch_analysis.json)。

| 组合（栈×权重） | 成功 | 超时 | 碰撞 | 到达中位 | 跟踪 RMSE 中位 | 网络时延中位 |
|---|---:|---:|---:|---:|---:|---:|
| Simple 栈 + 官方 | 8/9 | 1 | 0 | 6.82 s | 0.249 m | 4.5 ms |
| Simple 栈 + 自训练 seed0 | 8/9 | 1 | 0 | 11.75 s | 0.235 m | 4.5 ms |
| main 栈 + 官方 | 7/9 | 1 | 1 | **4.61 s** | 1.103 m | 16.5 ms |
| main 栈 + 自训练 seed0 | 7/9 | 1 | 1 | 13.93 s | **0.512 m** | 16.2 ms |

按速度的成功数（官方/自训练，Simple 与 main 两栈）：

| 速度 | Simple 官方 | Simple 自训练 | main 官方 | main 自训练 |
|---:|---|---|---|---|
| 2 m/s | 2/3 | **3/3** | 2/3 | **3/3** |
| 4 m/s | **3/3** | **3/3** | **3/3** | 2/3 |
| 6 m/s | **3/3** | 2/3 | 2/3 | 2/3 |

关键结论（与[权重批量对照实验](02_权重批量对照实验.md)一致）：

- 成功率分不出两类权重：同栈下观察成功数相同（8/9 与 8/9、7/9 与 7/9），每格仅 1 架次，不具统计显著性。
- 权衡点不同：官方更快（main 栈到达中位 4.61 s vs 13.93 s），自训练跟踪更准（main 栈 RMSE 中位 0.512 m vs 1.103 m；官方在 6 m/s 单格最高 4.77 m）。
- 栈的匹配效应大于权重差异：同一权重换栈引起的 RMSE 变化幅度大于换权重，不能单独归因于权重退化。
- 失败模式：4 个超时都是「飞得动但收敛不到终点」（航迹 134–352 m）；2 个碰撞都发生在 6 m/s，安全裕度主要被速度与场景吃掉。
- 场景相关：官方在 main 栈的旧网格场景曾两次超时，但在 3 个森林场景 7/9 成功——单点结论不可推广。

## 4. 与正式矩阵的关系

官方权重不参与 1500/1800 冻结矩阵；矩阵内 YOPO 全部为自训练三种子（另有 TopoTraj、Agile 基线，MPPI 300 槽未执行）。本文的 36 架次与离线对照均为独立 scope（`weights A/B batch outside the frozen benchmark matrix`），未触碰冻结证据。正式矩阵结果见 [summary.json](../../artifacts/benchmark_summary/summary.json)。

## 5. 展示对比（两阶段，不是受控实验）

| 阶段 | 权重 | 视频与清单 |
|---|---|---|
| 官方预训练部署阶段（2026-09 早期） | 官方 Simple epoch50 | [yopo_global_flight.mp4](../../artifacts/showcase/forest_seed7_v3/yopo_global_flight.mp4)、[render_manifest.json](../../artifacts/showcase/forest_seed7_v3/render_manifest.json)、[完成验收与成果路径](../90_archive/01_完成验收与成果路径.md) |
| 自训练最终展示（50 轮审计权重） | 自训练 seed0 | [global_trajectory.mp4](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_trajectory.mp4)、[metrics.json](../../artifacts/ros2_flights/showcase_formal_main_v1_seed0_20260926_014921/metrics.json)（成功、RMSE 0.116 m、最小净空 1.188 m、端到端 p50 92.7 ms） |

两个展示的场景、栈与录制方式不同，只用于说明两个阶段各自能飞，不构成对照结论。

## 6. 口径与局限

- 每格 1 架次、总 36 架次：不能做显著性判断，“谁更稳”在现有样本量下不成立。
- 网络时延中位只覆盖网络管道；不含取像/渲染读取（约 43 ms）与传输，不能当端到端指标。
- 程序化森林不是官方 Flightmare 资产；官方权重在本地分布上的行为不等同官方场景表现。
- 本地离线集的优势（Table I 口径）不能外推为“训练方法普遍更优”。

## 7. 证据与复跑入口

- 逐架次原始指标：`artifacts/navigation/wab2_<arm>_s<scene>_v<speed>/metrics.json`（36 个目录）；日志见 [batch_logs](../../artifacts/weights_ab_demo/batch_logs)。
- 批量驱动：[scripts/run_weights_ab_batch.py](../../scripts/run_weights_ab_batch.py)（支持 `--skip-existing` 续跑）；离线对照：[scripts/compare_expert_network.py](../../scripts/compare_expert_network.py)。
- 权重身份：官方映射记录 [official_checkpoint_mapping.json](../../artifacts/expert/official_checkpoint_mapping.json)；自训练审计 [checkpoints/formal_main_v1_seed0/training_audit.json](../../checkpoints/formal_main_v1_seed0/training_audit.json)。
