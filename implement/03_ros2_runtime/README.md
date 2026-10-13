# 03 ROS2 运行时

> 论文对应：II-A（推理与在线选择）、III-C（闭环部署的本地仿真替代）｜ 一句话定位：把训练好的策略接进 ROS2 闭环，负责时钟、候选选择、轨迹生成与执行监督。

## 职责范围

本模块覆盖从"观测到达"到"轨迹交给控制器"的全部在线逻辑：帧门控与新鲜度检查、预测代价 argmin 选择、只解码所选端点的终端状态、五次多项式生成、时间管理（轨迹有效期与续接重规划）、协议事件发布；以及基线（TopoTraj/Agile）在同一协议下的节点化接入。训练侧不在这里（见 [02 训练流水线](../02_training_pipeline/README.md)）。

## 代码地图

| 路径 | 角色 | 说明 |
|---|---|---|
| [ros2_ws/src/yopo_runtime/yopo_runtime/main_planner.py](../../ros2_ws/src/yopo_runtime/yopo_runtime/main_planner.py) | YOPO 在线规划器 | 加载审计权重；`argmin` 选候选后只解码所选端点；有效旧轨迹存在时从其当前时刻 p/v/a 续接，否则用观测 p/v 与零初始加速度 |
| [ros2_ws/src/yopo_runtime/yopo_runtime/protocol_node.py](../../ros2_ws/src/yopo_runtime/yopo_runtime/protocol_node.py) | 协议节点 | 处理 episode/goal/observation/clock 消息；发布 `/yopo/runtime/*` 轨迹与事件；`max_age_ns` 守卫 |
| [ros2_ws/src/yopo_runtime/yopo_runtime/frame_gate.py](../../ros2_ws/src/yopo_runtime/yopo_runtime/frame_gate.py) | 帧门控 | 观测新鲜度（`max_age_ns`）、episode 帧一致性、轨迹是否仍然当前（`trajectory_is_current`） |
| [ros2_ws/src/yopo_runtime/yopo_runtime/agile_planner.py](../../ros2_ws/src/yopo_runtime/yopo_runtime/agile_planner.py) | Agile 节点内规划器 | TensorFlow/Torch 引擎的 Agile 网络接入（基线对照） |
| [ros2_ws/src/yopo_runtime/test/test_frame_gate.py](../../ros2_ws/src/yopo_runtime/test/test_frame_gate.py) | 测试 | 帧门控单元测试 |
| [ros2_ws/src/yopo_interfaces/msg/PolynomialTrajectory.msg](../../ros2_ws/src/yopo_interfaces/msg/PolynomialTrajectory.msg) | 接口 | 多项式轨迹消息定义 |
| [src/yopo_sim/trajectory_buffer.py](../../src/yopo_sim/trajectory_buffer.py) | 轨迹生命周期 | 轨迹过期与有效性缓冲（闭环执行侧） |
| [scripts/run_ros2_navigation.py](../../scripts/run_ros2_navigation.py) | 闭环编排入口 | 创建 `/clock` 与 `/yopo/runtime/*` 发布/订阅，驱动 Isaac 闭环并记录 planning/execution 事件 |
| [scripts/ros2/serve_planner.py](../../scripts/ros2/serve_planner.py) | 规划服务 | 容器侧规划器服务（准入与飞行共用） |
| [scripts/record_runtime_validation.py](../../scripts/record_runtime_validation.py) | 准入记录器 | 记录运行时文件哈希与后端验证到 `benchmarks/protocol_v1/runtime_validation.json` |
| [scripts/validate_ros2_flight.py](../../scripts/validate_ros2_flight.py)、[scripts/evaluate_ros2_flight.py](../../scripts/evaluate_ros2_flight.py) | 证据契约与指标 | 校验飞行记录契约、汇总每架次指标 |

## 输入与输出

- 输入：深度观测、里程计状态、目标点、仿真时钟（`/clock`）、episode 标识。
- 输出：`/yopo/runtime/trajectory`（轨迹）、`/yopo/runtime/planning_event`、`/yopo/runtime/execution_status`（JSON 事件流）。
- 参数：`--run`（run 名称）决定权重与输出目录；权重为各 `checkpoints/<run>/best_policy.pth`。

## 常用命令（项目根目录执行）

```powershell
Set-Location '<项目根目录>'

# 闭环飞行（需 Isaac 与 ROS2 环境）
python scripts/run_ros2_navigation.py --run showcase_formal_main_v1_seed0_20260926_014921

# 记录/核对运行协议准入
python scripts/record_runtime_validation.py

# 校验与评测单次飞行
python scripts/validate_ros2_flight.py --help
python scripts/evaluate_ros2_flight.py --help
```

## 证据与产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 运行协议准入 | [runtime_validation.json](../../benchmarks/protocol_v1/runtime_validation.json) | `status=passed`；agile/topotraj/yopo 三后端；含运行时文件哈希 |
| 飞行原始记录 | [artifacts/ros2_flights](../../artifacts/ros2_flights) | 按 run 分目录；体积巨大，勿递归扫描 |
| 演示飞行指标 | [showcase … 014921/metrics.json](../../artifacts/ros2_flights/showcase_formal_main_v1_seed0_20260926_014921/metrics.json) | 最终展示链的测量日志 |

## 验证方法

- 帧门控与协议：`pytest -q tests/test_trajectory_buffer.py` 与 `tests/test_runtime_admission*.py`；包内还有 `test/test_frame_gate.py`。
- 契约：`tests/test_flight_evidence_contract.py` 校验飞行证据结构；`tests/test_runtime_admission_contract.py` 校验准入记录。
- 实跑：`scripts/record_runtime_validation.py` 重放固定 episode 生成准入记录（需要容器与 ROS2）。

## 已知限制与论文差异

- 在线选择使用预测正代价 `argmin`，只解码所选端点；与论文"负评分 argmax、解码全部 15 条"的叙述不同（差异 D1/D7）。
- 重规划起点在有效旧轨迹存在时取自旧参考的当前时刻状态（差异 D8）。
- 相机名义 15 Hz，控制 100 Hz（`control_dt_s=0.01`），物理 500 Hz（`physics_dt_s=0.002`，见 [configs/unified_quad.json](../../configs/unified_quad.json)）；异步接受率不能等同名义频率（差异 D6）。
- 在线轨迹时域 `T=8/v`（4 m/s 时为 2 s）；训练时域固定 1.333 s（差异 D5）。
- 里程计来自仿真状态；实机（论文 III-C）未复现（差异 D11）。

## 相关入口

- [模块总图](../../report/00_index/01_module_map.md) ｜ [02 方法对照](../../report/02_method/01_paper_to_code.md)
- [04 Isaac 仿真](../04_isaac_sim/README.md) ｜ [ROS2基线迁移记录](../../report/04_evaluation/06_ROS2基线迁移记录.md)

