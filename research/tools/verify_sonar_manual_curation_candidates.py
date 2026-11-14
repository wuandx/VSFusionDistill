"""Read-only replay of six pre-existing mortar evaluations for the review service."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import numpy as np
from sonar_manual_curation_server import DatasetSource, ROOT


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source = DatasetSource()
    prior_path = ROOT/'DataSet/mortar_fixed_registration/evaluation-results.json'
    prior = json.loads(prior_path.read_bytes())
    checks = []
    for old in prior['frames']:
        frame = source.frame(old['sample'])
        width, height = frame['sonar']['width'], frame['sonar']['height']
        for candidate in frame['sonar']['candidates']:
            fitted = candidate['id'] == 'mortar_fixed_start00'
            metric = old['candidate_metrics']['start-00'] if fitted else old['prior_fixed_mesh_metrics']
            expected_raw = np.array(metric['visible_raw_bbox_7deg'])
            padding = 0. if fitted else 1.
            expected_raw += np.array([-padding, -padding, padding, padding])
            expected_raw = np.clip(expected_raw, [0., 0., 0., 0.], [width, height, width, height])
            raw_delta = float(np.max(np.abs(np.array(candidate['bbox_xyxy'])-expected_raw)))
            polar_delta = float(np.max(np.abs(np.array(candidate['polar_bbox_xyxy'])-metric['visible_polar_bbox_7deg'])))
            pose_delta = float(np.max(np.abs(np.array(frame['provenance']['candidates']['world_from_sonar'])-metric['world_from_sonar'])))
            assert max(raw_delta, polar_delta, pose_delta) < 1e-9
            assert candidate['raw_padding_beam_bin'] == padding and candidate['polar_padding_px'] == 0
            checks.append(dict(sample=old['sample'], candidate_id=candidate['id'], raw_padding_beam_bin=padding,
                               raw_max_abs_delta_px=raw_delta, polar_max_abs_delta_px=polar_delta, pose_max_abs_delta=pose_delta))
        source.validate_for_save(frame)
    historical_hashes = []
    for filename, expected in prior['source_hashes'].items():
        actual = digest(filename)
        historical_hashes.append(dict(path=filename, expected_sha256=expected, actual_sha256=actual, unchanged=expected==actual))
    assert all(row['unchanged'] for row in historical_hashes)
    loaded_hashes = []
    for filename, (_, expected) in source.hash_cache.items():
        actual = digest(filename)
        loaded_hashes.append(dict(path=filename, sha256=actual, unchanged=actual==expected))
    assert all(row['unchanged'] for row in loaded_hashes)
    out = ROOT/'DataSet/sonar_manual_curation_validation'
    out.mkdir(parents=True, exist_ok=True)
    result = dict(status='pass', scope='read-only six existing development frames; no review writes, optimization, train or test',
                  reference=dict(path=str(prior_path), sha256=digest(prior_path)), comparisons=checks,
                  historical_source_hashes=historical_hashes, loaded_source_hashes=loaded_hashes,
                  annotation_note='old_pca_fixed raw padding=1 beam/bin; mortar_fixed_start00 raw padding=0; all polar padding=0. Both remain unvalidated suggestions.',
                  service_sha256=digest(ROOT/'tools/sonar_manual_curation_server.py'))
    target = out/'candidate-replay-verification.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='pass', samples=6, candidate_comparisons=len(checks), historical_hashes=len(historical_hashes),
                          loaded_hashes=len(loaded_hashes), max_raw_delta_px=max(x['raw_max_abs_delta_px'] for x in checks),
                          max_polar_delta_px=max(x['polar_max_abs_delta_px'] for x in checks), output=str(target)),ensure_ascii=True))


if __name__ == '__main__': main()
