# 04 Isaac Sim 仿真链路

> 论文对应：III（实验环境与实机的本地等效替代）｜ 一句话定位：程序化森林、PhysX 机体、深度相机与两条运行链，为训练数据、准入和闭环飞行提供等效测试场。

## 职责范围

本模块是"世界"一侧：场景生成（程序化森林与 USD）、物理仿真（PhysX 机体与控制器）、传感器（深度采集与质量检查）、轨迹缓冲与机体资源调度，以及原生/ROS2 两条运行链的编排。它不是论文的 Flightmare 场景，也不代表论文实机平台（见已知限制）。

## 代码地图

| 路径 | 角色 | 说明 |
|---|---|---|
| [src/yopo_sim/unified_quad.py](../../src/yopo_sim/unified_quad.py) | 统一机体 | Fast-Planner 参数来源的等效四旋翼；`configs/unified_quad.json` 记录质量/惯量/桨叶/控制器增益与来源 commit |
| [src/yopo_sim/physx_vehicle.py](../../src/yopo_sim/physx_vehicle.py) | PhysX 机体 | 物理步进与电机模型（物理 500 Hz） |
| [src/yopo_sim/trajectory_buffer.py](../../src/yopo_sim/trajectory_buffer.py) | 轨迹缓冲 | 轨迹有效期、过期与当前参考查询 |
| [src/yopo_sim/evaluation_geometry.py](../../src/yopo_sim/evaluation_geometry.py) | 评测几何 | 净空、轨迹长度等评测几何计算 |
| [src/yopo_sim/resource_sampler.py](../../src/yopo_sim/resource_sampler.py)、[src/yopo_sim/job_guard.py](../../src/yopo_sim/job_guard.py) | 资源与任务守卫 | 采样资源使用、防止并发任务冲突 |
| [src/yopo_repro/forest.py](../../src/yopo_repro/forest.py) | 场景几何 | 程序化森林生成、解析距离与光线深度、USD 场景输出 |
| [scripts/run_navigation.py](../../scripts/run_navigation.py) | 原生链入口 | Windows 原生 Isaac 飞行/回放 |
| [scripts/run_ros2_navigation.py](../../scripts/run_ros2_navigation.py) | ROS2 链入口 | 与 [03 ROS2 运行时](../03_ros2_runtime/README.md) 配合的闭环编排 |
| [scripts/collect_isaac_shard.py](../../scripts/collect_isaac_shard.py) | 数据采集 | 单 shard 深度/位姿采集（供 100K/10K/10K 数据集） |
| [scripts/probe_isaac_depth.py](../../scripts/probe_isaac_depth.py)、[scripts/depth_quality.py](../../scripts/depth_quality.py) | 深度探针与质量 | 深度帧检查与质量指标 |
| [scripts/scene.py](../../scripts/scene.py) | 场景脚本 | 场景搭建辅助入口 |
| [configs/unified_quad.json](../../configs/unified_quad.json) | 机体配置 | `physics_dt_s=0.002`（500 Hz）、`control_dt_s=0.01`（100 Hz）、`classification` 声明等效性边界 |

## 输入与输出

- 输入：地图 seed、密度、位姿采样、机体配置；ROS2 链还需要运行协议（episode/goal）。
- 输出：深度帧与位姿（datasets/）、飞行记录与指标（artifacts/ros2_flights）、探针证据（artifacts/isaac_depth_probe、artifacts/probes、artifacts/environment/isaac_*）。

## 常用命令（项目根目录执行）

```powershell
Set-Location 'D:\_AAA_CODE_ALL\Tech_reproduction\YOPO_reproduction'

# 原生链飞行/回放
python scripts/run_navigation.py --help

# 深度采集与质量
python scripts/collect_isaac_shard.py --help
python scripts/depth_quality.py --help

# 统一演示入口（含回放）
./scripts/demo_flight.ps1
```

Isaac 相关命令需要 Windows 原生 Isaac Sim 环境；容器内训练不依赖 Isaac（见 [02 训练流水线](../02_training_pipeline/README.md)）。

## 证据与产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 深度探针 | [artifacts/isaac_depth_probe](../../artifacts/isaac_depth_probe)、[artifacts/probes](../../artifacts/probes) | 采集正确性与物理探针 |
| 传输与环境探针 | `artifacts/environment/isaac_transport*.log`、`isaac_humble_probe.json` | Isaac↔ROS2 传输验证 |
| 数据校验 | [datasets/isaac_full_v1/validation.json](../../datasets/isaac_full_v1/validation.json) | 深度帧、位姿、地图隔离的机械校验 |
| 闭环飞行 | [artifacts/ros2_flights](../../artifacts/ros2_flights) | 按 run 分目录（体积大，勿递归扫描） |

## 验证方法

- 几何与评测：`pytest -q tests/test_evaluation_geometry.py tests/test_evaluation_metrics.py`。
- 深度质量：`tests/test_depth_quality.py` 与 `scripts/depth_quality.py`。
- 轨迹缓冲：`tests/test_trajectory_buffer.py`。

## 已知限制与论文差异

- 场景是 Isaac 程序化森林（等效条件实验），不是论文的 Flightmare 森林资产（差异 D9）。
- 机体是"Common Isaac equivalent vehicle"（Fast-Planner 参数 + PhysX），`unified_quad.json` 明确不声明 YOPO 实机平台一致性。
- 本地闭环在仿真中执行；论文 III-C 实机实验未复现（差异 D11）。
- 深度流水线：采集后裁剪到 20 m 并缩放到网络输入 96×160（见 [src/yopo_repro/dataset.py](../../src/yopo_repro/dataset.py)）；相机内参记录在 [datasets/isaac_dagger_v1/aggregation_manifest.json](../../datasets/isaac_dagger_v1/aggregation_manifest.json) 的 `camera` 段。

## 相关入口

- [模块总图](../../report/00_index/01_module_map.md) ｜ [03 ROS2 运行时](../03_ros2_runtime/README.md)
- [演示程序与权重飞行验证命令](../../report/05_visualization/01_演示程序与权重飞行验证命令.md) ｜ [report/05 可视化](../../report/05_visualization/README.md)

