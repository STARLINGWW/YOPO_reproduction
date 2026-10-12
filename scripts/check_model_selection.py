from pathlib import Path
import argparse,json
from training_audit_utils import verify_model_selection
ROOT=Path('/workspace')
parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--expected-epochs',type=int,required=True);args=parser.parse_args()
result=verify_model_selection(ROOT/'checkpoints'/args.run,args.expected_epochs)
report={'status':'passed','scope':'Checkpoint selection helper verification only; not formal50epoch completion','run':args.run,**result}
(ROOT/'artifacts/environment/checkpoint_selection_helper.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
