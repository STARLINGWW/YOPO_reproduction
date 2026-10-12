import math
import numpy as np


def percentiles(values):
    values=np.asarray(values,float)
    if len(values)==0:return None
    if not np.isfinite(values).all():raise ValueError('Non-finite metric samples')
    return {key:float(value) for key,value in zip(['p50','p95','p99'],np.percentile(values,[50,95,99]))}


def wilson_interval(successes,total,z=1.959963984540054):
    if total<0 or successes<0 or successes>total:raise ValueError('Invalid trial counts')
    if not total:return None
    p=successes/total;denominator=1+z*z/total
    center=(p+z*z/(2*total))/denominator
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator
    return [max(0.,center-half),min(1.,center+half)]


def flight_metrics(log,frames,latencies,source,planning_events):
    log=np.asarray(log,float);frames=np.asarray(frames,float);latencies=np.asarray(latencies,float)
    if log.ndim!=2 or log.shape[1]!=30 or len(log)<3 or not np.all(np.diff(log[:,0])>0):raise ValueError('Invalid measured control log')
    if not np.isfinite(log).all():raise ValueError('Non-finite control log')
    times=log[:,0];duration=float(times[-1]-times[0]);speed=np.linalg.norm(log[:,4:7],axis=1)
    tracking=np.linalg.norm(log[:,1:4]-log[:,11:14],axis=1)
    jerk_fd=np.gradient(log[:,21:24],times,axis=0,edge_order=2)
    report={'status':source['status'],'samples':len(log),'sim_duration_s':duration,
        'path_length_m':float(np.linalg.norm(np.diff(log[:,1:4],axis=0),axis=1).sum()),
        'mean_net_clearance_m':float(np.trapz(log[:,17],times)/duration),'min_net_clearance_m':float(log[:,17].min()),
        'mean_center_obstacle_distance_m':float(np.trapz(log[:,17],times)/duration+source['vehicle']['collision_envelope_radius_m']),
        'min_center_obstacle_distance_m':float(log[:,17].min()+source['vehicle']['collision_envelope_radius_m']),
        'tracking_rmse_m':float(np.sqrt(np.mean(tracking**2))),'tracking_error_m':percentiles(tracking),
        'speed_mps':percentiles(speed),'max_speed_mps':float(speed.max()),
        'reference_curve_squared_jerk_integral_m2_per_s5':float(np.trapz(np.sum(log[:,27:30]**2,axis=1),times)),
        'measured_raw_fd_squared_jerk_integral_m2_per_s5':float(np.trapz(np.sum(jerk_fd**2,axis=1),times)),
        'jerk_note':'Reference curve derivative integral excludes impulses at replanning/hold switches; measured acceleration finite-difference is unfiltered and includes numeric noise.',
        'motor_saturation_fraction':float(np.mean(log[:,19]>0)),
        'max_physical_contact_force_N':source.get('max_physical_contact_force_N'),
        'real_time_factor':source.get('real_time_factor'),
        'end_to_end_wall_ms':percentiles(latencies[:,2]*1000) if len(latencies) else None,
        'capture_and_publish_wall_ms':percentiles(frames[:,11]) if len(frames) else None}
    published=[v for v in planning_events if v['status']=='published']
    report['planner_and_publish_wall_ms']=percentiles([v['planner_wall_ms'] for v in published])
    report['planner_queue_wall_ms']=percentiles([v['queue_wall_ms'] for v in published if v.get('queue_wall_ms') is not None])
    report['map_fusion_wall_ms']=percentiles([v['map_fusion_wall_ms'] for v in published if v.get('map_fusion_wall_ms') is not None])
    report['map_esdf_wall_ms']=percentiles([v['map_esdf_wall_ms'] for v in published if v.get('map_esdf_wall_ms') is not None])
    report['backend_pipeline_wall_ms']=percentiles([v['debug']['planning_wall_ms'] for v in published if 'planning_wall_ms' in v.get('debug',{})])
    captures={round((row[0]+source.get('ros_clock_origin_s',1.))*1e9):row[11] for row in frames}
    responses={round((row[0]+source.get('ros_clock_origin_s',1.))*1e9):row[2]*1000 for row in latencies}
    residual=[]
    for v in published:
        key=v['observation_stamp_ns']
        if key in captures and key in responses and v.get('queue_wall_ms') is not None:residual.append(responses[key]-captures[key]-v['planner_wall_ms']-v['queue_wall_ms'])
    report['transport_and_other_scheduling_residual_ms']=percentiles(residual)
    report['negative_residual_count']=int(np.sum(np.asarray(residual)<0))
    report['residual_note']='Residual includes both transports, callbacks and native polling; not a separately synchronized one-way network measurement.'
    applied=[v for v in source.get('events',[]) if v['event']=='trajectory_applied']
    report['per_command_application_audit_available']=bool(applied)
    if applied:
        deltas=np.array([v['t']-v['capture_t'] for v in applied])
        assert all(v['t']+1e-8>=v['available_t'] and v['t']-v['capture_t']+1e-8>=v['wall_latency_s'] for v in applied)
        report['applied_simulation_delay_ms']=percentiles(deltas*1000)
    else:report['applied_simulation_delay_ms']=None
    return report
