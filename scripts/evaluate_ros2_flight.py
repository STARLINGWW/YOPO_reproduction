from pathlib import Path
import argparse,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from yopo_eval.metrics import flight_metrics
parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
parser.add_argument('--root',default=None,help='Override the project root (used by tests; defaults to the real project root)')
args=parser.parse_args()
ROOT=Path(args.root).resolve() if args.root else ROOT
folder=(ROOT/'artifacts/ros2_flights'/args.run).resolve()
if not folder.is_relative_to(ROOT/'artifacts/ros2_flights'):raise ValueError('Unexpected source')
source=json.loads((folder/'metrics.json').read_text());data=np.load(folder/'flight.npz')
event_path=folder/'planning_events.jsonl';events=[json.loads(v) for v in event_path.read_text().splitlines()] if event_path.is_file() else []
try:
    report=flight_metrics(data['log'],data['frames'],data['latencies'],source,events)
    report['metrics_available']=True
except ValueError as exc:
    if source['status']!='crashed':raise
    report={'status':'crashed','metrics_available':False,'metric_unavailability_reason':str(exc),
            'per_command_application_audit_available':False}
report['scope']=source['scope'];report['checkpoint_sha256']=source['checkpoint_sha256']
def rows(name):
    path=folder/name
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []
native_resources=rows('native_resources.jsonl');planner_resources=rows('planner_resources.jsonl');container_resources=rows('container_resources.jsonl')
report['resource_samples_available']=bool(native_resources and (planner_resources or any(v.get('docker_stats') for v in container_resources)))
report['resource_sample_counts']={'native':len(native_resources),'planner_process':len(planner_resources),'planner_container':len(container_resources)}
report['native_peak_sampled_rss_bytes']=max((v.get('native_rss_bytes',0) for v in native_resources),default=None)
report['planner_peak_rss_kib']=max((v.get('process_peak_rss_kib',0) for v in planner_resources),default=None)
gpu_memory=[gpu['gpu_used_memory_MiB'] for row in native_resources for gpu in row.get('gpus',[]) if gpu.get('gpu_used_memory_MiB') is not None]
report['host_gpu_peak_sampled_memory_MiB']=max(gpu_memory,default=None)
report['resource_scope_note']='Host GPU totals can include other processes. Native and planner process/container figures are reported separately.'
report['instrumentation_gaps']=[name for name,value in [('per-frame planning telemetry',bool(events)),
    ('per-command application events',report['per_command_application_audit_available']),('resource samples',report['resource_samples_available'])] if not value]
(folder/'evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
