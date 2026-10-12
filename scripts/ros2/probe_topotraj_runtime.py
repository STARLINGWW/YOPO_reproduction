"""Unified-input/reset regression for the real TopoTraj ROS2 runtime."""
from pathlib import Path
import json
import subprocess
import time
import numpy as np
import rclpy
from std_msgs.msg import UInt64,String
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from rosgraph_msgs.msg import Clock
from trajectory_msgs.msg import MultiDOFJointTrajectory
from probe_topotraj_node import stamp

ROOT=Path('/workspace');OUT=ROOT/'artifacts/environment'


def main():
    rclpy.init();node=rclpy.create_node('topotraj_runtime_probe')
    received=[];telemetry=[];lifecycle=[]
    sub=node.create_subscription(MultiDOFJointTrajectory,'/yopo/runtime/trajectory',received.append,50)
    timing_sub=node.create_subscription(String,'/yopo/runtime/planning_event',lambda m:telemetry.append(json.loads(m.data)),50)
    lifecycle_sub=node.create_subscription(String,'/yopo/runtime/execution_status',lambda m:lifecycle.append(json.loads(m.data)),50)
    pubs={name:node.create_publisher(cls,'/yopo/runtime/'+name,10) for name,cls in
          [('episode',UInt64),('depth',Image),('odom',Odometry),('goal',PoseStamped)]}
    clocks=node.create_publisher(Clock,'/clock',10)
    log=(OUT/'topotraj_runtime_stdout.log').open('w')
    process=subprocess.Popen(['ros2','run','yopo_topotraj','topotraj_runtime','--ros-args','--params-file',
        str(ROOT/'configs/topotraj/component_test.yaml')],stdout=log,stderr=subprocess.STDOUT)
    report={'status':'running','scope':'ROS2 real TopoTraj adapter: pairing, complete map/FSM reset and clock rewind; synthetic sensors, no dynamics'}
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            rclpy.spin_once(node,timeout_sec=.002)
            if process.poll() is not None:raise RuntimeError('Planner runtime exited')
    def clock(sim):
        msg=Clock();stamp(msg.clock,sim);clocks.publish(msg)
    def frame(episode,sim,wall=False,depth_only=False):
        odom=Odometry();odom.header.frame_id=f'e{episode}/world';stamp(odom.header.stamp,sim)
        odom.child_frame_id=f'e{episode}/base_link';odom.pose.pose.position.x=-3.;odom.pose.pose.position.z=2.;odom.pose.pose.orientation.w=1.
        image=Image();image.header.stamp=odom.header.stamp;image.header.frame_id=f'e{episode}/camera_optical'
        image.width=160;image.height=90;image.encoding='32FC1';image.step=640
        columns=np.arange(160);row=np.where(np.abs(-(columns-80)*3/80)<.8,3.,20.) if wall else np.full(160,20.)
        image.data=np.tile(row,(90,1)).astype('<f4').tobytes()
        pubs['depth'].publish(image)
        if not depth_only:pubs['odom'].publish(odom)
    def phase(episode,base,wall,send_episode=True):
        clock(base);spin(.1)
        if send_episode:pubs['episode'].publish(UInt64(data=episode));spin(.2)
        goal=PoseStamped();goal.header.frame_id=f'e{episode}/world';goal.pose.position.x=3.;goal.pose.position.z=2.
        for k in range(300):
            sim=base+k*.01;clock(sim)
            if k%5==0:frame(episode,sim,wall)
            if 75<=k<100 and k%5==0:stamp(goal.header.stamp,sim);pubs['goal'].publish(goal)
            # Delayed old task data must never repopulate the freshly reset map.
            if episode>1 and k%10==0:frame(episode-1,sim,True)
            spin(.01)
        messages=[m for m in received if m.header.frame_id==f'e{episode}/world' and m.points]
        assert any(v['episode']==episode and v['phase']=='episode_ready' and v['initialization_wall_ms']>=0 for v in lifecycle)
        assert messages,f'No trajectory in episode{episode}'
        ymax=[max(abs(p.transforms[0].translation.y) for p in m.points) for m in messages]
        if wall:assert max(ymax)>.8,'Wall was not detected/detoured'
        else:assert max(ymax)<.1,'Old map leaked across reset or straight path deformed'
        timing={v['trajectory_stamp_ns']:v for v in telemetry if v['frame_id']==f'e{episode}/world' and v['status']=='published'}
        for message in messages:
            ns=message.header.stamp.sec*1_000_000_000+message.header.stamp.nanosec
            assert ns in timing,'Missing per-trajectory observation metadata'
            value=timing[ns]
            assert round(base*1e9)<=value['observation_stamp_ns']<=ns
            assert value['map_esdf_stamp_ns']>=round(base*1e9), 'ESDF timestamp leaked across reset'
            assert value['planner_wall_ms']>=0 and value['map_fusion_wall_ms']>=0 and value['map_esdf_wall_ms']>=0
        return {'episode':episode,'trajectories':len(messages),'max_abs_y':max(ymax),'wall':wall,'causal_timing_records':len(timing)}
    try:
        deadline=time.monotonic()+20
        while node.count_subscribers('/yopo/runtime/episode')==0 and time.monotonic()<deadline:spin(.05)
        assert node.count_subscribers('/yopo/runtime/episode')>0
        first=phase(1,10.,True)
        # Monotonically increasing /clock: explicit episode reset.
        second=phase(2,15.,False)
        # Backward /clock: runtime increments epoch and clears planner/map.
        third=phase(3,1.,False,send_episode=False)
        report.update(status='passed',episodes=[first,second,third],
                      old_task_frames_injected=True,explicit_reset=True,clock_rewind_reset=True,
                      reset_stops=sum(not m.points for m in received))
        report['timing_records']=telemetry
        report['initialization_records']=lifecycle
    except Exception as exc:report.update(status='failed',error=repr(exc));raise
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close();node.destroy_node();rclpy.shutdown()
        (OUT/'topotraj_runtime_probe.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)


if __name__=='__main__':main()
