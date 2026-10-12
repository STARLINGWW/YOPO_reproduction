"""Build paper comparison tables and the success-vs-speed figure from evidence.

Every number comes from the coverage-aware aggregate (artifacts/benchmark_summary/
summary.json) or from the expert comparison JSON. Missing coverage is never
interpolated: incomplete cells are drawn with open markers and listed in the
manifest so the incompleteness cannot be mistaken for a finished result.
"""
from pathlib import Path
import argparse
import csv
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import sha256_file,write_json_atomic

DENSITY_LABEL = {1/30:'sparse',1/20:'dense'}
MODEL_ORDER = ['yopo_seed0','yopo_seed1','yopo_seed2','expert_50_steps','topotraj','agile_autonomy','mppi_reference17']


def dig(value,*keys,default=None):
    for key in keys:
        if not isinstance(value,dict) or key not in value:return default
        value = value[key]
    return value


def display_path(path):
    resolved = Path(path).resolve()
    try:return str(resolved.relative_to(ROOT).as_posix())
    except ValueError:return str(resolved.as_posix())


def load_groups(summary,subset='all30'):
    return [row for row in summary.get('groups',[]) if row['subset']==subset]


def write_csv(path,header,rows):
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer = csv.writer(handle);writer.writerow(header)
        for row in rows:writer.writerow(['' if v is None else v for v in row])


