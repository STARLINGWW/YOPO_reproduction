# GitHub发布检查清单

- [x] 结构文件已提交：plan、implement、report、源代码和配置（3 个结构基线提交）。
- [x] .gitignore排除build、install、log、缓存、临时文件和敏感信息。
- [x] .gitattributes声明大文件LFS规则。
- [x] README和MIGRATION_UBUNTU22说明源代码、数据和模型获取。
- [x] 运行时协议、验收规则和审计权重没有被修改（本次仅新增文档与向后兼容审计开关）。
- [x] 小型smoke数据可用于第一次迁移验证：2026-10-12 本机 Ubuntu 22.04 容器 smoke 停止/恢复通过。
- [ ] 完整数据和checkpoint归档有SHA256。
- [x] 本地检查已可运行Python语法、核心测试和文档链接检查：`python -m compileall -q src scripts`、pytest 核心用例、`python scripts/audit_command_evidence.py --reports "reports,report,implement,plan" --recursive --extra-files "README.md,MIGRATION_UBUNTU22.md,CONTRIBUTING.md,AGENTS.md" --output artifacts/refactor_20261012/document_audit_all.json --fail-on-missing`（59 份文档全通过）。
- [ ] GitHub仓库设置为Private，未提交账号令牌、绝对私有路径和临时日志。
- [x] Ubuntu 22.04（本机 Docker Desktop Linux 容器）完成 smoke 训练和恢复：见 report/06_migration/01_local_environment.md。
- [ ] 独立 Ubuntu 22.04 主机完成 smoke 训练和恢复（驱动、NVIDIA Container Toolkit、数据归档）。

