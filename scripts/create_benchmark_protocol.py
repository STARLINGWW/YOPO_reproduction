"""Freeze independent maps/tasks and all requested1800 primary episode slots."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.forest import generate,signed_distance
output=ROOT/'benchmarks/protocol_v1';output.mkdir(parents=True,exist_ok=False)
(output/'maps').mkdir();tasks=[];maps=[]
for condition,density,base in [('sparse',1/30,5000),('dense',1/20,6000)]:
    scenes={}
    for i in range(10):
        scene=generate(base+i,density);scenes[i]=scene
        path=output/'maps'/f'{base+i}.json';path.write_text(json.dumps(scene,indent=2)+'\n')
        maps.append({'condition':condition,'seed':base+i,'file':path.relative_to(output).as_posix(),
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    for repeat in range(3):
        for i in range(10):
            seed=(base+i)*100+repeat;rng=np.random.default_rng(seed);scene=scenes[i]
            for attempt in range(10000):
                theta=rng.uniform(-np.pi,np.pi);start=np.r_[25*np.array([np.cos(theta),np.sin(theta)]),2.5];goal=np.r_[-start[:2],2.5]
                # Endpoint validity only, no corridor/path filtering or planner outcome selection.
                if min(signed_distance(start,scene),signed_distance(goal,scene))>=1.:break
            else:raise RuntimeError('Cannot sample valid fixed endpoints')
            tasks.append({'condition':condition,'density_per_m2':density,'map_seed':base+i,'task_seed':seed,
                'trial':repeat*10+i,'paper_first10':repeat==0,'start':start.tolist(),'goal':goal.tolist(),
                'initial_yaw':float(np.arctan2(goal[1]-start[1],goal[0]-start[0])),
                'straight_distance_m':float(np.linalg.norm(goal-start)),'endpoint_sampling_attempts':attempt+1})
models=['yopo_seed0','yopo_seed1','yopo_seed2','topotraj','agile_autonomy','mppi_reference17']
episodes=[]
for model in models:
    for task_index,task in enumerate(tasks):
        for speed in [2,4,6,8,10]:
            episodes.append({'id':f'{model}_{task["condition"]}_v{speed}_trial{task["trial"]:02d}',
                'model':model,'task_index':task_index,'speed_mps':speed,'paper_first10':task['paper_first10'],
                'timeout_s':max(30.,1.5*task['straight_distance_m']/speed+10.),'status':'pending'})
assert len(tasks)==60 and len(episodes)==1800
assert {s['seed'] for s in maps}.isdisjoint(set(range(100,120))|set(range(1000,1004))|set(range(2000,2004))|{3000})
protocol={'version':1,'status':'task_matrix_frozen_runtime_gates_pending','paper':'https://tju-air-lab.github.io/projects/YOPO/YOPO.pdf',
    'maps':maps,'tasks':tasks,'episodes':episodes,
    'scope':'Isaac equivalent paired task matrix; no baseline silently omitted; official-weight and Simple runs excluded from primary1800',
    'criteria':{'collision':'Any physical contact or conservative vehicle-envelope signed distance<=0',
        'goal':'Within0.5m and speed<0.3m/s continuously0.5s, without collision',
        'terminal_hold_entry_m':1.,'all_failures_in_denominator':True,'missing_episode_is_not_success':True,
        'confidence_interval':'Wilson95% with n30, and separate first10 paper-size subset',
        'latency':'Count wall acquisition/communication/planning delay in simulation-time command availability; report wall and simulation times and RTF',
        'safety':'Report both center-to-obstacle distance and net envelope clearance',
        'smoothness':'Report reference jerk integral and separately measured-state derivative metrics with any filtering disclosed'},
    'paper_experiments':[
        {'id':'table_I','scope':'Expert50 optimization steps vs random-initial and50epoch network; average and best of15 trajectories; independent offline test maps','status':'pending','unknowns':['Exact YOPO expert optimizer/step-size script not present in releasedmain; cited2017 optimizer usesNLopt24 and time budgets. Must label adaptation.']},
        {'id':'table_II','scope':'Two densities at4m/s; mapping/front/back/total latency, mean/min clearance, squared-jerk integral, path length','status':'pending'},
        {'id':'figure_7','scope':'Success vs2/4/6/8/10m/s for both densities; first10 and full30 tasks','status':'pending'},
        {'id':'figure_8','scope':'Actual global trajectories, self-trained videos, representative successes and failures','status':'pending'},
        {'id':'DAgger','scope':'Separate aggregation/fine-tuning data version and checkpoint; never overwrite base training','status':'pending'},
        {'id':'real_world','scope':'Excluded by user; no real drone flight','status':'out_of_scope'}]}
(output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
print(json.dumps({'maps':len(maps),'tasks':len(tasks),'primary_episodes':len(episodes),'output':str(output)}))
