"""Live ROS2 protocol tests with an explicitly synthetic planner, not flight results."""
from pathlib import Path
import json
import threading
import time
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import Image
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseStamped
from rosgraph_msgs.msg import Clock
from std_msgs.msg import UInt64,String
from trajectory_msgs.msg import MultiDOFJointTrajectory,MultiDOFJointTrajectoryPoint
from yopo_runtime.protocol_node import PlannerProtocol

ROOT=Path('/workspace')
rclpy.init(domain_id=43)
prefix='/yopo/protocol_test'
started=threading.Event();release=threading.Event();delayed=[False]
reset_calls=[]
def reset_backend(episode):
    reset_calls.append(episode)
    if episode==4:raise RuntimeError('injected reset failure')
def fake_planner(observation,goal):
    if delayed[0]:started.set();release.wait(timeout=3.)
    msg=MultiDOFJointTrajectory();msg.header.stamp=observation.depth.header.stamp
    msg.header.frame_id=f'e{observation.episode_id}/world';msg.joint_names=['synthetic_protocol_only']
    point=MultiDOFJointTrajectoryPoint();point.time_from_start.sec=1;msg.points=[point]
    return msg
fake_planner.reset=reset_backend
runtime=PlannerProtocol(fake_planner,prefix)
client=Node('yopo_protocol_test_client')
clock=client.create_publisher(Clock,'/clock',10)
episodes=client.create_publisher(UInt64,prefix+'/episode',10)
goals=client.create_publisher(PoseStamped,prefix+'/goal',10)
images=client.create_publisher(Image,prefix+'/depth',10)
odometry=client.create_publisher(Odometry,prefix+'/odom',10)
received=[]
telemetry=[];lifecycle=[]
sub=client.create_subscription(MultiDOFJointTrajectory,prefix+'/trajectory',lambda msg:received.append(msg),10)
telemetry_sub=client.create_subscription(String,prefix+'/planning_event',lambda msg:telemetry.append(json.loads(msg.data)),10)
lifecycle_sub=client.create_subscription(String,prefix+'/execution_status',lambda msg:lifecycle.append(json.loads(msg.data)),10)
executor=SingleThreadedExecutor();executor.add_node(runtime);executor.add_node(client)
def spin(seconds=.15):
    until=time.monotonic()+seconds
    while time.monotonic()<until:executor.spin_once(timeout_sec=.01)
def set_clock(ns):
    msg=Clock();msg.clock.sec=ns//1_000_000_000;msg.clock.nanosec=ns%1_000_000_000;clock.publish(msg);spin()
    assert runtime.get_clock().now().nanoseconds==ns
def set_episode(e):
    episodes.publish(UInt64(data=e));spin()
    goal=PoseStamped();goal.header.frame_id=f'e{e}/world';goal.pose.position.x=10.;goals.publish(goal);spin()
def pair(e,ns,order=('depth','odometry')):
    image=Image();image.header.frame_id=f'e{e}/camera_optical';image.header.stamp.sec=ns//1_000_000_000;image.header.stamp.nanosec=ns%1_000_000_000
    odom=Odometry();odom.header.frame_id=f'e{e}/world';odom.header.stamp=image.header.stamp
    for kind in order:
        (images if kind=='depth' else odometry).publish(image if kind=='depth' else odom)
    spin()
try:
    spin(1.)
    set_episode(1);set_clock(0)
    pair(1,100_000_000)  # arrives before clock; must be deferred, not lost
    assert not received
    set_clock(100_000_000);spin()
    assert len(received)==1
    pair(1,100_000_000);assert len(received)==1  # no duplicate command
    delayed[0]=True;pair(1,200_000_000);set_clock(200_000_000)
    assert started.wait(timeout=1.)
    set_clock(1_500_000_000);release.set();spin()
    assert len(received)==1 and runtime.stats['stale_result']==1
    delayed[0]=False;set_episode(2);set_clock(0)
    pair(1,100_000_000);set_clock(100_000_000);assert len(received)==1
    pair(2,100_000_000,order=('odometry','depth'));spin()
    assert len(received)==2 and received[-1].header.frame_id=='e2/world'
    before=runtime.stats['wrong_episode']
    bad_goal=PoseStamped();bad_goal.header.frame_id='e2/base_link';goals.publish(bad_goal);spin()
    assert runtime.stats['wrong_episode']==before+1
    # Rewinding the clock clears pending work and requires fresh goal/frames.
    set_clock(0);assert runtime.episode==3 and runtime.goal is None
    pair(2,0);assert len(received)==2
    set_episode(3);pair(3,0);spin()
    assert len(received)==3 and reset_calls==[1,2,3]
    assert len(telemetry)==4 and sum(v['status']=='published' for v in telemetry)==3
    delayed_event=next(v for v in telemetry if v['status']=='stale_result')
    assert delayed_event['observation_stamp_ns']==200_000_000 and delayed_event['planner_wall_ms']>=100
    assert all(v['queue_wall_ms']>=0 and v['planner_wall_ms']>=0 for v in telemetry)
    assert {v['episode'] for v in lifecycle if v['phase']=='episode_ready'}>={1,2,3}
    set_episode(4);set_clock(100_000_000);pair(4,100_000_000);assert len(received)==3
    assert any(v['episode']==4 and v['phase']=='episode_failed' for v in lifecycle)
    set_episode(5);set_clock(100_000_000);pair(5,100_000_000);spin();assert len(received)==4
    assert reset_calls==[1,2,3,4,5]
    result={'status':'passed','scope':'ROS2 clock/pairing/reset/expiry integration with synthetic planner; not Isaac dynamics',
            'assertions':['future frames deferred until clock','duplicate frame emits once','clock advances while planner runs','expired result rejected','previous episode frames rejected','reversed topic arrival order accepted','wrong coordinate frame rejected','clock rewind resets backend before next observation'],
            'stats':runtime.stats,'backend_reset_calls':reset_calls,'planning_events':telemetry,'lifecycle_events':lifecycle,
            'telemetry_verified':'one event per processed observation, source stamp preserved, delayed backend duration measured'}
    (ROOT/'artifacts/environment/ros2_protocol_integration.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
finally:
    release.set();runtime.close();client.destroy_node();executor.shutdown();rclpy.shutdown()
