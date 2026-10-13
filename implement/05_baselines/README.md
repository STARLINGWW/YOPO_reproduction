# 05 基线与专家

> 论文对应：III-A（与专家的对照，Table I）、III-B（与 TopoTraj/MPPI/Agile 的仿真对比，Table II / Fig.7）｜ 一句话定位：把论文的四类对照对象在同一协议下跑通或明确记录缺口。

## 职责范围

四类对象：① 梯度专家（本地重建，对应论文 classical gradient-based expert）；② TopoTraj（Fast-Planner 拓扑路径，移植为 ROS2 包）；③ Agile Autonomy（官方网络导出接入）；④ 参考[17] MPPI（仅归档身份材料，未实现）。基线与专家必须通过与 YOPO 相同的准入与飞行证据契约，才能进入正式矩阵汇总。

## 代码地图

| 路径 | 角色 | 说明 |
|---|---|---|
| [src/yopo_expert/core.py](../../src/yopo_expert/core.py) | 专家重建（Python） | 上游代价的梯度优化器移植；变体定义见 [configs/expert_variants.json](../../configs/expert_variants.json)（scaled_gd50、MMA） |
| [ros2_ws/src/yopo_expert_core/src/expert.cpp](../../ros2_ws/src/yopo_expert_core/src/expert.cpp) | 专家核心（C++） | 原版代价与梯度重编译，`provenance.json` 记录来源；`original_gradient.inc` 保留原梯度实现 |
| [ros2_ws/src/yopo_math_reference](../../ros2_ws/src/yopo_math_reference) | 数值参考包 | cost/matrix/sdf/voxel 的 C++ 参考实现，供 parity 检查 |
| [ros2_ws/src/yopo_topotraj](../../ros2_ws/src/yopo_topotraj) | TopoTraj 移植 | vendored `bspline`/`bspline_opt`/`path_searching`/`plan_env`/`plan_manage`/`poly_traj` + `topotraj_node.cpp`；[port_provenance.json](../../ros2_ws/src/yopo_topotraj/port_provenance.json) 记录移植来源 |
| [src/agile_runtime/torch_network.py](../../src/agile_runtime/torch_network.py) | Agile 运行时 | 官方网络 Torch 导出与推理 |
| [ros2_ws/src/yopo_runtime/yopo_runtime/agile_planner.py](../../ros2_ws/src/yopo_runtime/yopo_runtime/agile_planner.py) | Agile 节点内接入 | ROS2 闭环中的 Agile 规划器 |
| [ros2_ws/src/yopo_agile_core/src/trajectory_core.cpp](../../ros2_ws/src/yopo_agile_core/src/trajectory_core.cpp) | Agile 轨迹核心（C++） | 官方轨迹核心提取，带 provenance |
| [ros2_ws/src/yopo_quad_reference](../../ros2_ws/src/yopo_quad_reference) | 控制器参考 | SO3Control 参考实现（控制器 parity） |
| [scripts/run_expert_cache.py](../../scripts/run_expert_cache.py)、[scripts/compare_expert_network.py](../../scripts/compare_expert_network.py) | 专家对照 | 生成专家缓存并在离线测试集比较网络与专家 |
| [scripts/port_topotraj_components.py](../../scripts/port_topotraj_components.py)、[scripts/port_topotraj_fsm.py](../../scripts/port_topotraj_fsm.py)、[scripts/configure_topotraj.py](../../scripts/configure_topotraj.py) | TopoTraj 移植链 | 组件与 FSM 移植、配置生成 |
| [scripts/port_agile_network.py](../../scripts/port_agile_network.py)、[scripts/export_agile_network.py](../../scripts/export_agile_network.py)、[scripts/extract_agile_trajectory_core.py](../../scripts/extract_agile_trajectory_core.py) | Agile 导出链 | 网络导出与轨迹核心提取 |
| [scripts/ros2/probe_topotraj_node.py](../../scripts/ros2/probe_topotraj_node.py)、[scripts/ros2/probe_topotraj_runtime.py](../../scripts/ros2/probe_topotraj_runtime.py) | 探针 | TopoTraj 节点/运行时探针 |

