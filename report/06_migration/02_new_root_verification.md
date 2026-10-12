# 新根重构验证记录（YOPO_reproduction_new）

更新：2026-10-12 ｜ 范围：结构、链接、运行三方面复核；全部在本机执行

## 1. 结构校验

- 运行层复制：3300+ 文件；代码保持既有相对位置（`src/scripts/configs/docker/ros2_ws/tests/external/benchmarks/vendor/assets`）。
- 报告重排：`reports/` 20 份详细报告与 `docs/proposals/` 4 件提案迁入 `report/NN_*`、`plan/90_decisions/references/`，并加序号前缀。
- 媒体落盘：`report/05_visualization/media/`（视频、图片、Table I/II、渲染清单，共 9.9 MB）；`report/00_index/03_project_map.html`（交互式全景）。
- 参考随迁：`plan/01_paper_protocol/references/YOPO_原始笔记对话_conversation.txt`（SHA256 `b5d70813…` 与报告记录一致）、`plan/02_environment_ros2/references/isaac61_env.md`。
- 重数据引用：`datasets/isaac_full_v1`、`datasets/isaac_dagger_v1`、全部既有 `checkpoints/*`、`artifacts/` 7 个重目录以 NTFS junction 本地引用（不复制、不入 Git；Ubuntu 按发布清单恢复）。
- 链接迁移：770 处跨目录引用 + 16 处绝对路径重写为相对路径；`reports/` 目录不再存在（旧根保留为历史归档）。

## 2. 编译与静态检查

| 检查 | 命令（新根根目录） | 结果 |
|---|---|---|
| Python 编译 | `python -m compileall -q src scripts` | exit=0，0 错误 |
| PowerShell 解析 | 全部 `scripts/**.ps1`（AST 解析） | 0 问题 |
| 核心测试 | `python -m pytest -q tests/test_quintic.py tests/test_main_cost.py tests/test_maps.py tests/test_forest.py` | **13 passed**（1.56 s） |

## 3. 运行验证（Docker Desktop Linux 引擎 / Ubuntu 22.04 容器）

| 步骤 | 命令摘要 | 结果 | 证据 |
|---|---|---|---|
| GPU/ROS2 探针 | `docker compose --profile training run --rm train python3 scripts/ros2/verify_environment.py --gpu` | passed（ROS2 pub/sub、CUDA/CuDNN 反向、nvcc 12.8） | [newroot_env_gpu_probe.log](../../artifacts/refactor_20261012/newroot_env_gpu_probe.log) |
| smoke 停止 | `train_scratch.py --dataset /workspace/datasets/smoke_v1 --run migration_smoke_newroot --seed 0 --epochs 1 --batch-size 16 --stop-after-steps 20` | step 20 写入检查点 | [newroot_smoke_stop20.log](../../artifacts/refactor_20261012/newroot_smoke_stop20.log) |
| smoke 恢复 1 | 同命令 `--resume --stop-after-steps 40` | 30 → 40 步 | [newroot_smoke_resume40.log](../../artifacts/refactor_20261012/newroot_smoke_resume40.log) |
| smoke 恢复 2（完成） | 同命令 `--resume` | 1 epoch / 125 步，`status=complete` | [newroot_smoke_resume_final.log](../../artifacts/refactor_20261012/newroot_smoke_resume_final.log)、[result.json](../../checkpoints/migration_smoke_newroot/result.json) |

确定性复核：新根 smoke 的逐步损失、验证损失（`0.04632359673992635`）与 `final_model_sha256`（`2254297c…`）和旧根 smoke 运行**逐位一致**；`initial_model_sha256=8b00d0cc…` 与三种子正式训练同源。

## 4. 文档/证据一致性审计（新根标准命令）

```powershell
python scripts/audit_command_evidence.py --reports "report,plan,benchmarks,implement/00_workspace_map,implement/01_core_algorithm,implement/02_training_pipeline,implement/03_ros2_runtime,implement/04_isaac_sim,implement/05_baselines,implement/06_validation,implement/07_visualization,implement/99_workspace_rules" --recursive --extra-files "README.md,MIGRATION_UBUNTU22.md,CONTRIBUTING.md,AGENTS.md" --fail-on-missing
```

结果：**68 份文档，0 缺失链接、0 缺失路径、0 不可解析 JSON**（输出 [document_audit_newroot.json](../../artifacts/refactor_20261012/document_audit_newroot.json)）。命令显式列出 implement 模块目录，避免进入 `implement/workspace` 的本地链接视图（视图不是仓库内容）。

## 5. 冻结快照

[freeze_snapshot.json](../../artifacts/refactor_20261012/freeze_snapshot.json)：受保护文件哈希、三种子 `best_policy.pth` 实算哈希（与 `training_audit` 全部一致）、数据集与 checkpoint 规模（`isaac_full_v1` 8.90 GB、三种子 checkpoint 各 8.65 GB 等）。快照中的 `git_head` 在初始提交后重跑时记录为新根仓库提交。

## 6. Git 基线与边界

- 新根已独立 `git init` 并完成初始提交（见提交记录）；旧仓库 `origin` 保持不变，新文件夹已加入旧仓库 `.gitignore`。
- 本次 **未删除任何数据、权重或证据**；旧根 `YOPO_reproduction/` 保留为冻结归档。
- 仍待执行：独立 Ubuntu 22.04 主机迁移、LFS/Release 大文件上传；实验侧缺口（MPPI 300 槽、DAgger 收益验证、矩阵 1500/1800）与结构重构无关，保持如实标注。
