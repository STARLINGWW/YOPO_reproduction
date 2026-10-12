import tempfile
from pathlib import Path
import unittest
import numpy as np
from yopo_repro.maps import VoxelSDF,pointcloud_esdf,surface_points,write_ply


class MapTests(unittest.TestCase):
    def test_axis_order_and_edge_gradient_on_linear_field(self):
        xyz=np.indices((7,8,9),dtype=float)
        field=.2*(xyz[0]+2*xyz[1]-3*xyz[2])
        sdf=VoxelSDF(field,[-1,-2,-3],.2)
        indices=np.array([[0,0,0],[3,4,5],[6,7,8]])
        points=np.array([-1,-2,-3])+(indices+.5)*.2
        values,grad,valid=sdf.query(points)
        self.assertTrue(valid.all())
        np.testing.assert_allclose(grad,np.tile([1,2,-3],(3,1)),atol=1e-12)
        np.testing.assert_allclose(values,field[tuple(indices.T)],atol=1e-12)
        # Upstream static_cast<int64_t> truncates toward zero. Retain its
        # near-negative-boundary behavior rather than silently "fixing" it.
        self.assertTrue(sdf.query([[-1.01,-2,-3]])[2][0])
        self.assertFalse(sdf.query([[-1.21,-2,-3]])[2][0])
        strict=VoxelSDF(field,[-1,-2,-3],.2,index_mode="floor")
        self.assertFalse(strict.query([[-1.01,-2,-3]])[2][0])

    def test_occupancy_signed_values_and_ply_payload(self):
        scene={"extent_m":2.,"tree_sides":16,"trees":[[0,0,.3,1.]],"shrubs":[]}
        points=surface_points(scene,.1)
        values,occupancy,origin,upper=pointcloud_esdf(points,.2)
        self.assertTrue((values[occupancy]<0).all())
        self.assertTrue((values[~occupancy]>0).all())
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"cloud.ply";write_ply(p,points)
            blob=p.read_bytes().split(b"end_header\n",1)[1]
            restored=np.frombuffer(blob,dtype="<f4").reshape(-1,3)
            np.testing.assert_array_equal(points,restored)


if __name__=="__main__":
    unittest.main()
