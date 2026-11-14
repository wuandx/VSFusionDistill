"""Export cumulative labels under the user-authorized camera truncation rule."""
import argparse
import json
import export_paired_reviewed as export
import verify_paired_reviewed as verify
from export_paired_assistant_full_review import REVIEW_ROOTS as PRIOR_ROOTS, CANDIDATE_RELATIVE_FILES

ROOT = export.ROOT
OUT = ROOT / 'DataSet/paired_assistant_truncated_review/export'
REVIEW_ROOTS = PRIOR_ROOTS + ['paired_assistant_bomb_truncated']


def annotate_visibility():
    rows = export.b.read(OUT / 'manifest.json')
    visibility = {}
    for row in rows:
        info = row['review'].get('camera_visibility')
        if info:
            row['camera_visibility'] = info
            visibility[row['sample']] = info
    assert len(visibility) == 115
    export.b.save(OUT / 'manifest.json', rows)
    for name in ('coco_all_reviewed.json', 'coco_selected.json'):
        data = export.b.read(OUT / 'camera' / name)
        by_id = {im['id']: im['file_name'].rsplit('/', 1)[-1].rsplit('.', 1)[0] for im in data['images']}
        for ann in data['annotations']:
            info = visibility.get(by_id[ann['image_id']])
            if info:
                ann['attributes'] = dict(camera_visibility_status=info['status'],
                                         truncated=info['truncated'],
                                         box_extent='visible_part_within_image',
                                         original_camera_label_preserved=True)
        export.b.save(OUT / 'camera' / name, data)
    export.b.save(OUT / 'camera-visibility.json', visibility)
    summary = export.b.read(OUT / 'summary.json')
    summary.update(camera_truncated_clear_added=110, camera_edge_transition_added=5,
                   acceptance_rule='Identifiable partial camera targets allowed; labels bound visible part.',
                   paper_count_met=True, paper_method_reproduced=False)
    export.b.save(OUT / 'summary.json', summary)
    html = (OUT / 'index.html').read_text(encoding='utf-8')
    html = html.replace('目标 3000 对尚未完成。', '数量达到30条各100对，共3000对；不等同于CMHD标注方法复现。')
    html = html.replace('</h1>', '</h1><p><strong>182317复核后146对接受，选入100、备用46。</strong>'
                        '按用户要求允许可辨认的截断目标，新增115对（110明确底部截断、5触底过渡）。'
                        '保留原相机框和时间对应，精密同步疑点未解决。'
                        '<a href="README.md">使用说明</a> · '
                        '<a href="camera-visibility.json">截断记录</a> · '
                        '<a href="selected-samples.txt">选入清单</a></p>', 1)
    (OUT / 'index.html').write_text(html, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    export.OUT = OUT
    export.REVIEW_ROOTS = REVIEW_ROOTS
    export.CANDIDATE_FILES = [ROOT / 'DataSet' / p for p in CANDIDATE_RELATIVE_FILES]
    verify.OUT = OUT
    if not args.verify_only:
        export.main()
        annotate_visibility()
    verify.main()


if __name__ == '__main__':
    main()
