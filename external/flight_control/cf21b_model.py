"""Crazyflie 2.1 Brushless (cf21B_500) parameters, rotor model and CTBR controller.

Sources (Crazyflow / drone-models, MIT):
  * crazyflow/drones/cf21B_500.xml              geometry, motor sites, collision
  * crazyflow/drones/params.toml  [cf21B_500]   identified physical parameters

Rotor positions and spin directions come from the MJCF; the thrust / torque
curves, inertia, drag and motor dynamics come from the identified parameter
file.  Torques are computed geometrically from the rotor positions so that the
meaning of every number stays explicit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

GRAVITY = np.array([0.0, 0.0, -9.81])


@dataclass
class Cf21BParams:
    """Identified physical parameters of the Crazyflie 2.1 Brushless."""

    name: str = "cf21B_500"
    mass: float = 0.04338
    # Diagonal inertia in the body frame [kg m^2].  Two independent sources
    # exist: the identified value below (params.toml) and the MuJoCo body
    # value (2.3951e-5, 2.3951e-5, 3.2347e-5) baked into the MJCF.
    inertia: tuple = (25.0e-6, 28.0e-6, 49.0e-6)
    arm_length: float = 0.035355          # motor offset in x and y [m]
    prop_radius: float = 0.0275           # propeller radius [m]
    prop_inertia: float = 38.93e-9        # one propeller, z axis [kg m^2]
    # f_i = c0 + c1 * rpm + c2 * rpm^2   [N]
    rpm2thrust: tuple = (0.0, -3.133427287299859e-7, 4.407354891648379e-10)
    # tau_i = c0 + c1 * rpm + c2 * rpm^2 [N m]
    rpm2torque: tuple = (0.0, 1.65886356219615e-9, 2.4693477924534137e-12)
    # dOmega/dt = c1 (w_c - w) + c2 (w_c^2 - w^2)  [spin up]
    #           = c3 (w_c - w) + c4 (w_c^2 - w^2)  [spin down]
    rotor_dyn_coef: tuple = (13.996001897562685, 0.00011093207920685363,
                             5.933168530682111, 0.00031951312393561264)
    drag_matrix: tuple = ((-0.02149163, 0.0, 0.0),
                          (0.0, -0.02149163, 0.0),
                          (0.0, 0.0, -0.02359736))
    thrust_min: float = 0.02136263065537499   # N per motor
    thrust_max: float = 0.2                   # N per motor
    rpm_min: float = 0.0
    rpm_max: float = 24000.0
    # Motor sites in the body frame (FLU: x forward, y left, z up).
    rotor_positions: tuple = ((0.03536, -0.03536, 0.0),
                              (-0.03536, -0.03536, 0.0),
                              (-0.03536, 0.03536, 0.0),
                              (0.03536, 0.03536, 0.0))
    # +1 = counter clockwise seen from above (right hand rule about +z).
    rotor_spin: tuple = (-1.0, 1.0, -1.0, 1.0)
    source: str = "learnsyslab/crazyflow params.toml [cf21B_500]"

    @property
    def weight(self) -> float:
        return self.mass * 9.81

    @property
    def thrust_weight_ratio(self) -> float:
        return 4.0 * self.thrust_max / self.weight

    @property
    def hover_rpm(self) -> float:
        return rpm_for_thrust(self.thrust_max * 0.0 + self.weight / 4.0, self)

    def summary(self) -> dict:
        return {
            "name": self.name,
            "mass_kg": self.mass,
            "inertia_kg_m2": list(self.inertia),
            "arm_length_m": self.arm_length,
            "motor_radial_distance_m": float(np.linalg.norm(self.rotor_positions[0])),
            "prop_radius_m": self.prop_radius,
            "weight_n": self.weight,
            "hover_thrust_per_motor_n": self.weight / 4.0,
            "hover_rpm": self.hover_rpm,
            "thrust_max_per_motor_n": self.thrust_max,
            "max_total_thrust_n": 4.0 * self.thrust_max,
            "thrust_weight_ratio": self.thrust_weight_ratio,
            "thrust_min_per_motor_n": self.thrust_min,
            "rpm2thrust": list(self.rpm2thrust),
            "rpm2torque": list(self.rpm2torque),
            "rotor_dyn_coef": list(self.rotor_dyn_coef),
            "drag_matrix": [list(row) for row in self.drag_matrix],
            "rotor_positions_m": [list(p) for p in self.rotor_positions],
            "rotor_spin_signs": list(self.rotor_spin),
            "source": self.source,
        }


def poly(coefficients, x):
    return (coefficients[0]
            + coefficients[1] * x
            + coefficients[2] * x * x)


def thrust_from_rpm(rpm, params: Cf21BParams):
    rpm = np.asarray(rpm, dtype=float)
    return poly(params.rpm2thrust, rpm)


def torque_from_rpm(rpm, params: Cf21BParams):
    rpm = np.asarray(rpm, dtype=float)
    return poly(params.rpm2torque, rpm)


def rpm_for_thrust(thrust, params: Cf21BParams) -> float:
    """Invert the quadratic thrust curve (positive root)."""
    _, c1, c2 = params.rpm2thrust
    disc = c1 * c1 + 4.0 * c2 * thrust
    if disc < 0.0:
        raise ValueError("thrust outside the invertible range")
    return float((-c1 + np.sqrt(disc)) / (2.0 * c2))


@dataclass
class RotorState:
    """Rotor speeds of one vehicle in RPM."""

    rpm: np.ndarray = field(default_factory=lambda: np.zeros(4))

    @classmethod
    def hovering(cls, params: Cf21BParams) -> "RotorState":
        return cls(np.full(4, params.hover_rpm))


def rotor_dynamics(rpm_cmd, rpm, params: Cf21BParams) -> np.ndarray:
    """Identified first order motor model (separate spin up / spin down)."""
    c1, c2, c3, c4 = params.rotor_dyn_coef
    rpm_cmd = np.atleast_1d(np.asarray(rpm_cmd, dtype=float))
    rpm = np.atleast_1d(np.asarray(rpm, dtype=float))
    accelerating = rpm_cmd >= rpm
    linear = np.where(accelerating, c1, c3)
    quadratic = np.where(accelerating, c2, c4)
    return linear * (rpm_cmd - rpm) + quadratic * (rpm_cmd ** 2 - rpm ** 2)


def body_wrench(rpm, params: Cf21BParams, body_velocity=None):
    """Body-frame force and torque produced by the four rotors.

    ``force`` is the total thrust along +z of the body frame; ``torque``
    contains the rotor-arm moments, the propeller reaction torques and the
    propeller gyroscopic term.  Aerodynamic body drag is added when a body
    frame velocity is supplied.
    """
    rpm = np.asarray(rpm, dtype=float)
    thrust = thrust_from_rpm(rpm, params)
    torque = torque_from_rpm(rpm, params)
    positions = np.asarray(params.rotor_positions, dtype=float)
    spin = np.asarray(params.rotor_spin, dtype=float)

    force = np.array([0.0, 0.0, float(thrust.sum())])
    # tau = sum_i r_i x (f_i e_z) + s_i * tau_i e_z
    arm = np.cross(positions, np.tile([0.0, 0.0, 1.0], (4, 1)) * thrust[:, None])
    moment = arm.sum(axis=0)
    moment[2] += float((spin * torque).sum())
    if body_velocity is not None:
        force = force + np.asarray(params.drag_matrix, dtype=float) @ np.asarray(
            body_velocity, dtype=float)
    return force, moment


def rotor_gyroscopic_torque(body_rate, net_spin_rpm, rpm_dot, params: Cf21BParams):
    """Propeller gyroscopic / reaction torque in the body frame."""
    omega_rpm = net_spin_rpm * 2.0 * np.pi / 60.0
    omega_dot_rpm = rpm_dot * 2.0 * np.pi / 60.0
    jp = params.prop_inertia
    wx, wy, _ = body_rate
    return np.array([-jp * wy * omega_rpm,
                     -jp * wx * omega_rpm,
                      jp * omega_dot_rpm])


# --------------------------------------------------------------------------- #
# Quaternion helpers (scalar first: w, x, y, z -- Isaac Sim convention)
# --------------------------------------------------------------------------- #
def quat_to_matrix(q):
    w, x, y, z = np.asarray(q, dtype=float)
    n = w * w + x * x + y * y + z * z
    if n < 1e-12:
        return np.eye(3)
    s = 2.0 / n
    return np.array([
        [1 - s * (y * y + z * z), s * (x * y - w * z), s * (x * z + w * y)],
        [s * (x * y + w * z), 1 - s * (x * x + z * z), s * (y * z - w * x)],
        [s * (x * z - w * y), s * (y * z + w * x), 1 - s * (x * x + y * y)],
    ])


def matrix_to_quat(m):
    m = np.asarray(m, dtype=float)
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0.0:
        s = np.sqrt(tr + 1.0) * 2.0
        return np.array([0.25 * s,
                         (m[2, 1] - m[1, 2]) / s,
                         (m[0, 2] - m[2, 0]) / s,
                         (m[1, 0] - m[0, 1]) / s])
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        return np.array([(m[2, 1] - m[1, 2]) / s, 0.25 * s,
                         (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s])
    if m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        return np.array([(m[0, 2] - m[2, 0]) / s,
                         (m[0, 1] + m[1, 0]) / s, 0.25 * s,
                         (m[1, 2] + m[2, 1]) / s])
    s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
    return np.array([(m[1, 0] - m[0, 1]) / s,
                     (m[0, 2] + m[2, 0]) / s,
                     (m[1, 2] + m[2, 1]) / s, 0.25 * s])


def quat_conjugate(q):
    w, x, y, z = np.asarray(q, dtype=float)
    return np.array([w, -x, -y, -z])


def vee(m):
    return np.array([m[2, 1] - m[1, 2], m[0, 2] - m[2, 0], m[1, 0] - m[0, 1]]) * 0.5


def desired_rotation(acceleration, yaw, gravity=GRAVITY):
    """Rotation whose body z axis points along the requested thrust direction."""
    thrust_dir = np.asarray(acceleration, dtype=float) - np.asarray(gravity, dtype=float)
    norm = np.linalg.norm(thrust_dir)
    if norm < 1e-9:
        return np.eye(3)
    b3 = thrust_dir / norm
    x_ref = np.array([np.cos(yaw), np.sin(yaw), 0.0])
    b2 = np.cross(b3, x_ref)
    b2_norm = np.linalg.norm(b2)
    if b2_norm < 1e-6:
        x_ref = np.array([1.0, 0.0, 0.0])
        b2 = np.cross(b3, x_ref)
        b2_norm = np.linalg.norm(b2)
    b2 = b2 / b2_norm
    b1 = np.cross(b2, b3)
    return np.column_stack((b1, b2, b3))


@dataclass
class CtbrController:
    """Cascaded position/velocity -> attitude -> body rate -> rotor RPM loop."""

    params: Cf21BParams = field(default_factory=Cf21BParams)
    k_position: tuple = (5.0, 5.0, 6.0)
    k_velocity: tuple = (4.2, 4.2, 5.0)
    k_attitude: float = 60.0
    k_rate: float = 12.0
    max_tilt_deg: float = 55.0
    kp_rotor: float = 900.0
    integral_limit: float = 0.35
    mass_error: float = 1.0

    def __post_init__(self):
        self._integral = np.zeros(3)

    def reset(self):
        self._integral = np.zeros(3)

    def collective_thrust_and_torque(self, position, velocity, quat, body_rate,
                                     reference, dt: float):
        p = self.params
        rot = quat_to_matrix(quat)
        error_p = np.asarray(reference["p"], dtype=float) - np.asarray(position, dtype=float)
        error_v = np.asarray(reference["v"], dtype=float) - np.asarray(velocity, dtype=float)
        self._integral = np.clip(self._integral + error_p * dt,
                                 -self.integral_limit, self.integral_limit)
        acc_des = (np.asarray(reference["a"], dtype=float)
                   + np.asarray(self.k_position) * error_p
                   + np.asarray(self.k_velocity) * error_v
                   + 0.15 * self._integral)
        # keep the requested acceleration inside what the vehicle can produce
        max_tilt = np.deg2rad(self.max_tilt_deg)
        thrust_dir = acc_des - GRAVITY
        tilt = np.arccos(np.clip(thrust_dir[2] / max(np.linalg.norm(thrust_dir), 1e-9),
                                 -1.0, 1.0))
        if tilt > max_tilt:
            scale = np.tan(max_tilt) / max(np.tan(tilt), 1e-9)
            acc_des[:2] *= scale
        rotation_des = desired_rotation(acc_des, reference.get("yaw", 0.0))
        thrust_vector = acc_des - GRAVITY
        max_total_thrust = 4.0 * p.thrust_max
        total_thrust = float(np.clip(p.mass * self.mass_error * np.linalg.norm(thrust_vector),
                                     0.0, max_total_thrust))

        error_rot = vee(rotation_des.T @ rot - rot.T @ rotation_des)
        rate_des = -self.k_attitude * error_rot
        feedforward = np.asarray(reference.get("body_rate", np.zeros(3)), dtype=float)
        rate_des = rate_des + feedforward
        rate_des = np.clip(rate_des, -12.0, 12.0)
        error_rate = rate_des - np.asarray(body_rate, dtype=float)
        inertia = np.diag(np.asarray(p.inertia, dtype=float))
        torque = inertia @ (self.k_rate * error_rate)
        torque += np.cross(body_rate, inertia @ body_rate) * 0.0
        rpm_cmd = self._mixer(total_thrust, torque)
        return total_thrust, torque, rpm_cmd

    def _mixer(self, total_thrust, torque):
        """Map a collective thrust and body torque to four rotor speeds."""
        positions = np.asarray(self.params.rotor_positions, dtype=float)
        arm = positions[:, :2]
        # tau_x = sum ry_i f_i ; tau_y = -sum rx_i f_i
        allocated = np.zeros(4)
        # least squares allocation of the three torque components
        matrix = np.vstack([arm[:, 1], -arm[:, 0], np.asarray(self.params.rotor_spin)])
        torques = np.asarray(torque, dtype=float)
        # approximate propeller torque share so that yaw allocation has a scale
        hover_rpm = max(self.params.hover_rpm, 1.0)
        hover = thrust_from_rpm(hover_rpm, self.params)
        hover_torque = torque_from_rpm(hover_rpm, self.params)
        km_over_kf = hover_torque / max(hover, 1e-9)
        matrix[2] = matrix[2] * km_over_kf
        solution, *_ = np.linalg.lstsq(matrix, torques, rcond=None)
        # Remove the common mode: it is in the null space of the torque map and
        # would otherwise change the commanded collective thrust.
        solution = solution - solution.mean()
        allocated += solution
        base = max(total_thrust, 0.0) / 4.0
        force = np.clip(base + allocated, 0.0, self.params.thrust_max)
        rpm = np.array([rpm_for_thrust(max(f, 1e-6), self.params) for f in force])
        return rpm


def torus_mesh_points(center, axis, major_radius, minor_radius,
                      n_major=64, n_minor=14):
    """Return (points, face_vertex_counts, face_vertex_indices) for a torus."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(helper, axis)) > 0.9:
        helper = np.array([1.0, 0.0, 0.0])
    u = np.cross(axis, helper)
    u = u / np.linalg.norm(u)
    v = np.cross(axis, u)
    points = []
    for i in range(n_major):
        theta = 2.0 * np.pi * i / n_major
        radial = np.cos(theta) * u + np.sin(theta) * v
        ring_center = np.asarray(center, dtype=float) + major_radius * radial
        for j in range(n_minor):
            phi = 2.0 * np.pi * j / n_minor
            points.append(ring_center
                          + minor_radius * np.cos(phi) * radial
                          + minor_radius * np.sin(phi) * axis)
    counts = []
    indices = []
    for i in range(n_major):
        for j in range(n_minor):
            i2 = (i + 1) % n_major
            j2 = (j + 1) % n_minor
            counts.append(4)
            indices.extend([i * n_minor + j,
                            i2 * n_minor + j,
                            i2 * n_minor + j2,
                            i * n_minor + j2])
    return points, counts, indices
