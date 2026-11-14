"""Verify retained package, new visibility annotations and selected identities."""
import collections
import json
from pathlib import Path
import build_paired_paper_scale as b

ROOT = b.ROOT
OLD = ROOT / 'DataSet/paired_assistant_full_review/export'
OUT = ROOT / 'DataSet/paired_assistant_truncated_review/export'


def main():
    old = b.read(OLD / 'manifest.json')
    rows = b.read(OUT / 'manifest.json')
    lookup = {r['sample']: r for r in rows}
    selected_changes = 0
    for prior in old:
        current = lookup[prior['sample']]
        for key in ('recording', 'category', 'aris_frame', 'source', 'reference_sd', 'sd_index',
                    'sd_pts', 'camera_boxes_xyxy', 'sonar_bbox_xyxy', 'review',
                    'camera_image_sha256', 'sonar_image_sha256', 'camera_original_label_sha256'):
            assert prior[key] == current[key], (prior['sample'], key)
        for key in ('camera_image', 'sonar_image', 'camera_original_label'):
            assert (OLD / prior[key]).read_bytes() == (OUT / current[key]).read_bytes()
        changed = prior['selected_for_100_per_recording'] != current['selected_for_100_per_recording']
        assert not changed or prior['recording'] == '2023-09-20_182317'
        selected_changes += changed
    added = [r for r in rows if r['sample'] not in {p['sample'] for p in old}]
    assert len(old) == 3283 and len(rows) == 3398 and len(added) == 115
    assert {r['aris_frame'] for r in added} == set(range(171, 286))
    visibility = b.read(OUT / 'camera-visibility.json')
    assert set(visibility) == {r['sample'] for r in added}
    status = collections.Counter(v['status'] for v in visibility.values())
    assert status == {'bottom_edge_transition': 5, 'truncated_bottom': 110}
    for r in added:
        assert r['camera_visibility'] == r['review']['camera_visibility'] == visibility[r['sample']]
        assert r['camera_boxes_xyxy'][0][3] == 360
    for name in ('coco_all_reviewed.json', 'coco_selected.json'):
        coco = b.read(OUT / 'camera' / name)
        ids = {i['id']: Path(i['file_name']).stem for i in coco['images']}
        for ann in coco['annotations']:
            if ids[ann['image_id']] in visibility:
                assert ann['attributes']['camera_visibility_status'] == visibility[ids[ann['image_id']]]['status']
    summary = b.read(OUT / 'summary.json')
    assert summary['selected_pairs'] == 3000 and summary['reserve_pairs'] == 398
    assert summary['recordings_with_100'] == 30 and summary['selected_shortfall_to_3000'] == 0
    for row in summary['recordings']:
        assert row['selected'] == 100
    selected_by_class = collections.Counter(r['category'] for r in rows if r['selected_for_100_per_recording'])
    assert set(selected_by_class.values()) == {1000}
    rec = [r for r in rows if r['recording'] == '2023-09-20_182317']
    result = dict(status='passed', retained_prior_pairs_exact=len(old), new_accepted=len(added),
        accepted_pairs=len(rows), selected_pairs=3000, reserve_pairs=398, recording_total=146,
        recordings_with_100=30, visibility_counts=dict(status),
        prior_182317_selection_flags_changed=selected_changes,
        prior_package_manifest_sha256=b.sha(OLD / 'manifest.json'),
        new_package_manifest_sha256=b.sha(OUT / 'manifest.json'),
        new_source_min_sd_index=min(r['sd_index'] for r in rec),
        new_source_max_sd_index=max(r['sd_index'] for r in rec),
        paired_camera_video_progress_max_s=max(r['sd_index'] for r in rec)/(30000/1001),
        timing_unchanged=True, precision_sync_certified=False, expert_gt_certified=False,
        original_camera_labels_preserved=True,
        quality_claim='Integrity and recorded assistant review, not expert annotation or precision synchronization.',
        source_hashes={
            'review_decisions': b.sha(ROOT / 'DataSet/paired_assistant_bomb_truncated/decisions.json'),
            'review_events': b.sha(ROOT / 'DataSet/paired_assistant_bomb_truncated/review-events.jsonl'),
            'review_visual_log': b.sha(ROOT / 'DataSet/paired_assistant_bomb_truncated/visual-review.json'),
            'temporal_manifest': b.sha(b.CAM / 'manifest-resolved.json'),
        })
    b.save(OUT / 'provenance-audit.json', result)
    for kind, flag in (('selected', True), ('reserve', False)):
        (OUT / f'{kind}-samples.txt').write_text(''.join(r['sample'] + '\n' for r in rows
            if r['selected_for_100_per_recording'] == flag), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
