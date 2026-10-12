# 选项 A 实施计划（**未执行，等待用户批准开跑**）：按参考[17] 原文补齐 300 个 mppi_reference17 槽位

记录时间：2026-09-26 (+08:00)
状态：**plan only**。用户已提供参考[17] 的合法全文（归档与身份核对见 `artifacts/paper_sources/mppi_reference17_identity_verified.json`，SHA256 `61d2675b…`）。本文件只描述"若批准 A 要做什么"，未改任何代码、判据或证据。

## 1. 目标与成功判据

- 让 `benchmarks/protocol_v1/protocol.json` 里 300 个 `mppi_reference17` 槽位产生**真实终态飞行证据**（同一 frozen protocol、同一 identity/校验/评估闸门）。
- 主矩阵覆盖从 1500/1800 变为 **1800/1800**，`scripts/final_acceptance_audit.py` 的 `benchmark_matrix` 项达到 verified。
- MPPI 那一项（`mppi_reference17`）需要一处小扩展：现在只要协议状态含 `reference_only` 就判 `documented_gap`，否则一律 `pending`；补齐后应改为"按论文重实现 + 300 槽逐槽证据"才判 verified（否则该项会从 documented_gap 变成 pending，反而更差）。

## 2. 按论文实现什么（不是按 YOPO 的一句话转述）

论文正文（已提取到 `artifacts/paper_sources/mppi_reference17_text.txt`）给出的方法：

- **前端（全局）**：RRT* 在当前感知地图上低频生成全局路径 `Pg`；从路径上选局部目标 `Gl`（需在传感器量程 `ds` 内或距离小于 `dt`），并对 `Gl→Gg` 做可行性检查，不可行则触发应急重规划。
- **后端（局部）**：stochastic optimal control / **sampling-based MPC**（KL 散度最小化 + 重要性采样权重，即 MPPI 家族；论文引用 [8][9][10]，原文并未自称 MPPI）。参数：**10 Hz** 控制、每次迭代 **N=2560** 条采样轨迹、预测时域 **3.5 s**、控制协方差 **Σ=diag(4.25, 4.25, 2.2, 1.4)**、平均更新 **20.69 ms（Jetson Xavier NX）/ 8.10 ms（笔记本）**；标称状态 100 Hz 发布给底层。
- **代价项**：动力学/运动代价、碰撞代价、有限 FOV 软约束（偏航对齐 `c_ψ`、视场外惩罚 `c_FOVh`、水平飞行 `c_FOVv`）、终端代价；引导路径选择权重 `λs / λp / λm`（运动 / 路径长度 / 记忆项）。
- **平台**：Jetson Xavier NX（384 CUDA 核）、RealSense D455（87°×58°，约 10 m）、Pixhawk + 几何控制器 + Tube-MPC 框架。

**必须在报告里显式记录的口径差异**：YOPO 把参考[17] 写成 "MPPI Planner with Hybrid A*"，而原文前端是 **RRT***；本复现按原文实现，并在 MPPI 基线的报告里写明这一转述差异（不因此改变 YOPO 论文的结论比较口径）。

## 3. 工程落地清单（预估 6–10 小时编码 + 4–5 小时 GPU）

被改动的文件里有多个属于 **20 文件运行时冻结清单**，因此 A 必然包含"运行时换代 + 重新准入"这一步：

| # | 文件 | 改动 | 冻结? |
|---|---|---|---|
| 1 | 新增 `ros2_ws/src/yopo_runtime/yopo_runtime/mppi_planner.py` 等 | 采样型 MPC（2560 采样、3.5 s、10 Hz）+ RRT* 前端 + 局部目标选择 + FOV 软约束代价 | 新增，不在冻结清单 |
| 2 | `scripts/ros2/serve_planner.py` | 注册 `mppi_reference17` 后端与既有统一接口 | ✅ 冻结 |
| 3 | `scripts/run_ros2_navigation.py` | `--backend` 增加 `mppi_reference17`，按后端选择容器/启动命令（CPU/GPU 判定） | ✅ 冻结 |
| 4 | `scripts/run_benchmark_matrix.py` | 删除对 `mppi_reference17` 的硬跳过，纳入正常执行与设备选择 | ✅ 冻结 |
| 5 | `scripts/record_runtime_validation.py` | `BACKENDS` 增加 `mppi_reference17`（phase A + phase B 冻结 episode） | ✅ 冻结 |
| 6 | `artifacts/environment/protocol_snapshot_delta.json` | 记录"新增一个后端 + 运行时文件集换代"，声明不改 1500 集既有证据 | 证据文件 |
| 7 | `configs/reproduction_protocol.json` | `baseline_sources.MPPI.status` 从 `reference_only…` 改为 `reimplemented_from_paper_reference17_sha256_61d2675b…` | 协议元数据 |
| 8 | `scripts/final_acceptance_audit.py` | `check_mppi`：新增"按论文重实现 + 300 槽全终态"→ verified 的分支 | 判据脚本 |

