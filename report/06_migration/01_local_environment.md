# 本机复现环境与 Docker 基线（Ubuntu 22.04 容器验证）

更新：2026-10-12 ｜ 作用：回答“本地 YOPO 复现用的是哪个 Docker、什么环境”，并记录 2026-10-12 在本机 Docker 完成的迁移验证结果

## 1. 环境结论

- 本地复现使用 **Docker Desktop for Windows 的 Linux 容器**（context `desktop-linux`）；不是直接使用 WSL 发行版（`EGO-Ubuntu-22.04`、`FASTLIVO-Ubuntu-22.04` 属于其他项目）。场景与物理使用 Windows 原生 Isaac Sim。
- Docker Desktop 4.81.0 (232925)，引擎 **29.6.1**（containerd 2.2.5 / runc 1.3.6 / WSL2 内核 6.18.33.2），分配 28 CPU / 16.6 GB，存储驱动 overlayfs。
- 训练与 ROS2 全部在 Ubuntu 22.04 (jammy) 容器内：ROS2 Humble、Python 3.10.12、PyTorch 2.7.1+cu128、CUDA 12.8、NVIDIA GeForce RTX 5070 Ti（compute capability 12.0）。
- compose 项目名 `yopo-ros2-reproduction`；项目根目录挂载到 `/workspace`，数据卷 `yopo-data` 挂载到 `/data`。

## 2. 主要镜像（2026-10-12 实测）

| 镜像 | Digest 前缀 | 大小 | 用途 |
|---|---|---|---|
| `yopo-repro:train-cu128-jammy` | `a1a0da143927` | 25.9 GB | 训练容器（GPU，`--profile training`） |
| `yopo-repro:ros-humble-jammy` | `4520b9bba3cb` | 1.61 GB | ROS2 基础镜像 |
| `yopo-repro:baselines-cpp-humble-jammy` | `0e3d3a7498c5` | 4.27 GB | 基线 C++ 构建 |
| `yopo-repro:expert-jammy` | `5e4c568e3663` | 25.9 GB | 专家求解器 |
| `yopo-repro:agile-tf215-humble-jammy` | `124d9f5a4717` | 3.56 GB | Agile 运行时 |
| `yopo-repro:agile-tf24-reference-jammy` | `1f33901901e1` | 3.19 GB | Agile TF2.4 参考 |
| `nvidia/cuda:12.8.1-devel-ubuntu22.04` | `a99a1860ba8e` | 14.5 GB | train 镜像基础层（见 [base_image_lock.json](../../artifacts/environment/base_image_lock.json)） |

完整清单：[docker_images.jsonl](../../artifacts/refactor_20261012/docker_images.jsonl)；版本快照：[docker_version.json](../../artifacts/refactor_20261012/docker_version.json)、[docker_info.json](../../artifacts/refactor_20261012/docker_info.json)。

## 3. 启动方式

打开 Docker Desktop，等待引擎可用后，所有训练/ROS2 命令从项目根目录通过 compose 进入容器（不要直接使用 WSL 发行版）：

```powershell
cd <项目根目录>   # 历史记录：当时为本机 D:\ 路径，现已泛化
docker version --format '{{.Server.Version}}'   # 期望返回 29.6.1
docker context show                             # desktop-linux
docker compose --profile training run --rm train python3 scripts/ros2/verify_environment.py --gpu
```

## 4. 启动故障与修复（2026-10-12，重要）

现象：Docker Desktop 弹窗 “An unexpected error occurred”，引擎始终 stopped；日志（`%LOCALAPPDATA%\Docker\log\host\com.docker.backend.exe.log`）报：

```text
starting services: initializing Inference manager: listening on unix://<本机用户>/AppData/Local/Docker/run/dockerInference:
remove ...: The file cannot be accessed by the system.
```

