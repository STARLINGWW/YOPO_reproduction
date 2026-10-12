"""Read-back checks for checkpoint selection; no training or mutation of models."""
import hashlib,json,math
from pathlib import Path
import torch


def state_hash(state):
    digest=hashlib.sha256()
    for name,value in sorted(state.items()):
        digest.update(name.encode());digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def verify_model_selection(folder,expected_epochs):
    folder=Path(folder);manifest=json.loads((folder/'run_manifest.json').read_text(encoding='utf-8'))
    rows=[]
    for line in (folder/'metrics.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row.get('kind')=='epoch':rows.append(row)
    assert [row['epoch'] for row in rows]==list(range(1,expected_epochs+1)), 'Missing/duplicate epoch records'
    assert all(math.isfinite(row['validation_total']) for row in rows)
    best=min(rows,key=lambda row:row['validation_total']) # earliest epoch wins exact ties, like trainer.
    selected=torch.load(folder/'best_policy.pth',map_location='cpu',weights_only=True)
    selected_hash=state_hash(selected);del selected
    expected=torch.load(folder/f'policy_epoch_{best["epoch"]:03d}.pth',map_location='cpu',weights_only=True)
    assert selected_hash==state_hash(expected),'best_policy is not the validation-selected checkpoint'
    del expected
    initial=torch.load(folder/'initial_policy.pth',map_location='cpu',weights_only=True)
    initial_hash=state_hash(initial);del initial
    assert initial_hash==manifest['initial_model_sha256'],'Initialization file differs from provenance'
    return {'best_epoch':best['epoch'],'best_validation_total':best['validation_total'],
            'best_model_tensor_sha256':selected_hash,'initial_model_tensor_sha256':initial_hash,
            'best_policy_file_sha256':hashlib.sha256((folder/'best_policy.pth').read_bytes()).hexdigest()}
