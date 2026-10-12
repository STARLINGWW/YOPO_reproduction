# 计划与管理变更日志

## 2026-10-12 新根重构（v2）

- 建立 `YOPO_reproduction_new/` 新根：plan / implement / report 三大区 + 运行层（代码保持既有相对位置）。
- report 改为编号文件夹：22 份详细报告迁入 01_status / 02_method / 03_training / 04_evaluation / 05_visualization / 90_archive / 99_artifact_index / 00_index，并加序号前缀。
- 报告媒体实体落盘：`report/05_visualization/media/`（视频、图片、Table I/II、渲染清单）、`report/00_index/03_project_map.html`（交互式项目全景 + 截图）。
- `docs/proposals/` → `plan/90_decisions/references/`；项目外参考 conversation.txt、isaac61_env.md 随迁为 plan references（含 SHA256 校验）。
- implement 增加 `workspace/` 代码工作区视图与 `bootstrap_links.{ps1,sh}`；依据见 DEC-20261012-01（Docker 挂载不穿越 junction）。
- 链接迁移：770 处引用 + 16 处绝对路径重写为相对路径；全库文档审计 0 缺失（见 report/06_migration/02_new_root_verification.md）。
- 修改两个脚本默认值：make_status_overview.py 默认输出报告页、audit_command_evidence.py 默认扫描 report/plan。
- 未删除任何数据、权重或实验证据；旧根保留为冻结归档。

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
- 独立复跑复核：`python -m compileall -q src scripts` 通过；59 份文档扩展审计 0 缺失链接、0 缺失路径；终审 JSON 与提交内容一一对应。
- 未修改固定协议、审计权重和正式实验结果；验收脚本仅做上述向后兼容扩展。
- 新增 report/04_evaluation/01_official_vs_selftrained.md：官方权重 vs 自训练权重总对照（离线 10k + 闭环 36 架次 + 两阶段展示）。
- 新增 report/06_migration/01_local_environment.md：本机 Docker/环境基线、启动故障修复与 2026-10-12 容器验证记录。
- 验证通过：GPU/ROS2 探针、smoke 训练停止/恢复（`checkpoints/migration_smoke_v1`，status=complete，不进入正式矩阵）。
- 新增证据 artifacts/refactor_20261012/{docker_version.json,docker_images.jsonl,docker_info.json,train_env_gpu_probe.log,migration_smoke_*.log}。
- 新增 scripts/refactor_freeze_snapshot.py 与 artifacts/refactor_20261012/freeze_snapshot.json（阶段0 冻结）：受保护文件哈希、三种子 best_policy 哈希实算复核（全部与 training_audit 一致）、数据与 checkpoint 规模快照。
