"""Run a real planner backend through the already validated standard ROS2 gate."""
from pathlib import Path
import argparse,json,signal,time,resource,os
import rclpy
from yopo_runtime.protocol_node import PlannerProtocol
ROOT=Path('/workspace')
parser=argparse.ArgumentParser();parser.add_argument('--backend',choices=['yopo','agile'],default='yopo')
parser.add_argument('--checkpoint',default='resume_split_v2/best_policy.pth');parser.add_argument('--device',default='cpu')
parser.add_argument('--agile-engine',choices=['tensorflow','torch'],default='torch')
parser.add_argument('--speed',type=float,default=2.);parser.add_argument('--run',required=True)
parser.add_argument('--provenance-class',choices=['scratch','external_reference'],default='scratch')
parser.add_argument('--expected-sha256',default=None)
parser.add_argument('--wall-timeout',type=float,default=600.);args=parser.parse_args()
output=(ROOT/'artifacts/ros2_flights'/args.run).resolve()
if not output.is_relative_to(ROOT/'artifacts/ros2_flights') or not output.is_dir():raise ValueError('Native run must create output folder first')
rclpy.init()
if args.backend=='yopo':
    from yopo_runtime.main_planner import MainPlanner
    backend=MainPlanner(ROOT/'checkpoints'/args.checkpoint,args.speed,args.device,
                        provenance_class=args.provenance_class,expected_sha256=args.expected_sha256)
else:
    from yopo_runtime.agile_planner import AgilePlanner
    backend=AgilePlanner(args.speed,engine=args.agile_engine,device=args.device)
node=PlannerProtocol(backend);stopping=False;started=time.monotonic();last=0.
def stop(*_):
    global stopping
    stopping=True
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
def record(status):
    value={'status':status,'backend':args.backend,'device':args.device,'checkpoint_sha256':backend.checkpoint_sha256,
           'stats':dict(node.stats),'last_debug':backend.last_debug,'wall_s':time.monotonic()-started}
    temporary=output/'planner_status.tmp';temporary.write_text(json.dumps(value,indent=2));temporary.replace(output/'planner_status.json')
    usage=resource.getrusage(resource.RUSAGE_SELF)
    sample={'wall_unix_s':time.time(),'wall_elapsed_s':time.monotonic()-started,'pid':os.getpid(),
            'process_peak_rss_kib':usage.ru_maxrss,'process_user_cpu_s':usage.ru_utime,'process_system_cpu_s':usage.ru_stime}
    memory=Path('/sys/fs/cgroup/memory.current')
    if memory.exists():sample['container_memory_current_bytes']=int(memory.read_text())
    if args.device=='cuda':
        import torch
        sample['torch_cuda_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
        sample['torch_cuda_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
    with (output/'planner_resources.jsonl').open('a') as file:file.write(json.dumps(sample)+'\n')
try:
    record('ready');print('PLANNER_READY '+backend.checkpoint_sha256,flush=True)
    while rclpy.ok() and not stopping and time.monotonic()-started<args.wall_timeout:
        rclpy.spin_once(node,timeout_sec=.02)
        if time.monotonic()-last>1:record('running');last=time.monotonic()
finally:
    record('stopped');node.close();rclpy.shutdown()
