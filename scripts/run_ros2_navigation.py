"""Native Isaac force-driven navigation using a separate Ubuntu22/ROS2 planner.

Real observations and actual PhysX states only. Wall acquisition/communication/
inference delay is charged to simulation-time command availability. Physics does
not wait for planner results. Existing output runs and containers are refused.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.forest import generate,signed_distance
from yopo_sim.unified_quad import Quadrotor
from yopo_sim.trajectory_buffer import TrajectoryBuffer,decode_ros_trajectory
from yopo_sim.evaluation_geometry import ForestEvaluator
from yopo_sim.resource_sampler import ResourceSampler
from yopo_sim.job_guard import require_training_gpu_released
from yopo_eval.task_spec import resolve_episode,verify_formal_yopo_checkpoint,verify_reference_weights,verify_runtime_admission


def stamp(msg,value):
    ns=int(round(value*1e9));msg.sec=ns//1_000_000_000;msg.nanosec=ns%1_000_000_000


def assign_xyz(msg,value):msg.x,msg.y,msg.z=map(float,value)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    parser.add_argument('--checkpoint')
    parser.add_argument('--backend',choices=['yopo','yopo_reference','agile','topotraj'],default='yopo');parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--topo-config',type=Path,default=ROOT/'configs/topotraj/isaac_development.yaml')
    parser.add_argument('--episode-id');parser.add_argument('--protocol',type=Path,default=ROOT/'benchmarks/protocol_v1/protocol.json')
    parser.add_argument('--map-seed',type=int,default=3000);parser.add_argument('--speed',type=float,default=2.)
    parser.add_argument('--duration',type=float,default=20.);parser.add_argument('--camera-hz',type=float,default=15.)
    parser.add_argument('--scope');args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',args.run):raise ValueError('Invalid run name')
    require_training_gpu_released()
    mission=None;admission=None;initial_yaw=0.
    if args.episode_id:
        mission=resolve_episode(args.protocol,args.episode_id)
        if mission['backend'] not in ['yopo','yopo_reference','agile','topotraj']:raise ValueError('Requested baseline native adapter is not ready; no replacement is permitted')
        args.backend=mission['backend'];args.speed=mission['episode']['speed_mps'];args.duration=mission['episode']['timeout_s']
        args.map_seed=mission['task']['map_seed']
        args.scope='primary_frozen_benchmark' if args.backend!='yopo_reference' else 'reference_arm_official_v1'
        if args.backend in ['yopo','yopo_reference','agile'] and args.device!='cuda':raise ValueError('Primary neural benchmark requires GPU; CPU comparisons must be separate')
        admission=verify_runtime_admission(ROOT,args.protocol,mission)
        scene=mission['scene'];start=np.array(mission['task']['start']);goal=np.array(mission['task']['goal']);initial_yaw=mission['task']['initial_yaw']
        if args.backend=='yopo':args.checkpoint=args.checkpoint or f'formal_main_v1_seed{mission["training_seed"]}/best_policy.pth'
    else:scene=generate(args.map_seed);start=np.array([-12.,0.,2.5]);goal=np.array([12.,0.,2.5])
    if args.backend=='yopo':
        args.checkpoint=args.checkpoint or 'resume_split_v2/best_policy.pth';checkpoint=(ROOT/'checkpoints'/args.checkpoint).resolve()
        if not checkpoint.is_relative_to(ROOT/'checkpoints') or not checkpoint.is_file():raise ValueError('Expected project scratch checkpoint')
        if mission:verify_formal_yopo_checkpoint(ROOT,checkpoint,mission['training_seed'])
        weight_description='local scratch training';checkpoint_sha=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    elif args.backend=='yopo_reference':
        # External-reference class: hash-pinned released weights. No from-scratch or
        # validation-selection claim is made; byte identity is the pinned fact.
        reference=json.loads(Path(args.protocol).read_text(encoding='utf-8'))['reference_weights']
        args.checkpoint=args.checkpoint or reference['staged_checkpoint']
        checkpoint=ROOT/'checkpoints'/args.checkpoint
        verified=verify_reference_weights(ROOT,checkpoint,reference)
        weight_description='official released epoch50 weights, rename-only into the main layout (external_reference class)'
        checkpoint_sha=verified['checkpoint_sha256']
        args.provenance_class='external_reference';args.reference_sha256=checkpoint_sha
        args.reference_provenance_file=reference['provenance_file']
    elif args.backend=='agile':
        gate=json.loads((ROOT/f'artifacts/agile_autonomy/torch_export_v1/torch_{args.device}_parity.json').read_text())
        if gate['status']!='passed' or gate['original_tf24_comparison']['status']!='passed':raise ValueError('Agile requested device has not passed numerical parity')
        weight_description='official Agile Autonomy ckpt50, converted without training';checkpoint_sha=gate['checkpoint_sha256']
    else:
        if args.device!='cpu':raise ValueError('TopoTraj numerical backend is CPU')
        args.topo_config=args.topo_config.resolve()
        if not args.topo_config.is_relative_to(ROOT) or not args.topo_config.is_file():raise ValueError('Expected explicit project TopoTraj configuration')
        weight_description='Analytic TopoTraj, no learned weights';checkpoint_sha=None
    identity_sha=checkpoint_sha if checkpoint_sha else hashlib.sha256(args.topo_config.read_bytes()+str(float(args.speed)).encode()+b'41be219fe4ecc43bf0e0c2b42a523f8755ccc0bd').hexdigest()
    args.scope=args.scope or ('scratch_smoke_interface_not_formal_benchmark' if args.backend=='yopo' else 'baseline_development_interface')
    initial_quaternion=np.array([np.cos(initial_yaw/2),0.,0.,np.sin(initial_yaw/2)])
    evaluator=ForestEvaluator(scene)
    if min(signed_distance(start,scene),signed_distance(goal,scene))<.8:raise ValueError('Fixed test endpoints are not clear')
    output=ROOT/'artifacts/ros2_flights'/args.run;output.mkdir(parents=True,exist_ok=False)
    if args.backend=='topotraj':(output/'backend_config.yaml').write_bytes(args.topo_config.read_bytes())
    (output/'scene.json').write_text(json.dumps(scene,indent=2))
    name='yopo-flight-'+args.run.lower();container_started=False;app=None;node=None
    report={'status':'running','scope':args.scope,'config':{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},'vehicle':json.loads((ROOT/'configs/unified_quad.json').read_text()),
            'backend':args.backend,'device':args.device,'mission':mission,'runtime_admission':admission,'initial_yaw':initial_yaw,
            'weights':weight_description,'checkpoint_sha256':checkpoint_sha,'identity_sha256':identity_sha,
            'map_truth_used_by_planner':False,'vehicle_hidden_from_depth':True,'start':start.tolist(),'goal':goal.tolist(),
            'ros_clock_origin_s':1.,'latency_rule':'availability>=capture_sim_time+measured_wall_acquisition_to_receipt_delay',
            'container_name':name,'physics':'PhysX rigid body plus motor lag and SO3 force/torque control; no pose/velocity setter after initial reset'}
    report['log_columns']=['t','x','y','z','vx','vy','vz','qw','qx','qy','qz','rx','ry','rz','rvx','rvy','rvz',
        'net_clearance','goal_error','motor_saturated','thrust_N','ax','ay','az','rax','ray','raz','rjx','rjy','rjz']
    rows=[];frames=[];depths=[];latencies=[];events=[];planning_events=[];sampler=None;status='crashed';model=Quadrotor();buffer=TrajectoryBuffer(1)
    current_sim=[1.];captures={};pending_trajectories={};timing_by_start={};lifecycle_events=[]
    hold_position=start.copy();terminal_since=None;settled_since=None
    try:
        existing=subprocess.check_output(['docker','ps','-aq','--filter',f'name=^/{name}$'],cwd=ROOT,text=True).strip()
        if existing:raise RuntimeError('Run container already exists; inspect it before proceeding')
        subprocess.run([sys.executable,str(ROOT/'scripts/ros2/configure_dds_tcp.py')],cwd=ROOT,check=True)
        command=['docker','compose','--profile','baselines' if args.backend=='topotraj' else 'training','run','-d','--rm','--name',name,
                 '-p','127.0.0.1:50142:50142','-e','FASTRTPS_DEFAULT_PROFILES_FILE=/workspace/configs/dds/tcp_server.xml',
                 'baseline-cpp' if args.backend=='topotraj' else 'train']
        if args.backend=='topotraj':
            config_path='/workspace/'+args.topo_config.relative_to(ROOT).as_posix()
            command+=['ros2','run','yopo_topotraj','topotraj_runtime','--ros-args','--params-file',config_path,
                '-p',f'manager.max_vel:={float(args.speed)}','-p',f'optimization.max_vel:={float(args.speed)}']
        else:
            planner_backend='yopo' if args.backend in ('yopo','yopo_reference') else args.backend
            command+=['python3','scripts/ros2/serve_planner.py','--run',args.run,'--backend',planner_backend,
                      '--speed',str(args.speed),'--device',args.device,'--wall-timeout','600']
            if args.backend in ('yopo','yopo_reference'):command+=['--checkpoint',args.checkpoint]
            if args.backend=='yopo_reference':
                command+=['--provenance-class','external_reference','--expected-sha256',args.reference_sha256]
        launch=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,check=True)
        container_started=True;report['container_id']=launch.stdout.strip().splitlines()[-1]
        (output/'container_launch.log').write_text(launch.stdout+launch.stderr)
        core=Path(sys.executable).parent/'Lib/site-packages/isaacsim/exts/isaacsim.ros2.core'
        os.environ.update(ROS_DISTRO='humble',RMW_IMPLEMENTATION='rmw_fastrtps_cpp',ROS_DOMAIN_ID='42',
            FASTRTPS_DEFAULT_PROFILES_FILE=str(ROOT/'configs/dds/tcp_client_windows.xml'),ROS_LOG_DIR=str(ROOT/'artifacts/ros2_logs'))
        os.environ['PATH']=str(core/'humble/lib')+os.pathsep+os.environ['PATH']
        from isaacsim import SimulationApp
        app=SimulationApp({'headless':True,'enable_cameras':True,'width':320,'height':180})
        import omni.kit.app
        import omni.usd
        import omni.replicator.core as rep
        from isaacsim.core.api import World
        from isaacsim.core.prims import RigidPrim
        from pxr import Gf,UsdGeom
        from scipy.spatial.transform import Rotation
        from yopo_sim.physx_vehicle import author_vehicle,read_state
        from yopo_repro.forest import author_scene
        omni.kit.app.get_app().get_extension_manager().set_extension_enabled_immediate('isaacsim.ros2.bridge',True)
        for _ in range(20):app.update()
        import rclpy
        from sensor_msgs.msg import Image,CameraInfo
        from nav_msgs.msg import Odometry
        from geometry_msgs.msg import PoseStamped
        from rosgraph_msgs.msg import Clock
        from std_msgs.msg import UInt64,String
        from trajectory_msgs.msg import MultiDOFJointTrajectory
        rclpy.init(domain_id=42);node=rclpy.create_node('yopo_native_physics')
        pubs={key:node.create_publisher(cls,'/yopo/runtime/'+key,10) for key,cls in
              [('episode',UInt64),('goal',PoseStamped),('depth',Image),('odom',Odometry),('camera_info',CameraInfo)]}
        clock_pub=node.create_publisher(Clock,'/clock',10)
        def accept_trajectory(message,source_key):
            start_ns=message.header.stamp.sec*1_000_000_000+message.header.stamp.nanosec
            if source_key not in captures:events.append({'event':'unmatched_observation_stamp','stamp_ns':source_key});return
            latency=time.perf_counter()-captures[source_key]['wall_start']
            accepted=buffer.submit(start_ns*1e-9,*decode_ros_trajectory(message),current_sim[0],latency,observation_start=source_key*1e-9)
            latencies.append([source_key*1e-9-1.,current_sim[0]-1.,latency,float(accepted)])
        def on_trajectory(message):
            if message.header.frame_id!='e1/world':return
            if not message.points:buffer.stop(current_sim[0]);events.append({'t':current_sim[0]-1.,'event':'planner_stop'});return
            key=message.header.stamp.sec*1_000_000_000+message.header.stamp.nanosec
            if args.backend=='topotraj':
                if key in timing_by_start:accept_trajectory(message,timing_by_start[key]['observation_stamp_ns'])
                else:
                    pending_trajectories[key]=message
                    while len(pending_trajectories)>16:pending_trajectories.pop(next(iter(pending_trajectories)))
            else:accept_trajectory(message,key)
        def on_planning_event(message):
            value=json.loads(message.data);planning_events.append(value)
            if args.backend=='topotraj' and value.get('frame_id')=='e1/world' and value['status']=='published':
                key=value['trajectory_stamp_ns'];timing_by_start[key]=value
                if key in pending_trajectories:accept_trajectory(pending_trajectories.pop(key),value['observation_stamp_ns'])
                while len(timing_by_start)>32:timing_by_start.pop(next(iter(timing_by_start)))
        subscription=node.create_subscription(MultiDOFJointTrajectory,'/yopo/runtime/trajectory',on_trajectory,10)
        planning_subscription=node.create_subscription(String,'/yopo/runtime/planning_event',on_planning_event,50)
        lifecycle_subscription=node.create_subscription(String,'/yopo/runtime/execution_status',lambda message:lifecycle_events.append(json.loads(message.data)),10)
        deadline=time.monotonic()+40
        while node.count_subscribers('/yopo/runtime/depth')==0 and time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.02);app.update()
        if node.count_subscribers('/yopo/runtime/depth')==0:raise RuntimeError('Container planner DDS discovery failed')
        omni.usd.get_context().new_stage();stage=omni.usd.get_context().get_stage()
        initial_rotation=Rotation.from_euler('z',initial_yaw).as_matrix()
        author_scene(stage,scene);vehicle=author_vehicle(stage,report['vehicle'],position=start,orientation_wxyz=initial_quaternion)
        UsdGeom.Imageable(vehicle.GetPrim()).MakeInvisible()
        camera=UsdGeom.Camera.Define(stage,'/World/DepthCamera')
        camera.CreateFocalLengthAttr(18.);camera.CreateHorizontalApertureAttr(36.)
        camera.CreateVerticalApertureAttr(20.25);camera.CreateClippingRangeAttr((.04,40.))
        xf=UsdGeom.Xformable(camera);translate=xf.AddTranslateOp();orient=xf.AddOrientOp()
        def camera_pose(p,rotation):
            cp=p+rotation@np.array([0.,0.,.1]);usd=np.column_stack([-rotation[:,1],rotation[:,2],-rotation[:,0]])
            q=Rotation.from_matrix(usd).as_quat();translate.Set(Gf.Vec3d(*cp.tolist()))
            orient.Set(Gf.Quatf(float(q[3]),Gf.Vec3f(*q[:3].tolist())))
        product=rep.create.render_product('/World/DepthCamera',(160,90))
        depth_ann=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');depth_ann.attach(product)
        dt=model.config['physics_dt_s'];world=World(stage_units_in_meters=1.,physics_dt=dt,rendering_dt=1/args.camera_hz)
        body=world.scene.add(RigidPrim('/World/Quadrotor',name='common_quadrotor',track_contact_forces=True));world.reset()
        body.set_world_poses(positions=start[None].astype(np.float32),orientations=initial_quaternion[None].astype(np.float32))
        body.set_linear_velocities(np.zeros((1,3),np.float32));body.set_angular_velocities(np.zeros((1,3),np.float32))
        camera_pose(start,initial_rotation)
        for _ in range(12):rep.orchestrator.step(delta_time=0.,pause_timeline=False,rt_subframes=1)
        initial_clock=float(world.current_time)
        goal_message=PoseStamped();goal_message.header.frame_id='e1/world';goal_message.pose.orientation.w=1.;assign_xyz(goal_message.pose.position,goal)
        clock=Clock();clock.clock.sec=1
        initialization_started=time.perf_counter();initialization_deadline=time.monotonic()+60
        while not any(v.get('episode')==1 and v.get('phase')=='episode_ready' for v in lifecycle_events):
            if time.monotonic()>initialization_deadline:raise RuntimeError('Planner did not acknowledge episode initialization')
            if any(v.get('episode')==1 and v.get('phase')=='episode_failed' for v in lifecycle_events):raise RuntimeError('Planner episode initialization failed')
            pubs['episode'].publish(UInt64(data=1));clock_pub.publish(clock);pubs['goal'].publish(goal_message);rclpy.spin_once(node,timeout_sec=.02)
        report['episode_initialization_wall_s']=time.perf_counter()-initialization_started
        report['initialization_note']='Waited before flight timing for the backend to initialize/reset; no sensor data supplied during initialization.'
        for _ in range(5):pubs['goal'].publish(goal_message);rclpy.spin_once(node,timeout_sec=.01)
        wall_start=time.perf_counter();next_capture=0.;last_velocity=np.zeros(3);acceleration=np.zeros(3)
        sampler=ResourceSampler(output/'native_resources.jsonl',lambda:current_sim[0]-1.,container_id=report['container_id'])
        sampler.start()
        force=np.array([0.,0.,model.mass*model.gravity]);desired=initial_rotation.copy();status='timeout'
        report['camera']={'width':160,'height':90,'fx':80.,'fy':80.,'cx_pixel_index':79.5,'cy_pixel_index':44.5,'body_translation_m':[0,0,.1]}
        in_hold=True;max_drift=0.;max_contact=0.
        for k in range(round(args.duration/dt)):
            t=k*dt;current_sim[0]=1.+t;stamp(clock.clock,current_sim[0]);clock_pub.publish(clock)
            for _ in range(3):rclpy.spin_once(node,timeout_sec=0.)
            p,q,rotation,velocity,rates=read_state(body)
            if not np.isfinite(np.r_[p,q,velocity,rates]).all():raise RuntimeError('Non-finite physics state')
            if k:acceleration=(velocity-last_velocity)/dt
            last_velocity=velocity.copy();clear=evaluator.distance(p)-model.config['collision_envelope_radius_m']
            distance=float(np.linalg.norm(goal-p))
            contact=np.asarray(body.get_net_contact_forces(dt=dt),float).reshape(-1,3)[0]
            contact_force=float(np.linalg.norm(contact));max_contact=max(max_contact,contact_force)
            if clear<=0 or contact_force>1e-5:
                events.append({'t':t,'event':'collision','net_clearance_m':clear,'physical_contact_force_N':contact_force})
                status='collision';break
            if np.any(np.abs(p[:2])>39):status='out_of_map';break
            if distance<1. and terminal_since is None:terminal_since=t;buffer.stop();events.append({'t':t,'event':'terminal_hold'})
            if terminal_since is not None:
                if distance<.5 and np.linalg.norm(velocity)<.3:
                    if settled_since is None:settled_since=t
                    if t-settled_since>=.5:status='success';break
                else:settled_since=None
            if t+1e-9>=next_capture and terminal_since is None:
                next_capture+=1/args.camera_hz;key=int(round(current_sim[0]*1e9));capture_started=time.perf_counter()
                camera_pose(p,rotation);before=float(world.current_time)
                for _ in range(2):rep.orchestrator.step(delta_time=0.,pause_timeline=False,rt_subframes=1)
                max_drift=max(max_drift,abs(float(world.current_time)-before))
                if max_drift>dt*.5:raise RuntimeError('Rendering advanced physics unexpectedly')
                depth=np.asarray(depth_ann.get_data(),np.float32).reshape(90,160).copy()
                depth=np.clip(np.nan_to_num(depth,nan=20.,posinf=20.,neginf=0.),0.,20.)
                captures[key]={'wall_start':capture_started,'sim':current_sim[0]}
                image=Image();stamp(image.header.stamp,current_sim[0]);image.header.frame_id='e1/camera_optical'
                image.width=160;image.height=90;image.step=640;image.encoding='32FC1';image.data=depth.tobytes()
                odom=Odometry();odom.header.stamp=image.header.stamp;odom.header.frame_id='e1/world';odom.child_frame_id='e1/base_link'
                assign_xyz(odom.pose.pose.position,p)
                odom.pose.pose.orientation.w,odom.pose.pose.orientation.x,odom.pose.pose.orientation.y,odom.pose.pose.orientation.z=map(float,q)
                assign_xyz(odom.twist.twist.linear,rotation.T@velocity);assign_xyz(odom.twist.twist.angular,rates)
                info=CameraInfo();info.header=image.header;info.width=160;info.height=90
                info.k=[80.,0.,79.5,0.,80.,44.5,0.,0.,1.];info.p=[80.,0.,79.5,0.,0.,80.,44.5,0.,0.,0.,1.,0.]
                pubs['camera_info'].publish(info);pubs['odom'].publish(odom);pubs['depth'].publish(image)
                frames.append([t,*p,*q,*velocity,(time.perf_counter()-capture_started)*1000]);depths.append(depth)
            if k%5==0:
                applied_before=buffer.stats['applied']
                reference=buffer.sample(current_sim[0]) if terminal_since is None else None
                if buffer.stats['applied']>applied_before:
                    active=buffer.active
                    events.append({'event':'trajectory_applied','t':t,'capture_t':active.observation_start-1.,'trajectory_start_t':active.start-1.,
                        'available_t':active.available-1.,'wall_latency_s':active.latency})
                if reference is None:
                    if not in_hold:
                        hold_position=p.copy()
                        events.append({'t':t,'event':'terminal_hold_started' if terminal_since is not None else 'trajectory_expired_hold'})
                    in_hold=True
                    reference={'position':goal if terminal_since is not None else hold_position,'velocity':np.zeros(3),'acceleration':np.zeros(3),
                               'yaw':float(np.arctan2(rotation[1,0],rotation[0,0])),'jerk':np.zeros(3)}
                else:in_hold=False
                force,desired=model.outer(p,velocity,acceleration,reference)
            fw,tw,debug=model.step_wrench(rotation,rates,velocity,force,desired,dt)
            if k%5==0:rows.append([t,*p,*velocity,*q,*reference['position'],*reference['velocity'],clear,distance,float(debug['saturated']),debug['collective_thrust_N'],*acceleration,*reference['acceleration'],*reference['jerk']])
            body.apply_forces_and_torques_at_pos(fw[None].astype(np.float32),tw[None].astype(np.float32),is_global=True)
            world.step(render=False)
            # Pace when faster than real time; a slow simulator still charges
            # measured wall pipeline delay through TrajectoryBuffer.
            remaining=wall_start+(t+dt)-time.perf_counter()
            if remaining>0:time.sleep(remaining)
            if k%1000==0:print(f'ROS2_FLIGHT t={t:.1f} p={p.round(2).tolist()} trajectories={buffer.stats["applied"]} clearance={clear:.3f}',flush=True)
        elapsed=time.perf_counter()-wall_start
        t=float(world.current_time)-initial_clock;p,q,rotation,velocity,rates=read_state(body)
        clear=evaluator.distance(p)-model.config['collision_envelope_radius_m'];distance=float(np.linalg.norm(goal-p))
        if rows and t>rows[-1][0]:rows.append([t,*p,*velocity,*q,*reference['position'],*reference['velocity'],clear,distance,float(debug['saturated']),debug['collective_thrust_N'],*acceleration,*reference['acceleration'],*reference['jerk']])
        data=np.asarray(rows);lat=np.asarray(latencies)
        report.update(status=status,wall_runtime_s=elapsed,sim_duration_s=t,real_time_factor=t/elapsed,
            final_position=p.tolist(),goal_error_m=distance,render_clock_drift_max_s=max_drift,buffer_stats=buffer.stats,
            max_physical_contact_force_N=max_contact,
            interface_passed=buffer.stats['applied']>=3,frames=len(frames),events=events,
            path_length_m=float(np.linalg.norm(np.diff(data[:,1:4],axis=0),axis=1).sum()) if len(data)>1 else 0.,
            min_net_clearance_m=min(float(data[:,17].min()),clear) if len(data) else clear,
            tracking_rmse_m=float(np.sqrt(np.mean(np.sum((data[:,1:4]-data[:,11:14])**2,axis=1)))) if len(data) else None,
            max_speed_mps=float(np.linalg.norm(data[:,4:7],axis=1).max()) if len(data) else None,
            end_to_end_wall_p50_ms=float(np.percentile(lat[:,2],50)*1000) if len(lat) else None,
            end_to_end_wall_p95_ms=float(np.percentile(lat[:,2],95)*1000) if len(lat) else None)
    except Exception as exc:
        report.update(status='crashed',traceback=traceback.format_exc(),buffer_stats=buffer.stats,events=events)
        if isinstance(exc,subprocess.CalledProcessError):report['subprocess_stderr']=exc.stderr
        print(report['traceback'],flush=True)
    finally:
        if sampler is not None:sampler.close()
        if report['status']=='running':report.update(status='interrupted',reason='Execution ended before final verdict')
        np.savez_compressed(output/'flight.npz',log=np.asarray(rows),frames=np.asarray(frames),depths=np.asarray(depths),latencies=np.asarray(latencies),start=start,goal=goal)
        if rows:np.savetxt(output/'flight.csv',np.asarray(rows),delimiter=',',header=','.join(report['log_columns']),comments='')
        (output/'metrics.json').write_text(json.dumps(report,indent=2)+'\n')
        (output/'planning_events.jsonl').write_text(''.join(json.dumps(event)+'\n' for event in planning_events),encoding='utf-8')
        (output/'lifecycle_events.jsonl').write_text(''.join(json.dumps(event)+'\n' for event in lifecycle_events),encoding='utf-8')
        if args.backend=='topotraj':
            summary={'status':'stopped','backend':'topotraj','device':'cpu','checkpoint_sha256':None,'identity_sha256':identity_sha,
                     'stats':{'published':sum(v.get('status')=='published' for v in planning_events),
                     'no_path':sum(v.get('status')=='planner_no_path' for v in planning_events),
                     'stale_result':sum(v.get('status')=='stale_result' for v in planning_events),
                     'planner_errors':sum(v.get('status')=='nonfinite_result' for v in planning_events)},
                     'source':'Native receiver timing/lifecycle messages from original ROS2 C++ backend'}
            (output/'planner_status.json').write_text(json.dumps(summary,indent=2)+'\n')
        if node is not None:node.destroy_node();rclpy.shutdown()
        if container_started:
            logs=subprocess.run(['docker','logs',name],cwd=ROOT,text=True,capture_output=True)
            (output/'planner_container.log').write_text(logs.stdout+logs.stderr,encoding='utf-8')
            subprocess.run(['docker','stop','--time','10',name],cwd=ROOT,check=False)
        if app is not None:app.close()
    print('ROS2_FLIGHT_RESULT '+json.dumps(report),flush=True)
    return 0 if report.get('interface_passed') else 2


if __name__=='__main__':raise SystemExit(main())
