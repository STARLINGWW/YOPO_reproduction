"""Reject native GPU admission while this project's formal trainer is running."""
import json,subprocess


def active_project_trainers():
    ids=subprocess.check_output(['docker','ps','-q','--filter','label=com.docker.compose.project=yopo-ros2-reproduction'],text=True).split()
    if not ids:return []
    records=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True))
    active=[]
    for record in records:
        command=record['Config'].get('Cmd') or []
        if record['State']['Running'] and any(str(part).endswith('train_scratch.py') for part in command):
            if '--device' in command and command[command.index('--device')+1]=='cpu':continue
            active.append({'id':record['Id'],'name':record['Name'].lstrip('/'),'command':command})
    return active


def require_training_gpu_released():
    active=active_project_trainers()
    if active:raise RuntimeError('Native GPU task refused while project training is live: '+', '.join(v['name'] for v in active))