**运行时换代的诚实口径**：既有 1500 集的 `metrics.json` 各自内嵌了生成它们时的准入记录（哈希自洽），聚合器只读该内嵌记录与协议哈希，所以**不需要重跑 1500 集**；只是矩阵的 300 个 MPPI 槽位属于"运行时第 2 代"，必须在报告与 `protocol_snapshot_delta.json` 里写明，不得含糊成"同一代运行时跑完 1800 集"。

## 4. 执行顺序（批准后）

1. 写 MPPI 规划器 + RRT* 前端（CPU 单测：采样数/时域/协方差/代价项可复算，哈希可追踪）。
2. 接入统一 ROS2 接口（`/yopo/runtime/trajectory` 等），用 1 架次开发航次做接口冒烟（development scope，不进矩阵）。
3. 重新记录准入：phase A（各后端开发航次）+ phase B（每个后端消费 2 个冻结 episode）→ 新 `runtime_validation.json`（含 4 个后端）；记录 `protocol_snapshot_delta.json`。
4. 跑 `mppi_reference17` 的 300 个槽位（串行，单集约 40–60 s 墙钟 → 约 4–5 小时 GPU；沿用 900 s 守卫 + 隔离留证 + 续跑的既有机制）。
5. 重跑 `scripts/aggregate_benchmarks.py`（应得 completed=1800/expected=1800、invalid 0、duplicate 0）→ `scripts/final_acceptance_audit.py`（应得 6 verified + 1 documented_gap 或 7 verified，取决于 MPPI 项是否按第 3 节第 8 条改为 verified）→ `scripts/make_status_overview.py`。
6. 用全量 1800 集数据重生成 Figure 7 / Table II（`scripts/make_paper_figures.py`），并在报告里更新 MPPI 行（不再 n/a）。

## 5. 风险与边界

- **不准顶替**：不得用 RAPA-Planner 或任何第三方 hybrid-A*-guided MPPI 代替；必须按参考[17] 正文实现。
- **不准伪造**：300 个槽位必须是真实 Isaac 闭环飞行产生的终态证据；任何失败（碰撞/超时）如实记录，不做筛选。
- **判据改动只限必要项**：`benchmark_matrix` 的 1800/1800 判据本就在协议里，A 不改它；唯一要动的是 `check_mppi` 的 verified 分支（第 3 节第 8 条），且必须同时保留"没有 300 槽证据就回落 pending"的反向约束。
- **GPU 串行**：训练/矩阵/展示任务互斥，沿用现有 job guard；不触碰 `fastlivo2-ros1` / `ego-planner-ros1v` 容器。
- **时间**：编码 6–10 小时 + 飞行 4–5 小时；若中途遇到论文未给出的参数（例如具体代价权重未在正文列出），一律以"未知即记录"的方式处理，不臆造数值，并在报告里列为 documented_gap 细节。

## 6. 与选项 B 的关系

- A 与 B 互斥（A 补齐 300 槽后不需要排除；B 是承认这 300 槽按政策不执行）。
- 两者都要求最终报告口径诚实：A 要写明"按论文重实现 + 运行时第 2 代 + 300 槽真实执行"，B 要写明"1500 已执行 + 300 显式排除、不是 1800 集等价复现"。
- 若你选 A：请回复"批准 A"（或"开跑 A"），我会先做接口冒烟与准入，再开始 300 槽。若你改选 B：补丁已备好，几分钟即可落地。
