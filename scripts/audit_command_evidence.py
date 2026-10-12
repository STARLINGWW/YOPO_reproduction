"""Audit that documented reproduction commands and evidence paths actually resolve.

This is a documentation/evidence consistency check, not a result claim: it
verifies that relative links in the project reports exist, that every
referenced script exists, and that referenced JSON evidence parses. Anything
that cannot be resolved is reported explicitly instead of being silently
accepted.
"""
from pathlib import Path
import argparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import write_json_atomic

LINK = re.compile(r'\]\(([^)\s]+?)\)')
PATH_TOKEN = re.compile(r'(?<![\w/.-])((?:scripts|src|configs|benchmarks|docker|ros2_ws|datasets|artifacts)/[A-Za-z0-9_./\-]+\.(?:py|ps1|sh|json|yaml|yml|jsonl|md|npz|npy|pth|pt|csv))')
FENCE = re.compile(r'```[a-zA-Z]*\n(.*?)```',re.S)


def normalise(target,source):
    target = target.strip().strip('<>')
    if target.startswith(('http://','https://','mailto:','codex://','#')):return None
    if target.startswith('/'):return None
    if re.match(r'^[A-Za-z]:[\\/]',target):return Path(target.replace('\\','/')).resolve()
    return (source.parent/target.replace('\\','/')).resolve()


def display(path):
    text = str(path).replace('\\','/')
    root = str(ROOT.resolve()).replace('\\','/')
    return text[len(root)+1:] if text.startswith(root+'/') else text


def audit_report(path):
    text = path.read_text(encoding='utf-8')
    links = [];missing_links = [];scripts = [];missing_scripts = [];bad_json = []
    for match in LINK.finditer(text):
        resolved = normalise(match.group(1),path)
        if resolved is None:continue
        relative = display(resolved)
        links.append(relative)
        if not resolved.exists():missing_links.append(relative)
        elif resolved.suffix=='.json' and resolved.stat().st_size<20*1024*1024:
            try:json.loads(resolved.read_text(encoding='utf-8'))
            except Exception as exc:bad_json.append({'path':relative,'error':str(exc)})
    for fence in FENCE.finditer(text):
        for token in set(PATH_TOKEN.findall(fence.group(1))):
            resolved = (ROOT/token).resolve()
            scripts.append(token)
            if not resolved.exists():missing_scripts.append(token)
    return {'report':str(path.relative_to(ROOT)).replace('\\','/'),'links':sorted(set(links)),
            'missing_links':sorted(set(missing_links)),'referenced_paths':sorted(set(scripts)),
            'missing_referenced_paths':sorted(set(missing_scripts)),'unparsable_json':bad_json}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reports',default='reports',
                        help='comma-separated folders to scan (default: reports)')
    parser.add_argument('--recursive',action='store_true',
                        help='scan the given folders recursively (default: top-level *.md only)')
    parser.add_argument('--extra-files',default='',
                        help='comma-separated extra markdown files to audit, relative to the project root')
    parser.add_argument('--output',default='artifacts/environment/command_evidence_audit.json')
    parser.add_argument('--fail-on-missing',action='store_true')
    args = parser.parse_args()
    reports = []
    for spec in [item.strip() for item in args.reports.split(',') if item.strip()]:
        folder = (ROOT/spec).resolve()
        if not folder.is_dir():
            print('skip missing folder',spec)
            continue
        found = folder.rglob('*.md') if args.recursive else folder.glob('*.md')
        reports.extend(sorted(found))
    reports.extend(sorted((ROOT/'benchmarks').glob('*.md')))
    for spec in [item.strip() for item in args.extra_files.split(',') if item.strip()]:
        reports.append((ROOT/spec).resolve())
    seen = set(); unique = []
    for path in reports:
        key = str(path).lower()
        if key in seen: continue
        seen.add(key); unique.append(path)
    reports = unique
    results = [audit_report(path) for path in reports if path.is_file()]
    summary = {'status':'passed','reports_scanned':len(results),
               'missing_link_count':sum(len(r['missing_links']) for r in results),
               'missing_path_count':sum(len(r['missing_referenced_paths']) for r in results),
               'unparsable_json_count':sum(len(r['unparsable_json']) for r in results),
               'scope':'documentation and evidence path consistency only; not a result or success-rate claim',
               'details':results}
    if summary['missing_link_count'] or summary['missing_path_count'] or summary['unparsable_json_count']:
        summary['status'] = 'gaps_found'
    write_json_atomic(ROOT/args.output,summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='details'},indent=2,ensure_ascii=False))
    for result in results:
        if result['missing_links'] or result['missing_referenced_paths'] or result['unparsable_json']:
            print(result['report'])
            for missing in result['missing_links'][:10]:print('  missing_link',missing)
            for missing in result['missing_referenced_paths'][:10]:print('  missing_path',missing)
            for bad in result['unparsable_json'][:5]:print('  unparsable_json',bad['path'])
    if args.fail_on_missing and summary['status']!='passed':raise SystemExit('Documented evidence gaps found')


if __name__=='__main__':main()
