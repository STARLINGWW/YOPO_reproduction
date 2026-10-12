"""Coverage-aware benchmark aggregation; missing and duplicate runs stay visible."""
from collections import Counter,defaultdict
import numpy as np
from .metrics import wilson_interval,percentiles

TERMINAL={'success','collision','timeout','crashed','out_of_map'}
FIELDS=['path_length_m','mean_net_clearance_m','min_net_clearance_m','tracking_rmse_m',
        'reference_curve_squared_jerk_integral_m2_per_s5','measured_raw_fd_squared_jerk_integral_m2_per_s5',
        'max_speed_mps','real_time_factor','motor_saturation_fraction']


def aggregate(protocol,records):
    groups=defaultdict(list)
    for episode in protocol['episodes']:
        task=protocol['tasks'][episode['task_index']]
        groups[(episode['model'],task['condition'],episode['speed_mps'])].append(episode)
    summaries=[]
    for key,episodes in sorted(groups.items()):
        for subset in ['all30','paper_first10']:
            expected=[e for e in episodes if subset=='all30' or e['paper_first10']]
            found=[records[e['id']] for e in expected if e['id'] in records]
            if any(r['status'] not in TERMINAL for r in found):raise ValueError('Nonterminal record cannot be counted')
            counts=Counter(r['status'] for r in found);success=counts['success'];n=len(found);missing=len(expected)-n
            row={'model':key[0],'condition':key[1],'speed_mps':key[2],'subset':subset,
                 'expected':len(expected),'completed':n,'missing':missing,'complete':missing==0,
                 'outcomes':dict(counts),'success_rate_among_completed':success/n if n else None,
                 'failure_rates_among_completed':{status:counts[status]/n if n else None for status in sorted(TERMINAL-{'success'})},
                 'wilson95_among_completed':wilson_interval(success,n),
                 'possible_final_success_rate_bounds':[success/len(expected),(success+missing)/len(expected)]}
            for scope,selected in [('all_attempts',found),('successful_only',[r for r in found if r['status']=='success'])]:
                metrics={}
                for field in FIELDS:
                    values=[r.get('metrics',{}).get(field) for r in selected]
                    values=[v for v in values if v is not None and np.isfinite(v)]
                    metrics[field]={'n':len(values),'mean':float(np.mean(values)) if values else None}
                row[scope]=metrics
            latency=[v for record in found for v in record.get('latency_samples_ms',[])]
            row['pooled_end_to_end_wall_ms']=percentiles(latency)
            row['latency_sample_count']=len(latency)
            summaries.append(row)
    completed=sum(e['id'] in records for e in protocol['episodes']);expected=len(protocol['episodes'])
    return {'status':'outcome_coverage_complete' if completed==expected else 'incomplete','expected_episodes':expected,
            'completed_episodes':completed,'missing_episodes':expected-completed,'groups':summaries,
            'statistics_note':'Outcome coverage is not full measurement or goal completion. Failures remain in success denominators; missing runs are unknown. Wilson intervals describe completed trials, not missing coverage. Path/safety/smoothness are reported both across attempts and conditional on success.'}
