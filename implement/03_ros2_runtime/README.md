# 03 ROS2运行时

ROS2运行时负责观测配对、时钟、任务编号、轨迹过期、规划线程和标准轨迹消息。

主要源码：ros2_ws/src/yopo_runtime、src/yopo_sim/trajectory_buffer.py、scripts/run_ros2_navigation.py。

验证：benchmarks/protocol_v1/runtime_validation.json、scripts/validate_ros2_flight.py、scripts/evaluate_ros2_flight.py。

