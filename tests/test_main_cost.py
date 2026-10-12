import unittest
import numpy as np
from yopo_repro.main_cost import CostConfig,cost_and_gradient,boundary_gradient,upstream_network_gradient


class Plane:
    resolution=.2
    def query(self,positions):
        return positions[:,2].copy(),np.tile([0.,0.,1.],(len(positions),1)),np.ones(len(positions),dtype=bool)


class MainCostTests(unittest.TestCase):
    def test_raw_gradient_against_finite_differences_with_smooth_distance(self):
        rng=np.random.default_rng(23)
        start=rng.normal(0,.2,(2,3,3));start[:,2,0]+=2
        end=start.copy();end[:,0,0]+=4;end[:,2,0]+=.3
        goals=start[:,:,0]+[8.,0.,0.]
        lower,upper=np.full(3,-100.),np.full(3,100.)
        value,gradient,_=cost_and_gradient(start,end,goals,Plane(),lower,upper)
        # Float32 spatial intermediates in original C++ need a finite step
        # larger than float roundoff; field itself is smooth for this check.
        eps=.002;numerical=np.zeros_like(end)
        for batch in range(2):
            for axis in range(3):
                for derivative in range(3):
                    plus,minus=end.copy(),end.copy()
                    plus[batch,axis,derivative]+=eps;minus[batch,axis,derivative]-=eps
                    p=cost_and_gradient(start,plus,goals,Plane(),lower,upper)[0]
                    m=cost_and_gradient(start,minus,goals,Plane(),lower,upper)[0]
                    numerical[batch,axis,derivative]=(p[batch]-m[batch])/(2*eps)
        np.testing.assert_allclose(gradient,numerical,rtol=.004,atol=3e-6)

    def test_boundary_stencil_and_asymmetric_clip(self):
        lower=np.array([0.,0.,0.]);upper=np.array([10.,10.,10.])
        points=np.array([[-1,5,5],[11,5,5],[5,-1,5],[5,5,11]],float)
        np.testing.assert_allclose(boundary_gradient(points,lower,upper,.2),[[1,0,0],[-1,0,0],[0,1,0],[0,0,-1]],atol=1e-12)
        np.testing.assert_array_equal(upstream_network_gradient(np.array([-5.,.5,5.])),[-5.,.5,1.])

    def test_batch_matches_individual_evaluation(self):
        start=np.zeros((2,3,3));start[:,2,0]=2
        end=start.copy();end[:,0,0]=[3.,5.]
        goal=np.tile([8.,0.,2.],(2,1))
        cost,gradient,_=cost_and_gradient(start,end,goal,Plane(),[-10]*3,[20]*3)
        for i in range(2):
            c,g,_=cost_and_gradient(start[i:i+1],end[i:i+1],goal[i:i+1],Plane(),[-10]*3,[20]*3)
            np.testing.assert_allclose(cost[i],c[0]);np.testing.assert_allclose(gradient[i],g[0])


if __name__=='__main__':unittest.main()
