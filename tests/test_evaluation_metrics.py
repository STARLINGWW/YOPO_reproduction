from pathlib import Path
import sys
import numpy as np
import pytest
from scipy.stats import binomtest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from yopo_eval.metrics import wilson_interval,flight_metrics


def test_wilson_matches_independent_scipy_implementation():
    assert wilson_interval(0,0) is None
    for total in [10,30,90]:
        for successes in range(total+1):
            expected=binomtest(successes,total).proportion_ci(confidence_level=.95,method='wilson')
            np.testing.assert_allclose(wilson_interval(successes,total),[expected.low,expected.high],atol=1e-14)


def fixture():
    log=np.zeros((3,30));log[:,0]=[0,.1,1.];log[:,1]=log[:,0];log[:,4]=1.;log[:,7]=1.
    log[:,11]=log[:,1];log[:,14]=1.;log[:,17]=[1,1,3];log[:,27]=2.
    source={'status':'success','vehicle':{'collision_envelope_radius_m':.3},'events':[]}
    return log,source


def test_time_weighted_clearance_and_analytic_jerk():
    log,source=fixture();report=flight_metrics(log,np.empty((0,12)),np.empty((0,4)),source,[])
    assert report['mean_net_clearance_m']==pytest.approx(1.9)
    assert report['reference_curve_squared_jerk_integral_m2_per_s5']==pytest.approx(4.)
    assert report['measured_raw_fd_squared_jerk_integral_m2_per_s5']==pytest.approx(0.)
    assert report['path_length_m']==pytest.approx(1.)
    assert report['planner_and_publish_wall_ms'] is None


def test_missing_wall_delay_cannot_pass_application_audit():
    log,source=fixture();source['events']=[{'event':'trajectory_applied','t':.1,'capture_t':0.,'available_t':.2,'wall_latency_s':.2}]
    with pytest.raises(AssertionError):flight_metrics(log,np.empty((0,12)),np.empty((0,4)),source,[])
