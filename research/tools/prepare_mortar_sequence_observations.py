"""Prepare only preregistered unboxed mortar sequence images; no model inputs."""
from pathlib import Path
from datetime import datetime, timezone
import csv, hashlib, io, json, shutil, sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from check_official_sonar_coordinates import Geometry, beam_count, load_beam_tables, read_gray

OUT = ROOT / 'DataSet/sonar_mortar_sequence_observations'
PLAN = ROOT / 'experiment/sonar-mortar-sequence-observation-plan.md'
MANIFEST = ROOT / 'DataSet/camera_temporal_all/manifest-resolved.json'
REC = '2023-09-21_100927'
CENTERS = (87, 451, 811)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def gain(a, amount):
    return np.minimum(a.astype(np.uint16) * amount, 255).astype(np.uint8)


def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/arial.ttf', size)


def raw_panel(a, amount, sx=4, sy=2):
    h, w = a.shape
    p = Image.new('RGB', (w*sx+65, h*sy+75), 'white')
    p.paste(Image.fromarray(gain(a, amount)).convert('RGB').resize((w*sx, h*sy), Image.Resampling.NEAREST), (50, 50))
    d = ImageDraw.Draw(p)
    d.text((7, 4), f'raw {w}x{h}; fixed gain {amount}', font=font(17), fill='black')
    for x in range(0, w+1, 16):
        d.text((50+x*sx-8, 29), str(x), font=font(14), fill='black')
    for y in range(0, h+1, 50):
        d.text((4, 50+y*sy-7), str(y), font=font(14), fill='black')
    return p


def fit_image(im, box):
    result = im.copy()
    result.thumbnail(box, Image.Resampling.NEAREST)
    return result


