# GitHub发布检查清单

- [x] 结构文件已提交：plan、implement、report、源代码和配置（3 个结构基线提交）。
- [x] .gitignore排除build、install、log、缓存、临时文件和敏感信息。
- [x] .gitattributes声明大文件LFS规则。
- [x] README和MIGRATION_UBUNTU22说明源代码、数据和模型获取。
- [x] 运行时协议、验收规则和审计权重没有被修改（本次仅新增文档与向后兼容审计开关）。
- [x] 小型smoke数据可用于第一次迁移验证：2026-10-12 本机 Ubuntu 22.04 容器 smoke 停止/恢复通过。
- [x] YOPO-only 活动范围冻结：`benchmarks/protocol_v1/active_scope_yopo_only.json`；MPPI 移出并归档（见 DEC-20261013-01），summary/终审按 1,500 口径重生成。
- [x] 证据字节锚定：`.gitattributes` 对 protocol/maps/runtime_validation 等加 `-text`，保证 clone 后 sha256 与记录一致。
- [x] 历史归档：`benchmarks/archive/protocol_v1_1800/`、`report/90_archive/mppi/`、`plan/90_decisions/archive_mppi/`。
- [ ] 旧 main 保存为 tag `archive/pre-yopo-only-20261013` 并推送。
- [ ] v2 内容替换 `main`（force-with-lease）并推送 Git LFS 权重与代表媒体。
- [ ] clean clone 验证：路径 grep、标准文档审计、Python/PowerShell 语法、LFS 权重哈希、smoke 停止/恢复。
- [ ] 完整数据与 checkpoint 外部归档及 SHA256 清单（发布时补录到 report/06_migration）。
- [x] 本地检查：`python -m compileall -q src scripts`、pytest 核心用例、标准文档审计（命令与结果见 [report/06_migration/02_new_root_verification.md](../../report/06_migration/02_new_root_verification.md) §4）。
- [ ] 发布前复核：GitHub 仓库为 Private；提交中不含令牌、私密绝对路径与临时日志（活动文档机器路径已清除）。
- [x] Ubuntu 22.04（本机 Docker Desktop Linux 容器）完成 smoke 训练和恢复：见 report/06_migration/01_local_environment.md。
- [ ] 独立 Ubuntu 22.04 主机完成 smoke 训练和恢复（驱动、NVIDIA Container Toolkit、数据归档）。

