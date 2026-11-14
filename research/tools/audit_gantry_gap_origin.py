"""Read-only provenance audit of six previously authorized development trajectories."""
from pathlib import Path
import ast
import csv
import hashlib
import io
import json
import math
import os
import statistics
import subprocess
import tempfile
import types
import zlib
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/pby/data_processed')
UPSTREAM = ROOT / 'related_work/uxo-upstream-history'
OUT = ROOT / 'DataSet/sonar_gantry_gap_origin'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    result_path = OUT / 'results.json'
    assert not result_path.exists(), 'Preserve prior runs'
    audit_path = ROOT / 'DataSet/sonar_motion_timing/results.json'
    audit = json.loads(audit_path.read_text('utf-8'))
    assert [x['recording'] for x in audit['records']] == [
        '2023-09-20_171105', '2023-09-20_173329', '2023-09-21_100927',
        '2023-09-21_101131', '2023-09-21_120653', '2023-09-21_120912']
    hashes = {str(audit_path): sha(audit_path)}
    catalog_path = ROOT / 'related_work/uxo/sd-fhd-trace/data_processed/catalog.json'
    hashes[str(catalog_path)] = sha(catalog_path)
    catalog = {x['name']: x for x in json.loads(catalog_path.read_text('utf-8'))}
    records = []
    for a in audit['records']:
        p = BASE / a['match']['gantry_file']
        hashes[str(p)] = sha(p)
        assert hashes[str(p)] == audit['input_hashes'][str(p)]
        data = p.read_bytes()
        member = catalog['data_processed/' + a['match']['gantry_file']]
        crc = zlib.crc32(data) & 0xffffffff
        assert len(data) == member['size'] and crc == member['crc32']
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(io.StringIO(data.decode('utf-8-sig')))]
        ts = [r['timestamp_us'] for r in rows]
        dt = [(b - a) / 1e6 for a, b in zip(ts, ts[1:])]
        dxyz = [math.sqrt(sum((b[k] - a[k]) ** 2 for k in ('x', 'y', 'z'))) for a, b in zip(rows, rows[1:])]
        first = next(i for i in range(1, len(rows)) if math.hypot(rows[i]['x'] - rows[i-1]['x'], rows[i]['y'] - rows[i-1]['y']) > 1e-10)
        official = next(i for i in range(1, len(rows)) if (rows[i]['x'] - rows[i-1]['x']) + (rows[i]['y'] - rows[i-1]['y']) != 0)
        assert first == official
        start = ts[0]
        onset = (ts[first] - start) / 1e6
        off = float(a['match']['gantry_offset']) / 1e6
        detail = dict(recording=a['recording'], source=str(p), size=len(data), crc32=crc,
                      official_archive_size_crc_match=True, rows=len(rows),
                      dt_median_s=statistics.median(dt), dt_max_s=max(dt),
                      nonpositive_intervals=sum(t <= 0 for t in dt),
                      first_changed_row_zero_based=first, first_change_distance_m=dxyz[first-1],
                      last_unchanged_elapsed_s=(ts[first-1]-start)/1e6,
                      first_changed_elapsed_s=onset, onset_gap_s=dt[first-1],
                      old_offset_s=off,
                      old_mapping_gap_s=[(ts[first-1]-start)/1e6-off, onset-off],
                      intervals_gt_1s=[dict(previous_row=i, next_row=i+1, dt_s=t,
                                           elapsed_before_s=(ts[i]-start)/1e6,
                                           elapsed_after_s=(ts[i+1]-start)/1e6,
                                           position_change_m=dxyz[i], is_first_change=(i+1==first))
                                       for i, t in enumerate(dt) if t > 1],
                      local_rows=[dict(row_index=i, elapsed_s=(ts[i]-start)/1e6,
                                       **rows[i]) for i in range(max(0, first-3), min(len(rows), first+6))])
        if a['recording'].startswith('2023-09-20'):
            video = BASE / a['match']['gopro_file']
            probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                               '-show_entries', 'stream=avg_frame_rate', '-of', 'json', str(video)], text=True))
            fps = Fraction(probe['streams'][0]['avg_frame_rate'])
            go = int(a['match']['gopro_offset'])
            predicted = onset + go / float(fps)
            detail['offset_coupling_check'] = dict(gopro_file=str(video), avg_frame_rate=str(fps),
                gopro_offset_frames=go, onset_plus_gopro_offset_over_fps_s=predicted,
                published_offset_s=off, difference_s=off-predicted,
                interpretation='Arithmetic matches public coupling rule; actual GUI checkbox state not recorded')
            assert abs(off-predicted) < 1e-9
        records.append(detail)

    source_paths = ['scripts/prep_5_gantry_extract.py', 'scripts/prep_6_gantry_find_offsets.py',
                    'scripts/common/matching_context.py', 'scripts/prep_x_match_recordings.py',
                    'scripts/config.yaml', 'README.md']
    for rel in source_paths:
        hashes[str(UPSTREAM / rel)] = sha(UPSTREAM / rel)
    code_path = UPSTREAM / source_paths[0]
    module = ast.parse(code_path.read_text('utf-8'))
    functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name in ('stamp_to_microseconds', 'extract_bag')]
    # Distinct bag-record timestamps ensure this control identifies the exported clock.
    header_us = [0, 109000, 2297000, 2406000]
    bag_us = [0, 109000, 218000, 327000]
    ns = types.SimpleNamespace
    messages = [('/odom', ns(header=ns(stamp=ns(secs=t//1000000, nsecs=(t%1000000)*1000)),
                             pose=ns(pose=ns(position=ns(x=0 if i < 2 else .001*(i-1), y=0., z=0.)))), bag_us[i])
                for i, t in enumerate(header_us)]
    class Bag:
        def __init__(self, path):
            pass
        def get_message_count(self, topic):
            assert topic == '/odom'
            return len(messages)
        def read_messages(self, topic):
            assert topic == '/odom'
            return iter(messages)
    env = dict(os=os, csv=csv, rosbag=ns(Bag=Bag), tqdm=lambda it, **kwargs: it)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(code_path), 'exec'), env)
    with tempfile.TemporaryDirectory(prefix='gantry_gap_control_') as td:
        env['extract_bag']('synthetic.bag', td, 2.)
        generated = list(csv.DictReader((Path(td)/'synthetic.csv').open()))
        exported = [float(r['timestamp_us']) for r in generated]
        assert len(generated) == len(messages)
        assert exported == [t+7200000000 for t in header_us]
        gap_deltas = [(exported[i+1]-exported[i])/1e6 for i in range(3)]
        assert abs(gap_deltas[1]-2.188) < 1e-12
        try:
            env['extract_bag']('string_adjust.bag', td, '2')
        except TypeError as e:
            string_failure = str(e)
        else:
            raise AssertionError('Expected current CLI string time_adjust incompatibility')
    synthetic = dict(passed=True, scope='Unmodified function AST with synthetic bag; not actual ROS bag replay',
                     message_count=len(messages), output_rows=len(generated),
                     header_intervals_s=[.109, 2.188, .109], bag_record_intervals_s=[.109, .109, .109],
                     exported_intervals_s=gap_deltas, static_rows_preserved=True,
                     constant_two_hour_shift_preserves_intervals=True,
                     current_cli_string_adjust_failure=string_failure,
                     current_cli_output_key='gantry_output', published_config_output_key='gantry_extract')
    history = {}
    for commit in ['7e60aea88f69f9a7b832919b9571de12161b12a2', '2ca6ecb5b0a195a536e890d4dec3a38de1846df7',
                   '866ab6061e0cbeca280c33cb79f45610ec7692bd']:
        # Patch includes only source, not historical mixed-recording matches tables.
        text = subprocess.check_output(['git', '-C', str(UPSTREAM), 'show', commit, '--', '*.py'], text=True, encoding='utf-8')
        hp = OUT / (commit[:7] + '-source.patch')
        hp.write_text(text, encoding='utf-8')
        history[commit] = dict(path=str(hp), sha256=sha(hp))
    head = subprocess.check_output(['git','-C',str(UPSTREAM),'rev-parse','HEAD'],text=True).strip()
    for p,h in hashes.items():
        assert sha(Path(p)) == h, p
    result = dict(run='sonar_gantry_gap_origin', upstream_commit=head, records=records,
                  synthetic_extraction_control=synthetic, source_history=history,
                  input_hashes=hashes, inputs_unchanged=True,
                  missing_raw_evidence=['ROS bag record timestamps', 'header sequence numbers',
                                        'gantry publisher/control-state logs'],
                  exact_acquisition_cause_resolved=False, formal_time_version_frozen=False,
                  new_image_decodes=0, training_runs=0, model_fits=0, test_sample_access=0)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for r in records:
        print(r['recording'], 'CRC passed', 'gap', r['onset_gap_s'],
              'large intervals', [(x['dt_s'], x['is_first_change']) for x in r['intervals_gt_1s']])
    print('Synthetic extraction control passed; exact acquisition cause unresolved.')


if __name__ == '__main__':
    main()
