"""Quintic boundary-value problem and exact jerk integral.

State convention: each row is one spatial axis, columns are p/v/a.
The matrices follow the pinned upstream qp_generator.cpp. Comments in that
source refer to snap, but its third-derivative expression is a jerk integral.
"""
import math
import numpy as np


def matrices(duration):
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    matrix = np.zeros((6, 6), dtype=np.float64)
    for derivative in range(3):
        matrix[2 * derivative, derivative] = math.factorial(derivative)
        for power in range(derivative, 6):
            matrix[2 * derivative + 1, power] = (math.factorial(power) / math.factorial(power - derivative)
                                                  * duration ** (power - derivative))
    selection = np.zeros((6, 6))
    selection[[0, 2, 4, 1, 3, 5], np.arange(6)] = 1.
    mapping = np.linalg.solve(matrix, selection)
    hessian = np.zeros((6, 6))
    for i in range(3, 6):
        for j in range(3, 6):
            hessian[i, j] = (math.factorial(i) / math.factorial(i - 3)
                             * math.factorial(j) / math.factorial(j - 3)
                             * duration ** (i + j - 5) / (i + j - 5))
    return mapping, hessian, mapping.T @ hessian @ mapping


class Quintic:
    def __init__(self, start, end, duration):
        self.start, self.end = np.asarray(start, dtype=float), np.asarray(end, dtype=float)
        if self.start.shape != (3, 3) or self.end.shape != (3, 3):
            raise ValueError("start/end must be axes x [p,v,a]")
        if not np.isfinite(self.start).all() or not np.isfinite(self.end).all():
            raise ValueError("non-finite boundary")
        self.duration = duration
        self.mapping, self.hessian, self.cost_matrix = matrices(duration)
        self.boundary = np.concatenate([self.start, self.end], axis=1)
        self.coefficients = self.boundary @ self.mapping.T

    def evaluate(self, times, derivative=0):
        if derivative not in range(6):
            raise ValueError("derivative outside 0..5")
        times = np.asarray(times, dtype=float)
        basis = np.stack([np.zeros_like(times) if i < derivative else
                          math.factorial(i) / math.factorial(i - derivative) * times ** (i - derivative)
                          for i in range(6)], axis=-1)
        return basis @ self.coefficients.T

    def jerk_integral(self):
        return float(np.einsum("ai,ij,aj->", self.boundary, self.cost_matrix, self.boundary))

    def end_gradient(self):
        return (2 * self.boundary @ self.cost_matrix)[:, 3:]
