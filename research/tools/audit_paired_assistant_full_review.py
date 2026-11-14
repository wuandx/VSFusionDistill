"""Audit cumulative provenance and retention after the named full review export."""
import collections
import json
from pathlib import Path
import build_paired_paper_scale as b
from export_paired_assistant_full_review import REVIEW_ROOTS, CANDIDATE_RELATIVE_FILES

ROOT = b.ROOT
OUT = ROOT/'DataSet/paired_assistant_full_review/export'
OLD = ROOT/'DataSet/paired_assistant_remaining/export'


def main():
    rows = b.read(OUT/'manifest.json')
    old = b.read(OLD/'manifest.json')
    lookup = {r['sample']: r for r in rows}
    retained = 0
    selection_changed = 0
    for prior in old:
        current = lookup[prior['sample']]
        for key in ['recording', 'aris_frame', 'source', 'reference_sd', 'sd_index',
                    'sd_pts', 'camera_boxes_xyxy', 'sonar_bbox_xyxy',
                    'camera_image_sha256', 'sonar_image_sha256',
                    'camera_original_label_sha256']:
            assert current[key] == prior[key], (prior['sample'], key)
        for key in ['camera_image', 'sonar_image', 'camera_original_label']:
            assert (OUT/current[key]).read_bytes() == (OLD/prior[key]).read_bytes()
        retained += 1
        selection_changed += current['selected_for_100_per_recording'] != prior['selected_for_100_per_recording']

    snapshots = {}
    decisions = []
    temporal = {r['sample']:r for r in b.read(b.CAM/'manifest-resolved.json')['items']}
    legacy_specs_without_label_hash = 0
    for name in REVIEW_ROOTS:
        folder = ROOT/'DataSet'/name
        for filename in ['decisions.json', 'review-events.jsonl']:
            path = folder/filename
            if path.exists():
                snapshots[str(path.relative_to(ROOT))] = b.sha(path)
        for sample, decision in b.read(folder/'decisions.json').items():
            decisions.append(dict(decision, review_root=name))
            sheet = folder/decision['sheet']
            assert b.sha(sheet) == decision['sheet_sha256']
            specs = b.read(sheet.with_suffix('.json'))
            spec = next(x for x in specs['items'] if x['sample'] == sample)
            for path, key in [(Path(spec['source']), 'source_sha256'),
                              (b.CAM/spec['reference_sd'], 'camera_sha256'),
                              (b.CAM/spec['label_copy'], 'camera_label_sha256')]:
                if key == 'camera_label_sha256' and key not in spec:
                    expected = temporal[sample]['original_label_sha256_before']
                    legacy_specs_without_label_hash += 1
                else:
                    expected = spec[key]
                assert b.sha(path) == expected
            if decision['decision'] == 'accepted':
                assert decision['bbox_xyxy'] == spec['proposed_box']

    for relative in CANDIDATE_RELATIVE_FILES:
        path = ROOT/'DataSet'/relative
        snapshots[str(path.relative_to(ROOT))] = b.sha(path)
    for relative in ['DataSet/camera_temporal_all/manifest-resolved.json',
                     'DataSet/paired_paper_scale/source-inventory.json',
                     'tools/export_paired_assistant_full_review.py']:
        snapshots[relative] = b.sha(ROOT/relative)

    accepted_counts = collections.Counter(r['recording'] for r in rows)
    inventory = b.read(ROOT/'DataSet/paired_paper_scale/source-inventory.json')
    eligible = collections.Counter(r['recording'] for r in inventory
                                  if not r['camera_issues'] and r['pairing']['eligible_for_review'])
    seen = {d['sample'] for d in decisions}
    by_rec_seen = collections.defaultdict(set)
    for decision in decisions:
        by_rec_seen[decision['recording']].add(decision['sample'])
    category = {r['recording']: r['category'] for r in inventory}
    coverage = [dict(recording=rec, category=category[rec], eligible_source_count=n,
                     unique_viewed=len(by_rec_seen[rec]), accepted=accepted_counts[rec],
                     selected=min(100, accepted_counts[rec]),
                     shortfall=max(0, 100-accepted_counts[rec]),
                     source_identities_all_viewed=len(by_rec_seen[rec]) == n)
                for rec, n in sorted(eligible.items())]
    result = dict(status='passed', accepted_pairs=len(rows), unique_viewed=len(seen),
                  candidate_decisions=len(decisions), prior_885_retained_exact=retained,
                  legacy_specs_label_hash_checked_against_temporal=legacy_specs_without_label_hash,
                  prior_885_selection_flags_changed=selection_changed,
                  new_accepted_pairs=len(rows)-len(old),
                  by_category=dict(collections.Counter(r['category'] for r in rows)),
                  selected_by_category=dict(collections.Counter(r['category'] for r in rows
                      if r['selected_for_100_per_recording'])),
                  pairing_status=dict(collections.Counter(r['pairing']['status'] for r in rows)),
                  recordings_with_100_by_category=dict(collections.Counter(category[rec]
                      for rec, count in accepted_counts.items() if count >= 100)),
                  quality_claim='Integrity, retained provenance and assistant decisions only; not expert GT or precision synchronization.',
                  source_hashes=snapshots)
    b.save(OUT/'all-recording-coverage.json', coverage)
    b.save(OUT/'provenance-audit.json', result)
    print(json.dumps({k:v for k,v in result.items() if k != 'source_hashes'}, ensure_ascii=True))


if __name__ == '__main__':
    main()
