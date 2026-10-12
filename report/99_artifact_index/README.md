# 99 产物索引

更新：2026-10-12。哈希来源：各产物自带 manifest / 审计 JSON；规则：大文件按 [plan/06](../../plan/06_github_migration/README.md) 走 LFS 或 Release，不进入普通 Git。

## 模型与数据

| 产物 | 路径 | 哈希/校验来源 |
|---|---|---|
| 三种正式权重 | [checkpoints/formal_main_v1_seed{0,1,2}](../../checkpoints) | 各目录 `training_audit.json`（审计哈希与 `best_policy.pth` 一致） |
| DAgger 微调权重 | [checkpoints/dagger_main_v1_seed0](../../checkpoints/dagger_main_v1_seed0/result.json) | `result.json` / `run_manifest.json` |
| 正式数据 | [datasets/isaac_full_v1](../../datasets/isaac_full_v1/validation.json) | `dataset_sha256=ee0330a7…`（validation.json） |
| 聚合数据 | [datasets/isaac_dagger_v1](../../datasets/isaac_dagger_v1/aggregation_manifest.json) | `dataset_sha256=4d45354a…`（aggregation_manifest.json） |
| 迁移 smoke 运行 | [checkpoints/migration_smoke_v1](../../checkpoints/migration_smoke_v1/result.json) | 本机 Ubuntu 22.04 容器验证（不进入正式矩阵），见[环境基线](../06_migration/01_local_environment.md) |

## 评测与验收

| 产物 | 路径 | 哈希/校验来源 |
|---|---|---|
| 正式矩阵汇总 | [summary.json](../../artifacts/benchmark_summary/summary.json) | `protocol_sha256=d2fd3052…` |
| 终审 | [final_acceptance_audit.json](../../artifacts/environment/final_acceptance_audit.json) | 每项列出证据文件路径 |
| 命令/证据审计 | [command_evidence_audit.json](../../artifacts/environment/command_evidence_audit.json) | 链接与 JSON 解析审计（`status=passed`） |
| 进度简报 | [progress_brief.json](../../artifacts/environment/progress_brief.json) | 由既有 JSON 生成 |
| 文档刷新审计 | [refactor_20261012/document_audit.json](../../artifacts/refactor_20261012/document_audit.json) | 报告链接与证据路径一致性 |
| 冻结快照 | [refactor_20261012/freeze_snapshot.json](../../artifacts/refactor_20261012/freeze_snapshot.json) | 受保护文件哈希、权重哈希复核（与审计一致）与数据规模 |

## 展示与图表

| 产物 | 路径 | 哈希/校验来源 |
|---|---|---|
| 最终视频与总览图 | [showcase … _final](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final) | `render_manifest.json`（含权重 SHA256） |
| 原始飞行指标 | [ros2_flights/showcase…/metrics.json](../../artifacts/ros2_flights/showcase_formal_main_v1_seed0_20260926_014921/metrics.json) | 测量日志 |
| 论文图表 | [paper_figures](../../artifacts/paper_figures/manifest.json) | `manifest.json` |
| 官方/本地权重对照 | [weights_ab_demo](../../artifacts/weights_ab_demo) | 详见 [权重批量对照实验](../04_evaluation/02_权重批量对照实验.md) |
| 训练图核查 | [note_alignment_20261008](../../artifacts/note_alignment_20261008/training_graph_trace.json) | CPU 计算图探针脚本与结果 |

## 下载与获取规则

- 源码与文档：Git 仓库直接 clone。
- 数据与权重：按 [发布检查清单](../../plan/06_github_migration/01_release_checklist.md) 生成的 manifest 从 LFS/Release/对象存储获取，并逐项校验 SHA256。
- 完整原始数据（59 GB 级）与全量飞行输出不进入普通 Git。

