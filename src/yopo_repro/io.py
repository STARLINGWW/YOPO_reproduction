"""Project-local provenance and atomic progress files."""
import hashlib
import json
from pathlib import Path


def sha256_file(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda:file.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)
