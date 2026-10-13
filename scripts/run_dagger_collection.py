"""Serial on-policy rollout collection for the DAgger aggregation dataset.

Every flight is a real Isaac PhysX closed-loop run through the validated ROS2
planner interface with a locally trained checkpoint. The driver refuses to run
while a formal trainer holds the GPU, refuses benchmark/validation map seeds,
refuses to reuse an existing run name, and writes a manifest the aggregation
builder consumes.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from yopo_repro.io import write_json_atomic
from yopo_repro.forest import generate, signed_distance
from yopo_sim.job_guard import require_training_gpu_released
from yopo_dagger.build_dataset import FORBIDDEN_MAP_SEEDS, parse_seeds

DEFAULT_START = np.array([-12.,0.,2.5])
DEFAULT_GOAL = np.array([12.,0.,2.5])


def endpoints_clearance(scene):
    return min(signed_distance(DEFAULT_START,scene),signed_distance(DEFAULT_GOAL,scene))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run',required=True,help='Collection prefix and output folder name')
    parser.add_argument('--checkpoint',required=True,help='Checkpoint path relative to checkpoints/')
    parser.add_argument('--map-seeds',required=True)
    parser.add_argument('--flights-per-map',type=int,default=2)
    parser.add_argument('--speeds',default='1.5,2.5,3.5')
    parser.add_argument('--durations',default='20,30')
    parser.add_argument('--camera-hz',type=float,default=15.)
    parser.add_argument('--python',default=None,help='Isaac Sim python interpreter (default: $YOPO_ISAAC_PYTHON or python on PATH)')
    parser.add_argument('--plan-only',action='store_true',
                        help='Write the flight plan (seeds, clearance, speeds, durations) without launching Isaac')
    args = parser.parse_args()
    if not args.plan_only:require_training_gpu_released()
    if args.python is None:args.python = os.environ.get('YOPO_ISAAC_PYTHON','python')
    if not args.plan_only and not Path(args.python).is_file():
        resolved = shutil.which(args.python)
        if resolved is None:
            raise SystemExit('Isaac Sim python not found: %s (set YOPO_ISAAC_PYTHON or pass --python)'%args.python)
        args.python = resolved
    checkpoint = (ROOT/'checkpoints'/args.checkpoint).resolve()
    if not checkpoint.is_relative_to(ROOT/'checkpoints') or not checkpoint.is_file():
        raise ValueError('Expected a project checkpoint inside checkpoints/')
    seeds = sorted(parse_seeds(args.map_seeds))
    if not seeds:raise ValueError('No map seeds requested')
    overlap = set(seeds)&FORBIDDEN_MAP_SEEDS
    if overlap:raise ValueError('Map seeds overlap training/validation/test/benchmark ranges: %s'%sorted(overlap))
    speeds = [float(v) for v in args.speeds.split(',') if v]
    durations = [float(v) for v in args.durations.split(',') if v]
    output = ROOT/'artifacts/dagger_flights'/args.run
    if args.plan_only:
        plan = {'status':'plan_only','run':args.run,'checkpoint':str(checkpoint.relative_to(ROOT).as_posix()),
                'map_seeds':seeds,'flights_per_map':args.flights_per_map,'speeds':speeds,'durations':durations,
                'camera_hz':args.camera_hz,'flights':[],'skipped':[],
                'note':'Planning only: no Isaac process was launched and no GPU work was scheduled.'}
        import hashlib
        plan['checkpoint_sha256'] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        for seed in seeds:
            scene = generate(seed);clearance = float(endpoints_clearance(scene))
            if clearance < 1.0:
                plan['skipped'].append({'map_seed':seed,'reason':'default endpoints not clear','endpoint_clearance_m':clearance})
                continue
            for index in range(args.flights_per_map):
                plan['flights'].append({'map_seed':seed,'index':index,'speed_mps':speeds[index%len(speeds)],
                                        'duration_s':durations[index%len(durations)],'endpoint_clearance_m':clearance,
                                        'run':('%s__m%d__f%02d'%(args.run,seed,index))})
        output.parent.mkdir(parents=True,exist_ok=True)
        plan_path = ROOT/'artifacts/dagger_flights'/(args.run+'_plan.json')
        write_json_atomic(plan_path,plan)
        print(json.dumps({'status':plan['status'],'flights':len(plan['flights']),'skipped':len(plan['skipped']),
                          'plan':str(plan_path.relative_to(ROOT).as_posix())},indent=2))
        return
    output.mkdir(parents=True,exist_ok=False)
    manifest = {'status':'running','run':args.run,'checkpoint':str(checkpoint.relative_to(ROOT).as_posix()),
                'checkpoint_sha256':None,'map_seeds':seeds,'flights_per_map':args.flights_per_map,
                'speeds':speeds,'durations':durations,'camera_hz':args.camera_hz,
                'scope':'dagger_aggregation_rollout_not_benchmark','flights':[],'skipped':[],
                'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    import hashlib
    manifest['checkpoint_sha256'] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    write_json_atomic(output/'flights.json',manifest)
    env = os.environ.copy();env['OMNI_KIT_ACCEPT_EULA'] = 'YES'
    failures = 0
    try:
        for seed in seeds:
            scene = generate(seed)
            clearance = endpoints_clearance(scene)
            if clearance < 1.0:
                manifest['skipped'].append({'map_seed':seed,'reason':'default endpoints not clear',
                                            'endpoint_clearance_m':float(clearance)})
                write_json_atomic(output/'flights.json',manifest)
                continue
            for index in range(args.flights_per_map):
                speed = speeds[index%len(speeds)]
                duration = durations[index%len(durations)]
                flight_run = '%s__m%d__f%02d'%(args.run,seed,index)
                flight_output = ROOT/'artifacts/ros2_flights'/flight_run
                if flight_output.exists():raise ValueError('Run output already exists: '+str(flight_output))
                # The planner container is Linux: it resolves --checkpoint under
                # /workspace/checkpoints, so the runner must receive the same
                # relative form the matrix and showcase use. Passing the resolved
                # Windows path made serve_planner.py exit immediately, the host
                # then never saw the container's depth subscriber and every
                # flight failed with "Container planner DDS discovery failed"
                # (33/33 on 2026-09-26). args.checkpoint is documented as
                # relative to checkpoints/ and is validated above.
                command = [args.python,str(ROOT/'scripts/run_ros2_navigation.py'),'--run',flight_run,
                           '--backend','yopo','--device','cuda','--checkpoint',args.checkpoint,
                           '--map-seed',str(seed),'--speed',str(speed),'--duration',str(duration),
                           '--camera-hz',str(args.camera_hz),'--scope','dagger_aggregation_rollout_not_benchmark']
                log = output/(flight_run+'.log')
                with log.open('a',encoding='utf-8') as handle:
                    completed = subprocess.run(command,cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT)
                record = {'run':flight_run,'map_seed':seed,'speed_mps':speed,'duration_s':duration,
                          'returncode':int(completed.returncode),'output':str(flight_output.relative_to(ROOT).as_posix()),
                          'path':str(flight_output)}
                metrics_path = flight_output/'metrics.json'
                if metrics_path.is_file():
                    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
                    record['status'] = metrics.get('status')
                    record['frames'] = metrics.get('frames')
                    record['min_net_clearance_m'] = metrics.get('min_net_clearance_m')
                    record['real_time_factor'] = metrics.get('real_time_factor')
                    record['checkpoint_sha256'] = metrics.get('checkpoint_sha256')
                else:record['status'] = 'no_metrics'
                if completed.returncode or record.get('status') in (None,'crashed','no_metrics'):
                    failures += 1
                manifest['flights'].append(record)
                write_json_atomic(output/'flights.json',manifest)
        manifest['status'] = 'complete' if not failures else 'complete_with_failures'
        manifest['failures'] = failures
        manifest['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        write_json_atomic(output/'flights.json',manifest)
        print(json.dumps({'status':manifest['status'],'flights':len(manifest['flights']),
                          'failures':failures,'skipped':len(manifest['skipped'])},indent=2))
    except Exception:
        manifest['status'] = 'failed'
        manifest['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        write_json_atomic(output/'flights.json',manifest)
        raise


if __name__=='__main__':main()
