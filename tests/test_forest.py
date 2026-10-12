import unittest
import numpy as np
from yopo_repro.forest import generate, ray_depth, signed_distance


class ForestTests(unittest.TestCase):
    def test_generation_is_reproducible_and_counts_density(self):
        a, b = generate(10), generate(10)
        self.assertEqual(a, b)
        self.assertEqual(len(a["trees"]), round(80*80/30))
        self.assertGreater(len(a["shrubs"]), 0)
        self.assertNotEqual(a, generate(11))

    def test_cylinder_side_cap_and_miss(self):
        scene = {"extent_m":80., "trees":[[0.,0.,1.,4.]], "shrubs":[]}
        np.testing.assert_allclose(ray_depth([-3,0,2], [[1,0,0],[0,1,0]], scene), [2,20])
        np.testing.assert_allclose(ray_depth([0,0,6], [[0,0,-1]], scene), [2])
        self.assertAlmostEqual(signed_distance([0,0,2], scene), -1.)

    def test_box_parallel_rays_and_ground(self):
        scene = {"extent_m":80., "trees":[], "shrubs":[[0.,0.,1.,2.,2.,2.]]}
        np.testing.assert_allclose(ray_depth([-3,0,1], [[1,0,0]], scene), [2])
        np.testing.assert_allclose(ray_depth([-3,3,1], [[1,0,0],[0,0,-1]], scene), [20,1])

    def test_polygon_matches_explicit_prism_faces(self):
        scene = {"extent_m":80., "tree_sides":4, "trees":[[0.,0.,1.,4.]], "shrubs":[]}
        # Four vertices at cardinal directions: at y=.5 the front x is -.5.
        np.testing.assert_allclose(ray_depth([-3,.5,2], [[1,0,0],[0,0,-1]], scene), [2.5,2])
        np.testing.assert_allclose(ray_depth([0,0,6], [[0,0,-1]], scene), [2])


if __name__ == "__main__":
    unittest.main()
