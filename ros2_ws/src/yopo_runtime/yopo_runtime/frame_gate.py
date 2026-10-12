"""Simulation-time pairing and reset guards, independent of ROS middleware.

The ROS adapter must invoke reset for explicit episodes, and recreate or drain
subscriptions at reset so same-stamp samples from distinct episodes cannot mix.
Call these methods from one mutually exclusive callback group.
"""
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Observation:
    episode_id: int
    observation_id: int
    stamp_ns: int
    depth: Any
    odometry: Any


class FrameGate:
    def __init__(self, max_age_ns=100_000_000, capacity=8):
        if max_age_ns < 0 or capacity < 1:
            raise ValueError("invalid age/capacity")
        self.max_age_ns, self.capacity = max_age_ns, capacity
        self.episode_id = 0
        self.now_ns = None
        self._depth, self._odom = OrderedDict(), OrderedDict()
        self.last_stamp_ns = -1
        self.observation_id = 0

    def reset(self, episode_id=None):
        self.episode_id = self.episode_id + 1 if episode_id is None else int(episode_id)
        self._depth.clear()
        self._odom.clear()
        self.last_stamp_ns = -1
        self.observation_id = 0
        self.now_ns = None

    def advance_clock(self, stamp_ns):
        if stamp_ns < 0:
            raise ValueError("negative simulation time")
        if self.now_ns is not None and stamp_ns < self.now_ns:
            self.reset()
        self.now_ns = stamp_ns
        for queue in (self._depth, self._odom):
            for t in list(queue):
                if not self._fresh(t):
                    del queue[t]

    def _fresh(self, stamp_ns):
        return self.now_ns is not None and 0 <= self.now_ns - stamp_ns <= self.max_age_ns

    def add(self, kind, stamp_ns, value):
        if kind not in ("depth", "odometry"):
            raise ValueError("unknown observation kind")
        if not self._fresh(stamp_ns) or stamp_ns <= self.last_stamp_ns:
            return None
        queue = self._depth if kind == "depth" else self._odom
        if stamp_ns in queue:
            return None
        queue[stamp_ns] = value
        while len(queue) > self.capacity:
            queue.popitem(last=False)
        if stamp_ns not in self._depth or stamp_ns not in self._odom:
            return None
        self.observation_id += 1
        observation = Observation(self.episode_id, self.observation_id, stamp_ns,
                                  self._depth.pop(stamp_ns), self._odom.pop(stamp_ns))
        self.last_stamp_ns = stamp_ns
        for q in (self._depth, self._odom):
            for t in list(q):
                if t <= stamp_ns:
                    del q[t]
        return observation

    def trajectory_is_current(self, episode_id, start_ns, valid_until_ns):
        return (episode_id == self.episode_id and self.now_ns is not None and
                start_ns <= self.now_ns < valid_until_ns)
