from pathlib import Path
import json
import sys
import unittest
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from depth_quality import assess_depth


class DepthQualityTests(unittest.TestCase):
    def test_actual_silhouette_keeps_raw_error_and_classifies_subpixel_limit(self):
        folder=ROOT/'tests/fixtures/depth_edge'
        pose=json.loads((folder/'pose.json').read_text(encoding='utf-8'))
        scene=json.loads((folder/'scene.json').read_text(encoding='utf-8'))
        q=np.array(pose['quaternion']);rotation=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
        rng=np.random.default_rng(817);pixels=np.column_stack([rng.integers(4,156,128),rng.integers(4,86,128)])
        result=assess_depth(np.load(folder/'depth.npy'),np.array(pose['position']),rotation,scene,pixels,4700)
        self.assertEqual(result['status'],'passed')
        self.assertGreater(result['max_m'],4.)
        self.assertEqual(len(result['ambiguous_pixels']),1)
        self.assertEqual(result['unresolved_pixels'],[])
        self.assertLess(result['ambiguous_pixels'][0]['closest_subpixel_error_m'],.001)

    def test_wrong_pose_or_depth_is_not_excused_as_an_edge(self):
        scene={'extent_m':80.,'trees':[],'shrubs':[]}
        result=assess_depth(np.full((90,160),2.,np.float32),np.array([0.,0.,2.]),np.eye(3),scene,np.array([[80,70],[90,80]]),0)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(len(result['unresolved_pixels']),2)


if __name__=='__main__':unittest.main()
