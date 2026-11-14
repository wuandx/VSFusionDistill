"""Frozen fixed registration compared across all permitted recordings."""
from pathlib import Path
import sys,json,hashlib,argparse,html
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image,ImageDraw
from scipy.spatial.transform import Rotation
from sonar_manual_curation_server import DatasetSource,CATEGORY_MODEL,target_frame_for
from fit_mortar_fixed_registration import read_obj
from check_official_sonar_coordinates import Geometry,beam_count

OUT=ROOT/'DataSet/sonar_fixed_registration_refinement'
FITS={'2023-09-20_171105':[622,981,1336],'2023-09-21_100927':[87,451,811],'2023-09-21_120653':[163,551,933]}
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def transform(p,T):return p@T[:3,:3].T+T[:3,3]
def box(uv,g):
    if len(uv)==0:return None
    a=np.maximum(uv.min(0),[0,0]);b=np.minimum(uv.max(0),[g.w,g.h])
    return np.r_[a,b].tolist() if np.all(b>a) else None
def project(world,sw,g):
    p=transform(world,sw);r=np.linalg.norm(p,axis=1);a=-np.degrees(np.arctan2(p[:,0],p[:,2]));e=np.degrees(np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2])))
    vis=(p[:,2]>0)&(r>=g.r0)&(r<=g.data_range)&(a>=g.beams[0,1])&(a<=g.beams[-1,2])&(np.abs(e)<=7)
    uv=g.points_to_raw_edges(r[vis],a[vis]);b=box(uv,g)
    hull=cv2.convexHull(uv.astype('float32')).reshape(-1,2).tolist() if len(uv)>=3 else []
    return dict(bbox_xyxy=b,visible_point_count=int(vis.sum()),surface_count=len(p),hull_raw_edges=hull)
