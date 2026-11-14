"""Compare all surface intersections and true first intersections on identical 3D rays.

No fit, no intensity threshold, no external-scene occluders. Original assets read-only.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
from pathlib import Path
import sys, json, hashlib, csv, time
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image, ImageDraw
from fit_box_guided_sonar_registration import Frame, transform
from sonar_manual_curation_server import DatasetSource

OUT = ROOT/'DataSet/sonar_ray_visibility'
PLAN = ROOT/'experiment/archive/sonar-ray-visibility-plan.md'

def read(p): return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, x): Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')

def load_mesh(info):
    vertices, faces = [], []
    for line in Path(info['source']).read_text('utf-8').splitlines():
        s = line.split()
        if not s: continue
        if s[0] == 'v': vertices.append(list(map(float, s[1:4])))
        if s[0] == 'f':
            ids = [int(x.split('/')[0])-1 for x in s[1:]]
            faces.extend([[ids[0], ids[j], ids[j+1]] for j in range(1, len(ids)-1)])
    return transform(np.array(vertices), np.array(info['mesh_to_target_similarity'])), np.array(faces)

def cast_raster(v, f, n):
    """Perspective-correct triangle rasterization; each pixel denotes one 3D ray.

    Ray d=(x/z,y/z,1). Reciprocal depth is affine in projected barycentrics.
    All triangles are double sided. Keep both nearest and farthest intersection.
    """
    assert v[:, 2].min() > 0
    xy = v[:, :2]/v[:, 2:]
    lo, hi = xy.min(0), xy.max(0)
    pad = (hi-lo)*.01
    lo, hi = lo-pad, hi+pad
    step = (hi-lo)/n
    screen = (xy-lo)/step-.5
    front, back = np.full(n*n, np.inf), np.full(n*n, -np.inf)
    candidates = 0
    for k in range(0, len(f), 3000):
        ids = f[k:k+3000]
        t = screen[ids]
        lower = np.maximum(0, np.ceil(t.min(1)).astype(int))
        upper = np.minimum(n-1, np.floor(t.max(1)).astype(int))
        wh = np.maximum(0, upper-lower+1)
        count = wh[:, 0]*wh[:, 1]
        end = np.cumsum(count)
        if not len(end) or end[-1] == 0: continue
        tri = np.repeat(np.arange(len(ids)), count)
        off = np.arange(end[-1])-np.repeat(end-count, count)
        width = wh[tri, 0]
        px = lower[tri, 0]+off % width
        py = lower[tri, 1]+off // width
        a, b, c = (t[tri, j] for j in range(3))
        den = (b[:,1]-c[:,1])*(a[:,0]-c[:,0])+(c[:,0]-b[:,0])*(a[:,1]-c[:,1])
        valid = abs(den) > 1e-16
        safe = np.where(valid, den, 1.)
        w0 = ((b[:,1]-c[:,1])*(px-c[:,0])+(c[:,0]-b[:,0])*(py-c[:,1]))/safe
        w1 = ((c[:,1]-a[:,1])*(px-c[:,0])+(a[:,0]-c[:,0])*(py-c[:,1]))/safe
        w2 = 1-w0-w1
        valid &= (w0 >= -1e-10)&(w1 >= -1e-10)&(w2 >= -1e-10)
        tri, px, py = tri[valid], px[valid], py[valid]
        weights = np.c_[w0[valid], w1[valid], w2[valid]]
        z = 1/np.sum(weights/v[ids[tri], 2], axis=1)
        index = py*n+px
        np.minimum.at(front, index, z)
        np.maximum.at(back, index, z)
        candidates += len(index)
    hit = np.isfinite(front)
    ix = np.flatnonzero(hit)
    dirs = np.c_[lo[0]+(ix % n+.5)*step[0], lo[1]+(ix//n+.5)*step[1], np.ones(len(ix))]
    return dict(directions=dirs, front=front[hit], back=back[hit], pixel_indices=ix,
                grid_size=n, grid_lo=lo.tolist(), grid_step=step.tolist(), intersections=candidates)

def brute_ray(v, f, d):
    """Independent Moller-Trumbore implementation, no screen barycentrics."""
    a = v[f[:, 0]]; e1 = v[f[:, 1]]-a; e2 = v[f[:, 2]]-a
    h = np.cross(np.broadcast_to(d, e2.shape), e2)
    det = np.sum(e1*h, axis=1)
    valid = abs(det) > 1e-14
    inv = np.divide(1., det, out=np.zeros_like(det), where=valid)
    s = -a
    u = inv*np.sum(s*h, axis=1)
    q = np.cross(s, e1)
    w = inv*(q@d)
    z = inv*np.sum(e2*q, axis=1)
    good = valid&(u >= -1e-9)&(w >= -1e-9)&(u+w <= 1+1e-9)&(z > 0)
    return float(z[good].min()), float(z[good].max())

def projected_bounds(points, geom):
    r = np.linalg.norm(points, axis=1)
    beta = -np.degrees(np.arctan2(points[:, 0], points[:, 2]))
    uv = geom.points_to_raw_edges(r, beta)
    return np.r_[uv.min(0), uv.max(0)]

def measure(cast, geom):
    p = cast['directions']*cast['front'][:, None]
    q = cast['directions']*cast['back'][:, None]
    full = projected_bounds(np.r_[p, q], geom)
    visible = projected_bounds(p, geom)
    assert np.max(abs((visible-full)[[0, 1, 2]])) < 1e-9
    assert visible[3] <= full[3]+1e-9
    return dict(full_bbox_raw=full.tolist(), visible_bbox_raw=visible.tolist(),
                visible_minus_full_raw=(visible-full).tolist(), rays=len(p),
                intersection_count=cast['intersections'],
                far_edge_reduction_m=float(full[3]-visible[3])*geom.dr)

def synthetic():
    # Two rectangles at z=1 and z=1.4. Front rectangle has half the elevation support.
    # Different elevations at the same azimuth must survive first-hit rendering.
    v = np.array([[-.2,-.05,1],[.2,-.05,1],[.2,.05,1],[-.2,.05,1],
                  [-.28,-.14,1.4],[.28,-.14,1.4],[.28,.14,1.4],[-.28,.14,1.4]])
    f = np.array([[0,1,2],[0,2,3],[4,5,6],[4,6,7]])
    cast = cast_raster(v, f, 128)
    d = cast['directions']
    expected = np.where(abs(d[:,1]) <= .05, 1., 1.4)
    error = max(float(abs(cast['front']-expected).max()), float(abs(cast['back']-1.4).max()))
    assert error < 1e-9
    # Closed axis-aligned cuboid, analytic slab intersection independent of triangulation.
    box = np.array([[x,y,z] for x in [-.2,.2] for y in [-.1,.1] for z in [1.,1.4]])
    bf = np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],
                   [2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]])
    bc = cast_raster(box, bf, 128)
    dirs = bc['directions']; low=np.array([-.2,-.1,1.]); high=np.array([.2,.1,1.4])
    slab1=low/dirs; slab2=high/dirs
    entry=np.minimum(slab1,slab2).max(1); leave=np.maximum(slab1,slab2).min(1)
    box_error=max(float(abs(entry-bc['front']).max()),float(abs(leave-bc['back']).max()))
    assert box_error < 1e-9
    independent = []
    for i in np.linspace(0, len(cast['front'])-1, 25).round().astype(int):
        a,b=brute_ray(v,f,d[i]);independent.append(max(abs(a-cast['front'][i]),abs(b-cast['back'][i])))
    assert max(independent) < 1e-8
    return dict(two_layer_max_error_m=error, cuboid_max_error_m=box_error,
                independent_ray_max_error_m=max(independent),
                visible_back_plane_rays=int((cast['front']>1.1).sum()),
                explanation='Back plane remains directly visible at other elevations; azimuth-only nearest is different.')

def panel(sid, source, measures, out):
    raw = Image.open(source).convert('L')
    a = np.asarray(raw)
    im = Image.fromarray(np.minimum(a.astype(float)*2.5,255).astype('uint8')).convert('RGB')
    boxes=[r[key] for r in measures for key in ['full_bbox_raw','visible_bbox_raw']]
    lo=max(0,int(min(b[1] for b in boxes))-30);hi=min(raw.height,int(max(b[3] for b in boxes))+30)
    # Preserve full range when the projection lies outside the raw frame.
    if hi <= lo: lo,hi=0,raw.height
    canvas=Image.new('RGB',(1100,700),'#f5f6f8');d=ImageDraw.Draw(canvas)
    d.text((15,10),sid+' | fixed pose; diagnostic, not physical GT',fill='black')
    for j,r in enumerate(measures):
        tile=im.crop((0,lo,raw.width,hi)).resize((510,580))
        td=ImageDraw.Draw(tile)
        for key,col in [('full_bbox_raw','orange'),('visible_bbox_raw','cyan')]:
            b=r[key];xy=(b[0]*510/raw.width,(b[1]-lo)*580/(hi-lo),b[2]*510/raw.width,(b[3]-lo)*580/(hi-lo))
            td.rectangle(xy,outline=col,width=2)
        x=15+j*550;canvas.paste(tile,(x,70));d.text((x,38),r['pose']+' | far reduction %.4f m'%r['far_edge_reduction_m'],fill='black')
    d.text((15,665),'Orange: all intersections. Cyan: first intersection per 3D ray. No image threshold or refit.',fill='black')
    canvas.save(out,quality=93)

def main():
    assert not OUT.exists(), 'Preserve previous evidence'
    OUT.mkdir();(OUT/'frames').mkdir()
    (OUT/'plan-before-run.md').write_bytes(PLAN.read_bytes())
    (OUT/'implementation.py').write_bytes(Path(__file__).read_bytes())
    control=synthetic();save(OUT/'synthetic.json',control);print('SYNTHETIC PASS',control,flush=True)
    registry_path=ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json'
    selpath=ROOT/'DataSet/sonar_rgb_pose_pilot/selection.json'
    rolespath=ROOT/'DataSet/paired_recording_split/recordings.csv'
    calpath=ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json'
    hashes={str(p):sha(p) for p in [PLAN,Path(__file__),registry_path,selpath,rolespath,calpath]}
    roles={r['recording']:r['role'] for r in csv.DictReader(rolespath.open(encoding='utf-8-sig'))}
    selected=read(selpath)['samples']
    assert len(selected)==6 and all(roles[r['recording']]=='train' for r in selected)
    registry=read(registry_path)['models']
    statics={k:np.array(v) for k,v in read(calpath)['versions']['release_current']['parent_from_child_matrices'].items()}
    ds=DatasetSource();hashes[str(ds.manifest_path)]=ds.manifest_hash
    models={};rows=[];independent_errors=[]
    for entry in selected:
        started=time.perf_counter();sid=entry['sample'];model=entry['model'];rec=entry['recording']
        assert roles[rec]=='train'
        if model not in models:
            info=registry[model];assert sha(info['source'])==info['source_sha256'];hashes[info['source']]=sha(info['source'])
            v,f=load_mesh(info)
            posepath=ROOT/f'DataSet/sonar_box_guided_registration/{model}/freeze-model.json'
            hashes[str(posepath)]=sha(posepath)
            poses={'old_pca':np.array(info['world_from_target']), 'box_guided':np.array(read(posepath)['chosen']['world_from_model'])}
            models[model]=(v,f,poses)
        v,f,poses=models[model];frame=Frame(ds,sid,statics)
        for prov in frame.provenance.values():hashes[prov['path']]=prov['sha256']
        rawpath=ds.rec_dirs[rec]/'aris_raw'/f"{frame.row['aris_frame']:04d}.pgm"
        hashes[str(rawpath)]=sha(rawpath)
        pm=[]
        for name,T in poses.items():
            vs=transform(v,frame.sw@T);results={}
            for n in [512,1024]:
                cast=cast_raster(vs,f,n);results[str(n)]=measure(cast,frame.geom)
                if n==1024:
                    rayerrs=[]
                    for ix in np.linspace(0,len(cast['front'])-1,7).round().astype(int):
                        near,far=brute_ray(vs,f,cast['directions'][ix])
                        rayerrs.append(max(abs(near-cast['front'][ix]),abs(far-cast['back'][ix])))
                    independent_errors+=rayerrs
                    assert max(rayerrs)<1e-8
            fine=results['1024'];coarse=results['512']
            convergence=max(abs(np.array(fine[key])-coarse[key]).max() for key in ['full_bbox_raw','visible_bbox_raw'])
            row=dict(sample=sid,recording=rec,role='train',model=model,pose=name,resolutions=results,
                     max_edge_resolution_difference_raw_px=float(convergence),converged=bool(convergence<=.5),
                     independent_ray_max_error_m=max(rayerrs),world_from_model=T.tolist(),
                     geometry=frame.geom.description())
            rows.append(row);pm.append(dict(pose=name,**fine))
            print(sid,name,'delta',fine['visible_minus_full_raw'],'convergence',round(convergence,5),flush=True)
        panel(sid,rawpath,pm,OUT/'frames'/f'{sid}.jpg')
        print('FRAME seconds',round(time.perf_counter()-started,2),flush=True)
    assert all(sha(p)==h for p,h in hashes.items())
    save(OUT/'results.json',dict(run='sonar_ray_visibility',frames=rows,synthetic=control,
         geometry_scope='self-occlusion only; no intensity, floor, support, multipath or refit',
         physical_registration_validated=False,formal_gt_generated=0))
    save(OUT/'verification.json',dict(input_hashes=hashes,inputs_unchanged=True,
         independent_real_ray_count=len(independent_errors),independent_ray_max_error_m=max(independent_errors),
         all_resolution_checks_pass=all(r['converged'] for r in rows),test_access=False,training=False,
         all_selected_recordings_current_train=True))
    cards=''.join(f'<h2>{e["sample"]}</h2><img src="frames/{e["sample"]}.jpg">' for e in selected)
    (OUT/'index.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>3D ray visibility control</title><style>body{font:16px system-ui;margin:30px;background:#f5f6f8}img{max-width:100%}</style><h1>三维首交点与完整表面投影</h1><p>同模型同姿态；橙：全部交点，青：每条三维射线的首交点。仅自遮挡几何支持，不是真实回波或已认证姿态。</p><p><a href="results.json">逐帧数值</a> · <a href="verification.json">核验</a> · <a href="synthetic.json">解析控制</a></p>'+cards,'utf-8')
    print('COMPLETE',len(rows),flush=True)

if __name__=='__main__': main()
