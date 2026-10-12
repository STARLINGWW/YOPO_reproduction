# Ubuntu 22.04 迁移说明

## 迁移边界

训练代码和Docker工作区可以迁移到Ubuntu 22.04。Windows原生Isaac Sim展示链、已生成的Windows路径和视频不需要在Ubuntu重建；需要重新运行闭环时，按支持的Isaac/ROS2方案单独验证。

## 本机容器验证（2026-10-12）

本机已在 Docker Desktop（Linux 引擎）的 Ubuntu 22.04 容器完成 GPU/ROS2 环境探针与 smoke 训练停止/恢复（`checkpoints/migration_smoke_v1`，status=complete）。环境画像、启动故障修复与全部证据见 [report/06_migration/01_local_environment.md](report/06_migration/01_local_environment.md)。以下步骤用于独立 Ubuntu 22.04 主机。

## 快速迁移

```bash
git clone <YOUR_PRIVATE_GITHUB_URL> YOPO_reproduction
cd YOPO_reproduction
git lfs install
git lfs pull
sudo apt-get install -y docker.io docker-compose-plugin
# 另行安装匹配宿主驱动和NVIDIA Container Toolkit
docker compose --profile training build train
docker compose --profile training run --rm train python3 scripts/ros2/verify_environment.py --gpu
```

随后校验数据和checkpoint manifest，再做smoke训练、停止和恢复。正式数据不应通过Git普通对象传输；从Git LFS、Release或对象存储下载后写入 datasets/，并比较SHA256。

## Smoke恢复

```bash
docker compose --profile training run --rm train python3 scripts/train_scratch.py --dataset /workspace/datasets/smoke_v1 --run migration_smoke_v1 --seed 0 --epochs 1 --batch-size 16 --stop-after-steps 20
docker compose --profile training run --rm train python3 scripts/train_scratch.py --dataset /workspace/datasets/smoke_v1 --run migration_smoke_v1 --seed 0 --epochs 1 --batch-size 16 --resume --stop-after-steps 40
docker compose --profile training run --rm train python3 scripts/train_scratch.py --dataset /workspace/datasets/smoke_v1 --run migration_smoke_v1 --seed 0 --epochs 1 --batch-size 16 --resume
```

## 正式训练

```bash
docker compose --profile training run --rm train python3 scripts/validate_dataset.py --dataset /workspace/datasets/isaac_full_v1
docker compose --profile training run --rm train python3 scripts/stage_training_data.py --name isaac_full_v1
docker compose --profile training run --rm train python3 scripts/train_scratch.py --dataset /data/isaac_full_v1 --run formal_migrated_seed0 --seed 0 --epochs 50 --batch-size 16
docker compose --profile training run --rm train python3 scripts/audit_training_run.py --run formal_migrated_seed0 --seed 0
```

迁移后的新run不应覆盖现有formal_main_v1。完成后在 report/06_migration 记录镜像、GPU、数据SHA256、训练代码SHA256、权重SHA256和验证结果。