def select(ds):
    path=OUT/'evaluation-selection.json'
    if path.exists():return read(path)
    samples=[]
    for rec,members in sorted(ds.recordings.items()):
        chosen=[f'{rec}_{idx:04d}' for idx in FITS[rec]] if rec in FITS else [members[0],members[len(members)//2],members[-1]]
        for sid in chosen:
            row=ds.require(sid)
            samples.append(dict(sample=sid,recording=rec,aris_frame=row['aris_frame'],category=row['category'],model_name=CATEGORY_MODEL[row['category']],role='fit' if rec in FITS else 'development_check',historical_paired_role=row.get('paired_role')))
    assert len(samples)==120 and len({x['sample'] for x in samples})==120
    data=dict(manifest=ds.manifest_provenance,samples=samples,selection='All 40 permitted recordings: first/middle/last native; existing 3 centers in fit recordings',fit_count=9,check_count=111,not_final_test=True)
    save(path,data);return data
def panel(raw,result,title,color):
    h,w=raw.shape;pic=Image.fromarray(np.clip(raw.astype(float)*3,0,255).astype('uint8')).convert('RGB').resize((384,h),Image.Resampling.NEAREST)
    dr=ImageDraw.Draw(pic)
    if result:
        if result['bbox_xyxy']:
            b=result['bbox_xyxy'];dr.rectangle([b[0]*384/w,b[1],b[2]*384/w,b[3]],outline=color,width=2)
        hull=result['hull_raw_edges']
        if hull:
            pts=[(u*384/w,v) for u,v in hull];dr.line(pts+[pts[0]],fill=color,width=1)
    tile=Image.new('RGB',(410,h+60),'white');tile.paste(pic,(20,40));d=ImageDraw.Draw(tile);d.text((8,8),title,fill='black')
    return tile
def build_index():
    data=[]
    for model in ('100lbs','incindiary','mortar_shell'):
        p=OUT/model/'evaluation-results.json'
        if p.exists():data.extend(read(p)['frames'])
    cards=[]
    for f in sorted(data,key=lambda x:x['sample']):
        sid=f['sample'];m=f['model_name'];status=f.get('review_status','待独立复核')
        cards.append(f'<article data-model="{m}"><h3>{sid} · {f["role"]}</h3><p>{html.escape(status)}</p><a href="{m}/evaluation/{sid}-comparison.jpg"><img loading="lazy" src="{m}/evaluation/{sid}-comparison.jpg"></a><p>原图 / 旧 PCA / 新固定注册；全范围、gain=3；助手候选，待用户验收。</p></article>')
    doc='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>固定注册改进与跨录音检查</title><style>body{background:#f2f5f7;color:#1e293b;font:16px system-ui;margin:24px}article{background:white;padding:16px;margin:20px 0;border-radius:10px}img{width:100%;max-width:1230px}button{padding:8px 16px;margin:8px}</style><h1>固定注册改进 · 40条录音</h1><p>新候选由每类一套固定变换投影，未逐帧移动。旧版本与全部失败保留。这是开发检查，未写正式标注或用户审阅。</p><p>原图、旧 PCA 和新候选全高并排；原始 raw 坐标。框/轮廓显示仅为几何候选，非声学真值。</p><button onclick="filter('')">全部</button><button onclick="filter('100lbs')">bomb</button><button onclick="filter('incindiary')">grenade</button><button onclick="filter('mortar_shell')">mortar</button>'''+''.join(cards)+'''<script>function filter(m){document.querySelectorAll('article').forEach(x=>x.hidden=!!m&&x.dataset.model!==m)}</script></html>'''
    (OUT/'index.html').write_text(doc,encoding='utf-8')
def evaluate(model,ds,selection):
    folder=OUT/model;freeze=folder/'freeze-model.json'
    frozen=read(freeze);freeze_sha=sha(freeze)
    dest=folder/'evaluation';dest.mkdir(exist_ok=True)
    resultpath=folder/'evaluation-results.json'
    if resultpath.exists():raise RuntimeError('Preserve existing evaluation')
    old=read(ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json')['models'][model]
    vs,faces=read_obj(old['source']);tri=vs[faces]
    dense=np.concatenate([vs,tri.mean(1),(tri[:,0]+tri[:,1])/2,(tri[:,1]+tri[:,2])/2,(tri[:,2]+tri[:,0])/2])
    oldS=np.asarray(old['mesh_to_target_similarity']);oldWT=np.asarray(old['world_from_target'])
    newW=np.asarray(frozen['world_from_model'])@np.asarray(frozen['raw_obj_to_model_similarity'])
    calpath=ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json'
    statics={k:np.asarray(v) for k,v in read(calpath)['versions']['release_current']['parent_from_child_matrices'].items()}
    frames=[]
    for row in selection['samples']:
        if row['model_name']!=model:continue
        sid=row['sample'];r=ds.require(sid);rec=r['recording'];idx=r['aris_frame'];metas,gs,mp,gp=ds.recording_metadata(rec);m=metas[idx];g=gs[idx]
        assert int(m['FrameTime'])==int(r['aris_time_us'])
        wa=np.eye(4);wa[:3,:3]=statics['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ('SonarRoll','SonarTilt','SonarPan')],degrees=True).as_matrix();wa[:3,3]=[float(g[k]) for k in 'xyz'];wa[:3,3]+=statics['setup/ar3'][:3,3]
        ws=wa@statics['setup/aris']@statics['setup/sonar'];sw=np.linalg.inv(ws)
        geom=Geometry(m,ds.tables[beam_count(m['PingMode'])],1000.)
        tf=target_frame_for(r);wt=statics[tf];oldmatrix=wt@oldS
        # Preserve class registration relative to the official target. Floor
        # transfer is explicitly marked extrapolation, not separately refitted.
        newmatrix=wt@np.linalg.inv(oldWT)@newW
        oldres=project(transform(dense,oldmatrix),sw,geom);newres=project(transform(dense,newmatrix),sw,geom)
        rb,rp=ds.source_bytes(ds.rec_dirs[rec]/'aris_raw'/f'{idx:04d}.pgm');raw=cv2.imdecode(np.frombuffer(rb,np.uint8),cv2.IMREAD_GRAYSCALE)
        assert raw.shape==(geom.h,geom.w)
        Image.fromarray(raw).save(dest/(sid+'-raw.png'))
        tiles=[panel(raw,None,'Unboxed raw / gain 3',(0,0,0)),panel(raw,oldres,'Old PCA / same imaging',(255,160,0)),panel(raw,newres,'New fixed registration',(0,235,130))]
        canvas=Image.new('RGB',(1230,geom.h+265),'#eeeeee')
        for i,t in enumerate(tiles):canvas.paste(t,(410*i,0))
        dr=ImageDraw.Draw(canvas);dr.text((10,geom.h+63),sid+' | '+row['role']+' | target '+tf,fill='black')
        cp=None
        if ds.sd_paths[sid] and ds.sd_paths[sid].is_file():
            cb,cp=ds.source_bytes(ds.sd_paths[sid]);cam=cv2.imdecode(np.frombuffer(cb,np.uint8),cv2.IMREAD_COLOR);im=Image.fromarray(cv2.cvtColor(cam,cv2.COLOR_BGR2RGB));im.thumbnail((320,180));canvas.paste(im,(10,geom.h+82))
        dr.text((350,geom.h+90),'Candidate geometry only; no human acceptance. Padding = 0.',fill='black')
        if tf.endswith('_floor'):dr.text((350,geom.h+110),'FLOOR: class registration transfer remains unvalidated.',fill='black')
        canvas.save(dest/(sid+'-comparison.jpg'),quality=93)
        frames.append(row|dict(target_frame=tf,floor_extrapolation=tf.endswith('_floor'),old=oldres,new=newres,new_world_from_obj=newmatrix.tolist(),world_from_sonar=ws.tolist(),geometry=geom.description(),provenance=dict(raw=rp,camera=cp,metadata=mp,gantry=gp),candidate_id=frozen['candidate_id']))
        print(sid,flush=True)
    assert sha(freeze)==freeze_sha
    for f in frames:ds.validate_provenance(f['provenance'],full_hash=True)
    for rec in sorted({f['recording'] for f in frames}):
        pics=[Image.open(dest/(f['sample']+'-comparison.jpg')).convert('RGB') for f in frames if f['recording']==rec]
        sheet=Image.new('RGB',(max(p.width for p in pics),sum(p.height for p in pics)),'white');y=0
        for p in pics:sheet.paste(p,(0,y));y+=p.height
        sheet.save(dest/(rec+'-contact.jpg'),quality=93)
    save(resultpath,dict(model_name=model,freeze_path=str(freeze),freeze_sha256=freeze_sha,selection_sha256=sha(OUT/'evaluation-selection.json'),script_sha256=sha(__file__),frames=frames,frame_count=len(frames),old_bbox_padding=0,new_bbox_padding=0,new_formal_gt=0,user_reviews_written=0))
    build_index()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--model',choices=list(CATEGORY_MODEL.values()));args=ap.parse_args();OUT.mkdir(exist_ok=True)
    ds=DatasetSource();s=select(ds)
    if args.model:evaluate(args.model,ds,s)
    else:print(json.dumps({'selection_count':len(s['samples']),'sha256':sha(OUT/'evaluation-selection.json')}))
if __name__=='__main__':main()
