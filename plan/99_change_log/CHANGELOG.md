# 计划与管理变更日志

## 2026-10-12

- 建立 plan / implement / report 三个项目入口。
- 保留根目录运行路径，避免移动代码破坏 ROOT=Path(...).parents[1] 和容器 /workspace。
- 增加GitHub、LFS和Ubuntu 22.04迁移计划。
- 把当前、历史、算法、训练、评测和展示报告分层索引。
- 新增 report/00_index/01_module_map.md：复现模块总图（5 阶段 × 12 模块）与论文章节反查、差异索引。
- 新增 report/02_method/01_paper_to_code.md：论文 II-A/II-B/III 与本地代码的逐项对照。
- 扩写 implement 各模块 README 为代码地图（入口、输入输出、证据、限制）与 00/99 工作区规范。
- 填充 report 分类页（01 状态、03 训练、04 评测、05 可视化、06 迁移、90 历史、99 产物索引）。
- `scripts/audit_command_evidence.py` 增加向后兼容的 `--recursive` 与 `--extra-files`（`--reports` 支持多目录）；默认行为不变。
- 文档审计扩展到 plan/implement/report/根文档：59 份、0 缺失链接、0 缺失路径、0 不可解析 JSON → artifacts/refactor_20261012/document_audit_all.json。
- 运行 scripts/check_training_integrity.py 生成 artifacts/environment/seed_training_integrity_v2.json（三种子指标流检查通过，无异常）。
- 清理 12:18 误建的空目录 YOPO_reproduction/YOPO_reproduction（0 文件）。
- 未修改固定协议、验收脚本、审计权重和正式实验结果。
