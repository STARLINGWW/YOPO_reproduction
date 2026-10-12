# 06 GitHub 与 Ubuntu 迁移

更新：2026-10-12 ｜ 论文对应：工程支撑（交付与迁移，无直接论文对应）

## 当前状态

| 事项 | 状态 | 证据 |
|---|---|---|
| Git 初始化与结构基线 | 已完成（3 个提交，`main`） | `git log`：plan/implement/report 结构、迁移文档、可复现来源 |
| GitHub 远端 | 已配置并同步源码与文档 | `origin` = github.com/STARLINGWW/YOPO_reproduction；结构基线已推送 |
| 大文件（数据/权重/视频） | 未上传；按 LFS/Release 规则另行发布 | [发布检查清单](../../plan/06_github_migration/01_release_checklist.md) |
| 本机 Ubuntu 22.04 容器验证 | 已完成（2026-10-12：GPU/ROS2 探针 + smoke 停止/恢复） | [01_local_environment.md](01_local_environment.md) |
| 独立 Ubuntu 主机迁移 | 待执行（驱动、NVIDIA Container Toolkit、数据归档） | [MIGRATION_UBUNTU22.md](../../MIGRATION_UBUNTU22.md) |

## 迁移设计

- 源码仓库提交：源码、配置、Docker、ROS2 源码、测试、固定上游、plan/implement/report、README/AGENTS/LICENSE 与小型演示包。
- 默认排除：`ros2_ws/build|install|log`、pytest 缓存、全量飞行输出、深度 npy、逐轮检查点、私密凭据。
- 大文件：`pth/pt/npy/npz/mp4/pdf/usda` 走 Git LFS 或 Release/对象存储；完整 59 GB 级数据不放入普通 Git。
- 运行兼容：训练代码保留项目根目录相对路径；容器统一挂载为 `/workspace`。

## 接续步骤（Ubuntu 22.04）

1. clone 主仓库，`git lfs pull`。
2. 安装匹配驱动与 NVIDIA Container Toolkit；`docker compose --profile training build train`。
3. `python3 scripts/ros2/verify_environment.py --gpu` 检查 GPU/ROS2 环境。
4. 校验数据与 checkpoint manifest（SHA256），再跑 smoke 训练、停止、恢复。
5. 需要复现闭环时单独安装 Isaac Sim 并验证。

迁移后的新 run 不得覆盖 `formal_main_v1`；完成后按模板在 [MIGRATION_UBUNTU22.md](../../MIGRATION_UBUNTU22.md) 记录镜像、GPU、数据/代码/权重 SHA256 与结果。

## 相关文档

- [本机环境与 Docker 基线](01_local_environment.md)（含启动故障修复记录）
- [plan/06 GitHub 与 Ubuntu 迁移计划](../../plan/06_github_migration/README.md)
- [发布检查清单](../../plan/06_github_migration/01_release_checklist.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)、[.gitignore](../../.gitignore)、[.gitattributes](../../.gitattributes)

