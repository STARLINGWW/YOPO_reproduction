"""Batch weights A/B: scene x speed ladder x {Simple, main} x {official, local}.

Every cell is one real Isaac Sim flight in the legacy (non-frozen) harness with a
procedural forest scene identical to yopo_repro.forest.generate(seed). The four arms
per cell are:

  simple_official  released Simple network + Simple config + released epoch50 weights
  simple_local     released Simple network + Simple config + local weights renamed into that layout
  main_official    main-branch network + main config + released weights renamed into that layout
  main_local       main-branch network + main config + local audited weights

so each weight is measured both in its native stack and in the other stack, which is
what separates "weights are better" from "stack matches the weights".
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ARMS = {
    'simple_official':{'planner':'simple','weights':None,
                       'label':'official YOPO-Simple epoch50 in its native Simple stack'},
    'simple_local':{'planner':'simple','weights':'artifacts/expert/local_seed0_simple_layout.pth',
                    'label':'local seed0 weights renamed into the Simple layout'},
    'main_official':{'planner':'main','weights':'artifacts/expert/official_epoch50_policy_layout.pth',
                     'label':'official YOPO-Simple epoch50 renamed into the main layout'},
    'main_local':{'planner':'main','weights':'checkpoints/formal_main_v1_seed0/best_policy.pth',
                  'label':'local formal seed0 audited best_policy'},
}
SUMMARY = ROOT/'artifacts/weights_ab_demo/batch_summary.json'
LOGS = ROOT/'artifacts/weights_ab_demo/batch_logs'


def load_summary():
    if SUMMARY.is_file():
        return json.loads(SUMMARY.read_text(encoding='utf-8'))
    return {'scope':'weights A/B batch outside the frozen benchmark matrix','records':[]}


def collect(run):
    metrics_path = ROOT/'artifacts/navigation'/run/'metrics.json'
    if not metrics_path.is_file():
        return None
    m = json.loads(metrics_path.read_text(encoding='utf-8'))
    keys = ['status','weight_sha256','weights','planner_network','scene_model','scene_density_per_m2','seed',
            'sim_duration_s','arrival_time_s','wall_runtime_s','real_time_factor','path_length_m','min_clearance_m',
            'goal_error_m','final_speed_mps','max_speed_mps','tracking_rmse_m','network_pipeline_p50_ms',
            'network_pipeline_p95_ms','depth_render_readback_p50_ms','planner_updates','obstacle_count']
    return {key:m.get(key) for key in keys}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenes',default='5002,5004,5001')
    parser.add_argument('--speeds',default='2,4,6')
    parser.add_argument('--arms',default='simple_official,simple_local,main_official,main_local')
    parser.add_argument('--duration',type=float,default=45.)
    parser.add_argument('--density',type=float,default=1/30.)
    parser.add_argument('--tag',default='b1')
    parser.add_argument('--flight-timeout',type=float,default=420.,
                        help='wall-clock budget per flight; on expiry the harness process is killed and '
                             'whatever metrics were already written are recorded (default 420 s; the flight '
                             'itself is capped at --duration simulated seconds)')
    parser.add_argument('--python',default=None,help='Isaac Sim python interpreter (default: $YOPO_ISAAC_PYTHON or python on PATH)')
    parser.add_argument('--skip-existing',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    args = parser.parse_args()
    if args.python is None:args.python = os.environ.get('YOPO_ISAAC_PYTHON','python')
    scenes = [int(v) for v in args.scenes.split(',') if v.strip()]
    speeds = [float(v) for v in args.speeds.split(',') if v.strip()]
    arms = [v.strip() for v in args.arms.split(',') if v.strip()]
    interpreter = Path(args.python)
    if not interpreter.is_file():
        resolved = shutil.which(args.python)
        if resolved is None:
            raise SystemExit('Isaac Sim python not found: %s (set YOPO_ISAAC_PYTHON or pass --python)'%args.python)
        interpreter = Path(resolved)
    LOGS.mkdir(parents=True,exist_ok=True)
    summary = load_summary()
    known = {record['run'] for record in summary['records']}
    planned = 0
    for speed in speeds:
        for scene in scenes:
            for arm in arms:
                config = ARMS[arm]
                run = 'wab2_%s_s%d_v%g'%(arm,scene,speed)
                planned += 1
                if args.skip_existing and (ROOT/'artifacts/navigation'/run).is_dir():
                    record = collect(run)
                    if record is not None:
                        record.update({'run':run,'arm':arm,'planner':config['planner'],'scene_seed':scene,
                                       'speed_mps':speed,'note':'reused existing run'})
                        summary['records'] = [r for r in summary['records'] if r['run']!=run]+[record]
                        print('reuse %s %s'%(run,record['status']),flush=True)
                        continue
                command = [str(interpreter),str(ROOT/'scripts/run_navigation.py'),'--run',run,'--seed',str(scene),
                           '--speed',str(speed),'--duration',str(args.duration),'--planner',config['planner'],
                           '--scene','forest','--density',str(args.density),'--label',config['label']]
                if config['weights']:
                    command += ['--weights',config['weights']]
                if args.dry_run:
                    print(' '.join(command[1:]));continue
                log = LOGS/(run+'.log')
                env = os.environ.copy();env['OMNI_KIT_ACCEPT_EULA'] = 'YES'
                started = time.time()
                try:
                    result = subprocess.run(command,cwd=ROOT,text=True,capture_output=True,env=env,
                                            timeout=args.flight_timeout)
                    stdout = result.stdout or '';stderr = result.stderr or '';returncode = result.returncode
                except subprocess.TimeoutExpired as exc:
                    # Isaac Sim occasionally hangs in its shutdown path after the flight evidence has
                    # already been written; the simulator is capped at --duration, so a wall-clock
                    # budget only ever truncates that hang, never a live flight.
                    decode = lambda value: value.decode('utf-8','replace') if isinstance(value,bytes) else (value or '')
                    stdout = decode(exc.stdout)
                    stderr = decode(exc.stderr) + (
                        '\n[driver] flight exceeded %.0fs wall budget; harness killed, metrics collected\n'
                        % args.flight_timeout)
                    returncode = 'flight_timeout_killed'
                log.write_text(stdout+'\n'+stderr,encoding='utf-8')
                record = collect(run) or {'status':'no_metrics_recorded'}
                record.update({'run':run,'arm':arm,'planner':config['planner'],'scene_seed':scene,
                               'speed_mps':speed,'duration_s':args.duration,'wall_s':round(time.time()-started,1),
                               'runner_returncode':returncode,'log':str(log.relative_to(ROOT)),
                               'flight_timeout_s':args.flight_timeout,
                               'weights_label':config['label'],'weights_file':config['weights']})
                summary['records'] = [r for r in summary['records'] if r['run']!=run]+[record]
                summary['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
                summary['planned_runs'] = planned
                SUMMARY.parent.mkdir(parents=True,exist_ok=True)
                SUMMARY.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
                print(json.dumps({key:record.get(key) for key in ('run','status','arrival_time_s','path_length_m',
                                 'goal_error_m','min_clearance_m','tracking_rmse_m','real_time_factor','wall_s')},
                                 ensure_ascii=False),flush=True)
    print(json.dumps({'summary':str(SUMMARY.relative_to(ROOT)),'records':len(summary['records']),
                      'planned':planned},ensure_ascii=False))


if __name__ == '__main__':
    main()
