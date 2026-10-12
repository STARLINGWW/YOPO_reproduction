"""End-state rehearsal of the aggregation math at the real 1800-episode scale."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_eval.aggregate import aggregate


def protocol():
    return json.loads((ROOT/'benchmarks/protocol_v1/protocol.json').read_text(encoding='utf-8'))


def test_full_coverage_reports_complete_and_per_subset_counts():
    data = protocol()
    records = {episode['id']:{'status':'success','metrics':{'path_length_m':50.,'min_net_clearance_m':1.,
               'mean_net_clearance_m':1.2,'tracking_rmse_m':.1,'reference_curve_squared_jerk_integral_m2_per_s5':10.,
               'measured_raw_fd_squared_jerk_integral_m2_per_s5':20.,'max_speed_mps':2.,'real_time_factor':.4,
               'motor_saturation_fraction':0.},'latency_samples_ms':[100.,110.]} for episode in data['episodes']}
    result = aggregate(data,records)
    assert result['status']=='outcome_coverage_complete'
    assert result['expected_episodes']==1800 and result['completed_episodes']==1800 and result['missing_episodes']==0
    assert len(result['groups'])==6*2*5*2  # 6 models x 2 densities x 5 speeds x (all30, paper_first10)
    for row in result['groups']:
        if row['subset']=='all30':
            assert row['expected']==30 and row['completed']==30 and row['missing']==0
            assert row['wilson95_among_completed'] is not None
        else:
            assert row['expected']==10 and row['completed']==10
        assert row['success_rate_among_completed']==1.0
        assert row['failure_rates_among_completed']['collision']==0.0
        assert row['pooled_end_to_end_wall_ms']['p50']==105.0
        assert row['all_attempts']['path_length_m']['n']==row['completed']


def test_one_missing_episode_changes_the_bounds_not_the_success_count():
    data = protocol()
    records = {episode['id']:{'status':'success','metrics':{}} for episode in data['episodes']}
    dropped = data['episodes'][7]['id']
    records.pop(dropped)
    result = aggregate(data,records)
    assert result['status']=='incomplete' and result['missing_episodes']==1
    assert result['completed_episodes']==1799
    affected = [row for row in result['groups'] if row['missing']==1]
    # the dropped episode sits in one all-30 group and in its first-10 subset
    assert sorted(row['subset'] for row in affected)==['all30','paper_first10']
    all30 = next(row for row in affected if row['subset']=='all30')
    first10 = next(row for row in affected if row['subset']=='paper_first10')
    assert all30['possible_final_success_rate_bounds']==[29/30,1.0]
    assert first10['possible_final_success_rate_bounds']==[9/10,1.0]
    untouched = [row for row in result['groups'] if row['subset']=='all30' and row['missing']==0]
    assert len(untouched)==59
    assert all(row['possible_final_success_rate_bounds']==[1.0,1.0] for row in untouched)


def test_mixed_outcomes_keep_failures_in_the_denominator():
    data = protocol()
    records = {}
    for index,episode in enumerate(data['episodes']):
        records[episode['id']] = {'status':'success' if index%3 else 'collision','metrics':{}}
    result = aggregate(data,records)
    for row in result['groups']:
        outcomes = row['outcomes']
        total = sum(outcomes.values())
        assert total==row['completed']
        failure_total = sum(v for v in row['failure_rates_among_completed'].values() if v)
        assert abs(row['success_rate_among_completed']+failure_total-1.0)<1e-9
