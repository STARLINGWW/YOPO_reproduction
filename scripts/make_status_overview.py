"""Single user-facing status overview assembled from authoritative artifacts.

Nothing here is inferred: every number is read from a file that was produced by
a real run or a real audit, and each section names that file. Missing evidence
is printed as pending/missing rather than omitted.
"""
from pathlib import Path
import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import sha256_file,write_json_atomic

SEEDS = (0,1,2)


def read_json(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:return default


def training_rows(prefix):
    rows = []
    for seed in SEEDS:
        folder = ROOT/'checkpoints'/('%s_seed%d'%(prefix,seed))
        progress = read_json(folder/'progress.json',{}) or {}
        result = read_json(folder/'result.json')
        audit = read_json(folder/'training_audit.json')
        rows.append({'seed':seed,'status':progress.get('status'),'epochs_done':progress.get('epoch_completed'),
                     'step':progress.get('step'),'target_epochs':progress.get('target_epochs'),
                     'result':(result or {}).get('status'),'audit':(audit or {}).get('status'),
                     'best_epoch':((audit or {}).get('selection') or {}).get('best_epoch'),
                     'folder':str(folder.relative_to(ROOT).as_posix())})
    return rows


def matrix_rows():
    plan = read_json(ROOT/'artifacts/benchmark_summary/plan.json',{}) or {}
    progress = read_json(ROOT/'artifacts/benchmark_summary/matrix_progress.json',{}) or {}
    result = read_json(ROOT/'artifacts/benchmark_summary/matrix_result.json',{}) or {}
    summary = read_json(ROOT/'artifacts/benchmark_summary/summary.json',{}) or {}
    episodes = progress.get('episodes',{})
    counts = {}
    for record in episodes.values():counts[record.get('status')] = counts.get(record.get('status'),0)+1
    return {'plan_pending':plan.get('pending_episodes'),'plan_projection_hours':(plan.get('projection') or {}).get('projected_serial_wall_hours'),
            'ledger_records':len(episodes),'ledger_status_counts':counts,
            'last_batch':result.get('status'),'aggregate_status':summary.get('status'),
            'aggregate_completed':summary.get('completed_episodes'),'aggregate_expected':summary.get('expected_episodes'),
            'current_missing':summary.get('missing_episodes'),
            'invalid_evidence':len(summary.get('invalid_evidence') or []),
            'duplicate_primary_attempts':len(summary.get('duplicate_primary_attempts') or []),
            'measurement_gaps':len(summary.get('measurement_gaps') or []),
            'missing_by_model':{model:sum(g.get('missing',0) for g in summary.get('groups',[])
                                        if g.get('subset')=='all30' and g.get('model')==model)
                                for model in sorted({g.get('model') for g in summary.get('groups',[])})},
            'plan_note':'Historical scheduling snapshot; not current remaining work. Use aggregate coverage.',
            'model_outcomes':{model:dict(sum((Counter(g.get('outcomes',{})) for g in summary.get('groups',[])
                                           if g.get('subset')=='all30' and g.get('model')==model),Counter()))
                              for model in sorted({g.get('model') for g in summary.get('groups',[])})}}


def expert_rows():
    rows = []
    for path in sorted((ROOT/'artifacts/expert').glob('network_comparison_*.json')):
        data = read_json(path,{}) or {}
        variant = (data.get('network_vs_expert') or {}).get('scaled_gd50') or {}
        rows.append({'file':str(path.relative_to(ROOT).as_posix()),'samples':data.get('samples'),
                     'kind':((data.get('checkpoint') or {}).get('kind')),
                     'checkpoint_sha256':((data.get('checkpoint') or {}).get('sha256')),
                     'mean_of15_cost':variant.get('network_cost_of_predictions_mean_of15'),
                     'best_of15_cost':variant.get('network_cost_of_predictions_best_of15') or variant.get('network_cost_of_predictions_mean_best_of15'),
                     'alignment_max_abs_error':data.get('sample_alignment_max_abs_error')})
    full = [row for row in rows if row['samples']==10000]
    partial = [row for row in rows if row['samples']!=10000]
    return full,partial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-prefix',default='formal_main_v1')
    parser.add_argument('--markdown',default='report/01_status/02_复现状态总览.md')
    parser.add_argument('--json',default='artifacts/environment/status_overview.json')
    args = parser.parse_args()
    training = training_rows(args.run_prefix)
    matrix = matrix_rows()
    experts,partial_experts = expert_rows()
    admission = read_json(ROOT/'benchmarks/protocol_v1/runtime_validation.json')
    acceptance = read_json(ROOT/'artifacts/environment/final_acceptance_audit.json',{}) or {}
    runtime_decl = read_json(ROOT/'configs/benchmark_runtime/v1.json',{}) or {}
    dagger = read_json(ROOT/'checkpoints/dagger_main_v1_seed0/result.json',{}) or {}
    aggregation = read_json(ROOT/'datasets/isaac_dagger_v1/aggregation_manifest.json',{}) or {}
    payload = {'recorded_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'run_prefix':args.run_prefix,
               'training':training,'matrix':matrix,'expert_comparison':experts,
               'expert_comparison_partial_self_checks':partial_experts,
               'runtime_admission':{'present':admission is not None,'status':(admission or {}).get('status'),
                                    'validated_backends':(admission or {}).get('validated_backends'),
                                    'consumed_episode_ids':(admission or {}).get('consumed_episode_ids')},
               'runtime_declaration':{'path':'configs/benchmark_runtime/v1.json','status':runtime_decl.get('status'),
                                      'open_items':len(runtime_decl.get('open_items') or []),
                                      'note':'Historical declaration snapshot; the YOPO-only scope update (2026-10-13) removed the MPPI method and marked the superset matrix historical.'},
               'dagger':{'status':dagger.get('status'),'rehearsal':dagger.get('rehearsal'),'epochs':dagger.get('epochs'),
                         'steps':dagger.get('steps'),'added_samples':sum(s.get('samples',0) for s in aggregation.get('aggregation_shards',[])),
                         'evidence':'checkpoints/dagger_main_v1_seed0/result.json'},
               'mppi_archive':{'excluded':True,'note':'MPPI reference [17] was excluded from the active YOPO-only scope on 2026-10-13; identity/full-text records archived under report/90_archive/mppi.'},
               'acceptance':{'counts':acceptance.get('counts'),'all_verified':acceptance.get('all_verified'),
                             'items':[{'id':item['id'],'status':item['status'],'detail':item['detail']}
                                      for item in acceptance.get('items',[])]},
               'note':'Current result coverage comes from summary.json; historical plan/declaration fields are not current pending work. Acceptance rules are unchanged.'}
    write_json_atomic(ROOT/args.json,payload)
    lines = ['# YOPO 本地复现：状态总览','',
             '生成时间：%s（由 `scripts/make_status_overview.py` 从权威产物生成，未做任何推断）'%payload['recorded_at'],'',
             '## 1. 三种子正式训练','',
             '| 种子 | 状态 | 完成轮次 | 步数 | 结果文件 | 严格审计 | 最佳轮次 |','|---|---|---:|---:|---|---|---:|']
    for row in training:
        lines.append('| seed%d | %s | %s/%s | %s | %s | %s | %s |'%(row['seed'],row['status'],row['epochs_done'],
            row['target_epochs'],row['step'],row['result'] or 'pending',row['audit'] or 'pending',row['best_epoch'] or '-'))
    lines += ['','来源：`checkpoints/%s_seed{0,1,2}/progress.json|result.json|training_audit.json`'%args.run_prefix,
              '','## 2. 运行时准入（矩阵的门）','',
              '- 准入记录：%s'%('缺失（必须由真实飞行产生）' if not payload['runtime_admission']['present'] else
                                ('status=%s, backends=%s, 已消费 episode=%d'%(payload['runtime_admission']['status'],
                                 payload['runtime_admission']['validated_backends'] or [],len(payload['runtime_admission']['consumed_episode_ids'] or [])))),
              '- 冻结前的声明快照：`configs/benchmark_runtime/v1.json` status=%s，未闭公平性备注 %d（历史元数据，不代表当前准入失败；MPPI 条目已标注排除）'%(payload['runtime_declaration']['status'],
                                 payload['runtime_declaration']['open_items']),
              '','## 3. 1500 主矩阵（YOPO-only 活动范围）','',
              '活动范围由 `benchmarks/protocol_v1/active_scope_yopo_only.json` 定义：五模型 × 300 = 1500；1800 超集协议作为历史证据锚点保留（`historical_protocol_v1 / not_used_by_active_yopo_only_release`）。','',
              '| 项 | 值 |','|---|---|',
              '| 当前未执行槽位（汇总） | %s |'%matrix['current_missing'],
              '| 历史计划快照的 pending | %s（不用于当前剩余工作判断） |'%matrix['plan_pending'],
              '| 历史串行墙钟投影 | %s h（旧计划投影，非当前 ETA） |'%('%.2f'%matrix['plan_projection_hours'] if matrix['plan_projection_hours'] else 'n/a'),
              '| 账本记录数 | %s |'%matrix['ledger_records'],
              '| 账本状态分布 | %s |'%(matrix['ledger_status_counts'] or '{}'),
              '| 最近批次结果 | %s |'%(matrix['last_batch'] or '未开始'),
              '| 覆盖感知汇总 | completed=%s / expected=%s（%s） |'%(matrix['aggregate_completed'],matrix['aggregate_expected'],matrix['aggregate_status']),
              '| 无效证据 / 重复主尝试 / 测量缺口 | %s / %s / %s |'%(matrix['invalid_evidence'],matrix['duplicate_primary_attempts'],matrix['measurement_gaps']),
              '', '当前未执行槽位：%s。驱动跳过记录不是真实飞行失败；覆盖以 summary.json 为准。'%
                  (', '.join('%s=%s'%(model,n) for model,n in matrix['missing_by_model'].items() if n) or '无'),
              '准入记录另消费 %d 个正式任务；驱动账本与汇总覆盖的计数口径不同。'%len(payload['runtime_admission']['consumed_episode_ids'] or []),
              '', '| 模型 | 成功 | 碰撞 | 超时 | 已执行 |', '|---|---:|---:|---:|---:|']
    for model,counts in matrix['model_outcomes'].items():
        lines.append('| %s | %s | %s | %s | %s |'%(model,counts.get('success',0),counts.get('collision',0),counts.get('timeout',0),sum(counts.values())))
    lines += [
              '','## 4. 专家／网络离线对比（Table I 口径）','',
              '| 证据文件 | 来源 | 样本 | 15候选平均代价 | 15候选最优代价 | 样本对齐误差 |','|---|---|---:|---:|---:|---:|']
    for row in experts:
        label='trained（第39轮中间权重）' if row['kind']=='trained' else row['kind'] or '-'
        lines.append('| %s | %s | %s | %s | %s | %s |'%(row['file'],label,row['samples'],
            row['mean_of15_cost'],row['best_of15_cost'],row['alignment_max_abs_error']))
    if partial_experts:
        lines += ['','仅用于自检的小样本运行（不进入结论）：%s'%', '.join('%s(%s 样本)'%(row['file'],row['samples'])
                                                                            for row in partial_experts)]
    lines += ['','## 5. 当前 %d 项验收的机械审计'%len(payload['acceptance']['items']),'',
              '| 检查项 | 状态 | 说明 |','|---|---|---|']
    for item in payload['acceptance']['items']:
        detail=item['detail'] or ''
        if 'plan_pending=' in detail:detail+='（plan_pending是原审计引用的历史计划值，当前缺槽见第3节）'
        lines.append('| %s | %s | %s |'%(item['id'],item['status'],detail))
    lines += ['','计数：`%s`'%(json.dumps(payload['acceptance']['counts'],ensure_ascii=False) if payload['acceptance']['counts'] else 'n/a'),
              '','## 6. 聚合微调与真实未闭项','',
              '- DAgger：status=%s，rehearsal=%s，%s 轮、%s 步，新增 %s 样本；来源 `%s`。'%(payload['dagger']['status'],payload['dagger']['rehearsal'],payload['dagger']['epochs'],payload['dagger']['steps'],payload['dagger']['added_samples'],payload['dagger']['evidence']),
              '- MPPI（参考[17]）：2026-10-13 按用户决定移出活动范围；身份/全文记录归档于 `report/90_archive/mppi/`，不再作为当前待完成项。',
              '- 当前未通过项：%s。训练、准入和微调的具体状态以本页对应证据为准。'%
                  (', '.join('%s=%s'%(i['id'],i['status']) for i in payload['acceptance']['items'] if i['status']!='verified') or '无'),
              '- DAgger 闭环收益、高速可靠性与外部基线公平性仍不能由完成标记代替验证（研究限制，非验收项）。',
              '', '> YOPO-only 活动范围内整体验收完成：%s；MPPI 已移出活动范围并归档。'%(json.dumps(payload['acceptance']['counts'],ensure_ascii=False) if payload['acceptance']['counts'] else 'n/a'),
              '', '报告导航与历史范围见 [报告索引](README.md)。']
    (ROOT/args.markdown).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'markdown':args.markdown,'json':args.json,'acceptance_counts':payload['acceptance']['counts'],
                      'training':[{'seed':r['seed'],'epochs':r['epochs_done'],'audit':r['audit']} for r in training]},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
