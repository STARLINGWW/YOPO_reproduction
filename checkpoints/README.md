# checkpoints 精选说明（YOPO-only 发布）

2026-10-13 范围冻结后，本目录只保留发布所需的最小集合：

- `formal_main_v1_seed{0,1,2}/`：每个正式种子保留 `best_policy.pth`（Git LFS）、`run_manifest.json`、`result.json`、`training_audit.json`、`progress.json`。
- `dagger_main_v1_seed0/`：DAgger 聚合微调，保留 `best_policy.pth`（Git LFS）、`run_manifest.json`、`result.json`。
- `migration_smoke_newroot/`：2026-10-12 迁移 smoke 的完成记录（`result.json`、`run_manifest.json`、`progress.json`）。

完整训练历史（`epoch_*.pt`、`policy_epoch_*.pth`、`latest.pt`、TensorBoard、逐步指标流等）不进入本仓库，随外部归档发布；逐文件 SHA256 的完整清单见 `report/06_migration`（发布整理时另附 `yopo_full_checkpoint_manifest.json`）。三个正式种子的权重哈希与各自 `training_audit.json` 中 `selection.best_policy_file_sha256` 逐一一致，可由 `scripts/final_acceptance_audit.py` 复核。