def table_two(summary,outdir):
    rows = [];markdown = ['# Table II 对照（4 m/s，两档密度）','',
        '来源：`artifacts/benchmark_summary/summary.json`（覆盖感知汇总，缺失不当作成功）。阶段分解为补充证据。','',
        '| 模型 | 密度 | 完成/期望 | 成功率 | 总延迟P50(ms) | 总延迟P95(ms) | 平均净空(m) | 最小净空(m) | 参考jerk积分 | 实测jerk积分 | 路径(m) |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in load_groups(summary,'all30'):
        if row['speed_mps']!=4:continue
        latency = row.get('pooled_end_to_end_wall_ms') or {}
        attempts = row.get('all_attempts',{})
        def mean(field):return dig(attempts,field,'mean')
        values = {'model':row['model'],'condition':row['condition'],'completed':row['completed'],'expected':row['expected'],
                  'success_rate_among_completed':row['success_rate_among_completed'],
                  'end_to_end_p50_ms':latency.get('p50'),'end_to_end_p95_ms':latency.get('p95'),
                  'mean_net_clearance_m':mean('mean_net_clearance_m'),'min_net_clearance_m':mean('min_net_clearance_m'),
                  'reference_jerk_integral':mean('reference_curve_squared_jerk_integral_m2_per_s5'),
                  'measured_jerk_integral':mean('measured_raw_fd_squared_jerk_integral_m2_per_s5'),
                  'path_length_m':mean('path_length_m'),'missing':row['missing']}
        rows.append(values)
        markdown.append('| %s | %s | %d/%d | %s | %s | %s | %s | %s | %s | %s | %s |'%(values['model'],values['condition'],
            values['completed'],values['expected'],
            'n/a' if values['success_rate_among_completed'] is None else '%.3f'%values['success_rate_among_completed'],
            fmt(values['end_to_end_p50_ms']),fmt(values['end_to_end_p95_ms']),fmt(values['mean_net_clearance_m']),
            fmt(values['min_net_clearance_m']),fmt(values['reference_jerk_integral']),fmt(values['measured_jerk_integral']),
            fmt(values['path_length_m'])))
    markdown += ['','阶段分解（mapping/front/back/total）需要逐 episode 的规划遥测；本表的分解列来自补充扫描，正式口径仍以汇总 JSON 的准入校验为准。']
    (outdir/'table_ii_latency_safety_smoothness.md').write_text('\n'.join(markdown)+'\n',encoding='utf-8')
    write_csv(outdir/'table_ii_latency_safety_smoothness.csv',
              ['model','condition','completed','expected','success_rate_among_completed','end_to_end_p50_ms',
               'end_to_end_p95_ms','mean_net_clearance_m','min_net_clearance_m','reference_jerk_integral',
               'measured_jerk_integral','path_length_m','missing'],
              [[v.get(k) for k in ['model','condition','completed','expected','success_rate_among_completed',
               'end_to_end_p50_ms','end_to_end_p95_ms','mean_net_clearance_m','min_net_clearance_m',
               'reference_jerk_integral','measured_jerk_integral','path_length_m','missing']] for v in rows])
    return rows


def fmt(value,digits=4):
    return 'n/a' if value is None else ('%.*f'%(digits,value))


def table_one(outdir):
    candidates = sorted((ROOT/'artifacts/expert').glob('network_comparison_*.json'))
    if not candidates:
        return {'status':'pending','reason':'no expert comparison JSON present yet'}
    entries = {}
    for path in candidates:
        data = json.loads(path.read_text(encoding='utf-8'))
        kind = dig(data,'checkpoint','kind') or path.stem.replace('network_comparison_','')
        partial = '_limit' in path.stem
        samples = int(data.get('samples') or 0)
        previous = entries.get(kind)
        if previous and (previous['partial']<partial or (previous['partial']==partial and previous['samples']>=samples)):
            continue
        entries[kind] = {'path':str(path.relative_to(ROOT).as_posix()),'sha256':sha256_file(path),
                         'data':data,'samples':samples,'partial':partial}
    lines = ['# Table I 对照（专家50步 vs 随机初始化 vs 自训练网络）','',
             '来源：`artifacts/expert/` 下的对比 JSON（显式重建的专家口径，非未公开论文脚本的等价声明）。','',
             '| 来源 | 15条候选平均代价 | 15条最优平均代价 | 与专家最优候选一致率 | 位置误差均值(m) | 位置误差P95(m) | 采样预算 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    network_labels = [k for k in entries if k=='random_initial']+sorted(k for k in entries if k.startswith('trained'))
    if not network_labels:lines.append('| （网络侧） | pending | pending | pending | pending | pending | pending |')
    for name in network_labels:
        data = entries[name]['data'];baseline = dig(data,'baselines',name,default={})
        lines.append('| %s | %s | %s | %s | %s | %s | %s |'%(name,fmt(dig(baseline,'mean_of15_cost'),6),
            fmt(dig(baseline,'mean_best_of15_cost'),6),
            fmt(dig(data,'network_vs_expert','selected_candidate_matches_expert_best_fraction'),4),
            fmt(dig(data,'network_vs_expert','position_error_m','mean'),4),
            fmt(dig(data,'network_vs_expert','position_error_m','p95'),4),
            '15 candidates, single forward pass (no optimizer)'))
    for name,entry in entries.items():
        if name in network_labels:continue
        data = entry['data'];baseline = dig(data,'baselines',name,default={})
        lines.append('| %s | %s | %s | %s | %s | %s | %s |'%(name,fmt(dig(baseline,'mean_of15_cost'),6),
            fmt(dig(baseline,'mean_best_of15_cost'),6),'n/a',
            fmt(dig(baseline,'position_error_vs_expert_m','mean'),4),fmt(dig(baseline,'position_error_vs_expert_m','p95'),4),'n/a'))
    expert = entries.get('trained_seed0',entries.get('trained',{})).get('data',{})
    for variant in ['scaled_gd50','mma50_evaluations']:
        lines.append('| expert:%s | %s | %s | - | - | - | %s次目标函数评估均值%s |'%(variant,
            fmt(dig(expert,'expert',variant,'mean_of15_cost'),6),fmt(dig(expert,'expert',variant,'mean_best_of15_cost'),6),
            fmt(dig(expert,'expert',variant,'objective_evaluations_mean'),1),
            '' if dig(expert,'expert',variant,'objective_evaluations_mean') is None else ''))
    lines.append('')
    (outdir/'table_i_expert_vs_network.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return {'status':'available','sources':{k:{'path':v['path'],'sha256':v['sha256']} for k,v in entries.items()}}


PHASE_FIELDS = [('mapping_map_fusion_ms','map_fusion_wall_ms'),('mapping_esdf_ms','map_esdf_wall_ms'),
                ('front_queue_ms','planner_queue_wall_ms'),('back_plan_and_publish_ms','planner_and_publish_wall_ms'),
                ('capture_and_publish_ms','capture_and_publish_wall_ms'),('backend_pipeline_ms','backend_pipeline_wall_ms'),
                ('end_to_end_ms','end_to_end_wall_ms'),('transport_residual_ms','transport_and_other_scheduling_residual_ms')]


def authoritative_runs():
    """Join the driver ledger and the runtime-admission record to run folders."""
    joined = {}
    progress = ROOT/'artifacts/benchmark_summary/matrix_progress.json'
    if progress.is_file():
        data = json.loads(progress.read_text(encoding='utf-8'))
        for episode_id,record in data.get('episodes',{}).items():
            if record.get('status') in ('success','collision','timeout','crashed','out_of_map') and record.get('run'):
                joined[episode_id] = {'run':record['run'],'model':record.get('model'),'condition':record.get('condition'),
                                      'speed_mps':record.get('speed_mps'),'source':'driver_ledger'}
    admission = ROOT/'benchmarks/protocol_v1/runtime_validation.json'
    if admission.is_file():
        data = json.loads(admission.read_text(encoding='utf-8'))
        for episode_id,record in (data.get('phase_b') or {}).items():
            if record.get('evidence',{}).get('status') in ('success','collision','timeout','crashed','out_of_map'):
                joined.setdefault(episode_id,{'run':record.get('run'),'model':None,'condition':None,
                                              'speed_mps':None,'source':'runtime_admission_phase_b'})
    return joined


def table_two_latency_split(summary,outdir):
    """Phase decomposition for Table II; supplementary to the admission-checked aggregate."""
    protocol = json.loads((ROOT/'benchmarks/protocol_v1/protocol.json').read_text(encoding='utf-8'))
    by_id = {episode['id']:episode for episode in protocol['episodes']}
    joined = authoritative_runs()
    rows = {}
    for episode_id,record in joined.items():
        episode = by_id.get(episode_id)
        if not episode:continue
        task = protocol['tasks'][episode['task_index']]
        if episode['speed_mps']!=4:continue
        folder = ROOT/'artifacts/ros2_flights'/(record.get('run') or '')
        evaluation = dig_local = None
        try:evaluation = json.loads((folder/'evaluation.json').read_text(encoding='utf-8'))
        except Exception:evaluation = None
        if not evaluation:continue
        key = (episode['model'],task['condition'])
        rows.setdefault(key,[]).append(evaluation)
    lines = ['# Table II 延迟分解（4 m/s，两档密度；补充证据）','',
             '来源：驱动账本 `artifacts/benchmark_summary/matrix_progress.json` 与 runtime 准入记录关联到的逐 episode `evaluation.json`。',
             '正式口径仍以 `artifacts/benchmark_summary/summary.json` 的准入校验汇总为准；本表补充论文 Table II 需要的 mapping/front/back 分解。','',
             '| 模型 | 密度 | n | mapping融合P50 | mapping ESDF P50 | front队列P50 | back规划发布P50 | 取像发布P50 | 端到端P50 | 传输残差P50 |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    csv_rows = []
    for (model,condition),records in sorted(rows.items()):
        cells = {}
        for label,field in PHASE_FIELDS:
            values = [dig(record,field,'p50') for record in records if dig(record,field,'p50') is not None]
            cells[label] = (len(values),float(np.mean(values))) if values else (0,None)
        lines.append('| %s | %s | %d | %s | %s | %s | %s | %s | %s | %s |'%(model,condition,len(records),
            fmt(cells['mapping_map_fusion_ms'][1],2),fmt(cells['mapping_esdf_ms'][1],2),fmt(cells['front_queue_ms'][1],2),
            fmt(cells['back_plan_and_publish_ms'][1],2),fmt(cells['capture_and_publish_ms'][1],2),
            fmt(cells['end_to_end_ms'][1],2),fmt(cells['transport_residual_ms'][1],2)))
        csv_rows.append([model,condition,len(records)]+[cells[label][1] for label,_ in PHASE_FIELDS])
    (outdir/'table_ii_latency_split.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write_csv(outdir/'table_ii_latency_split.csv',['model','condition','n']+[label for label,_ in PHASE_FIELDS],csv_rows)
    return {'status':'available' if rows else 'pending','groups':len(rows),'episodes_joined':sum(len(v) for v in rows.values())}


def figure_seven(summary,outdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = load_groups(summary,'all30')
    models = [m for m in MODEL_ORDER if any(row['model']==m for row in groups)]
    if not models:return {'status':'pending','reason':'aggregate has no model groups yet'}
    figure,axes = plt.subplots(1,len(models),figsize=(3.4*len(models),3.2),sharey=True,squeeze=False)
    colours = {1/30:'tab:blue',1/20:'tab:red'}
    missing_cells = []
    for axis,model in zip(axes[0],models):
        for condition,colour in [('sparse','tab:blue'),('dense','tab:red')]:
            rows = sorted([r for r in groups if r['model']==model and r['condition']==condition],key=lambda r:r['speed_mps'])
            if not rows:continue
            speeds = [r['speed_mps'] for r in rows]
            rates = [r['success_rate_among_completed'] for r in rows]
            incomplete = [r['missing']>0 for r in rows]
            complete_x = [s for s,r,inc in zip(speeds,rates,incomplete) if r is not None and not inc]
            complete_y = [r for r,inc in zip(rates,incomplete) if r is not None and not inc]
            partial_x = [s for s,r,inc in zip(speeds,rates,incomplete) if r is not None and inc]
            partial_y = [r for r,inc in zip(rates,incomplete) if r is not None and inc]
            axis.plot(complete_x,complete_y,'-o',color=colour,label=condition+' (complete)')
            axis.plot(partial_x,partial_y,'--o',mfc='white',color=colour,label=condition+' (incomplete)')
            for row,rate in zip(rows,rates):
                if row['missing']>0:missing_cells.append({'model':model,'condition':condition,'speed_mps':row['speed_mps'],
                                                           'missing':row['missing'],'expected':row['expected']})
        axis.set_title(model);axis.set_xlabel('speed (m/s)');axis.set_ylim(-0.02,1.02);axis.grid(alpha=.3)
        axis.legend(fontsize=7)
    axes[0][0].set_ylabel('success rate among completed trials')
    figure.suptitle('Figure 7 style: success vs commanded speed (open markers = incomplete coverage)',fontsize=10)
    figure.tight_layout()
    figure.savefig(outdir/'figure_7_success_vs_speed.png',dpi=200)
    figure.savefig(outdir/'figure_7_success_vs_speed.pdf')
    plt.close(figure)
    return {'status':'available' if not missing_cells else 'incomplete_coverage','missing_cells':missing_cells}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary',type=Path,default=ROOT/'artifacts/benchmark_summary/summary.json')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/paper_figures')
    parser.add_argument('--require-complete',action='store_true')
    args = parser.parse_args()
    outdir = args.output.resolve();outdir.mkdir(parents=True,exist_ok=True)
    manifest = {'status':'pending_inputs','scope':'paper comparison tables and figures from real aggregate evidence only',
                'inputs':{},'outputs':{},'recorded_at':None}
    import datetime
    manifest['recorded_at'] = datetime.datetime.now().astimezone().isoformat()
    if not args.summary.is_file():
        write_json_atomic(outdir/'manifest.json',manifest)
        print(json.dumps(manifest,indent=2,ensure_ascii=False))
        if args.require_complete:raise SystemExit('Aggregate summary missing')
        return
    summary = json.loads(args.summary.read_text(encoding='utf-8'))
    protocol_path = ROOT/'benchmarks/protocol_v1/protocol.json'
    manifest['inputs']['summary'] = {'path':display_path(args.summary),'sha256':sha256_file(args.summary),
                                     'status':summary.get('status'),'completed_episodes':summary.get('completed_episodes'),
                                     'expected_episodes':summary.get('expected_episodes')}
    manifest['inputs']['protocol'] = {'path':display_path(protocol_path),'sha256':sha256_file(protocol_path)}
    if summary.get('protocol_sha256')!=manifest['inputs']['protocol']['sha256']:
        raise SystemExit('Aggregate summary does not match the frozen protocol hash')
    rows = table_two(summary,outdir)
    manifest['outputs']['table_ii'] = {'rows':len(rows),'path':'table_ii_latency_safety_smoothness.md'}
    manifest['outputs']['table_i'] = table_one(outdir)
    manifest['outputs']['table_ii_latency_split'] = table_two_latency_split(summary,outdir)
    manifest['outputs']['figure_7'] = figure_seven(summary,outdir)
    complete = summary.get('completed_episodes')==summary.get('expected_episodes')
    manifest['status'] = 'complete_coverage' if complete else 'incomplete_coverage'
    manifest['note'] = 'Incomplete coverage means some frozen episodes have no result yet; it is not a failure rate.'
    write_json_atomic(outdir/'manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!='inputs'},indent=2,ensure_ascii=False)[:2000])
    if args.require_complete and not complete:raise SystemExit('Aggregate coverage is incomplete')


if __name__=='__main__':main()
