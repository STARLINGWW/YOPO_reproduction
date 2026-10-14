# 官方权重参考臂（reference arm, external_reference）

这条矩阵回答一个主矩阵刻意不回答的问题：**上游发布的官方 epoch50 权重，在同一条 ROS2/Isaac 链、同一批任务与判据下表现如何**。它与 1,500 槽主矩阵**完全隔离**：

| 维度 | 主矩阵（活动范围） | 参考臂（本目录） |
|---|---|---|
| 模型 | YOPO 三种子（自训练）+ TopoTraj + Agile | `yopo_official_reference` |
| 来源类别 | from-scratch 训练 + 逐轮审计 + 验证集选优（`verify_formal_yopo_checkpoint`） | `external_reference`：**哈希锚定**的发布权重，rename-only 映射；不声明随机初始化、不声明选优 |
| 准入 | `benchmarks/protocol_v1/runtime_validation.json` | 本目录 `runtime_validation.json`（`validated_backends=['yopo_reference']`） |
| 汇总 | `artifacts/benchmark_summary/summary.json` | `artifacts/benchmark_summary/reference_arm_official_v1_summary.json` |
| 任务 | 20 图 × 3 trial × 5 速度（每格 n=30） | 与主矩阵逐任务一一对应（同 map/trial/速度/判据） |

**永远不要**把参考臂运行混入主矩阵断言：主聚合器按 `scope=reference_arm_official_v1` 忽略这些飞行，参考臂聚合器也拒绝写主 summary。

## 文件

- `protocol.json`：300 槽定义（由 `scripts/create_reference_arm_protocol.py` 从主协议 + 权重 provenance 生成；地图文件逐字节复制并校验 sha256）。
- `runtime_validation.json`：两阶段准入记录（`scripts/record_reference_admission.py`；阶段 A 开发飞行 + 阶段 B 两个真实 episode，消耗的 episode 由驱动自动跳过）。
- `maps/`：主协议地图的字节拷贝。

## 运行

```bash
# 1) 组装协议（幂等；权重变化会显式报错）
python scripts/create_reference_arm_protocol.py

# 2) 两阶段准入（需要 Isaac + Docker + 空闲 GPU）
python scripts/record_reference_admission.py --phase ab --dev-map-seed 3300

# 3) 参考矩阵（独立 progress/plan/result 文件；--execute 真跑，缺省 dry-run）
python scripts/run_benchmark_matrix.py --protocol benchmarks/reference_arm_official_v1/protocol.json \
  --progress artifacts/benchmark_summary/reference_arm_progress.json \
  --plan artifacts/benchmark_summary/reference_arm_plan.json \
  --result artifacts/benchmark_summary/reference_arm_result.json \
  --methods yopo_official_reference --execute

# 4) 独立汇总
python scripts/aggregate_reference_arm.py
```

## 运行前置（本机已处理，干净克隆需照做）

1. **ROS2 overlay**：容器 entrypoint 只会在存在时 source `ros2_ws/install/setup.bash`；干净克隆必须先构建：
   `docker compose --profile training run --rm train bash -lc "source /opt/ros/humble/setup.bash && cd /workspace/ros2_ws && colcon build --merge-install --packages-up-to yopo_runtime"`
2. **容器可见的目录**：Docker bind mount 不穿越 Windows junction，因此 `checkpoints/official_epoch50_reference`（官方权重）与 `artifacts/ros2_flights`（飞行产物目录）在本机已实体化为真实目录；历史重数据留在外部归档（`artifacts/ros2_flights/.archive_location.txt` 记录了路径）。
3. 官方权重可由上游原件重建：`external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth`（sha256 记录于 `checkpoints/official_epoch50_reference/PROVENANCE.json` 与参考协议）。

## 证据规则

- 每个 episode 的 `metrics.json` 必须带 `scope=reference_arm_official_v1`、`mission.protocol_sha256` 与本协议一致、`checkpoint_sha256 == reference_weights.staged_sha256`，并通过 `validate_ros2_flight.py` / `evaluate_ros2_flight.py`；
- 失败（碰撞/超时/崩溃）照实保留并按分母计入——超时同样是有效终态；
- 参考臂结论只用于对照，不改变主矩阵的 1,500/1,500、终审或活动范围声明。
