"""Check the installed Isaac Sim Humble bridge without host ROS installation.

Only process-local environment is set. This does not validate Docker transport.
"""
from pathlib import Path
import json
import os
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/environment"
OUTPUT.mkdir(parents=True, exist_ok=True)
core = Path(sys.executable).parent / "Lib/site-packages/isaacsim/exts/isaacsim.ros2.core"
assert (core / "humble/lib").is_dir(), core
os.environ["ROS_DISTRO"] = "humble"
os.environ["RMW_IMPLEMENTATION"] = "rmw_fastrtps_cpp"
os.environ["ROS_DOMAIN_ID"] = "42"
os.environ["ROS_LOG_DIR"] = str(ROOT / "artifacts/ros2_logs")
os.environ["PATH"] = str(core / "humble/lib") + os.pathsep + os.environ["PATH"]
from isaacsim import SimulationApp

app = SimulationApp({"headless": True, "enable_cameras": False})
result = {"status": "started", "scope": "native Isaac bundled Humble, same-process pub/sub; not Docker connectivity"}
try:
    import omni.kit.app
    manager = omni.kit.app.get_app().get_extension_manager()
    manager.set_extension_enabled_immediate("isaacsim.ros2.bridge", True)
    for _ in range(20):
        app.update()
    import rclpy
    from std_msgs.msg import String
    from sensor_msgs.msg import Image, CameraInfo
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Clock
    from trajectory_msgs.msg import MultiDOFJointTrajectory
    rclpy.init()
    node = rclpy.create_node("yopo_isaac_humble_probe")
    received = []
    subscription = node.create_subscription(String, "/yopo/isaac_probe", lambda msg: received.append(msg.data), 10)
    publisher = node.create_publisher(String, "/yopo/isaac_probe", 10)
    deadline = time.monotonic() + 10.
    while time.monotonic() < deadline and not received:
        publisher.publish(String(data="isaac-humble-ok"))
        rclpy.spin_once(node, timeout_sec=.05)
        app.update()
    assert "isaac-humble-ok" in received
    result.update(status="passed", ros_distro=os.environ["ROS_DISTRO"], python=sys.version,
                  rclpy_path=rclpy.__file__, messages=["String", "Image", "CameraInfo", "Odometry", "Clock", "MultiDOFJointTrajectory"],
                  pub_sub_received=received)
    node.destroy_node()
    rclpy.shutdown()
except Exception:
    result.update(status="failed", traceback=traceback.format_exc())
finally:
    (OUTPUT / "isaac_humble_probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("ISAAC_ROS2_RESULT " + json.dumps(result), flush=True)
    app.close()
