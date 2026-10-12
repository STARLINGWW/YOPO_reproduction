# 02 环境与 ROS2 计划

## 设计

Windows Isaac负责深度、场景、PhysX和可视化；Ubuntu 22.04 Docker负责训练、ROS2规划器、基线和评测；ROS2负责深度、里程计、目标、时钟和轨迹消息。

## 需要冻结的内容

- CUDA、PyTorch和Python版本。
- ROS_DOMAIN_ID、RMW实现和消息类型。
- 相机尺寸、深度单位、坐标系、时间戳和QoS。
- 轨迹过期、任务复位、时钟回跳和延迟计时规则。

## 验证顺序

1. 容器导入和ROS2同进程发布订阅。
2. CUDA前向、反向和卷积。
3. Isaac到Linux ROS2跨边界传输。
4. 训练规划器节点和标准轨迹输出。
5. 原生Isaac闭环和准入记录。

运行实现仍在根目录，以 implement/03_ros2_runtime/README.md 为代码入口。
