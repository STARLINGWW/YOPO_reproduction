"""Only inference compatibility patches; retain original architecture/checkpoint."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'external/agile_autonomy/planner_learning/src/PlannerLearning/models/nets.py'
target=ROOT/'vendor/agile_ros2/nets.py';target.parent.mkdir(parents=True,exist_ok=True)
s=source.read_text(encoding='utf-8')
s=s.replace('from tensorflow.python.keras.applications import mobilenet',
            'from tensorflow.keras.applications import mobilenet')
s=s.replace("weights='imagenet'",'weights=None')
target.write_text(s,encoding='utf-8')
(target.parent/'provenance.json').write_text(json.dumps({
    'upstream_commit':'958c0d22e11d28a4d73b627029cf62ef1a1a95ab',
    'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'changes':['Use public Keras MobileNet import','Do not download ImageNet initializer; require complete official checkpoint restore before inference'],
    'status':'TF2.15 compatibility under validation; original TF2.4 numerical comparison pending',
    'scope':'Agile Autonomy baseline official weights, never YOPO scratch evidence',
},indent=2)+'\n',encoding='utf-8')
