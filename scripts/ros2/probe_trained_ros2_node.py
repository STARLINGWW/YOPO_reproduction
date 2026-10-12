"""Real self-trained policy through ROS2 observation/control topics (no dynamics)."""
from pathlib import Path
import argparse
import json
import time
import numpy as np
from scipy.spatial.transform import Rotation
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from sensor_msgs.msg import Image
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseStamped
from rosgraph_msgs.msg import Clock
from std_msgs.msg import UInt64
from trajectory_msgs.msg import MultiDOFJointTrajectory
from yopo_runtime.protocol_node import PlannerProtocol
from yopo_runtime.main_planner import MainPlanner

ROOT=Path('/workspace');prefix='/yopo/trained_node_probe'
parser=argparse.ArgumentParser()
parser.add_argument('--checkpoint',default='checkpoints/resume_split_v2/best_policy.pth')
parser.add_argument('--dataset',default='datasets/smoke_v1/shards/002')
parser.add_argument('--output',default='artifacts/environment/trained_ros2_node.json')
args=parser.parse_args()
rclpy.init(domain_id=44)
backend=MainPlanner(ROOT/args.checkpoint,2.,'cpu')
runtime=PlannerProtocol(backend,prefix)
client=Node('yopo_recorded_observation_replay')
clock_pub=client.create_publisher(Clock,'/clock',10)
episode_pub=client.create_publisher(UInt64,prefix+'/episode',10)
goal_pub=client.create_publisher(PoseStamped,prefix+'/goal',10)
image_pub=client.create_publisher(Image,prefix+'/depth',10)
odom_pub=client.create_publisher(Odometry,prefix+'/odom',10)
received=[]
subscription=client.create_subscription(MultiDOFJointTrajectory,prefix+'/trajectory',lambda msg:received.append(msg),10)
executor=SingleThreadedExecutor();executor.add_node(runtime);executor.add_node(client)
def spin(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:executor.spin_once(timeout_sec=.01)
labels=np.load(ROOT/args.dataset/'poses.npz')
depth=np.load(ROOT/args.dataset/'depth_m.npy',mmap_mode='r')
try:
    spin(1.)
    results=[]
    for i in range(5):
        episode=i+1;episode_pub.publish(UInt64(data=episode));spin(.1)
        p=labels['positions'][i];q=labels['quaternions'][i]
        goal=PoseStamped();goal.header.frame_id=f'e{episode}/world'
        gp=p+Rotation.from_quat(q[[1,2,3,0]]).apply([10.,0.,0.])
        goal.pose.position.x,goal.pose.position.y,goal.pose.position.z=map(float,gp)
        goal_pub.publish(goal)
        clock=Clock();clock.clock.sec=1;clock_pub.publish(clock);spin(.1)
        image=Image();image.header.stamp.sec=1;image.header.frame_id=f'e{episode}/camera_optical'
        image.width=160;image.height=90;image.step=640;image.encoding='32FC1';image.data=depth[i].tobytes()
        odom=Odometry();odom.header.stamp.sec=1;odom.header.frame_id=f'e{episode}/world';odom.child_frame_id=f'e{episode}/base_link'
        odom.pose.pose.position.x,odom.pose.pose.position.y,odom.pose.pose.position.z=map(float,p)
        odom.pose.pose.orientation.w,odom.pose.pose.orientation.x,odom.pose.pose.orientation.y,odom.pose.pose.orientation.z=map(float,q)
        image_pub.publish(image);odom_pub.publish(odom)
        deadline=time.monotonic()+5
        while len(received)<episode and time.monotonic()<deadline:executor.spin_once(timeout_sec=.02)
        assert len(received)==episode,runtime.stats
        trajectory=received[-1]
        assert trajectory.header.frame_id==f'e{episode}/world' and trajectory.header.stamp.sec==1
        first=trajectory.points[0].transforms[0].translation
        np.testing.assert_allclose([first.x,first.y,first.z],p,atol=1e-10)
        assert runtime.get_clock().now().nanoseconds==1_000_000_000
        results.append({'episode':episode,'points':len(trajectory.points),'weights':backend.checkpoint_sha256})
    report={'status':'passed','scope':'real self-trained smoke policy, ROS2 depth/odom/goal/clock -> trajectory; recorded independent-map samples, no dynamics',
            'stats':runtime.stats,'results':results,'device':'cpu','official_weights_loaded':False,
            'checkpoint':args.checkpoint,'dataset':args.dataset}
    (ROOT/args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
finally:runtime.close();client.destroy_node();executor.shutdown();rclpy.shutdown()
