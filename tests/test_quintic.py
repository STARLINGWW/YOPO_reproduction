import unittest
import numpy as np
from yopo_repro.quintic import Quintic


class QuinticChecks(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(4)
        self.start, self.end = rng.normal(size=(3, 3)), rng.normal(size=(3, 3))
        self.duration = 8 / 6

    def test_boundary_conditions(self):
        q = Quintic(self.start, self.end, self.duration)
        for derivative in range(3):
            np.testing.assert_allclose(q.evaluate(0., derivative), self.start[:, derivative], atol=1e-12)
            np.testing.assert_allclose(q.evaluate(self.duration, derivative), self.end[:, derivative], atol=1e-11)

    def test_jerk_integral_against_gaussian_quadrature(self):
        q = Quintic(self.start, self.end, self.duration)
        points, weights = np.polynomial.legendre.leggauss(8)
        times = (points + 1) * self.duration / 2
        integral = np.sum(weights * np.sum(q.evaluate(times, 3) ** 2, axis=1)) * self.duration / 2
        self.assertAlmostEqual(q.jerk_integral(), integral, places=8)

    def test_gradient_against_central_difference(self):
        q = Quintic(self.start, self.end, self.duration)
        numerical = np.zeros((3, 3))
        eps = 1e-5
        for axis in range(3):
            for derivative in range(3):
                plus, minus = self.end.copy(), self.end.copy()
                plus[axis, derivative] += eps
                minus[axis, derivative] -= eps
                numerical[axis, derivative] = (Quintic(self.start, plus, self.duration).jerk_integral()
                                               - Quintic(self.start, minus, self.duration).jerk_integral()) / (2 * eps)
        np.testing.assert_allclose(q.end_gradient(), numerical, rtol=1e-7, atol=1e-6)

    def test_zero_jerk_for_constant_velocity(self):
        initial = np.array([[0., 1., 0.], [0., -2., 0.], [2., .5, 0.]])
        final = initial.copy()
        final[:, 0] += initial[:, 1] * self.duration
        q = Quintic(initial, final, self.duration)
        self.assertLess(abs(q.jerk_integral()), 1e-9)


if __name__ == "__main__":
    unittest.main()
