# YOPO 复现计划与项目管理

这里管理“要做什么、为什么做、怎么验收、谁改了什么”。plan 不存运行时代码，也不复制实验产物；它保存可迁移的计划、决策、协议和变更记录。

## 编号结构

| 编号 | 文件夹 | 管理内容 |
|---|---|---|
| 00 | 00_charter | 目标、范围、边界和完成定义 |
| 01 | 01_paper_protocol | 论文、源码版本、实验协议和差异 |
| 02 | 02_environment_ros2 | Ubuntu 22.04、Docker、ROS2和接口计划 |
| 03 | 03_dataset_training | 数据版本、训练配置、检查点和恢复策略 |
| 04 | 04_runtime_baselines | YOPO运行时、专家、TopoTraj、Agile和MPPI |
| 05 | 05_benchmark_acceptance | 基准矩阵、统计、验收和证据规则 |
| 06 | 06_github_migration | GitHub仓库、LFS、Ubuntu迁移与发布清单 |
| 90 | 90_decisions | 需要用户裁决的事项和已采纳决定 |
| 99 | 99_change_log | 计划、代码接口、判据和报告变更日志 |

每个编号文件夹至少包含一个 README.md。新增计划使用 NN_topic.md，决策使用 DEC-YYYYMMDD-NN.md，变更使用 YYYY-MM-DD.md。

## 当前约束

- 正式运行代码继续位于项目根目录的 src、scripts、configs、ros2_ws、docker；这是运行兼容层，不能仅为分类而移动。
- 论文主矩阵仍为 1500/1800，MPPI 的 300 槽位未执行。
- 固定协议、验收脚本、审计权重和既有飞行证据必须通过变更记录管理。
- GitHub源代码仓库与完整数据归档分开规划；59 GB级别的原始数据和运行输出不能直接当作普通Git文件上传。

## 相关入口

- 实施区：implement/README.md
- 报告区：report/README.md
- 当前状态：report/01_status/README.md
- GitHub和Ubuntu迁移：plan/06_github_migration/README.md
