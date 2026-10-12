# 00 工作区地图

运行根目录是项目根目录。代码没有被移动，因为脚本通过相对路径访问 external、configs、datasets、checkpoints 和 artifacts，Docker把同一个根目录挂载到 /workspace。

推荐入口：

- 训练：scripts/run_formal_training.ps1、scripts/train_scratch.py。
- 审计：scripts/audit_training_run.py、scripts/final_acceptance_audit.py。
- ROS2飞行：scripts/run_ros2_navigation.py。
- 原生飞行：scripts/run_navigation.py。
- 统一演示：scripts/demo_flight.ps1。
- 状态：scripts/queue_status.py、scripts/make_status_overview.py。

不要从implement子目录直接执行脚本；先把项目根设为当前目录。

