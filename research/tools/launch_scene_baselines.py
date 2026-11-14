"""Launch the two authorized baseline runs as persistent WSL user services."""
import argparse
import json
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_scene_baselines import dump, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--sonar-checkpoint', type=Path, required=True)
    parser.add_argument('--attempt', help='Fresh named attempt; preserves stopped runs and their logs')
    args = parser.parse_args()
    assert args.attempt is None or re.fullmatch(r'[a-z0-9_]+', args.attempt)
    specs = [dict(side='camera', name='scene_camera_m_baseline', unit='scene-camera-m-baseline',
                  checkpoint=ROOT / 'assets/checkpoints/yolox_m_coco_backbone_neck.pth'),
             dict(side='sonar', name='scene_sonar_s_baseline', unit='scene-sonar-s-baseline',
                  checkpoint=args.sonar_checkpoint.resolve())]
    # Check BOTH runs before starting either service.
    for spec in specs:
        base = ROOT / 'runs' / spec['name']
        if args.attempt:
            base = base / args.attempt
            spec['unit'] += '-' + args.attempt.replace('_', '-')
        spec['base'] = base
        assert not (base / 'train').exists() and not (base / 'train.log').exists(), base
        proof = json.loads((base / 'preflight/status.json').read_text(encoding='utf-8'))
        assert proof['status'] == 'preflight_passed'
        assert sha(spec['checkpoint']) == proof['initialization_sha256']
        assert sha(ROOT / 'DataSet/scene_expanded_baseline_trainval/files-sha256.json') == proof['dataset_sha256']
        for relative, digest in proof['implementation_sha256'].items():
            assert sha(ROOT / 'tools' / relative) == digest, relative
        for relative, digest in proof['source_sha256'].items():
            assert sha(args.repo / relative) == digest, relative
        load = subprocess.check_output(['systemctl', '--user', 'show', spec['unit'], '--property=LoadState', '--value'], text=True).strip()
        assert load == 'not-found', f'Service already exists: {spec["unit"]}: {load}'
    record = []
    for spec in specs:
        base = spec['base']
        command = [sys.executable, '-B', '-u', str(ROOT / 'tools/run_scene_baseline.py'),
                   '--modality', spec['side'], '--repo', str(args.repo.resolve()),
                   '--checkpoint', str(spec['checkpoint']), '--work-dir', str(base / 'train'), '--train']
        subprocess.run(['systemd-run', '--user', '--unit=' + spec['unit'],
                        '--description=' + spec['name'] + ' 200epoch baseline',
                        '--property=WorkingDirectory=' + str(ROOT),
                        '--property=StandardOutput=append:' + str(base / 'train.log'),
                        '--property=StandardError=inherit', '--property=Restart=no',
                        '--property=OOMPolicy=stop', '--setenv=PYTHONDONTWRITEBYTECODE=1',
                        '--setenv=PYTHONUNBUFFERED=1', '--setenv=OMP_NUM_THREADS=8',
                        '--setenv=MKL_NUM_THREADS=8'] + command, check=True)
        status = subprocess.check_output(['systemctl', '--user', 'show', spec['unit'],
                                          '--property=MainPID', '--property=ActiveState',
                                          '--property=SubState', '--property=Result'], text=True)
        item = dict(name=spec['name'], service=spec['unit'] + '.service', command=command,
                    log=str(base / 'train.log'), launch_status=status, automatic_restart=False,
                    attempt=args.attempt, test_content_read=False)
        dump(base / 'launch.json', item)
        record.append(item)
    filename = 'scene-baselines-parallel-launch' + ('-' + args.attempt if args.attempt else '') + '.json'
    dump(ROOT / 'runs' / filename, record)
    print(json.dumps(record))


if __name__ == '__main__':
    main()
