from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from yopo_sim.trajectory_buffer import TrajectoryBuffer


def add(buffer,start,receipt,latency):
    t=np.array([0.,.5,1.]);p=np.column_stack([t**5,np.zeros(3),np.ones(3)*3])
    v=np.column_stack([5*t**4,np.zeros((3,2))]);a=np.column_stack([20*t**3,np.zeros((3,2))])
    return buffer.submit(start,t,p,v,a,np.zeros(3),receipt,latency)


def test_wall_latency_not_hidden_by_slow_simulation():
    b=TrajectoryBuffer();assert add(b,0.,.01,.2)
    assert b.sample(.19) is None
    np.testing.assert_allclose(b.sample(.2)['position'],[.2**5,0,3],atol=1e-10)


def test_latest_command_and_expiry():
    b=TrajectoryBuffer();add(b,0.,.01,.01);add(b,.1,.11,.01)
    b.sample(.12);assert b.last_start==.1
    assert not add(b,.05,.15,.01)
    assert b.sample(1.11) is None
    assert b.stats['expired_in_control']==1


def test_expired_on_arrival_and_stop():
    b=TrajectoryBuffer();assert not add(b,0.,.2,1.2)
    add(b,1.,1.,.1);b.sample(1.2);b.stop(1.3);assert b.sample(1.3) is None
    assert not add(b,1.25,1.4,.1)


def test_quintic_reference_derivatives():
    b=TrajectoryBuffer();add(b,0.,0.,0.)
    for t in [.1,.4,.7,.99]:
        r=b.sample(t)
        np.testing.assert_allclose(r['velocity'],[5*t**4,0,0],atol=1e-9)
        np.testing.assert_allclose(r['acceleration'],[20*t**3,0,0],atol=1e-8)


def test_later_plan_start_does_not_double_charge_observation_age():
    b=TrajectoryBuffer();t=np.array([0.,1.]);p=np.array([[0.,0.,3.],[1.,0.,3.]])
    v=np.array([[1.,0.,0.],[1.,0.,0.]]);a=np.zeros((2,3))
    assert b.submit(1.1,t,p,v,a,np.zeros(2),1.11,.2,observation_start=1.)
    assert b.sample(1.199) is None
    np.testing.assert_allclose(b.sample(1.2)['position'],[.1,0.,3.],atol=1e-10)
    assert b.active.observation_start==1. and b.active.start==1.1
