"""Materialize only the accepted 2472/894 train/val COCO pairs, without test reads."""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ['100lbs_aircraft_bomb', 'mortar_shell', 'incindiary_grenade']
COUNTS = {'train': 2472, 'val': 894}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepare(source, output):
    import cv2
    import numpy as np
    source, output = source.resolve(), output.resolve()
    # Fresh destination only: interrupted packages remain reviewable.
    output.mkdir(parents=True, exist_ok=False)
    dump(output / 'verification.json', {'passed': False, 'status': 'preparing', 'test_content_read': False})
    recs = list(csv.DictReader((source / 'recordings.csv').open(encoding='utf-8-sig')))
    recs = {r['recording']: r for r in recs if r['role'] in COUNTS}
    groups = {role: {r['group_id'] for r in recs.values() if r['role'] == role} for role in COUNTS}
    assert not groups['train'] & groups['val'], 'Source-group overlap'
    assert [len(groups[r]) for r in COUNTS] == [17, 7]
    files, inputs, members, summary, seen_hashes = {}, {}, {}, {}, {}
    for role, expected in COUNTS.items():
        aligned = None
        for side in ['camera', 'sonar']:
            ann = source / side / f'coco_{role}.json'
            inputs[f'{side}/coco_{role}.json'] = sha(ann)
            coco = json.loads(ann.read_text(encoding='utf-8'))
            assert coco['categories'] == [dict(id=i + 1, name=n) for i, n in enumerate(CLASSES)]
            assert len(coco['images']) == expected
            assert len({i['id'] for i in coco['images']}) == expected
            annotations = {}
            for a in coco['annotations']:
                annotations.setdefault(a['image_id'], []).append(a)
            assert set(annotations) == {i['id'] for i in coco['images']}
            exported, dataset, identity = copy.deepcopy(coco), [], {}
            original = {i['id']: i for i in coco['images']}
            for item in exported['images']:
                src = original[item['id']]
                sample, recording = src['sample'], src['recording']
                assert sample not in identity
                rec = recs[recording]
                assert rec['role'] == role
                identity[sample] = dict(sample=sample, recording=recording, group_id=rec['group_id'],
                                        category=rec['category'], role=role, scene_id=rec['scene_id'])
                path = (source / src['file_name']).resolve()
                assert path.is_file(), path
                img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                assert img is not None and img.dtype == np.uint8, path
                assert img.shape[:2] == (src['height'], src['width'])
                if side == 'camera':
                    assert img.shape == (360, 640, 3)
                else:
                    assert img.ndim == 2 or (img.ndim == 3 and img.shape[2] == 3 and
                           np.array_equal(img[..., 0], img[..., 1]) and np.array_equal(img[..., 1], img[..., 2]))
                boxes, labels = [], []
                for a in annotations[src['id']]:
                    x, y, w, h = a['bbox']
                    assert np.isfinite([x, y, w, h]).all()
                    assert 0 <= x < x + w <= src['width'] and 0 <= y < y + h <= src['height']
                    assert CLASSES[a['category_id'] - 1] == rec['category']
                    boxes.append(a['bbox']); labels.append(a['category_id'] - 1)
                assert len(boxes) == 1, 'Current frozen package has one target per image'
                relative = Path(side) / 'images' / (sample + path.suffix.lower())
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                digest = sha(path)
                assert sha(target) == digest
                key = (side, digest)
                assert key not in seen_hashes or seen_hashes[key] == role, 'Cross-role image duplicate'
                seen_hashes[key] = role
                files[relative.as_posix()] = digest
                item['file_name'] = relative.as_posix()
                item.update(group_id=rec['group_id'], scene_id=rec['scene_id'])
                row = dict(sample_id=sample, recording=recording, group_id=rec['group_id'],
                           scene_id=rec['scene_id'], role=role, width=src['width'], height=src['height'],
                           fp_camera=None, fp_sonar=None, boxes_camera=[], labels_camera=[],
                           boxes_sonar=[], labels_sonar=[], deg_level='d0', deg_seed=0,
                           source_image=str(path), source_image_sha256=digest)
                row.update({f'fp_{side}': relative.as_posix(), f'coco_{side}_image_id': src['id'],
                            f'boxes_{side}': boxes, f'labels_{side}': labels})
                dataset.append(row)
            if aligned is None:
                aligned = identity
            else:
                assert aligned == identity, 'Camera/sonar member mismatch'
            for suffix, value in [('coco', exported), ('dataset', dataset)]:
                target = output / f'{side}-{role}-{suffix}.json'
                dump(target, value); files[target.name] = sha(target)
            summary[f'{side}-{role}'] = dict(images=len(dataset), boxes=len(coco['annotations']))
        members[role] = sorted(aligned.values(), key=lambda x: x['sample'])
    assert not {m['sample'] for m in members['train']} & {m['sample'] for m in members['val']}
    inputs['recordings.csv'] = sha(source / 'recordings.csv')
    inputs['user-split-confirmation.json'] = sha(source / 'user-split-confirmation.json')
    dump(output / 'trainval-members.json', members)
    files['trainval-members.json'] = sha(output / 'trainval-members.json')
    dump(output / 'files-sha256.json', files)
    report = dict(passed=True, status='prepared', source=str(source), input_sha256=inputs,
                  classes=CLASSES, counts=summary, source_groups={r: len(g) for r, g in groups.items()},
                  all_images_decoded=True, all_copies_hash_match=True, bbox_bounds_valid=True,
                  train_val_groups_disjoint=True, cross_role_image_duplicates=0, test_content_read=False,
                  train_steps_per_epoch=COUNTS['train'] // 8, total_updates_200_epochs=COUNTS['train'] // 8 * 200)
    dump(output / 'verification.json', report)
    dump(output / 'README.json', dict(description='Independent train/val package. Relative image paths resolve against this directory.',
                                    classes=CLASSES, test_included=False, geometry='keep_ratio + right/bottom pad114 to640',
                                    label_semantics=dict(camera='native SD camera boxes', sonar='accepted visible-echo boxes')))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'DataSet/scene_stratified_mortar_recovered_candidate')
    parser.add_argument('--output', type=Path, default=ROOT / 'DataSet/scene_expanded_baseline_trainval')
    args = parser.parse_args()
    prepare(args.source, args.output)
