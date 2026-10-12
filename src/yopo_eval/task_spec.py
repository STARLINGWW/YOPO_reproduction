"""Resolve a frozen benchmark slot without rendering or loading a network."""
from pathlib import Path
import hashlib,json,re
import numpy as np


def resolve_episode(protocol_path,episode_id):
    protocol_path=Path(protocol_path).resolve();raw=protocol_path.read_bytes();protocol=json.loads(raw)
    matches=[v for v in protocol['episodes'] if v['id']==episode_id]
    if len(matches)!=1:raise ValueError('Episode must occur exactly once in the frozen protocol')
    episode=matches[0];task=protocol['tasks'][episode['task_index']]
    maps=[m for m in protocol['maps'] if m['seed']==task['map_seed'] and m['condition']==task['condition']]
    if len(maps)!=1:raise ValueError('Ambiguous map identity')
    map_path=(protocol_path.parent/maps[0]['file']).resolve()
    if not map_path.is_relative_to(protocol_path.parent):raise ValueError('Map path escapes protocol directory')
    if hashlib.sha256(map_path.read_bytes()).hexdigest()!=maps[0]['sha256']:raise ValueError('Frozen map hash changed')
    scene=json.loads(map_path.read_text())
    if scene['seed']!=task['map_seed'] or scene['density_per_m2']!=task['density_per_m2']:raise ValueError('Map metadata differs from task')
    start=np.array(task['start'],float);goal=np.array(task['goal'],float)
    if start.shape!=(3,) or goal.shape!=(3,) or not np.isfinite(np.r_[start,goal]).all():raise ValueError('Invalid endpoints')
    yaw=float(task['initial_yaw']);bearing=np.arctan2(goal[1]-start[1],goal[0]-start[0])
    if abs(np.arctan2(np.sin(yaw-bearing),np.cos(yaw-bearing)))>1e-10:raise ValueError('Initial heading does not face task goal')
    if not np.isclose(np.linalg.norm(goal-start),task['straight_distance_m']):raise ValueError('Task distance inconsistent')
    model=episode['model'];match=re.fullmatch('yopo_seed([012])',model)
    if match:backend='yopo';seed=int(match.group(1))
    elif model=='agile_autonomy':backend='agile';seed=None
    elif model=='topotraj':backend='topotraj';seed=None
    elif model=='mppi_reference17':backend='mppi_reference17';seed=None
    else:raise ValueError('Unknown baseline; no implicit substitution')
    return {'episode_id':episode_id,'protocol_sha256':hashlib.sha256(raw).hexdigest(),
            'map_sha256':maps[0]['sha256'],'episode':episode,'task':task,'scene':scene,
            'backend':backend,'training_seed':seed}


def verify_formal_yopo_checkpoint(root,checkpoint,seed):
    root=Path(root).resolve();checkpoint=Path(checkpoint).resolve()
    if not checkpoint.is_relative_to(root/'checkpoints'):raise ValueError('Checkpoint outside project')
    folder=checkpoint.parent;audit=json.loads((folder/'training_audit.json').read_text())
    manifest=json.loads((folder/'run_manifest.json').read_text())
    if audit['status']!='passed' or audit['epochs']!=50 or audit['seed']!=seed:raise ValueError('Formal50epoch seed audit missing')
    if manifest['seed']!=seed or not manifest['initialization'].startswith('random entire network'):raise ValueError('Initialization/seed mismatch')
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=audit['selection']['best_policy_file_sha256']:
        raise ValueError('Primary benchmark must use the audited validation-selected model')
    return audit


def verify_runtime_admission(root,protocol_path,mission):
    root=Path(root).resolve();path=Path(protocol_path).resolve().parent/'runtime_validation.json'
    if not path.is_file():raise ValueError('Formal matrix runtime configuration has not been validated/frozen')
    admission=json.loads(path.read_text())
    if admission.get('status')!='passed' or admission.get('protocol_sha256')!=mission['protocol_sha256']:
        raise ValueError('Runtime validation does not match this fixed task matrix')
    if mission['backend'] not in admission.get('validated_backends',[]):raise ValueError('This baseline has not passed native runtime validation')
    if not admission.get('runtime_files'):raise ValueError('No frozen runtime file hashes')
    for name,digest in admission['runtime_files'].items():
        source=(root/name).resolve()
        if not source.is_relative_to(root) or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
            raise ValueError('Runtime changed after benchmark validation: '+name)
    return admission
