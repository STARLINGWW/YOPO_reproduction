# GitHub发布检查清单

- [x] 结构文件已提交：plan、implement、report、源代码和配置（3 个结构基线提交）。
- [x] .gitignore排除build、install、log、缓存、临时文件和敏感信息。
- [x] .gitattributes声明大文件LFS规则。
- [x] README和MIGRATION_UBUNTU22说明源代码、数据和模型获取。
- [x] 运行时协议、验收规则和审计权重未被放宽：唯一改动是 `run_benchmark_matrix.py` 解释器默认值（准入勘误，`runtime_files_amendment` 记录新旧哈希）；固定协议字节与全部飞行证据未变。
- [x] 小型smoke数据随库发布（LFS 子集，SHA256 见 datasets/smoke_v1/README.md）：2026-10-12 本机容器与本记录 §clone 验证均通过停止/恢复。
- [x] YOPO-only 活动范围冻结：`benchmarks/protocol_v1/active_scope_yopo_only.json`；MPPI 移出并归档（见 DEC-20261013-01），summary/终审按 1,500 口径重生成。
- [x] 证据字节锚定：`.gitattributes` 对 protocol/maps/runtime_validation 等加 `-text`，保证 clone 后 sha256 与记录一致。
- [x] 历史归档：`benchmarks/archive/protocol_v1_1800/`、`report/90_archive/mppi/`、`plan/90_decisions/archive_mppi/`。
- [x] 旧 main 保存为 tag `archive/pre-yopo-only-20261013` 并推送（→ `7321edf`）。
- [x] v2 内容替换 `main`（force-with-lease，`7321edf → 243a1f8`），LFS 147 对象/约 656 MB 已推送。
- [x] clean clone 验证：路径 grep 0、全量文档审计 75/0/0、compileall、pytest 87、LFS 权重哈希全部一致、Docker GPU 探针与 smoke 停止/恢复通过（见 [03_github_release_verification.md](../../report/06_migration/03_github_release_verification.md)）。
- [x] 完整数据与 checkpoint 外部归档 SHA256 清单：`report/06_migration/yopo_full_checkpoint_manifest.json`（完整训练历史）+ `artifacts/refactor_20261012/release_freeze_snapshot.json`（发布集受保护哈希）。
- [x] 本地检查：`python -m compileall -q src scripts`、pytest 核心用例、标准文档审计（命令与结果见 [report/06_migration/02_new_root_verification.md](../../report/06_migration/02_new_root_verification.md) §4）。
- [x] 发布前复核：GitHub 仓库为 Private（未认证 API 404）；跟踪内容 grep 无机器路径/无令牌/无临时日志。
- [x] Ubuntu 22.04（本机 Docker Desktop Linux 容器）完成 smoke 训练和恢复：见 report/06_migration/01_local_environment.md。
- [ ] 独立 Ubuntu 22.04 主机完成 smoke 训练和恢复（下一阶段：驱动、NVIDIA Container Toolkit、数据归档）。

