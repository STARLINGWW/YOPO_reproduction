from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from yopo_repro.policy import build_policy,prepare_observation,GuidanceCost,MapBank
from yopo_repro.main_cost import CostConfig
from yopo_repro.dataset import ForestDataset

ROOT=Path(__file__).resolve().parents[1]

class Plane:
    resolution=.2
    def query(self,p):return p[:,2].copy(),np.tile([0.,0.,1.],(len(p),1)),np.ones(len(p),bool)


class PolicyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.manual_seed(11)
        with patch('torch.load',side_effect=AssertionError('No checkpoint may be loaded during initialization')):
            cls.policy,cls.profile,cls.cfg=build_policy('cpu')

    def test_primitive_observation_order_matches_original_loop(self):
        obs=np.random.default_rng(5).normal(size=(4,9)).astype(np.float32)
        normalized=obs.copy();normalized[:,:3]/=self.policy.lattice_space.vel_max;normalized[:,3:6]/=self.policy.lattice_space.acc_max
        expected=np.empty((4,9,3,5),np.float32);identifier=0
        for i in range(2,-1,-1):
            for j in range(4,-1,-1):
                rotation=self.policy.lattice_primitive.getRotation(identifier)
                for start in [0,3,6]:expected[:,start:start+3,i,j]=normalized[:,start:start+3]@rotation
                identifier+=1
        np.testing.assert_allclose(prepare_observation(obs,self.policy),expected,atol=1e-7)

    def test_world_body_guidance_chain_against_numerical_derivative(self):
        bank=MapBank.__new__(MapBank);bank.config=CostConfig();bank.maps={0:(Plane(),np.full(3,-100.),np.full(3,100.))}
        p=np.array([[2.,-1.,3.]]);rot=Rotation.from_euler('ZYX',[[.5,.1,-.1]]).as_matrix()
        obs=np.array([[2.,.2,-.1,0.,.1,0.,1.,0.,0.]]);ids=np.array([0])
        values=np.array([[[4.,2.,0., .5,0.,0., .1,0.,0.], [3.,1.,0., -.5,.2,0., .2,0.,0.]]],dtype=np.float32)
        end=torch.tensor(values,requires_grad=True)
        weights=np.array([[.5,1.5]])
        cost=GuidanceCost.apply(end,p,rot,obs,ids,bank)
        (cost*torch.from_numpy(weights)).sum().backward()
        numerical=np.zeros_like(values);eps=.002
        for candidate in range(2):
            for component in range(9):
                plus,minus=values.copy(),values.copy();plus[0,candidate,component]+=eps;minus[0,candidate,component]-=eps
                c1=bank.evaluate(plus,p,rot,obs,ids)[0];c2=bank.evaluate(minus,p,rot,obs,ids)[0]
                numerical[0,candidate,component]=np.sum((c1-c2)*weights)/(2*eps)
        np.testing.assert_allclose(end.grad.numpy(),numerical,rtol=.006,atol=4e-6)

    @unittest.skipUnless((ROOT/'datasets/smoke_v1/dataset.json').exists(),'real smoke data required')
    def test_validation_fixed_training_augmented(self):
        val=ForestDataset(ROOT/'datasets/smoke_v1','valid',self.cfg,0)
        val.epoch=0;first=val[0];val.epoch=99;later=val[0]
        for x,y in zip(first,later):np.testing.assert_array_equal(x,y)
        train=ForestDataset(ROOT/'datasets/smoke_v1','train',self.cfg,0)
        train.epoch=0;a=train[0];train.epoch=1;b=train[0]
        np.testing.assert_array_equal(a[0],b[0]);self.assertFalse(np.array_equal(a[3],b[3]))
        self.assertTrue(0<=a[0].min()<=a[0].max()<=1)


if __name__=='__main__':unittest.main()
