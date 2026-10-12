"""Actual ROS2 TopoTraj node, synthetic camera wall; no flight/dynamics claim."""
from pathlib import Path
import json
import subprocess
import time
import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry,Path as PathMessage
from sensor_msgs.msg import Image
from rosgraph_msgs.msg import Clock
from trajectory_msgs.msg import MultiDOFJointTrajectory
from std_msgs.msg import Empty

ROOT=Path('/workspace'); output=ROOT/'artifacts/environment'


def stamp(message, seconds):
    ns=round(seconds*1e9);message.sec=ns//1_000_000_000;message.nanosec=ns%1_000_000_000


def main():
    rclpy.init();node=rclpy.create_node('topotraj_node_probe')
    results=[];emergencies=[]
    trajectory_sub=node.create_subscription(MultiDOFJointTrajectory,'/topotraj/trajectory',results.append,10)
    emergency_sub=node.create_subscription(Empty,'/planning/replan',lambda _:emergencies.append(time.monotonic()),10)
    depth_pub=node.create_publisher(Image,'/sdf_map/depth',10)
    pose_pub=node.create_publisher(PoseStamped,'/sdf_map/pose',10)
    odom_pub=node.create_publisher(Odometry,'/odom_world',10)
    goal_pub=node.create_publisher(PathMessage,'/waypoint_generator/waypoints',10)
    clock_pub=node.create_publisher(Clock,'/clock',10)
    log=(output/'topotraj_node_stdout.log').open('w')
    process=subprocess.Popen(['ros2','run','yopo_topotraj','topotraj_node','--ros-args','--params-file',
        str(ROOT/'configs/topotraj/component_test.yaml'),'-p','use_sim_time:=true'],stdout=log,stderr=subprocess.STDOUT)
    report={'status':'running','scope':'Native ROS2 original TopoTraj mapping/manager/FSM with synthetic stationary sensor wall; no flight'}
    try:
        deadline=time.monotonic()+20
        while node.count_subscribers('/sdf_map/depth')==0 and time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.05)
            if process.poll() is not None:raise RuntimeError('Planner exited during startup')
        assert node.count_subscribers('/sdf_map/depth')>0,'No planner depth subscriber'
        # Camera optical z is world +x; wall at x=0, |y|<0.8, spanning all z.
        rows,cols=np.mgrid[:90,:160]
        wall_y=-(cols-80)*3/80
        raw=np.where(np.abs(wall_y)<.8,3.,20.).astype('<f4').tobytes()
        goal=PathMessage();goal.header.frame_id='world';goal_pose=PoseStamped()
        goal_pose.pose.position.x=3.;goal_pose.pose.position.z=2.;goal.poses=[goal_pose]
        clock=Clock()
        for step in range(450):
            sim=10.+step*.01;stamp(clock.clock,sim);clock_pub.publish(clock)
            odom=Odometry();odom.header.frame_id='world';stamp(odom.header.stamp,sim)
            odom.child_frame_id='base_link';odom.pose.pose.position.x=-3.;odom.pose.pose.position.z=2.;odom.pose.pose.orientation.w=1.
            odom_pub.publish(odom)
            if step%5==0:
                image=Image();image.header.stamp=odom.header.stamp;image.header.frame_id='camera_optical'
                image.width=160;image.height=90;image.encoding='32FC1';image.step=640;image.data=raw
                pose=PoseStamped();pose.header.stamp=odom.header.stamp;pose.header.frame_id='world'
                pose.pose.position.x=-3.;pose.pose.position.z=2.
                pose.pose.orientation.x=.5;pose.pose.orientation.y=-.5;pose.pose.orientation.z=.5;pose.pose.orientation.w=-.5
                pose_pub.publish(pose);depth_pub.publish(image)
            if 100<=step<130 and step%5==0:goal.header.stamp=odom.header.stamp;goal_pub.publish(goal)
            until=time.monotonic()+.01
            while time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.001)
            if process.poll() is not None:raise RuntimeError('Planner crashed; inspect stdout')
        assert results,'No standard trajectory published'
        trajectories=[]
        for msg in results:
            assert msg.header.frame_id=='world' and msg.joint_names==['quadrotor']
            times=[];positions=[]
            for point in msg.points:
                assert len(point.transforms)==len(point.velocities)==len(point.accelerations)==1
                p=point.transforms[0].translation;v=point.velocities[0].linear;a=point.accelerations[0].linear
                assert np.isfinite([p.x,p.y,p.z,v.x,v.y,v.z,a.x,a.y,a.z]).all()
                times.append(point.time_from_start.sec+point.time_from_start.nanosec*1e-9)
                positions.append([p.x,p.y,p.z])
            assert times[0]==0 and np.all(np.diff(times)>0)
            trajectories.append({'stamp':msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9,'points':positions,'times':times})
        detours=[v for v in trajectories if max(abs(p[1]) for p in v['points'])>.8]
        report.update(status='passed' if detours else 'failed',trajectories=len(results),
                      detour_trajectories=len(detours),emergency_stops=len(emergencies),
                      sensor_geometry='3m forward depth to narrow wall; no map truth provided')
        (output/'topotraj_node_trajectories.json').write_text(json.dumps(trajectories))
        assert detours,'Planner did not produce a wall detour'
    except Exception as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close();node.destroy_node();rclpy.shutdown()
        (output/'topotraj_node_probe.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report),flush=True)


if __name__=='__main__':main()