def main():
    assert PLAN.exists()
    if (OUT / 'display-provenance.json').exists():
        raise RuntimeError('Completed preparation must not be overwritten')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'images').mkdir(exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    admitted = {r['recording'] for r in manifest['recordings']}
    assert REC in admitted and REC in manifest['identity']['recordings']
    rows = {r['sample']: r for r in manifest['items']}
    selected, skipped = [], []
    for center in CENTERS:
        for index in range(center-8, center+9, 4):
            sid = f'{REC}_{index:04d}'
            if sid not in rows:
                skipped.append(dict(sample=sid, reason='not_in_allowed_native_manifest; not_read'))
                continue
            r = rows[sid]
            assert r['recording'] == REC and r['category'] == 'mortar_shell'
            assert int(r['aris_frame']) == index and r.get('paired_role') in (None, 'train', 'val', 'val_id')
            directory = Path(r['original_image']).parent.parent
            assert directory.name == REC and Path(r['original_image']).parent.name == 'gopro'
            raw = directory / 'aris_raw' / f'{index:04d}.pgm'
            sd = (MANIFEST.parent / r['reference_sd']).resolve() if index == center and r.get('reference_sd') else None
            if sd:
                sd.relative_to(MANIFEST.parent.resolve())
            selected.append(dict(sample=sid, aris_frame=index, window_center=center, paired_role=r.get('paired_role'),
                                 raw_source=str(raw), metadata_source=str(directory/'aris_frame_meta.csv'),
                                 aris_time_us=int(r['aris_time_us']), camera_source=str(sd) if sd else None))
    assert len(selected) == 11 and len(skipped) == 4
    paths = {PLAN, MANIFEST, Path(__file__), ROOT/'tools/check_official_sonar_coordinates.py',
             ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py',
             ROOT/'related_work/uxo-upstream-history/scripts/prep_2_aris_to_polar.py'}
    for r in selected:
        paths.update([Path(r['raw_source']), Path(r['metadata_source'])])
        if r['camera_source']:
            paths.add(Path(r['camera_source']))
    inputs = {str(p): sha(p) for p in sorted(paths)}
    save(OUT/'selection.json', dict(selected=selected, skipped=skipped, allowed_manifest=str(MANIFEST),
                                   allowed_manifest_sha256=inputs[str(MANIFEST)], exact_identity_check_pass=True))
    save(OUT/'inputs-before.json', inputs)
    # No image has been decoded above this point.
    meta_path = Path(selected[0]['metadata_source'])
    metadata = {int(r['FrameIndex']): r for r in csv.DictReader(io.StringIO(meta_path.read_text(encoding='utf-8-sig')))}
    tables = load_beam_tables()
    panels = {}
    cameras = []
    outputs = []
    for r in selected:
        sid = r['sample']; index = r['aris_frame']; m = metadata[index]
        assert int(m['FrameTime']) == r['aris_time_us']
        raw = read_gray(r['raw_source'])
        geom = Geometry(m, tables[beam_count(m['PingMode'])], 1000.)
        assert raw.shape == (geom.h, geom.w)
        polar = geom.render(raw)
        base = OUT/'images'/sid
        raw_path = Path(str(base)+'-raw.png'); polar_path = Path(str(base)+'-official-polar2.png')
        Image.fromarray(raw).save(raw_path)
        Image.fromarray(polar).save(polar_path)
        Image.fromarray(gain(polar, 3)).save(Path(str(base)+'-official-polar2-gain3.png'))
        p1, p3 = raw_panel(raw, 1), raw_panel(raw, 3)
        review = Image.new('RGB', (p1.width+p3.width, p1.height+34), 'white')
        review.paste(p1, (0, 34)); review.paste(p3, (p1.width, 34))
        ImageDraw.Draw(review).text((8, 5), f'{sid} | no boxes / model / crop | edge coordinates', font=font(19), fill='black')
        review_path = Path(str(base)+'-raw-review.png'); review.save(review_path)
        panels[sid] = (p3, Image.fromarray(gain(polar, 3)).convert('RGB'))
        if r['camera_source']:
            camera_path = Path(str(base)+'-camera-unboxed.jpg')
            shutil.copyfile(r['camera_source'], camera_path)
            camera = Image.open(camera_path).convert('RGB')
            assert camera.size == (640, 360)
            cameras.append((sid, camera))
        outputs.append(r | dict(geometry=geom.description(), raw_output=str(raw_path), polar_output=str(polar_path),
                                raw_review=str(review_path), raw_sha256=inputs[r['raw_source']],
                                model_or_box_inputs_read=False, pixel_coordinates='native raw edge xy; rows increase down'))
    for center in CENTERS:
        group = [r for r in selected if r['window_center'] == center]
        sheet = Image.new('RGB', (360*len(group), 1130), 'white'); d = ImageDraw.Draw(sheet)
        d.text((8, 7), f'{REC} window {center:04d} | all gain 3; full raw and full official polar2; no boxes', font=font(18), fill='black')
        for k, r in enumerate(group):
            x = 360*k; d.text((x+8, 38), r['sample'], font=font(17), fill='black')
            raw_im, polar_im = panels[r['sample']]
            raw_thumb = fit_image(raw_im, (350, 500)); sheet.paste(raw_thumb, (x+(360-raw_thumb.width)//2, 68))
            polar_thumb = fit_image(polar_im, (350, 500)); sheet.paste(polar_thumb, (x+(360-polar_thumb.width)//2, 610))
            d.text((x+8, 580), 'official polar2 (full frame)', font=font(17), fill='black')
        sheet.save(OUT/f'window-{center:04d}-contact.png')
    camera_sheet = Image.new('RGB', (640, 400*len(cameras)), 'white'); d = ImageDraw.Draw(camera_sheet)
    for k, (sid, camera) in enumerate(cameras):
        d.text((8, k*400+7), f'{sid} | identity only; no labels', font=font(20), fill='black')
        camera_sheet.paste(camera, (0, k*400+40))
    camera_sheet.save(OUT/'center-camera-contact.jpg')
    after = {p: sha(p) for p in inputs}
    save(OUT/'inputs-after.json', after)
    assert inputs == after, 'Source input changed during rendering'
    save(OUT/'display-provenance.json', dict(created_at=datetime.now(timezone.utc).isoformat(), frames=outputs,
         skipped=skipped, input_hashes=inputs, input_hashes_unchanged=True, raw_decodes=11, camera_decodes=3,
         image_inputs_scope='only eleven first-recording allowed native frames and three center SD references',
         model_inputs_read=False, old_boxes_read=False, fitted_parameter_inputs_read=False, check_recording_images_read=False,
         renderer='Geometry.render: official polar2 geometry/quantization at 1000 px/m; fixed gains 1 and 3'))
    print(json.dumps(dict(frames=len(outputs), skipped=len(skipped), camera_frames=len(cameras), output=str(OUT))))


if __name__ == '__main__':
    main()
