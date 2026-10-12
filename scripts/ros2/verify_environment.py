"""Evidence for the environment gate; this is not a YOPO training result."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    os_release = platform.freedesktop_os_release()
    assert os_release["VERSION_ID"] == "22.04", os_release
    assert os.environ.get("ROS_DISTRO") == "humble"
    import rclpy
    from std_msgs.msg import String
    from sensor_msgs.msg import Image, CameraInfo
    from nav_msgs.msg import Odometry
    from trajectory_msgs.msg import MultiDOFJointTrajectory
    from rosgraph_msgs.msg import Clock
    rclpy.init()
    node = rclpy.create_node("yopo_environment_check")
    received = []
    subscriber = node.create_subscription(String, "/yopo/env_probe", lambda message: received.append(message.data), 10)
    publisher = node.create_publisher(String, "/yopo/env_probe", 10)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not received:
        publisher.publish(String(data="jammy-humble-ok"))
        rclpy.spin_once(node, timeout_sec=.1)
    assert "jammy-humble-ok" in received
    result = {"status": "passed", "scope": "container imports and same-process ROS2 pub/sub only",
              "ubuntu": os_release["VERSION_ID"], "ros_distro": os.environ["ROS_DISTRO"],
              "python": sys.version, "ros2_pub_sub": True,
              "standard_messages": ["Image", "CameraInfo", "Odometry", "MultiDOFJointTrajectory", "Clock"],
              "gpu_requested": args.gpu}
    node.destroy_node()
    rclpy.shutdown()
    if args.gpu:
        result["scope"] = "container ROS2 pub/sub, CUDA matmul/convolution backward and nvcc; not full YOPO training"
        import torch
        assert torch.cuda.is_available()
        a = torch.randn(512, 512, device="cuda", requires_grad=True)
        (a @ a).square().mean().backward()
        torch.cuda.synchronize()
        assert bool(torch.isfinite(a.grad).all())
        conv = torch.nn.Conv2d(1, 16, 3, padding=1).cuda()
        image = torch.randn(4, 1, 96, 160, device="cuda", requires_grad=True)
        conv(image).square().mean().backward()
        torch.cuda.synchronize()
        assert bool(torch.isfinite(image.grad).all()) and bool(torch.isfinite(conv.weight.grad).all())
        result.update(torch=torch.__version__, cuda_runtime=torch.version.cuda,
                      device=torch.cuda.get_device_name(), capability=list(torch.cuda.get_device_capability()),
                      cuda_forward_backward=True, cudnn_convolution_backward=True,
                      nvcc=subprocess.check_output(["nvcc", "--version"], text=True))
    output = Path("/workspace/artifacts/environment")
    output.mkdir(parents=True, exist_ok=True)
    name = "training_gpu.json" if args.gpu else "ros_core.json"
    (output / name).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