## 输入与输出

- 输入：与 YOPO 相同的 episode 协议（深度、状态、目标）；专家还需要 ESDF/代价配置。
- 输出：离线对照 JSON（artifacts/expert/）、CUDA/参考 parity（artifacts/agile_autonomy/、artifacts/environment/）、闭环飞行记录（artifacts/ros2_flights/）与矩阵汇总（由 [06 验证](../06_validation/README.md) 聚合）。

## 常用命令（项目根目录执行）

```powershell
Set-Location '<项目根目录>'

# 专家缓存与对照
python scripts/run_expert_cache.py --help
python scripts/compare_expert_network.py --help

# TopoTraj / Agile 探针（容器或 ROS2 环境）
python scripts/ros2/probe_topotraj_node.py --help
python scripts/probe_agile_torch.py --help
```

## 证据与产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 专家对照（三种子） | [network_comparison_trained_seed0.json](../../artifacts/expert/network_comparison_trained_seed0.json) 等 seed1/seed2 | 独立离线测试集全量样本 |
| 专家对照（随机初始化） | [network_comparison_random_initial.json](../../artifacts/expert/network_comparison_random_initial.json) | 随机权重基线 |
| 论文 Table I 汇总 | [table_i_expert_vs_network.md](../../artifacts/paper_figures/table_i_expert_vs_network.md) | 代价与时延对照 |
| Agile CUDA parity | [torch_cuda_parity.json](../../artifacts/agile_autonomy/torch_export_v1/torch_cuda_parity.json) | Torch 导出与参考数值一致性 |
| Agile 完整参考 parity | [agile_complete_reference_parity.json](../../artifacts/environment/agile_complete_reference_parity.json) | 与官方参考对齐记录 |
| 运行协议准入 | [runtime_validation.json](../../benchmarks/protocol_v1/runtime_validation.json) | agile/topotraj/yopo 三后端 passed |
| MPPI 身份材料 | [mppi_identity.json](../../artifacts/paper_sources/mppi_identity.json)、[MPPI_reference17_Lu2021_TIE.pdf](../../artifacts/paper_sources/MPPI_reference17_Lu2021_TIE.pdf) | 参考[17]全文归档；实现未完成 |

## 验证方法

- 矩阵内结果（各模型 300 槽）见 [artifacts/benchmark_summary/summary.json](../../artifacts/benchmark_summary/summary.json)：TopoTraj 71/300、Agile 30/300 成功（YOPO 三种子 163–184/300）。
- 进入矩阵前的准入：`scripts/record_runtime_validation.py` 与 `tests/test_runtime_admission*.py`。
- 专家缓存审计：`scripts/audit_expert_cache.py`。

## 已知限制与论文差异

- 参考[17] MPPI 只有身份材料与全文归档，未找到官方发布、需要重实现：300 槽未执行，状态为 documented_gap（见 [MPPI参考17身份与可得性](../../report/90_archive/mppi/05_MPPI参考17身份与可得性.md)）。
- 专家为本地重建（原 C++ 代价 + 明确记录的求解器变体），不是论文作者的原始实现二进制。
- TopoTraj 从 Fast-Planner 生态移植（含 vendored 源码），本地面向同一 Isaac 场与协议做过适配。
- Agile 为官方网络的导出与接入，用于对照，不是官方完整工程栈的逐文件复刻。

## 相关入口

- [模块总图](../../report/00_index/01_module_map.md) ｜ [04 评测交付](../../report/04_evaluation/README.md)
- [ROS2基线迁移记录](../../report/04_evaluation/06_ROS2基线迁移记录.md) ｜ [权重批量对照实验](../../report/04_evaluation/02_权重批量对照实验.md)

