"""CPU-only full-map video from measured ROS2/PhysX logs, including failures."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle,Rectangle
import imageio.v2 as imageio

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--output-tag',default='');args=parser.parse_args()
    if args.output_tag and not re.fullmatch('[A-Za-z0-9_-]+',args.output_tag):raise ValueError('Invalid output tag')
    source=(ROOT/'artifacts/ros2_flights'/args.run).resolve()
    if not source.is_relative_to(ROOT/'artifacts/ros2_flights'):raise ValueError('Invalid source path')
    metrics=json.loads((source/'metrics.json').read_text());scene=json.loads((source/'scene.json').read_text())
    data=np.load(source/'flight.npz');log=data['log'];frames=data['frames'];depths=data['depths']
    if len(log)<2 or len(frames)==0:raise ValueError('No measured flight/depth history to render')
    planner=json.loads((source/'planner_status.json').read_text())
    identity=metrics.get('identity_sha256',metrics['checkpoint_sha256'])
    if planner.get('identity_sha256',planner['checkpoint_sha256'])!=identity:raise ValueError('Planner/flight identity provenance mismatch')
    output=ROOT/'artifacts/ros2_showcase'/(args.run+('_'+args.output_tag if args.output_tag else ''));output.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig=plt.figure(figsize=(12.8,7.2),dpi=100,facecolor='#f8fafb')
    global_ax=fig.add_axes([.055,.14,.535,.72]);zoom_ax=fig.add_axes([.635,.515,.32,.35])
    depth_ax=fig.add_axes([.635,.22,.17,.19]);info_ax=fig.add_axes([.825,.095,.16,.32]);info_ax.axis('off')
    axes=[global_ax,zoom_ax]
    for ax in axes:
        ax.set_facecolor('#f0f5f1')
        for x,y,radius,height in scene['trees']:ax.add_patch(Circle((x,y),radius,color='#487966',alpha=.85,lw=0))
        for x,y,z,sx,sy,sz in scene['shrubs']:ax.add_patch(Rectangle((x-sx/2,y-sy/2),sx,sy,color='#a5b295',alpha=.75,lw=0))
        ax.scatter(*data['start'][:2],color='#118270',s=55,zorder=5,marker='o',label='Start')
        ax.scatter(*data['goal'][:2],color='#2366bb',s=100,zorder=5,marker='*',label='Goal')
        ax.set_aspect('equal');ax.grid(color='white',linewidth=.6);ax.set_xlabel('World x [m]');ax.set_ylabel('World y [m]')
        for spine in ax.spines.values():spine.set_edgecolor('#c1cbc7')
    extent=scene['extent_m']/2;global_ax.set(xlim=(-extent,extent),ylim=(-extent,extent),title='Complete map and measured flight')
    all_xy=np.vstack([log[:,1:3],data['start'][:2],data['goal'][:2]])
    lower=all_xy.min(axis=0)-3;upper=all_xy.max(axis=0)+3
    center=(lower+upper)/2;span=np.maximum(upper-lower,[12,8])
    zoom_ax.set(xlim=(center[0]-span[0]/2,center[0]+span[0]/2),ylim=(center[1]-span[1]/2,center[1]+span[1]/2),title='Flight detail')
    lines=[];markers=[]
    for ax in axes:
        lines.append(ax.plot([],[],color='#de9319',lw=2.4,zorder=4,label='Measured trajectory')[0])
        markers.append(ax.plot([],[],'o',color='#d96720',markersize=7,zorder=6)[0])
    global_ax.legend(loc='upper left',fontsize=8,framealpha=.95)
    depth_image=depth_ax.imshow(depths[0],vmin=0,vmax=20,cmap='viridis');depth_ax.set_title('Recorded depth [0–20 m]',fontsize=9);depth_ax.axis('off')
    status_color='#14846c' if metrics['status']=='success' else '#b34538'
    info=info_ax.text(0,1,'',va='top',fontsize=10,linespacing=1.65,color='#203940')
    backend=metrics.get('backend','yopo');display={'yopo':'YOPO','agile':'Agile Autonomy','topotraj':'TopoTraj'}[backend]
    fig.text(.055,.952,display+' · Isaac Sim / ROS2',fontsize=20,fontweight='bold',color='#183c41')
    checkpoint=metrics['config']['checkpoint'];scope=metrics.get('scope','')
    if backend=='yopo':label='INTERMEDIATE CHECKPOINT — NOT FINAL BENCHMARK' if 'intermediate' in scope or 'smoke' in scope else 'LOCALLY TRAINED CHECKPOINT'
    else:
        label='BASELINE DEVELOPMENT — NOT FINAL BENCHMARK' if scope!='primary_frozen_benchmark' else 'BASELINE'
        checkpoint='Official Agile checkpoint' if backend=='agile' else 'Original TopoTraj algorithm'
    fig.text(.055,.91,f'{label}  |  {checkpoint}  |  Identity SHA256 {identity[:12]}',fontsize=9,color='#566e72')
    fig.text(.055,.034,f'Measured PhysX log replay · map {metrics["config"]["map_seed"]} · target {metrics["config"]["speed"]:g} m/s · playback 1× · outcome: {metrics["status"]}',fontsize=10,color=status_color)
    fig.text(.635,.15,'Measured trajectory only.\nVehicle marker enlarged.\nNo rerouting or smoothing.',fontsize=8,color='#647a7b')
    fps=20;end=float(log[-1,0]);replay=np.minimum(np.arange(int(np.ceil(end*fps))+1)/fps,end)
    video=output/'global_trajectory.mp4';writer=imageio.get_writer(video,fps=fps,codec='libx264',quality=8,
        macro_block_size=16,ffmpeg_params=['-threads','2'])
    try:
        for frame_number,t in enumerate(replay):
            index=int(np.clip(np.searchsorted(log[:,0],t,side='right')-1,0,len(log)-1))
            for line,marker in zip(lines,markers):
                line.set_data(log[:index+1,1],log[:index+1,2]);marker.set_data([log[index,1]],[log[index,2]])
            image_index=int(np.clip(np.searchsorted(frames[:,0],t,side='right')-1,0,len(frames)-1))
            depth_image.set_data(depths[image_index])
            speed=float(np.linalg.norm(log[index,4:7]));clearance=float(log[index,17]);distance=float(log[index,18])
            info.set_text(f'TIME\n{t:5.2f} / {end:.2f} s\n\nSPEED / HEIGHT\n{speed:.2f} m/s · {log[index,3]:.2f} m\n\nNET CLEARANCE\n{clearance:.2f} m\n\nGOAL DISTANCE\n{distance:.2f} m')
            fig.canvas.draw();canvas=np.asarray(fig.canvas.buffer_rgba())[...,:3].copy();writer.append_data(canvas)
            if frame_number==len(replay)//2:fig.savefig(output/'flight_midpoint.png',dpi=150,facecolor=fig.get_facecolor())
            if frame_number%100==0:print(f'LOG_REPLAY {frame_number+1}/{len(replay)}',flush=True)
        for _ in range(2*fps):writer.append_data(canvas)
    finally:writer.close()
    fig.savefig(output/'global_overview.png',dpi=200,facecolor=fig.get_facecolor())
    fig.savefig(output/'global_overview.pdf',facecolor=fig.get_facecolor());plt.close(fig)
    # Native Isaac OpenCV omits FFmpeg; use its already installed standalone
    # imageio-ffmpeg decoder, as in the earlier project video validator.
    reader=imageio.get_reader(video,format='ffmpeg');count=0;first=None;middle=None;last=None
    for frame in reader:
        frame=np.asarray(frame)
        assert frame.shape==(720,1280,3)
        if count==0:first=frame.copy()
        if count==len(replay)//2:middle=frame.copy()
        last=frame;count+=1
    reader.close()
    assert count==len(replay)+2*fps and first is not None and last is not None and np.std(last)>10
    assert middle is not None and np.mean(np.abs(first.astype(float)-middle.astype(float)))>.05
    manifest={'source_flight':str(source/'flight.npz'),'source_sha256':hashlib.sha256((source/'flight.npz').read_bytes()).hexdigest(),
        'checkpoint_sha256':metrics['checkpoint_sha256'],'identity_sha256':identity,'backend':backend,'scope':scope,'navigation_status':metrics['status'],
        'rendering':'CPU Matplotlib visualization of measured Isaac PhysX logs, not a separate simulated flight',
        'global_map_extent_m':scene['extent_m'],'resolution':[1280,720],'fps':fps,'playback_speed':1.,
        'frames':count,'final_hold_seconds':2.,'video':str(video),'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),
        'first_last_frames_decoded':True,'trajectory_modified':False}
    (output/'render_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest),flush=True)


if __name__=='__main__':main()
