#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""几何 SE(3) CTBR 外环 —— 移植自 reference/crazyswarm 的 GeometricCtbrController。

world 采用 ROS 约定（z 轴向上）。``R`` 是机体→world 旋转矩阵，``R[:, 2]`` 为机体 z 轴
（螺旋桨正推力方向）。位置 m、速度 m/s、角速率 rad/s、推力 N（整机总推力）。

输出 ``(p, q, r)`` 是**真实 FLU 体轴角速度**，符号换算全部交给 CtbrBridge。

注意：测量角速度 ω **不参与**本控制律 —— 角速率环在固件里，主机只算到"期望角速率"
为止。ω 仅用于日志与符号校核。

本模块不依赖 ROS，可离线数值自检。
"""

import math
from dataclasses import dataclass, field

import numpy as np

from command import Command


# ----------------------------------------------------------------- 小工具
def smoothstep5(u):
    """五次平滑插值 s(u) 及其一、二阶导（对 u）。端点位置/速度/加速度全为零。

    s(u)   = 10u³ - 15u⁴ + 6u⁵
    s'(u)  = 30u² - 60u³ + 30u⁴
    s''(u) = 60u  - 180u² + 120u³
    """
    u = min(max(float(u), 0.0), 1.0)
    s = u * u * u * (10.0 - 15.0 * u + 6.0 * u * u)
    ds = 30.0 * u * u * (1.0 - 2.0 * u + u * u)
    dds = 60.0 * u * (1.0 - 3.0 * u + 2.0 * u * u)
    return s, ds, dds


def vee(matrix):
    """反对称矩阵 → 三维向量。"""
    return np.array([matrix[2, 1], matrix[0, 2], matrix[1, 0]])


def project_so3(rotation):
    """用 SVD 把数值误差造成的近似旋转矩阵投影回右手 SO(3)。"""
    u, _, vt = np.linalg.svd(rotation)
    result = u @ vt
    if np.linalg.det(result) < 0.0:
        u[:, 2] *= -1.0
        result = u @ vt
    return result


def so3_log(rotation):
    """SO(3) 对数映射 → 旋转向量 [rad]，用于对期望姿态做有限差分。"""
    cos_theta = float(np.clip((np.trace(rotation) - 1.0) * 0.5, -1.0, 1.0))
    theta = math.acos(cos_theta)
    if theta < 1e-7:
        return 0.5 * vee(rotation - rotation.T)
    if abs(math.pi - theta) < 1e-5:
        values, vectors = np.linalg.eigh((rotation + np.eye(3)) * 0.5)
        axis = vectors[:, int(np.argmax(values))]
        return theta * axis / max(float(np.linalg.norm(axis)), 1e-12)
    return theta * vee(rotation - rotation.T) / (2.0 * math.sin(theta))


def quaternion_to_rotation(x, y, z, w):
    """ROS ``[x, y, z, w]`` 四元数 → 机体→world 旋转矩阵。"""
    q = np.array([x, y, z, w], dtype=float)
    norm = float(np.linalg.norm(q))
    if norm < 1e-8 or not np.all(np.isfinite(q)):
        raise ValueError("无效姿态四元数")
    x, y, z, w = q / norm
    return np.array([
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
        [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
        [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
    ])


def rotation_yaw(rotation):
    """从机体→world 旋转矩阵取 ZYX 的 yaw [rad]。"""
    return math.atan2(rotation[1, 0], rotation[0, 0])


def rotation_tilt(rotation):
    """机体 z 轴与世界 z 轴的夹角 [rad]（倾角，安全判据用）。"""
    return math.acos(float(np.clip(rotation[2, 2], -1.0, 1.0)))


# ----------------------------------------------------------------- 配置
@dataclass
class ControllerConfig:
    mass: float = 0.0434                 # kg
    gravity: float = 9.80665             # m/s^2
    max_command_thrust: float = 0.80     # N（整机总推力上限）
    max_tilt_rad: float = math.radians(10.0)
    max_body_rate: np.ndarray = field(
        default_factory=lambda: np.array([3.0, 3.0, 2.0]))
    position_gain: np.ndarray = field(
        default_factory=lambda: np.array([0.75, 0.75, 0.45]))
    velocity_gain: np.ndarray = field(
        default_factory=lambda: np.array([0.45, 0.45, 0.35]))
    integral_gain: np.ndarray = field(
        default_factory=lambda: np.array([0.05, 0.05, 0.02]))
    integral_limit: np.ndarray = field(
        default_factory=lambda: np.array([0.80, 0.80, 0.80]))
    attitude_gain: np.ndarray = field(
        default_factory=lambda: np.array([3.0, 3.0, 2.0]))
    attitude_integral_gain: np.ndarray = field(
        default_factory=lambda: np.zeros(3))
    attitude_integral_limit: np.ndarray = field(
        default_factory=lambda: np.array([0.8, 0.8, 0.8]))
    position_integral_c1: float = 0.35
    use_body_rate_feedforward: bool = True   # 悬停测试默认关（目标几乎静止，无收益）


# ----------------------------------------------------------------- 控制器
class GeometricCtbrController:
    name = "geometric"

    def __init__(self, config=None):
        self.config = config or ControllerConfig()
        self.reset()

    # ---------------- 接口层（contracts 见 controllers/base.py） ----------------
    def provides(self):
        """产出的 Command 字段（CTBR：总推力 + 机体角速率）。"""
        return frozenset({"thrust_N", "omega_radps"})

    def to_command(self, result):
        """把 compute() 的诊断字典转成跨层 Command。"""
        return Command(thrust_N=float(result["collective_thrust"]),
                       omega_radps=tuple(float(x) for x in result["body_rate_command"]))

    def describe(self):
        c = self.config
        return (f"控制器: {self.name} | provides={sorted(self.provides())} | "
                f"kp={c.position_gain} kv={c.velocity_gain} katt={c.attitude_gain} "
                f"tilt<={math.degrees(c.max_tilt_rad):.0f}°")

    def reset(self):
        """清位置积分、姿态积分与期望姿态差分历史。

        在状态失效、阶段切换、接管/交回时调用，避免上一段的累计量带进下一段。
        """
        self.position_integral = np.zeros(3)
        self.attitude_integral = np.zeros(3)
        self.previous_desired_rotation = None
        self.previous_heading = None

    def compute(self, state, target, dt):
        """一个控制周期。

        state : dict  ``position``(3,) ``velocity``(3,) ``rotation``(3,3)
        target: dict  ``position``(3,) ``velocity``(3,) ``acceleration``(3,) ``yaw``(float)
                      可选 ``max_tilt_rad`` / ``min_collective_thrust``
        返回 dict，含 ``body_rate_command``(3,) [rad/s] 与 ``collective_thrust`` [N]。
        """
        cfg = self.config
        dt = float(np.clip(dt, 0.001, 0.05))

        # ---------------------------------------------------------- 位置环
        position_error = state["position"] - target["position"]
        velocity_error = state["velocity"] - target["velocity"]

        # C1 形式积分：同时吸收位置静差与速度静差；逐轴限幅，避免低电/饱和/丢帧
        # 期间长期累积，恢复后出现突然的大推力。
        self.position_integral += dt * (
            velocity_error + cfg.position_integral_c1 * position_error)
        self.position_integral = np.clip(
            self.position_integral, -cfg.integral_limit, cfg.integral_limit)

        # F_d = m(a_d + g e3) - Kp e_p - Kv e_v - Ki I      [N, world]
        desired_force = (
            cfg.mass * (target["acceleration"] + np.array([0.0, 0.0, cfg.gravity]))
            - cfg.position_gain * position_error
            - cfg.velocity_gain * velocity_error
            - cfg.integral_gain * self.position_integral
        )

        # 饱和顺序不能反：先限垂直，再按当前可用垂直力限水平（= 限倾角）。
        # 这样大位置误差不会要求接近 90° 的危险倾斜。
        desired_force[2] = float(np.clip(desired_force[2], 0.0, cfg.max_command_thrust))
        max_tilt = float(target.get("max_tilt_rad", cfg.max_tilt_rad))
        horizontal_norm = float(np.linalg.norm(desired_force[:2]))
        max_horizontal = desired_force[2] * math.tan(max_tilt)
        if horizontal_norm > max_horizontal and horizontal_norm > 1e-8:
            desired_force[:2] *= max_horizontal / horizontal_norm

        # ---------------------------------------------------------- 期望姿态
        force_norm = float(np.linalg.norm(desired_force))
        if force_norm < 1e-8:
            b3_d = (np.array([0.0, 0.0, 1.0]) if self.previous_desired_rotation is None
                    else self.previous_desired_rotation[:, 2])
        else:
            b3_d = desired_force / force_norm

        desired_yaw = float(target["yaw"])
        b1_ref = np.array([math.cos(desired_yaw), math.sin(desired_yaw), 0.0])
        b1_proj = b1_ref - b3_d * float(b3_d @ b1_ref)
        if np.linalg.norm(b1_proj) < 1e-6:      # b3_d 与 yaw 参考近似共线，回退上一帧航向
            b1_proj = (np.array([1.0, 0.0, 0.0]) if self.previous_heading is None
                       else self.previous_heading)
        b1_d = b1_proj / max(float(np.linalg.norm(b1_proj)), 1e-12)
        b2_d = np.cross(b3_d, b1_d)
        b2_d /= max(float(np.linalg.norm(b2_d)), 1e-12)
        b1_d = np.cross(b2_d, b3_d)
        b1_d /= max(float(np.linalg.norm(b1_d)), 1e-12)
        desired_rotation = project_so3(np.column_stack((b1_d, b2_d, b3_d)))

        # 期望姿态相邻帧的 SO(3) 对数差分 = 角速度前馈
        if self.previous_desired_rotation is None:
            feedforward = np.zeros(3)
        else:
            relative = self.previous_desired_rotation.T @ desired_rotation
            feedforward = so3_log(relative) / dt
        self.previous_desired_rotation = desired_rotation
        self.previous_heading = desired_rotation[:, 0]

        # ---------------------------------------------------------- 姿态环
        rotation = state["rotation"]
        attitude_error = 0.5 * vee(
            desired_rotation.T @ rotation - rotation.T @ desired_rotation)
        self.attitude_integral += dt * attitude_error
        self.attitude_integral = np.clip(
            self.attitude_integral,
            -cfg.attitude_integral_limit, cfg.attitude_integral_limit)

        if cfg.use_body_rate_feedforward:
            feedforward_body = rotation.T @ desired_rotation @ feedforward
        else:
            feedforward_body = np.zeros(3)

        body_rate = (feedforward_body
                     - cfg.attitude_gain * attitude_error
                     - cfg.attitude_integral_gain * self.attitude_integral)

        # e_R 在偏航相差 180° 处为零，是个无法自行脱离的平衡点 ⇒ yaw 单独用包角误差
        current_yaw = rotation_yaw(rotation)
        yaw_error = math.atan2(math.sin(current_yaw - desired_yaw),
                               math.cos(current_yaw - desired_yaw))
        body_rate[2] = (-cfg.attitude_gain[2] * yaw_error
                        - cfg.attitude_integral_gain[2] * self.attitude_integral[2])

        body_rate = np.clip(body_rate, -cfg.max_body_rate, cfg.max_body_rate)

        # ---------------------------------------------------------- 总推力
        # 投影到**当前**机体 z 轴（不是 ||F_d||）：姿态尚未跟上时不会把 world 合力
        # 模长直接当电机推力，避免姿态误差期间的推力上冲。
        minimum_thrust = float(target.get("min_collective_thrust", 0.0))
        collective_thrust = float(np.clip(
            max(float(desired_force @ rotation[:, 2]), minimum_thrust),
            0.0, cfg.max_command_thrust))

        return {
            "position_error": position_error,
            "velocity_error": velocity_error,
            "desired_force": desired_force,
            "desired_rotation": desired_rotation,
            "attitude_error": attitude_error,
            "body_rate_command": body_rate,
            "collective_thrust": collective_thrust,
        }
