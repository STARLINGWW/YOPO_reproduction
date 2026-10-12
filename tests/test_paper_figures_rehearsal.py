"""Rehearse the paper table/figure step on a simulated finished 600-slot batch.

The matrices take hours, so the deliverable that runs afterwards is rehearsed
here first: a real aggregate is built from the frozen protocol with only the
paper-size first-10 records present, then scripts/make_paper_figures.py must
render real figures, real Table II rows, and must label the coverage as
incomplete instead of presenting a subset as the full result.
"""
from pathlib import Path
import json
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_eval.aggregate import aggregate


def synthetic_records(protocol,paper_only):
    records = {}
    for index,episode in enumerate(protocol['episodes']):
        if paper_only and not episode['paper_first10']:continue
        metrics = {'path_length_m':50.-0.5*(index%5),'mean_net_clearance_m':1.1,'min_net_clearance_m':0.6,
                   'tracking_rmse_m':0.1,'reference_curve_squared_jerk_integral_m2_per_s5':12.,
                   'measured_raw_fd_squared_jerk_integral_m2_per_s5':24.,'max_speed_mps':episode['speed_mps'],
                   'real_time_factor':0.4,'motor_saturation_fraction':0.}
        records[episode['id']] = {'status':'success' if index%5 else 'collision','metrics':metrics,
                                  'latency_samples_ms':[95.,100.,105.]}
    return records


def test_rehearsal_of_the_600_slot_batch(tmp_path):
    protocol_path = ROOT/'benchmarks/protocol_v1/protocol.json'
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    summary = aggregate(protocol,synthetic_records(protocol,paper_only=True))
    summary['protocol_sha256'] = __import__('hashlib').sha256(protocol_path.read_bytes()).hexdigest()
    assert summary['completed_episodes']==600 and summary['missing_episodes']==1200
    summary_path = tmp_path/'summary_600.json';summary_path.write_text(json.dumps(summary),encoding='utf-8')
    outdir = tmp_path/'figures'
    outcome = subprocess.run([sys.executable,str(ROOT/'scripts/make_paper_figures.py'),
                              '--summary',str(summary_path),'--output',str(outdir)],
                             cwd=ROOT,capture_output=True,text=True)
    assert outcome.returncode==0, outcome.stderr[-2000:]
    manifest = json.loads((outdir/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['status']=='incomplete_coverage'
    assert manifest['inputs']['summary']['completed_episodes']==600
    assert (outdir/'figure_7_success_vs_speed.png').stat().st_size>10000
    assert (outdir/'figure_7_success_vs_speed.pdf').stat().st_size>5000
    figure = manifest['outputs']['figure_7']
    assert figure['status']=='incomplete_coverage'
    assert figure['missing_cells']
    table_two = (outdir/'table_ii_latency_safety_smoothness.md').read_text(encoding='utf-8')
    assert '| yopo_seed0 | sparse |' in table_two
    rows = (outdir/'table_ii_latency_safety_smoothness.csv').read_text(encoding='utf-8').strip().splitlines()
    assert len(rows)>=7  # header plus one row per (model,density) at 4 m/s
    latency_rows = [row for row in rows[1:] if row.startswith('yopo_seed0,sparse')]
    assert latency_rows and latency_rows[0].split(',')[4]  # p50 latency populated


def test_rehearsal_marks_missing_cells_for_a_partial_batch(tmp_path):
    protocol_path = ROOT/'benchmarks/protocol_v1/protocol.json'
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    records = synthetic_records(protocol,paper_only=True)
    # drop the first ten episodes of one model/speed cell to force an explicit gap
    dropped = [episode['id'] for episode in protocol['episodes'] if episode['model']=='yopo_seed0'][:10]
    for key in dropped:records.pop(key)
    summary = aggregate(protocol,records)
    summary['protocol_sha256'] = __import__('hashlib').sha256(protocol_path.read_bytes()).hexdigest()
    summary_path = tmp_path/'summary_gap.json';summary_path.write_text(json.dumps(summary),encoding='utf-8')
    outdir = tmp_path/'figures_gap'
    outcome = subprocess.run([sys.executable,str(ROOT/'scripts/make_paper_figures.py'),
                              '--summary',str(summary_path),'--output',str(outdir)],
                             cwd=ROOT,capture_output=True,text=True)
    assert outcome.returncode==0, outcome.stderr[-2000:]
    manifest = json.loads((outdir/'manifest.json').read_text(encoding='utf-8'))
    missing = manifest['outputs']['figure_7']['missing_cells']
    assert any(cell['model']=='yopo_seed0' and cell['speed_mps']==2 for cell in missing)
    rows = (outdir/'table_ii_latency_safety_smoothness.csv').read_text(encoding='utf-8')
    assert 'yopo_seed0' in rows
