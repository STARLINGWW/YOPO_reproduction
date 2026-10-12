#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command —— T2(executor) → T1(daemon) 的控制指令契约（纯数据，无硬件依赖）。

单位与坐标系（详见 docs/项目手册.md §4.1）：
    thrust_N         N        整机总推力（沿机体 z 轴）
    omega_radps      rad/s    机体 FLU 角速率 (p, q, r)
    attitude_rp_deg  deg      世界系目标倾角 (roll, pitch)  ← 唯一非 SI 字段（固件角度通道原生单位）
    yaw_rad          rad      世界系目标航向
    yawrate_radps    rad/s    机体 z 角速率
    velocity_world   m/s      世界系速度
    position_world   m        世界系位置
    accel_world      m/s^2    世界系加速度前馈
    quat_xyzw        —        body→world 四元数

只填用得上的字段：控制器产出什么由 ``Controller.provides()`` 声明，输出后端需要什么由
``OutputBackend.requires`` 声明，两者在 ctbr_enter 握手时校验（P2 起）。
"""

FIELDS = ("thrust_N", "omega_radps", "attitude_rp_deg", "yaw_rad", "yawrate_radps",
          "velocity_world", "position_world", "accel_world", "quat_xyzw")

_VEC_LEN = {"omega_radps": 3, "attitude_rp_deg": 2, "velocity_world": 3,
            "position_world": 3, "accel_world": 3, "quat_xyzw": 4}


class Command:
    """控制指令（字段默认 None = 未提供）。"""

    __slots__ = FIELDS

    def __init__(self, thrust_N=None, omega_radps=None, attitude_rp_deg=None,
                 yaw_rad=None, yawrate_radps=None, velocity_world=None,
                 position_world=None, accel_world=None, quat_xyzw=None):
        self.thrust_N = None if thrust_N is None else float(thrust_N)
        for name, value in (("omega_radps", omega_radps),
                            ("attitude_rp_deg", attitude_rp_deg),
                            ("velocity_world", velocity_world),
                            ("position_world", position_world),
                            ("accel_world", accel_world),
                            ("quat_xyzw", quat_xyzw)):
            if value is None:
                setattr(self, name, None)
            else:
                vec = tuple(float(x) for x in value)
                if len(vec) != _VEC_LEN[name]:
                    raise ValueError(f"{name} 需要 {_VEC_LEN[name]} 维，收到 {len(vec)}")
                setattr(self, name, vec)
        self.yaw_rad = None if yaw_rad is None else float(yaw_rad)
        self.yawrate_radps = None if yawrate_radps is None else float(yawrate_radps)

    # ---------------- 查询 ----------------
    def provided(self):
        """返回已提供（非 None）的字段名集合。"""
        return {k for k in FIELDS if getattr(self, k) is not None}

    def is_empty(self):
        return not self.provided()

    # ---------------- 序列化（JSON 友好） ----------------
    def to_msg(self):
        out = {}
        for k in FIELDS:
            v = getattr(self, k)
            if v is None:
                continue
            out[k] = list(v) if isinstance(v, tuple) else float(v)
        return out

    @classmethod
    def from_msg(cls, msg):
        """从 UDP dict 构造；未知键忽略（向前兼容），缺省字段保持 None。"""
        if not isinstance(msg, dict):
            raise TypeError("msg 必须是 dict")
        kw = {}
        for k in FIELDS:
            v = msg.get(k)
            if v is None:
                continue
            kw[k] = tuple(float(x) for x in v) if isinstance(v, (list, tuple)) else float(v)
        return cls(**kw)

    def __repr__(self):
        parts = []
        for k in FIELDS:
            v = getattr(self, k)
            if v is not None:
                parts.append(f"{k}={v}")
        return "Command(" + ", ".join(parts) + ")"
