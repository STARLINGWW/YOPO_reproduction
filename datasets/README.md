# datasets 发布策略（YOPO-only）

- 普通 Git 只保留清单类 JSON：`isaac_full_v1/{dataset.json,validation.json}`、`isaac_dagger_v1/{dataset.json,aggregation_manifest.json}`；深度/位姿等大文件不进入普通 Git。
- `smoke_v1/` 是迁移验证用子集：每个 shard 仅保留 `manifest.json`、`map.json`、`depth_m.npy`、`poses.npz`、`sdf.npy`（二进制走 Git LFS），用于在干净 clone 中跑通 smoke 训练的停止/恢复；逐文件 SHA256 见 `smoke_v1/README.md`。
- 完整数据（`isaac_full_v1` 约 9.5GB、`isaac_dagger_v1` 约 1.4GB）与全部深度 `.npy`、飞行 `.npz` 由外部归档提供，见 `report/06_migration` 与仓库根 `MIGRATION_UBUNTU22.md`。
