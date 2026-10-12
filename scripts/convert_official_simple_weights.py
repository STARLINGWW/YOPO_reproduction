"""Bridge the released YOPO-Simple checkpoint into the main-branch policy layout.

The two official branches (``YOPO-Simple`` and ``main``) name the same tensors
differently: 126 keys are identical and 7 keys are pure renames with identical
shapes (``image_backbone.cnn.output_layer`` -> ``image_backbone.cnn.fc`` and
``yopo_head.model.*`` -> ``yopo_header.*``). This tool renames only: no value is
copied across tensors, rescaled, retrained or dropped, and the strict load into
the main-branch policy must succeed before anything is written.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.policy import build_policy

RENAME = {'image_backbone.cnn.output_layer.weight':'image_backbone.cnn.fc.weight'}
for index in (0,2,4):
    for suffix in ('weight','bias'):
        RENAME['yopo_head.model.%d.%s'%(index,suffix)] = 'yopo_header.%d.%s'%(index,suffix)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--record',type=Path,default=ROOT/'artifacts/expert/official_checkpoint_mapping.json')
    parser.add_argument('--reverse',action='store_true',
                        help='convert main-layout weights into the Simple layout (control arm of the weights A/B)')
    parser.add_argument('--reference',type=Path,default=ROOT/'external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth',
                        help='checkpoint in the target layout; every renamed key must match its name and shape')
    args = parser.parse_args()
    source = args.checkpoint if args.checkpoint.is_absolute() else ROOT/args.checkpoint
    raw = torch.load(source,map_location='cpu',weights_only=True)
    state = raw['state_dict'] if isinstance(raw,dict) and 'state_dict' in raw else raw
    rename = {value:key for key,value in RENAME.items()} if args.reverse else dict(RENAME)
    if args.reverse:
        reference_raw = torch.load(args.reference,map_location='cpu',weights_only=True)
        reference = reference_raw['state_dict'] if isinstance(reference_raw,dict) and 'state_dict' in reference_raw else reference_raw
        target = {key:value for key,value in reference.items()}
        policy = None
    else:
        policy,_,_ = build_policy(device='cpu')
        target = {key:value for key,value in policy.state_dict().items()}
    converted = {};mapping = {};problems = []
    for key,value in state.items():
        renamed = rename.get(key,key);mapping[key] = renamed
        if renamed not in target:
            problems.append({'key':key,'problem':'no matching tensor in the target layout'});continue
        if tuple(target[renamed].shape)!=tuple(value.shape):
            problems.append({'key':key,'problem':'shape mismatch','source':list(value.shape),
                             'target':list(target[renamed].shape)});continue
        converted[renamed] = value
    missing = sorted(key for key in target if key not in converted)
    if problems or missing:
        raise SystemExit(json.dumps({'problems':problems,'missing_target_keys':missing[:10]},ensure_ascii=False))
    if policy is not None:
        policy.load_state_dict(converted,strict=True)
    output = args.output if args.output.is_absolute() else ROOT/args.output
    output.parent.mkdir(parents=True,exist_ok=True)
    torch.save(converted,output)
    record = {'recorded_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'scope':'key rename only between the two official branches; values are bit-identical, key/shape equality verified',
              'direction':'main_to_simple' if args.reverse else 'simple_to_main',
              'layout_check':'target layout key set and shapes matched' if args.reverse else 'strict load into the main-branch policy passed',
              'source_checkpoint':str(source),'source_sha256':sha256_file(source),
              'output_checkpoint':str(output),'output_sha256':sha256_file(output),
              'reference_checkpoint':str(args.reference) if args.reverse else None,
              'source_keys':len(state),'target_keys':len(target),'renamed_keys':len(rename),
              'renamed_count_applied':sum(1 for key in state if key in rename),
              'identical_keys':sum(1 for key in state if key not in rename and key in target),
              'rename_map':rename,
              'strict_load':'passed' if not args.reverse else 'not_applicable_reference_layout_used'}
    args.record.parent.mkdir(parents=True,exist_ok=True)
    args.record.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({key:record[key] for key in ('source_keys','target_keys','renamed_count_applied',
                                                  'identical_keys','output_sha256','layout_check')},ensure_ascii=False))


if __name__ == '__main__':
    main()
