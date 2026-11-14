"""Bounded diagnostic: separate SD/FHD transcodes of the same allowed UHD."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r'D:\pby\data_processed\gopro\clips_uhd')
OUT = ROOT / '复现/camera-baseline/annotation-issues/full-source-timing/controls'


def main():
    rows = []
    for clip in ['20230921_GX010012_04', '20230921_GX020012_02']:
        for res, size in [('sd', '640:360'), ('fhd', '1920:1080')]:
            dest = OUT / f'{clip}-independent-scale-{res}.mp4'
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'info', '-n',
                       '-i', str(SOURCE / (clip + '.mp4')), '-vf', 'scale=' + size,
                       '-t', '8', '-c:v', 'libx264', '-an', str(dest)]
            if dest.exists():
                raise FileExistsError(dest)
            proc = subprocess.run(command, capture_output=True)
            (OUT / (dest.stem + '.stderr')).write_bytes(proc.stderr)
            if proc.returncode:
                raise RuntimeError(proc.stderr.decode(errors='replace')[-1500:])
            result = subprocess.check_output([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_streams', '-of', 'json', str(dest)])
            data = json.loads(result)
            (OUT / (dest.stem + '-probe.json')).write_bytes(result)
            stream = data['streams'][0]
            row = {'clip': clip, 'resolution': res, 'command': command,
                   'probe': {k: stream.get(k) for k in [
                       'start_time', 'duration', 'nb_frames', 'avg_frame_rate']}}
            rows.append(row)
            print(json.dumps(row), flush=True)
    (OUT / 'independent-scale-results.json').write_text(
        json.dumps({'limit': '8s; current FFmpeg; two independent processes per clip; not historical execution logs',
                    'rows': rows}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