根因：Docker Desktop 4.81 的 Inference / Secrets 服务会在 `%LOCALAPPDATA%\Docker\run\` 与 `%LOCALAPPDATA%\docker-secrets-engine\` 创建 Unix 套接字；9 月 24 日遗留的 WSL 套接字在 Windows 侧无法删除（“系统无法访问此文件”），导致每次启动都在“删除旧套接字”一步失败，并留下新的套接字继续阻塞下一次启动。

修复步骤（本次实际执行，可复用）：

1. 退出 Docker Desktop（所有 `Docker Desktop` / `com.docker.backend` 进程）。
2. `wsl --shutdown`。
3. 从 WSL 侧删除残留套接字（Windows 侧删不掉；把 `<用户名>` 替换为本机用户名）：

```powershell
wsl -d FASTLIVO-Ubuntu-22.04 -e bash -c "rm -f '/mnt/c/Users/<用户名>/AppData/Local/Docker/run/dockerInference' '/mnt/c/Users/<用户名>/AppData/Local/Docker/run/dockerEthernetVfkit' '/mnt/c/Users/<用户名>/AppData/Local/Docker/run/userAnalyticsOtlpHttp.sock'"
```

4. `docker-secrets-engine` 目录如整体损坏，直接改名保留即可（本次改名为 `docker-secrets-engine.bad-20261012`，不删除数据）。
5. 重新启动 Docker Desktop，确认 `docker version` 返回 29.6.1。

## 5. 迁移验证记录（2026-10-12，本机 Ubuntu 22.04 容器）

| 步骤 | 命令摘要（项目根目录） | 结果 | 证据 |
|---|---|---|---|
| GPU/ROS2 环境探针 | `docker compose --profile training run --rm train python3 scripts/ros2/verify_environment.py --gpu` | passed：ROS2 pub/sub 通、CUDA/CuDNN 反向通、nvcc 12.8 | [train_env_gpu_probe.log](../../artifacts/refactor_20261012/train_env_gpu_probe.log) |
| smoke 训练（停止） | `train_scratch.py --dataset /workspace/datasets/smoke_v1 --run migration_smoke_v1 --seed 0 --epochs 1 --batch-size 16 --stop-after-steps 20` | 第 20 步写入检查点 | [migration_smoke_stop20.log](../../artifacts/refactor_20261012/migration_smoke_stop20.log) |
| smoke 恢复 1 | 同命令 `--resume --stop-after-steps 40` | 30→40 步，游标与 RNG 正常恢复 | [migration_smoke_resume40.log](../../artifacts/refactor_20261012/migration_smoke_resume40.log) |
| smoke 恢复 2（完成） | 同命令 `--resume` | 1 epoch / 125 步，`status=complete` | [migration_smoke_resume_final.log](../../artifacts/refactor_20261012/migration_smoke_resume_final.log)、[result.json](../../checkpoints/migration_smoke_v1/result.json) |

补充：smoke run 使用确定性随机初始化（`initial_model_sha256=8b00d0cc…`，与正式种子同源），运行目录 `checkpoints/migration_smoke_v1/`，不进入任何正式矩阵或验收统计。

## 6. 与“独立主机迁移”的区别

本验证证明代码在 Ubuntu 22.04 容器、`/workspace` 挂载与 GPU 直通下可以训练、停止、恢复，且不依赖 Windows 绝对路径。它**不代表**另一台独立 Ubuntu 22.04 主机的驱动、NVIDIA Container Toolkit 与数据归档已经迁移；独立主机的步骤见 [MIGRATION_UBUNTU22.md](../../MIGRATION_UBUNTU22.md)。

## 7. 相关入口

- [MIGRATION_UBUNTU22.md](../../MIGRATION_UBUNTU22.md)（独立主机迁移说明）
- [report/06_migration/README.md](README.md)（迁移状态总表）
- [plan/06_github_migration/README.md](../../plan/06_github_migration/README.md)（发布与大文件规则）
- [发布检查清单](../../plan/06_github_migration/01_release_checklist.md)
