"""Adapter that runs the project's real SE(3) geometric controller in Isaac Sim.

The extracted flight stack splits the loop in two, exactly like the hardware:

    host  100 Hz   ``GeometricCtbrController`` (controllers/geometric.py)
                   -> collective thrust [N] + desired body rate [rad/s]
    firmware 500 Hz body-rate PID -> body torque -> mixer -> rotor speeds
    motors         identified first-order rotor dynamics (cf21b_model.py)

This module supplies the missing 500 Hz inner loop and the mixer so that the
unmodified geometric controller can drive the PhysX vehicle.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

EXTERNAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EXTERNAL))

from geometric import (  # noqa: E402  (extracted, unmodified)
    ControllerConfig,
    GeometricCtbrController,
    project_so3,
    quaternion_to_rotation,
)

sys.path.insert(0, str(Path(__file__).parent))
from cf21b_model import Cf21BParams, rpm_for_thrust  # noqa: E402


def rotation_from_isaac_quaternion(quat_wxyz) -> np.ndarray:
    """Isaac Sim stores (w, x, y, z); the flight stack uses ROS (x, y, z, w)."""
    w, x, y, z = [float(value) for value in quat_wxyz]
    return quaternion_to_rotation(x, y, z, w)


@dataclass
class RateLoopConfig:
    """Firmware-equivalent body-rate PID (the real gains live on the board)."""

    kp: float = 12.0
    ki: float = 20.0
    integral_limit: float = 2.0
    max_torque: float = 0.012


class BodyRateLoop:
    """500 Hz inner loop: body-rate PID -> torque -> rotor speed commands."""

    def __init__(self, params: Cf21BParams, config: RateLoopConfig | None = None):
        self.params = params
        self.config = config or RateLoopConfig()
        self.integral = np.zeros(3)
        self.inertia = np.diag(np.asarray(params.inertia, dtype=float))

    def reset(self):
        self.integral = np.zeros(3)

    def step(self, rate_desired, rate_measured, total_thrust, dt):
        cfg = self.config
        error = np.asarray(rate_desired, dtype=float) - np.asarray(rate_measured, dtype=float)
        self.integral = np.clip(self.integral + error * dt,
                                -cfg.integral_limit, cfg.integral_limit)
        rate = np.asarray(rate_measured, dtype=float)
        # tau = J (kp e + ki int e) + omega x (J omega)
        torque = self.inertia @ (cfg.kp * error + cfg.ki * self.integral)
        torque = torque + np.cross(rate, self.inertia @ rate)
        torque = np.clip(torque, -cfg.max_torque, cfg.max_torque)
        return torque, self.mix(total_thrust, torque)

    def mix(self, total_thrust, torque):
        """Allocate a collective thrust and body torque to four rotor speeds."""
        params = self.params
        positions = np.asarray(params.rotor_positions, dtype=float)
        matrix = np.vstack([positions[:, 1], -positions[:, 0],
                            np.asarray(params.rotor_spin, dtype=float)
                            * self._torque_per_newton()])
        solution, *_ = np.linalg.lstsq(matrix, np.asarray(torque, dtype=float), rcond=None)
        solution = solution - solution.mean()   # keep the collective thrust
        base = max(float(total_thrust), 0.0) / 4.0
        force = np.clip(base + solution, 0.0, params.thrust_max)
        return np.array([rpm_for_thrust(max(value, 1e-6), params) for value in force])

    def _torque_per_newton(self) -> float:
        from cf21b_model import thrust_from_rpm, torque_from_rpm

        hover_rpm = self.params.hover_rpm
        return float(torque_from_rpm(hover_rpm, self.params)
                     / max(thrust_from_rpm(hover_rpm, self.params), 1e-9))


def flight_config() -> ControllerConfig:
    """Gains from the flown configuration (config/ctbr_dual.yaml)."""
    return ControllerConfig(
        mass=0.0434,
        gravity=9.80665,
        max_command_thrust=0.80,
        max_tilt_rad=float(np.deg2rad(10.0)),
        max_body_rate=np.array([3.0, 3.0, 2.0]),
        position_gain=np.array([0.30, 0.30, 1.00]),
        velocity_gain=np.array([0.25, 0.25, 0.35]),
        integral_gain=np.array([0.05, 0.05, 0.02]),
        attitude_gain=np.array([8.0, 8.0, 4.0]),
        attitude_integral_gain=np.zeros(3),
        use_body_rate_feedforward=False,
    )


def make_controller(config: ControllerConfig | None = None) -> GeometricCtbrController:
    return GeometricCtbrController(config or flight_config())
