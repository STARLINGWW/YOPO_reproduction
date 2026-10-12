# 99 实施规则与任务模板

> 论文对应：工程支撑 ｜ 一句话定位：所有实施任务（含大模型执行）必须遵守的流程规范。

## 职责范围

本目录不保存代码和产物，只规定实施流程：怎样立项、怎样改动、怎样验证、怎样记档。目标是让任何一个实施任务都能被复查：目标清楚、影响范围明确、证据可追溯、回滚可执行。

## 固定流程

1. 读 plan：先读 [plan/README](../../plan/README.md) 与相关编号计划；确认任务的验收条件和禁止修改范围。
2. 记录影响范围：列出将修改的文件与不会修改的文件；保护文件见下节。
3. 只读侦察：用 `rg`／`Test-Path`／`Get-Content` 核实真实路径与现有行为，禁止凭记忆写路径。
4. 最小修改：只改任务范围内的文件；不为分类复制源码；不为单次任务重构无关模块。
5. 针对性验证：跑与该模块对应的测试或审计命令（示例见 [02 训练流水线](../02_training_pipeline/README.md)、[06 验证](../06_validation/README.md)）。
6. 记录证据：写明命令、输出路径、SHA256（权重/数据/协议需要时）。
7. 写 report 并更新 [plan/99_change_log](../../plan/99_change_log/CHANGELOG.md)。

## 保护文件（未经变更记录不得修改）

- 固定协议：[benchmarks/protocol_v1/](../../benchmarks/protocol_v1) 内的任务、地图与协议哈希。
- 验收规则与脚本：`scripts/final_acceptance_audit.py`、`scripts/audit_command_evidence.py`（仅允许向后兼容的增量改动，并在变更日志记录）。
- 审计权重：`checkpoints/formal_main_v1_seed{0,1,2}/best_policy.pth` 与各 `training_audit.json`。
- 既有飞行证据：`artifacts/ros2_flights/`、`artifacts/ros2_showcase/`、`artifacts/benchmark_summary/`。
- 固定上游源码：`external/audit_sources/`。

## 任务模板

每个实施任务先写一页记录（可放在 plan 对应编号目录或任务记录文件）：

```text
目标：
输入与依据：
设计（含影响文件清单）：
禁止修改：
执行命令：
验证命令与通过标准：
产物路径（含哈希）：
风险与回滚方式：
完成条件：
```

## 证据分级

- verified：有真实产物路径，命令可复跑。
- documented_gap：已记录的功能或实验缺口（例：参考[17] MPPI 300 槽未执行）。
- pending：判据尚未满足（例：终审矩阵 1500/1800）。

不要把回放、接口探针或离线检查写成“新飞行”；不要把训练审计写成闭环成功率。

## 相关入口

- [plan 管理层](../../plan/README.md)
- [report 交付层](../../report/README.md)
- [中央模块总图](../../report/00_index/01_module_map.md)

