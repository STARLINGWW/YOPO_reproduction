# GitHub 发布与干净 clone 验证记录（2026-10-13）

## 发布对象

- 发布根目录：`YOPO_reproduction_new`（本仓库，唯一发布源）。
- 发布提交：`243a1f8`；前序 `2037820`（release: freeze YOPO-only portable archive）与 `e718a77`（clean-clone 审计补齐）。
- 旧主线归档：远程 tag `archive/pre-yopo-only-20261013` → `7321edf`（原 v1 main，保留可追溯）。
- 主线替换：`git push --force-with-lease origin HEAD:main`（`+ 7321edf...243a1f8 forced update`）。
- Git LFS：上传 147 个对象、约 656 MB；干净 clone 侧过滤 148 个对象、约 635 MiB。
- 仓库可见性：Private（未认证 API 返回 404）。

## 干净 clone 验证（从 GitHub 重新拉取）

```powershell
git clone https://github.com/STARLINGWW/YOPO_reproduction.git YOPO_reproduction_clean
```

| 检查 | 命令 | 结果 |
|---|---|---|
| 旧盘符路径 | `git grep`（匹配旧根绝对路径前缀的四组模式；模式串此处不展开以避免自命中） | 0 命中 |
| 文档审计（全量递归） | `python scripts/audit_command_evidence.py --reports "report,plan,benchmarks,implement/…" --recursive --extra-files "README.md,MIGRATION_UBUNTU22.md,CONTRIBUTING.md,AGENTS.md" --fail-on-missing` | passed：75 份、缺失链接 0、缺失路径 0 |
| Python 语法 | `python -m compileall -q src scripts` | 通过 |
| 主机测试 | `python -m pytest tests -q`（跳过容器专属 `test_policy_runtime.py`，其依赖 torch） | 87 passed |
| 权重哈希 | 三个正式种子 `best_policy.pth` vs `training_audit.json`；DAgger vs `release_freeze_snapshot.json` | 全部一致：`af2ea0fa…` / `908e79f6…` / `eaf157f7…` / `82abb402…` |
| 字节保真 | `protocol.json` / `maps/*` 的 sha256 | `d2fd3052…` / `151655f1…` 与记录一致（`.gitattributes -text` 生效） |
| 终审 | `python scripts/final_acceptance_audit.py` | 6 verified、all_verified=true |
| 代码视图 | `implement/workspace/bootstrap_links.ps1` | 正常重建 junction 视图 |
| Docker GPU/ROS2 探针 | `docker compose --profile training run --rm train python3 scripts/ros2/verify_environment.py --gpu` | passed（RTX 5070 Ti、CUDA 12.8、torch 2.7.1+cu128、ROS2 Humble） |
| smoke 训练 | `train_scratch.py --dataset /workspace/datasets/smoke_v1 --run clean_clone_smoke --seed 0 --epochs 1 --batch-size 16 --stop-after-steps 20`，随后 `--resume` | 停止于第 20 步；恢复后 125 步完成，`status=complete` |

## 说明与例外

- `external/agile_autonomy/…/pointcloud-unity_muted.ply` 在 clone 时提示“应为指针但非指针”：本地与 clone 的文件逐字节一致（1,010,831 B），属历史入库风格差异，不影响内容。
- 准入勘误：`scripts/run_benchmark_matrix.py` 仅把解释器默认值改为 `YOPO_ISAAC_PYTHON`；`benchmarks/protocol_v1/runtime_validation.json` 的 `runtime_files_amendment` 透明记录旧/新哈希。固定协议字节与全部飞行证据未变；后续再次改动运行时文件需重新准入。
- 发布集不含原始重数据（`ros2_flights` 全量、完整 epoch 历史、完整数据集）；完整训练历史逐文件 SHA256 见 [yopo_full_checkpoint_manifest.json](yopo_full_checkpoint_manifest.json)，获取方式见 [README.md](README.md)。
- 独立 Ubuntu 22.04 主机验证为下一阶段；本记录是 Windows 主机上的 clean clone + Docker 容器验证。
