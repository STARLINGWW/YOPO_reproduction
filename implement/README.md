# YOPO 实施工作区

这里是代码和实验实施的入口。根目录的 src、scripts、configs、docker、ros2_ws、tests、external、datasets、checkpoints、artifacts 保持原路径，确保训练和飞行命令继续可用；implement 目录保存可读的模块地图、接口契约和大模型实施规范。

## 模块

| 编号 | 模块 | 代码入口 |
|---|---|---|
| 00 | 工作区地图 | 根目录运行结构与命令入口 |
| 01 | 核心算法 | src/yopo_repro、external/audit_sources/main |
| 02 | 训练 | scripts/train_scratch.py、scripts/train_dagger_finetune.py |
| 03 | ROS2运行时 | ros2_ws/src/yopo_runtime、scripts/run_ros2_navigation.py |
| 04 | Isaac仿真 | scripts/run_navigation.py、scripts/run_ros2_navigation.py、src/yopo_sim |
| 05 | 基线 | src/yopo_expert、ros2_ws/src/yopo_topotraj、src/agile_runtime |
| 06 | 验证 | tests、scripts/validate_*、scripts/final_acceptance_audit.py |
| 07 | 可视化 | scripts/demo_flight.ps1、scripts/render_*.py、artifacts/ |
| 99 | 工作区规则 | 大模型实施规范和任务模板 |
| — | 代码工作区视图 | workspace/（junction/符号链接指向根目录真实代码；bootstrap_links.ps1/.sh 重建） |

整个复现的模块划分与论文章节对照入口：[report/00_index/01_module_map.md](../report/00_index/01_module_map.md)。

代码真实文件位于项目根（运行兼容与冻结证据依赖相对路径）；[workspace/README.md](workspace/README.md) 说明视图用法与接管约定。

每次改动先在plan中建立任务，完成后写入report。禁止为了归类复制一份可执行源码。

