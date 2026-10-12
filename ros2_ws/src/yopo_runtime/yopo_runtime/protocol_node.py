"""Clock-aware observation pairing and asynchronous planner result validity.

Boundary messages are standard ROS2 types supported by Isaac's Humble bridge.
Frames use e<episode>/world, e<episode>/base_link and e<episode>/camera_optical.
The planner callable is injected; this node does not provide an alternative
planning algorithm or access any map truth.
"""
from collections import OrderedDict
import threading
import time
import json
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import Image
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseStamped
from rosgraph_msgs.msg import Clock
from std_msgs.msg import UInt64,String
from trajectory_msgs.msg import MultiDOFJointTrajectory
from .frame_gate import FrameGate


def stamp_ns(stamp):return stamp.sec*1_000_000_000+stamp.nanosec


class PlannerProtocol(Node):
    def __init__(self,planner,prefix='/yopo/runtime',max_age_ns=200_000_000):
        super().__init__('yopo_planner_protocol',parameter_overrides=[Parameter('use_sim_time',value=True)])
        self.planner=planner;self.gate=FrameGate(max_age_ns=max_age_ns)
        self.episode=0;self.goal=None;self.pending=OrderedDict();self.job=None
        self.condition=threading.Condition();self.stopping=False
        self.worker_episode=0;self.worker_reset_failed=False;self.initialization_wall_ms=0.
        self.stats={'paired':0,'published':0,'wrong_episode':0,'stale_result':0,'planner_errors':0,'superseded':0}
        self.output=self.create_publisher(MultiDOFJointTrajectory,prefix+'/trajectory',10)
        self.planning_events=self.create_publisher(String,prefix+'/planning_event',10)
        self.lifecycle=self.create_publisher(String,prefix+'/execution_status',10)
        self.subscriptions_=[
            self.create_subscription(Clock,'/clock',self.on_clock,10),
            self.create_subscription(UInt64,prefix+'/episode',self.on_episode,10),
            self.create_subscription(PoseStamped,prefix+'/goal',self.on_goal,10),
            self.create_subscription(Image,prefix+'/depth',lambda msg:self.on_observation('depth',msg),10),
            self.create_subscription(Odometry,prefix+'/odom',lambda msg:self.on_observation('odometry',msg),10)]
        self.worker=threading.Thread(target=self._work,name='yopo-planning-worker',daemon=True)
        self.worker.start()

    def frame_ok(self,frame,suffix):return frame==f'e{self.episode}/{suffix}'

    def _reset(self,episode):
        self.episode=episode;self.gate.reset(episode);self.goal=None;self.pending.clear();self.job=None
        self.condition.notify_all()

    def on_episode(self,msg):
        with self.condition:
            if msg.data>self.episode:self._reset(int(msg.data))
            elif msg.data==self.worker_episode and not self.worker_reset_failed:self._ready()

    def _ready(self):
        self.lifecycle.publish(String(data=json.dumps({'episode':self.worker_episode,'phase':'episode_ready','initialization_wall_ms':self.initialization_wall_ms})))

    def on_clock(self,msg):
        with self.condition:
            now=stamp_ns(msg.clock)
            if self.gate.now_ns is not None and now<self.gate.now_ns:self._reset(self.episode+1)
            self.gate.advance_clock(now);self._drain()

    def on_goal(self,msg):
        with self.condition:
            if not self.frame_ok(msg.header.frame_id,'world'):self.stats['wrong_episode']+=1;return
            self.goal=msg;self._drain()

    def on_observation(self,kind,msg):
        with self.condition:
            if self.worker_reset_failed and self.worker_episode==self.episode:return
            suffix='camera_optical' if kind=='depth' else 'world'
            if not self.frame_ok(msg.header.frame_id,suffix):self.stats['wrong_episode']+=1;return
            stamp=stamp_ns(msg.header.stamp)
            self.pending[(stamp,kind)]=msg
            while len(self.pending)>32:self.pending.popitem(last=False)
            self._drain()

    def _drain(self):
        if self.worker_reset_failed and self.worker_episode==self.episode:return
        if self.gate.now_ns is None or self.goal is None:return
        for key in sorted(list(self.pending)):
            stamp,kind=key
            if stamp>self.gate.now_ns:continue
            msg=self.pending.pop(key)
            pair=self.gate.add(kind,stamp,msg)
            if pair is not None:
                self.stats['paired']+=1
                if self.job is not None:self.stats['superseded']+=1
                self.job=(pair,self.goal,time.perf_counter());self.condition.notify_all()

    def _work(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.stopping or self.job is not None or self.worker_episode!=self.episode)
                if self.stopping:return
                reset_episode=self.episode if self.worker_episode!=self.episode else None
                if reset_episode is None:observation,goal,paired_wall=self.job;self.job=None
            if reset_episode is not None:
                reset_started=time.perf_counter()
                try:
                    if hasattr(self.planner,'reset'):self.planner.reset(reset_episode)
                    with self.condition:
                        self.worker_episode=reset_episode;self.worker_reset_failed=False
                        self.initialization_wall_ms=(time.perf_counter()-reset_started)*1000
                        if self.episode==reset_episode:self._ready()
                except Exception as exc:
                    with self.condition:
                        self.worker_episode=reset_episode;self.worker_reset_failed=True;self.job=None;self.stats['planner_errors']+=1
                    self.lifecycle.publish(String(data=json.dumps({'episode':reset_episode,'phase':'episode_failed','error':str(exc)})))
                continue
            compute_started=time.perf_counter()
            def event(status,error=None):
                payload={'status':status,'episode':observation.episode_id,'observation_stamp_ns':observation.stamp_ns,
                    'queue_wall_ms':(compute_started-paired_wall)*1000,'planner_wall_ms':(time.perf_counter()-compute_started)*1000,
                    'debug':getattr(self.planner,'last_debug',{}),'error':error}
                self.planning_events.publish(String(data=json.dumps(payload)))
            try:
                trajectory=self.planner(observation,goal)
                if not trajectory.points:raise ValueError('Planner produced no trajectory points')
                start=stamp_ns(trajectory.header.stamp)
                duration=stamp_ns(trajectory.points[-1].time_from_start)
                with self.condition:
                    current=self.gate.trajectory_is_current(observation.episode_id,start,start+duration)
                    if self.stopping:return
                    if not current or not self.frame_ok(trajectory.header.frame_id,'world'):
                        self.stats['stale_result']+=1;event('stale_result');continue
                    self.output.publish(trajectory);self.stats['published']+=1
                    event('published')
            except Exception as exc:
                with self.condition:self.stats['planner_errors']+=1
                self.get_logger().error(f'Planner failed: {exc}')
                event('planner_error',str(exc))

    def close(self):
        with self.condition:self.stopping=True;self.condition.notify_all()
        self.worker.join(timeout=5.)
        if self.worker.is_alive():raise RuntimeError('Planner worker did not terminate')
        self.destroy_node()
