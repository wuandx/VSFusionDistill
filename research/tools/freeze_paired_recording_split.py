"""Freeze metadata-only paired recording roles. No image or original-test reads."""
import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'DataSet/paired_assistant_truncated_review/export'
OUT = ROOT / 'DataSet/paired_recording_split'
SEED = 42

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def dump(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    paths = [SOURCE / x for x in ['manifest.json', 'selected-samples.txt', 'reserve-samples.txt']]
    paths += [ROOT / 'DataSet/camera_temporal_all/manifest-resolved.json', Path('D:/pby/data_processed/matches.csv')]
    before = {str(p): sha(p) for p in paths}
    items = json.loads(paths[0].read_text(encoding='utf-8'))
    selected, reserve = [set(p.read_text(encoding='utf-8').splitlines()) for p in paths[1:3]]
    assert len(selected) == 3000 and len(reserve) == 398 and not selected & reserve
    assert {x['sample'] for x in items} == selected | reserve
    assert len(items) == 3398
    allowed = json.loads(paths[3].read_text(encoding='utf-8'))
    recs = defaultdict(list)
    for x in items:
        recs[x['recording']].append(x)
        assert x['source_paired_role'] != 'test'
        assert bool(x['selected_for_100_per_recording']) == (x['sample'] in selected)
    assert len(recs) == 30
    assert set(recs) <= {x['recording'] for x in allowed['recordings']}
    with paths[4].open(encoding='utf-8-sig', newline='') as f:
        matches = {r['aris_file'].split('/')[-1]: r for r in csv.DictReader(f) if r['aris_file'].split('/')[-1] in recs}
    assert set(matches) == set(recs)
    parent = {r: r for r in recs}
    def find(r):
        while parent[r] != r:
            r = parent[r]
        return r
    def union(a, b):
        a, b = find(a), find(b)
        parent[max(a, b)] = min(a, b)
    union('2023-09-21_122608', '2023-09-21_122855')
    for field in ['gantry_file', 'gopro_file']:
        seen = {}
        for r, m in sorted(matches.items()):
            if m[field] in seen:
                union(r, seen[m[field]])
            seen[m[field]] = r
    groups = defaultdict(list)
    for r in sorted(recs):
        groups[find(r)].append(r)
    roles, ranking = {}, {}
    for category in sorted({x['category'] for x in items}):
        gs = [g for g, rs in groups.items() if recs[rs[0]][0]['category'] == category]
        gs.sort(key=lambda g: hashlib.sha256(f'{SEED}|{category}|{g}'.encode()).hexdigest())
        ranking[category] = gs
        choices = [c for n in range(1, len(gs)+1) for c in itertools.combinations(gs, n) if sum(len(groups[g]) for g in c) == 2]
        test = choices[0]
        val = next(c for c in choices if not set(c) & set(test))
        for g in gs:
            for r in groups[g]:
                roles[r] = 'test' if g in test else 'val' if g in val else 'train'
    rows = []
    for r, xs in sorted(recs.items()):
        assert len({x['category'] for x in xs}) == 1
        assert sum(x['sample'] in selected for x in xs) == 100
        m = matches[r]
        rows.append(dict(recording=r, group_id=find(r), category=xs[0]['category'], role=roles[r], selected=100,
                         reserve=sum(x['sample'] in reserve for x in xs), historical_paired_roles=';'.join(sorted({x['source_paired_role'] for x in xs if x['source_paired_role']})),
                         development_history='included_in_40_recording_development_checks;full_history_not_certified',
                         gantry_file=m['gantry_file'], gopro_file=m['gopro_file'], notes=m['notes']))
    counts = Counter((r['category'], r['role']) for r in rows)
    assert all(counts[c, role] == n for c in ranking for role, n in [('train', 6), ('val', 2), ('test', 2)])
    for rs in groups.values():
        assert len({roles[r] for r in rs}) == 1
    overlay = [dict(sample=x['sample'], recording=x['recording'], group_id=find(x['recording']), category=x['category'], role=roles[x['recording']],
                    membership='selected' if x['sample'] in selected else 'reserve', camera_image=x['camera_image'], sonar_image=x['sonar_image'],
                    camera_image_sha256=x['camera_image_sha256'], sonar_image_sha256=x['sonar_image_sha256'], pairing_status=x['pairing']['status']) for x in items]
    for mod in ['camera', 'sonar']:
        byhash = defaultdict(set)
        for x in overlay:
            byhash[x[mod+'_image_sha256']].add(x['role'])
        assert all(len(v) == 1 for v in byhash.values())
    assert before == {str(p): sha(p) for p in paths}
    OUT.mkdir(exist_ok=True)
    assert not (OUT / 'manifest.json').exists(), 'Frozen output exists; do not overwrite'
    dump(OUT / 'manifest.json', overlay)
    with (OUT / 'recordings.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for role in ['train', 'val', 'test']:
        for member in ['selected', 'reserve']:
            names = sorted(x['sample'] for x in overlay if x['role'] == role and x['membership'] == member)
            (OUT / f'{role}-{member}.txt').write_text('\n'.join(names)+'\n', encoding='utf-8')
    dump(OUT / 'protocol.json', dict(name='paired_recording_split', seed=SEED, algorithm='sha256 group ranking; first feasible whole-group test then val combinations; remainder train', group_ranking=ranking, input_sha256=before, source_export=str(SOURCE), untouched_final_test=False, training_started=False))
    summary = {role: dict(recordings=sum(r['role']==role for r in rows), selected=sum(x['role']==role and x['membership']=='selected' for x in overlay), reserve=sum(x['role']==role and x['membership']=='reserve' for x in overlay)) for role in ['train','val','test']}
    dump(OUT / 'verification.json', dict(passed=True, summary=summary, per_class_recording_counts={c: {r: counts[c,r] for r in ['train','val','test']} for c in ranking}, recording_group_and_sample_disjoint=True, cross_role_image_hash_duplicates=0, source_inputs_unchanged=True, image_decodes=0, original_test_content_reads=0, output_sha256={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}))
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == '__main__':
    main()
