# 06 验证与验收

> 论文对应：III 的统计口径与证据链（工程支撑）｜ 一句话定位：把"训练/飞行/汇总/验收"的每一层事实变成可复跑、可审计的检查。

## 职责范围

五层验证：① 单元与数值对照（算法、几何、控制器 parity）；② 数据与权重契约（数据集校验、训练审计、恢复一致性）；③ 飞行逐帧验证（证据契约、指标评估）；④ 正式矩阵聚合（覆盖率感知统计）；⑤ 最终验收（机械验收审计 + 文档/证据一致性审计）。原则：smoke、CPU 预检、合成测试与开发飞行不能冒充正式矩阵证据。

## 代码地图

| 路径 | 角色 | 说明 |
|---|---|---|
| [tests/](../../tests) | 测试套件 | 21 个测试文件：算法（quintic/main_cost/maps/forest/policy_runtime）、运行时（trajectory_buffer、runtime_admission*）、矩阵（benchmark_tasks/aggregation/matrix_driver）、契约（flight_evidence_contract、final_acceptance_audit、runtime_admission_contract） |
| [scripts/validate_dataset.py](../../scripts/validate_dataset.py) | 数据契约 | 全量深度帧、位姿、地图隔离与哈希 |
| [scripts/audit_training_run.py](../../scripts/audit_training_run.py)、[scripts/training_audit_utils.py](../../scripts/training_audit_utils.py) | 训练审计 | 逐轮审计、最佳权重哈希核对 |
| [scripts/check_training_integrity.py](../../scripts/check_training_integrity.py) | 指标流完整性 | 步序连续、epoch 边界、损失分布与异常（只读） |
| [scripts/check_resume_equivalence.py](../../scripts/check_resume_equivalence.py)、[scripts/audit_resume_readiness.py](../../scripts/audit_resume_readiness.py) | 恢复一致性 | 停止—恢复等价性与可恢复性检查 |
| [scripts/check_model_selection.py](../../scripts/check_model_selection.py) | 模型选择 | best_policy 选择规则核对 |
| [scripts/validate_ros2_flight.py](../../scripts/validate_ros2_flight.py)、[scripts/evaluate_ros2_flight.py](../../scripts/evaluate_ros2_flight.py) | 飞行验证 | 逐帧证据契约与指标汇总 |
| [scripts/run_benchmark_matrix.py](../../scripts/run_benchmark_matrix.py)、[scripts/aggregate_benchmarks.py](../../scripts/aggregate_benchmarks.py)、[scripts/create_benchmark_protocol.py](../../scripts/create_benchmark_protocol.py) | 矩阵 | 协议生成、执行与覆盖率感知聚合 |
| [scripts/final_acceptance_audit.py](../../scripts/final_acceptance_audit.py) | 最终验收 | 生成 [final_acceptance_audit.json](../../artifacts/environment/final_acceptance_audit.json)（7 项机械审计） |
| [scripts/audit_command_evidence.py](../../scripts/audit_command_evidence.py) | 文档/证据审计 | 报告链接、代码块路径与 JSON 可解析性；支持 `--reports` 多目录、`--recursive`、`--extra-files` |
| [scripts/make_status_overview.py](../../scripts/make_status_overview.py) | 状态总览 | 由权威 JSON 生成复现状态总览 |
| [benchmarks/protocol_v1/protocol.json](../../benchmarks/protocol_v1/protocol.json) | 固定协议 | 任务、地图与协议哈希（`d2fd3052…`） |

## 输入与输出

- 输入：训练 run、数据集、飞行 run、协议文件。
- 输出：`checkpoints/<run>/training_audit.json`、`artifacts/environment/*.json`、`artifacts/benchmark_summary/summary.json`、`artifacts/refactor_20261012/document_audit*.json`。

## 常用命令（项目根目录执行）

```powershell
Set-Location 'D:\_AAA_CODE_ALL\Tech_reproduction\YOPO_reproduction'

python -m pytest -q tests --basetemp=.pytest_basetemp/local
python scripts/final_acceptance_audit.py
python scripts/check_training_integrity.py --runs formal_main_v1_seed0 formal_main_v1_seed1 formal_main_v1_seed2 --output artifacts/environment/seed_training_integrity_v2.json
python scripts/audit_command_evidence.py --reports "reports,report,implement,plan" --recursive --extra-files "README.md,MIGRATION_UBUNTU22.md,CONTRIBUTING.md,AGENTS.md" --output artifacts/refactor_20261012/document_audit_all.json --fail-on-missing
```

## 证据与产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 终审（7 项） | [final_acceptance_audit.json](../../artifacts/environment/final_acceptance_audit.json) | 5 verified ＋ 1 documented_gap ＋ 1 pending；`all_verified=false` |
| 命令/证据审计 | [command_evidence_audit.json](../../artifacts/environment/command_evidence_audit.json) | 默认范围（reports/ 与 benchmarks/）`status=passed` |
| 文档审计（扩展） | [document_audit_all.json](../../artifacts/refactor_20261012/document_audit_all.json) | 59 份文档、0 缺失链接/路径、0 不可解析 JSON |
| 矩阵汇总 | [summary.json](../../artifacts/benchmark_summary/summary.json) | 1500/1800；失败保留在分母；Wilson 区间仅覆盖已完成架次 |
| 训练完整性 | [seed_training_integrity_v2.json](../../artifacts/environment/seed_training_integrity_v2.json) | 三种子指标流检查：passed、无异常 |

## 验证方法

- 快速检查：`python -m compileall -q src scripts`（Python 语法）；`Parser::ParseFile` 解析 `scripts/*.ps1`（PowerShell 语法，9 文件通过）。
- 核心测试：`pytest -q tests/test_quintic.py tests/test_main_cost.py tests/test_maps.py tests/test_forest.py tests/test_trajectory_buffer.py --basetemp=.pytest_basetemp/<name>`。
- 需要 torch 的用例（test_policy_runtime、dagger 相关）在已配置环境运行；默认 pytest 临时目录可能无写权限，使用 `--basetemp`。

## 已知限制与论文差异

- 验收状态是机械审计：verified 表示该项有证据，不表示所有飞行成功。
- `plan.json` 中的 `plan_pending=310` 与运行配置里的旧 pending 是历史快照；实际以准入、训练审计、DAgger 结果与 summary 为准。
- MPPI 300 槽与矩阵 1800 的缺口是当前唯一的 pending/documented_gap 来源。

## 相关入口

- [模块总图](../../report/00_index/01_module_map.md) ｜ [01 当前状态](../../report/01_status/README.md) ｜ [04 评测交付](../../report/04_evaluation/README.md)

