# protocol_v1 说明（YOPO-only 发布）

- `protocol.json`：冻结的 **1800 槽超集矩阵**（六模型）。**字节不可变**——每条已记录飞行都内嵌它的 sha256（`d2fd3052…`），`runtime_validation.json` 亦引用它。标签：`historical_protocol_v1` / `not_used_by_active_yopo_only_release`。
- `active_scope_yopo_only.json`：YOPO-only **活动范围**（五模型 × 300 = 1500）。`scripts/aggregate_benchmarks.py`、`scripts/final_acceptance_audit.py`、`scripts/make_status_overview.py` 与基准测试按此口径计算；`--superset` 可复算历史 1800 口径。
- `maps/`：20 张冻结地图（sha256 记录于 `protocol.json`；`.gitattributes` 以 `-text` 保证字节保真，克隆后哈希不变）。
- `runtime_validation.json`：2026-09-24 真实飞行准入记录（YOPO、TopoTraj、Agile 三后端通过）。**2026-10-13 发布勘误**：`scripts/run_benchmark_matrix.py` 的机器解释器默认值改为 `YOPO_ISAAC_PYTHON`（容器内启动行为不变），文件内 `runtime_files_amendment` 透明记录旧/新哈希；其余 19 个冻结运行文件字节未变。后续任何再次修改运行时文件都会使准入失效。
- 1800 口径的调度/汇总/终审快照：`../archive/protocol_v1_1800/`。
