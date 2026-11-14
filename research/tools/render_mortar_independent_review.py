"""Independent frozen-best displays; never reads the check observations."""
from pathlib import Path
import json
import sys
sys.dont_write_bytecode = True
from verify_mortar_fixed_registration import (
    ROOT, ALL_IDS, FIT_IDS, np, read_json, digest, load_obj, surface_cloud,
    transform_points, selected_csv_rows, load_static_transforms, load_beam_tables,
    replay_projection,
)
from PIL import Image, ImageDraw


def main():
    out = ROOT/'DataSet/mortar_fixed_registration'
    dest = out/'independent-review'
    provenance = dest/'display-provenance.json'
    if provenance.exists():
        raise RuntimeError('Preserve independent review')
    frozen_path = out/'freeze-model.json'
    frozen = read_json(frozen_path)
    assert digest(frozen_path) == read_json(out/'freeze-model.sha256.json')['sha256']
    candidate = next(c for c in frozen['candidates'] if c['id'] == frozen['best_display_candidate_id'])
    selection = {r['sample']: r for r in read_json(ROOT/'DataSet/sonar_independent_registration/selection.json')['samples'] if r['sample'] in ALL_IDS}
    assert set(selection) == set(ALL_IDS)
    vertices, faces = load_obj(frozen['model']['obj_path'])
    world = transform_points(surface_cloud(vertices, faces), candidate['world_from_obj_similarity'])
    yaml_path = ROOT/'related_work/sonar-projection-audit-assets/calibration__transforms.yaml'
    beam_path = ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
    statics = load_static_transforms(yaml_path)
    tables = load_beam_tables(beam_path)
    hashes = {str(p): digest(p) for p in (frozen_path, yaml_path, beam_path, Path(__file__), ROOT/'tools/verify_mortar_fixed_registration.py')}
    frames = []
    for sid in ALL_IDS:
        row = selection[sid]
        for field in ('raw_sonar_source', 'gantry_source', 'meta_source'):
            hashes[row[field]] = digest(row[field])
        meta = selected_csv_rows(row['meta_source'], 'FrameIndex', [row['aris_frame']])[row['aris_frame']]
        gantry = selected_csv_rows(row['gantry_source'], 'aris_frame_idx', [row['aris_frame']])[row['aris_frame']]
        p = replay_projection(world, meta, gantry, statics, tables)
        raw = np.asarray(Image.open(row['raw_sonar_source']))
        assert list(raw.shape) == p['raw_shape_hw']
        h, w = raw.shape
        scale_x, scale_y = 4, 2
        base = Image.fromarray(np.minimum(raw.astype(np.uint16)*3,255).astype(np.uint8)).convert('RGB').resize((w*scale_x,h*scale_y),Image.Resampling.NEAREST)
        overlay = base.copy()
        draw = ImageDraw.Draw(overlay)
        box = p['visible_raw_bbox_padded_clipped_xyxy']
        if box is not None:
            draw.rectangle((box[0]*scale_x,box[1]*scale_y,box[2]*scale_x,box[3]*scale_y),outline=(0,255,100),width=2)
        uv = p['_raw_pixels'][p['_visible_mask']]
        # Sparse actual support pixels, not a convex silhouette or bright mask.
        for u,v in uv[::max(1,len(uv)//2000)]:
            x,y = int(u*scale_x),int(v*scale_y)
            if 0 <= x < overlay.width and 0 <= y < overlay.height:
                overlay.putpixel((x,y),(30,170,80))
        panel = Image.new('RGB',(w*scale_x*2+20,h*scale_y+55),'white')
        panel.paste(base,(0,55)); panel.paste(overlay,(w*scale_x+20,55))
        d = ImageDraw.Draw(panel)
        d.text((8,6),sid+' | '+('fit' if sid in FIT_IDS else 'check')+' | fixed best '+candidate['id'],fill='black')
        d.text((8,25),'Left: unboxed raw gain=3. Right: independently replayed geometric bbox/support; not GT.',fill='black')
        destination = dest/(sid+'-independent.jpg')
        panel.save(destination,quality=96)
        frames.append(dict(sample=sid,frame_time_us=int(meta['FrameTime']),output=str(destination),output_sha256=digest(destination),
                           visible_raw_bbox=None if box is None else box.tolist(),support_count=int(p['_visible_mask'].sum())))
    assert hashes == {p:digest(p) for p in hashes}
    provenance.write_text(json.dumps(dict(freeze_sha256=digest(frozen_path),candidate_id=candidate['id'],source_hashes=hashes,
                                        check_observations_read=False,optimizer_imported=False,test_access=False,frames=frames),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Independent displays generated for six allowed frames; no check observations read')


if __name__ == '__main__':
    main()
