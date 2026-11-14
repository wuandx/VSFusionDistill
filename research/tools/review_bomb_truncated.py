"""Record explicit visual decisions after all 13 existing paired sheets were viewed."""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import build_paired_paper_scale as b

ROOT = b.ROOT
REC = '2023-09-20_182317'
OUT = ROOT / 'DataSet/paired_assistant_bomb_truncated'
PRIOR = ROOT / 'DataSet/paired_assistant_full_review/export'
SHEETS = ROOT / 'DataSet/paired_assistant_bomb_remaining_review' / REC


def main():
    assert not OUT.exists(), 'Preserve named review'
    old = {r['sample']: r for r in b.read(PRIOR / 'manifest.json') if r['recording'] == REC}
    assert len(old) == 31 and {r['aris_frame'] for r in old.values()} == set(range(140, 171))
    OUT.mkdir(parents=True)
    decisions = {}
    pages = []
    now = datetime.now(timezone.utc).isoformat()
    for path in sorted(SHEETS.glob('page-*.json')):
        spec = b.read(path)
        jpg = path.with_suffix('.jpg')
        assert b.sha(jpg) == spec['sheet_sha256']
        destination = OUT / REC
        destination.mkdir(exist_ok=True)
        for source in (path, jpg):
            shutil.copyfile(source, destination / source.name)
            assert b.sha(source) == b.sha(destination / source.name)
        pages.append(dict(sheet=f'{REC}/{jpg.name}', sha256=b.sha(jpg), actually_viewed=True,
                          viewing='Actual paired review sheet inspected in this turn before decisions.'))
        for row in spec['items']:
            if row['sample'] in old:
                continue
            # Explicit accepted frame interval from the completed visual pass, not a proposal confidence rule.
            assert 171 <= row['aris_frame'] <= 285
            assert b.sha(row['source']) == row['source_sha256']
            assert b.sha(b.CAM / row['reference_sd']) == row['camera_sha256']
            assert b.sha(b.CAM / row['label_copy']) == row['camera_label_sha256']
            transition = row['aris_frame'] <= 175
            visibility = dict(status='bottom_edge_transition' if transition else 'truncated_bottom',
                              truncated=None if transition else True,
                              visible_target_identifiable=True,
                              visible_part_box_reviewed=True,
                              original_camera_label_preserved=True,
                              invisible_extent_estimated=False)
            reason = ('Actual paired sheet viewed under user-authorized partial-visibility rule. '
                      'Camera upper body and nose remain identifiable, original box bounds the visible part; '
                      'sonar B bounds the visible connected target echo without a separate lower return. '
                      'Bottom-edge transition is not asserted to be definite truncation.' if transition else
                      'Actual paired sheet viewed under user-authorized partial-visibility rule. '
                      'Camera target is cut by the bottom image boundary but remaining body/nose is identifiable; '
                      'original camera box bounds the visible part. Sonar B bounds the visible main echo. '
                      'Visual target consistency does not resolve published timing-offset uncertainty.')
            decisions[row['sample']] = dict(
                sample=row['sample'], recording=REC, category=row['category'], decision='accepted',
                bbox_xyxy=row['proposed_box'], author='assistant', reviewed_at=now, reason=reason,
                sheet=f'{REC}/{jpg.name}', sheet_sha256=spec['sheet_sha256'],
                source_sha256=row['source_sha256'], camera_sha256=row['camera_sha256'],
                camera_box_reviewed=True, cross_view_review='consistent_visible_target',
                camera_visibility=visibility, precision_sync_certified=False, expert_verified=False,
                acceptance_rule='partial_camera_target_allowed_when_identifiable_and_visible_box_valid',
            )
    assert len(pages) == 13 and len(decisions) == 115
    assert {int(k.rsplit('_', 1)[1]) for k in decisions} == set(range(171, 286))
    b.save(OUT / 'decisions.json', decisions)
    (OUT / 'review-events.jsonl').write_text(''.join(json.dumps(d, ensure_ascii=False) + '\n'
                                                  for d in decisions.values()), encoding='utf-8')
    b.save(OUT / 'visual-review.json', dict(recording=REC, actual_pages=pages,
        unique_identities_reviewed=146, new_decisions=115, prior_accepted_preserved=31,
        new_accepted=115, clear_camera_truncated=110, camera_bottom_transition=5,
        prior_manifest_sha256=b.sha(PRIOR / 'manifest.json'),
        precision_sync_certified=False, user_authorized_rule_change=True))
    print(json.dumps(dict(new_accepted=len(decisions), recording_total=146, viewed_pages=len(pages))))


if __name__ == '__main__':
    main()
