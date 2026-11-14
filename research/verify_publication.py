"""Read-only checks for the published research snapshot. No experiment execution."""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote


def main():
    root = Path(__file__).resolve().parent
    checkout = root.parent
    failures = []
    manifest = json.loads((root / 'publication-manifest.json').read_text(encoding='utf-8'))
    for item in manifest['records']:
        path = checkout / item['published']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['published_sha256']:
            failures.append('published hash mismatch: ' + item['published'])
        if item['transformation'].startswith('gzip'):
            with gzip.open(path, 'rb') as stream:
                digest = hashlib.sha256(stream.read()).hexdigest()
            if digest != item['source_sha256']:
                failures.append('decompressed source hash mismatch: ' + item['published'])
    json_count = 0
    for path in root.rglob('*.json'):
        try:
            json.loads(path.read_text(encoding='utf-8-sig'))
            json_count += 1
        except (ValueError, UnicodeError) as error:
            failures.append('invalid JSON: ' + str(path.relative_to(root)) + ' ' + str(error))
    link_count = 0
    paths = list(root.rglob('*.md')) + [checkout / 'README.md']
    pattern = re.compile(r'!?\[[^\]\n]*\]\(([^)\n]+)\)')
    for path in paths:
        for match in pattern.finditer(path.read_text(encoding='utf-8-sig')):
            href = match.group(1).strip().removeprefix('<').removesuffix('>')
            if href.startswith(('https://', 'http://', 'mailto:', '#', 'app://', 'codex://')):
                continue
            name, _, fragment = href.partition('#')
            dest = (path.parent / unquote(name).replace('\\', '/')).resolve()
            link_count += 1
            if not dest.exists() or not dest.is_relative_to(checkout):
                failures.append('missing/outside local link: ' + str(path.relative_to(checkout)) + ': ' + href)
            elif dest.name == 'ARTIFACTS.md' and fragment:
                if f'id="{fragment}"' not in dest.read_text(encoding='utf-8'):
                    failures.append('missing artifact anchor: ' + href)
    dangerous = re.compile(r'(?:ghp_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----)')
    for path in root.rglob('*'):
        if path.is_file() and path.suffix in {'.md', '.py', '.json', '.yaml', '.yml', '.sh', '.ps1'}:
            if dangerous.search(path.read_text(encoding='utf-8-sig', errors='replace')):
                failures.append('potential credential: ' + str(path.relative_to(root)))
    for name in ['tools/prepare_github_research_release.py', 'tools/run_weak_coverage_camera_teacher.py',
                 'tools/weak_coverage_teacher_runtime.py', 'verify_publication.py']:
        ast.parse((root / name).read_text(encoding='utf-8-sig'), filename=name)
    all_files = [path for path in root.rglob('*') if path.is_file()]
    for path in all_files:
        if path.stat().st_size >= 50_000_000:
            failures.append('oversized Git blob: ' + str(path.relative_to(root)))
        if path.suffix in {'.pth', '.pt', '.mp4', '.avi', '.7z', '.pyd'}:
            failures.append('excluded runtime/media blob: ' + str(path.relative_to(root)))
    print(json.dumps({'passed': not failures, 'imported_hashes_checked': len(manifest['records']),
                      'json_files_checked': json_count, 'local_links_checked': link_count,
                      'total_files': len(all_files), 'total_bytes': sum(p.stat().st_size for p in all_files),
                      'failures': failures}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
