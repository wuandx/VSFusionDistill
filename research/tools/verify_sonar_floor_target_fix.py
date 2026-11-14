"""Verify the single floor-target correction using metadata, with no image reads."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import sonar_manual_curation_server as current
import numpy as np
from check_official_sonar_coordinates import Geometry, beam_count

ROOT = current.ROOT
OUT = ROOT/'DataSet/sonar_initial_candidate_audit'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_candidates(source, row):
    index = int(row['aris_frame'])
    metadata, gantry, _, _ = source.recording_metadata(row['recording'])
    geometry = Geometry(metadata[index], source.tables[beam_count(metadata[index]['PingMode'])], 1000.)
    return source.candidates(row, metadata[index], gantry[index], geometry)


def main():
    snapshot = OUT/'sonar_manual_curation_server.before-floor-target.py'
    previous_record = json.loads((OUT/'server-before-floor-target.json').read_bytes())
    assert sha(snapshot) == previous_record['sha256']
    spec = importlib.util.spec_from_file_location('curation_before_floor_target', snapshot)
    previous = importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    source = current.DatasetSource(ROOT);old = previous.DatasetSource(ROOT)
    # Read model definitions only. No source image API is called anywhere here.
    model_checks = []
    for name in current.CATEGORY_MODEL.values():
        points, variants, _ = source.ensure_model(name)
        old_points, old_variants, _ = old.ensure_model(name)
        assert np.array_equal(points, old_points)
        for variant, prior in zip(variants, old_variants):
            assert variant['id'] == prior['id']
            assert np.array_equal(variant['transform'], prior['transform'])
        model_checks.append(dict(model=name, points_exact=True, ordinary_world_transforms_exact=True,
                                 variant_ids=[v['id'] for v in variants]))
    recording_checks = []
    for rec, members in sorted(source.recordings.items()):
        row = source.rows[members[0]]
        selected = current.target_frame_for(row)
        expected = 'target/100lbs_floor' if rec == current.FLOOR_RECORDING else current.TARGET_FRAME[row['category']]
        assert selected == expected
        recording_checks.append(dict(recording=rec, category=row['category'], target_frame=selected,
                                     changed=rec==current.FLOOR_RECORDING, sample_count=len(members)))
    assert sum(row['changed'] for row in recording_checks) == 1
    evaluation_path = ROOT/'DataSet/mortar_fixed_registration/evaluation-results.json'
    evaluated = json.loads(evaluation_path.read_bytes())
    ordinary_samples = [frame['sample'] for frame in evaluated['frames']]
    ordinary_samples += ['2023-09-20_175000_0887','2023-09-21_120653_0163']
    ordinary_results = []
    for sample in ordinary_samples:
        row = source.require(sample)
        candidates, provenance = build_candidates(source,row)
        prior_candidates, prior_provenance = build_candidates(old,row)
        assert candidates == prior_candidates
        assert provenance == prior_provenance
        ordinary_results.append(dict(sample=sample, candidate_ids=[c['id'] for c in candidates],
                                     candidate_values_byte_equivalent=True, provenance_equal=True,
                                     candidates=candidates))
    floor_sample = source.recordings[current.FLOOR_RECORDING][0]
    floor_row = source.require(floor_sample)
    prior_candidates, prior_provenance = build_candidates(old,floor_row)
    candidates, provenance = build_candidates(source,floor_row)
    assert [c['id'] for c in candidates] == [current.FLOOR_CANDIDATE_ID]
    candidate = candidates[0]
    expected_world = np.eye(4);expected_world[:3,3] = [1.174003,1.227536,-2.2411]
    np.testing.assert_array_equal(candidate['world_from_target'], expected_world)
    # Independently check the literal translation in the published YAML block.
    yaml_path = Path(candidate['target_mapping_evidence']['official_yaml']['path'])
    block = yaml_path.read_text(encoding='utf-8').split('frame_id: "target/100lbs_floor"',1)[1]
    translation = block.split('translation:',1)[1].split('rotation:',1)[0]
    vector = {line.split(':',1)[0].strip():float(line.split(':',1)[1]) for line in translation.splitlines() if ':' in line}
    np.testing.assert_array_equal([vector[k] for k in 'xyz'],expected_world[:3,3])
    np.testing.assert_array_equal(candidate['mesh_to_target_similarity'],source.old_model_info['100lbs']['mesh_to_target_similarity'])
    assert candidate['raw_padding_beam_bin'] == prior_candidates[0]['raw_padding_beam_bin'] == 1.
    assert candidate['polar_padding_px'] == prior_candidates[0]['polar_padding_px'] == 0.
    assert provenance['world_from_sonar'] == prior_provenance['world_from_sonar']
    assert provenance['beam_convention'] == prior_provenance['beam_convention']
    hashes = []
    for path, (_, expected_hash) in source.hash_cache.items():
        actual = sha(path)
        assert actual == expected_hash
        hashes.append(dict(path=path,sha256=actual,unchanged=True))
    journal = ROOT/'DataSet/sonar_manual_curation/reviews.jsonl'
    result = dict(status='pass', scope='metadata and frozen OBJ only; no source image reads, review writes, optimization, training or test',
                  old_server_sha256=sha(snapshot), corrected_server_sha256=sha(ROOT/'tools/sonar_manual_curation_server.py'),
                  recording_target_checks=recording_checks, ordinary_model_checks=model_checks, ordinary_candidate_regression=ordinary_results,
                  floor=dict(sample=floor_sample, sample_count=len(source.recordings[current.FLOOR_RECORDING]),
                             previous_candidates=prior_candidates, previous_provenance=prior_provenance,
                             corrected_candidates=candidates, corrected_provenance=provenance,
                             old_to_floor_world_translation_delta_m=(expected_world[:3,3]-np.asarray(source.old_model_info['100lbs']['world_from_target'])[:3,3]).tolist(),
                             geometry_registration_validated=False, numeric_change_only=True),
                  inputs_unchanged=hashes, unit_test_count=12, unit_test_status='pass',
                  production_journal=dict(exists=journal.exists(),bytes=journal.stat().st_size if journal.exists() else 0),
                  note='The target identity is corrected; no claim is made that PCA registration or sonar boxes are now physically correct. Running servers were not restarted.')
    target = OUT/'floor-target-fix-verification.json'
    with target.open('x',encoding='utf-8') as stream: json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status='pass',ordinary_recordings_unchanged=39,ordinary_samples_compared=len(ordinary_results),
                          ordinary_candidate_count=sum(len(x['candidate_ids']) for x in ordinary_results),
                          floor_sample=floor_sample,source_hashes_unchanged=len(hashes),old_floor_box=prior_candidates[0]['bbox_xyxy'],
                          corrected_floor_box=candidate['bbox_xyxy'],output=str(target)),ensure_ascii=True))


if __name__ == '__main__': main()
