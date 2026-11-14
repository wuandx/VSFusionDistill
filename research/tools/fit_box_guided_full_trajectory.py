"""Fixed per-class mesh registration constrained by existing reviewed sonar boxes."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,hashlib,csv,html,time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from PIL import Image,ImageDraw
from sonar_manual_curation_server import DatasetSource
from check_official_sonar_coordinates import Geometry,beam_count
from fit_sonar_fixed_registration_refinement import prepare_model

OUT=ROOT/'DataSet/sonar_box_guided_full_trajectory'
PLAN=ROOT/'experiment/sonar-box-guided-full-trajectory-plan.md'
INPUT=ROOT/'DataSet/sonar_box_guided_registration/input-snapshots/decisions.json'
CROSS=ROOT/'DataSet/sonar_box_guided_registration/input-snapshots/manifest.json'
REG=ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json'
CAL=ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json'
MODELS={'mortar_shell':('2023-09-21_103728','target/mortar_shell'), 'incindiary':('2023-09-21_123500','target/incendiary')}
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
def transform(p,T):return p@T[:3,:3].T+T[:3,3]
def matrix(q):
    T=np.eye(4);T[:3,:3]=Rotation.from_rotvec(q[3:]).as_matrix();T[:3,3]=q[:3];return T
def params(T):return np.r_[T[:3,3],Rotation.from_matrix(T[:3,:3]).as_rotvec()]
def clipped(b,w,h):
    b=np.r_[np.maximum(b[:2],[0,0]),np.minimum(b[2:],[w,h])]
    return b.tolist() if np.all(b[2:]>b[:2]) else None
def bbox(uv):return np.r_[uv.min(0),uv.max(0)]
def iou(a,b):
    if a is None:return 0.
    a=np.array(a);b=np.array(b);s=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2]));inter=np.prod(s)
    return float(inter/(np.prod(a[2:]-a[:2])+np.prod(b[2:]-b[:2])-inter))

class Frame:
    def __init__(self,ds,sid,statics):
        self.sid=sid;self.row=ds.require(sid);r=self.row
        mm,gg,mp,gp=ds.recording_metadata(r['recording']);m=mm[r['aris_frame']];g=gg[r['aris_frame']]
        assert int(m['FrameTime'])==r['aris_time_us']
        wa=np.eye(4);wa[:3,:3]=statics['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
        wa[:3,3]=np.array([float(g[k]) for k in 'xyz'])+statics['setup/ar3'][:3,3]
        self.ws=wa@statics['setup/aris']@statics['setup/sonar'];self.sw=np.linalg.inv(self.ws)
        self.geom=Geometry(m,ds.tables[beam_count(m['PingMode'])]);self.provenance=dict(metadata=mp,gantry=gp)
    def project(self,points,T):
        p=transform(points,self.sw@T);rng=np.linalg.norm(p,axis=1);beta=-np.degrees(np.arctan2(p[:,0],p[:,2]))
        uv=self.geom.points_to_raw_edges(rng,beta)
        return uv,p
    def box(self,points,T,details=False):
        uv,p=self.project(points,T);b=bbox(uv)
        if not details:return b,float(p[:,2].min())
        g=self.geom;el=np.degrees(np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2])))
        mask=(p[:,2]>0)&(abs(el)<=7)&(uv[:,0]>=0)&(uv[:,0]<=g.w)&(uv[:,1]>=0)&(uv[:,1]<=g.h)
        return dict(bbox_xyxy=clipped(b,g.w,g.h) if p[:,2].min()>0 else None,unclipped_bbox=b.tolist(),
                    gate7_bbox_xyxy=clipped(bbox(uv[mask]),g.w,g.h) if mask.any() else None,
                    elevation_range_deg=[float(el.min()),float(el.max())],fraction_in_gate7=float(mask.mean()),
                    min_forward_m=float(p[:,2].min()))

def metrics(pred,ref):
    b=pred['bbox_xyxy'];out=dict(iou=iou(b,ref))
    if b is not None:
        delta=np.array(b)-ref;out.update(edge_error_beam_bin=delta.tolist(),center_error_beam_bin=((delta[:2]+delta[2:])/2).tolist())
    return out

def render(ds,f,ref,preds,role,folder):
    rawpath=ds.rec_dirs[f.row['recording']]/'aris_raw'/f"{f.row['aris_frame']:04d}.pgm"
    rawbytes,rp=ds.source_bytes(rawpath)
    import io
    raw=np.array(Image.open(io.BytesIO(rawbytes)));g=f.geom;assert raw.shape==(g.h,g.w)
    gain=Image.fromarray(np.minimum(raw.astype(float)*2.5,255).astype('uint8')).convert('RGB')
    ys=[ref[1],ref[3]]+[b[k] for v in preds.values() if (b:=v['bbox_xyxy']) is not None for k in (1,3)]
    lo=max(0,int(min(ys))-25);hi=min(g.h,int(max(ys))+25)
    canvas=Image.new('RGB',(1600,750),'#f5f6f8');d=ImageDraw.Draw(canvas)
    d.text((12,8),f.sid+' | '+role+' | fixed mesh projection, NOT GT',fill='black')
    cam,cp=ds.source_bytes(ds.sd_paths[f.sid]);camera=Image.open(io.BytesIO(cam)).convert('RGB')
    canvas.paste(camera.resize((480,270)),(10,40));canvas.paste(gain.resize((210,400)),(10,330))
    d.text((230,335),'Full raw, gain 2.5',fill='black');d.text((230,355),'No flip; range down',fill='black')
    colors={'old_pca':'#ffae42','old_refinement':'#aa80ff','box_guided':'#00cfff'}
    for j,(key,pred) in enumerate(preds.items()):
        x=510+j*360;pic=gain.crop((0,lo,g.w,hi)).resize((350,590));pd=ImageDraw.Draw(pic)
        def drawbox(b,color,width):
            if b is not None:pd.rectangle((b[0]*350/g.w,(b[1]-lo)*590/(hi-lo),b[2]*350/g.w,(b[3]-lo)*590/(hi-lo)),outline=color,width=width)
        drawbox(ref,'#50ff60',2);drawbox(pred['bbox_xyxy'],colors[key],3)
        canvas.paste(pic,(x,85));d.text((x,43),key,fill='black');d.text((x,61),f"IoU {iou(pred['bbox_xyxy'],ref):.3f}",fill='black')
    d.text((230,385),'Green: existing assistant box',fill='black');d.text((230,405),'Color: complete mesh envelope',fill='black')
    d.text((230,425),f'Common zoom y={lo}:{hi}',fill='black');d.text((230,445),'Scale fixed; no per-frame shift',fill='black')
    name=f.sid+'.jpg';canvas.save(folder/name,quality=93)
    return name,dict(raw=rp,camera=cp)

def aggregate(rows):
    out={}
    for role in sorted({r['role'] for r in rows}):
        rr=[r for r in rows if r['role']==role];out[role]={}
        for key in ['old_pca','old_refinement','box_guided']:
            a=np.array([r['predictions'][key]['agreement']['iou'] for r in rr])
            out[role][key]=dict(n=len(a),median_iou=float(np.median(a)),mean_iou=float(a.mean()),fraction_iou_ge_05=float((a>=.5).mean()),fraction_iou_ge_075=float((a>=.75).mean()),local_practical_gate_passed=bool(np.median(a)>=.5 and (a>=.5).mean()>=.8))
    return out

def main():
    assert not OUT.exists(),'Preserve previous run; choose new version'
    OUT.mkdir();(OUT/'frames').mkdir();(OUT/'plan-before-fit.md').write_bytes(PLAN.read_bytes());(OUT/'solver-before-fit.py').write_bytes(Path(__file__).read_bytes())
    tracked={str(p):sha(p) for p in [INPUT,CROSS,REG,CAL,PLAN,Path(__file__),ROOT/'tools/check_official_sonar_coordinates.py',ROOT/'tools/fit_sonar_fixed_registration_refinement.py',ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py']}
    ds=DatasetSource();tracked[str(ds.manifest_path)]=ds.manifest_hash
    decisions=read(INPUT);cross=read(CROSS);registry=read(REG)['models'];statics={k:np.array(v) for k,v in read(CAL)['versions']['release_current']['parent_from_child_matrices'].items()}
    selected={};specs={}
    for rec in MODELS.values():
        rec=rec[0];rr=sorted([r for r in decisions.values() if r['recording']==rec and r['decision']=='accepted'],key=lambda r:r['sample'])
        n=len(rr);fit=[rr[i] for i in np.linspace(0,len(rr)-1,12).round().astype(int)];check=[r for r in rr if min(abs(int(r['sample'].rsplit('_',1)[1])-int(f['sample'].rsplit('_',1)[1])) for f in fit)>10]
        selected[rec]=dict(accepted_count=n,fit=[r['sample'] for r in fit],same_recording_check=[r['sample'] for r in check])
        for role,rs in [('fit',fit),('same_recording_check',check)]:
            for r in rs:specs[r['sample']]=dict(role=role,reference_bbox=r['bbox_xyxy'],reference_source=str(INPUT),reference_source_sha256=tracked[str(INPUT)],source_sha256=r['source_sha256'])
    for r in cross:
        assert r['review']['decision']=='accepted' and r['recording'] not in selected
        specs[r['sample']]=dict(role='cross_recording_check',reference_bbox=r['sonar_bbox_xyxy'],reference_source=str(CROSS),reference_source_sha256=tracked[str(CROSS)],source_sha256=r['review']['source_sha256'])
    for sid in specs:ds.require(sid)
    save(OUT/'selection.json',dict(recordings=selected,samples=specs,selection_rule='12 uniform in all accepted; non-fit >10 source frame gap check; 338 repeated cross-recording development checks; not blind or final test'))
    allrows=[];models={}
    for model,(rec,target) in MODELS.items():
        start=time.perf_counter();folder=OUT/model;folder.mkdir();info=registry[model];tracked[info['source']]=sha(info['source']);assert tracked[info['source']]==info['source_sha256']
        oldpath=ROOT/f'DataSet/sonar_fixed_registration_refinement/{model}/freeze-model.json';tracked[str(oldpath)]=sha(oldpath);old=read(oldpath)
        sampled,dense,definition=prepare_model(info)
        # Hull vertices retain angular and far-range extrema; area points constrain near range.
        hull=ConvexHull(sampled);points=np.r_[sampled[::8],sampled[hull.vertices]]
        origin=statics[target][:3,3];pca=np.array(info['world_from_target']);refine=np.array(old['world_from_model'])
        ids=[s for s in specs if ds.rows[s]['category']==info_category(model)]
        frames={sid:Frame(ds,sid,statics) for sid in ids};fits=[frames[s] for s in selected[rec]['fit']]
        for f in fits:
            assert sha(ds.rec_dirs[rec]/'aris_raw'/f"{f.row['aris_frame']:04d}.pgm")==specs[f.sid]['source_sha256']
        def residual(q):
            T=matrix(q);r=[]
            for f in fits:
                ref=np.array(specs[f.sid]['reference_bbox']);b,z=f.box(points,T);wh=np.maximum(ref[2:]-ref[:2],1)
                # Clip only FOV-censored reference edges; other edges retain overshoot penalty.
                if ref[0]<=1:b[0]=max(0,b[0])
                if ref[1]<=1:b[1]=max(0,b[1])
                if ref[2]>=f.geom.w-1:b[2]=min(f.geom.w,b[2])
                if ref[3]>=f.geom.h-1:b[3]=min(f.geom.h,b[3])
                r.extend((b-ref)/np.tile(wh,2));r.append(max(0,.05-z)*10)
            return np.array(r)
        lower=np.r_[origin-.5,[-6.3]*3];upper=np.r_[origin+.5,[6.3]*3]
        starts=[]
        for i in range(12):starts.append(np.r_[origin,Rotation.from_euler('xyz',[0 if i<6 else np.pi/2,0,-np.pi+2*np.pi*(i%6)/6]).as_rotvec()])
        starts += [params(pca),params(refine)]
        candidates=[]
        for i,q in enumerate(starts):
            q=np.clip(q,lower+1e-8,upper-1e-8)
            result=least_squares(residual,q,bounds=(lower,upper),loss='soft_l1',f_scale=.1,diff_step=1e-4,max_nfev=250,ftol=1e-7,xtol=1e-7,gtol=1e-7,x_scale=np.r_[[.1]*3,[1.]*3])
            candidates.append(dict(id=f'start-{i:02d}',parameters=result.x.tolist(),world_from_model=matrix(result.x).tolist(),fit_cost=float(result.cost),success=bool(result.success),nfev=result.nfev,message=result.message))
            print(model,i,round(result.cost,5),result.nfev,flush=True)
        best=min(candidates,key=lambda c:c['fit_cost']);T=np.array(best['world_from_model'])
        freeze=dict(model=model,chosen=best,candidates=candidates,raw_obj_to_model_similarity=info['mesh_to_target_similarity'],world_from_obj_similarity=(T@np.array(info['mesh_to_target_similarity'])).tolist(),fit_samples=selected[rec]['fit'],check_used_for_selection=False,scale_fixed=True,per_frame_parameters=0,time_offsets_changed=False,approved_for_training_gt=False,physical_registration_validated=False,model_definition=definition,optimization_points=len(points),selection_sha256=sha(OUT/'selection.json'))
        save(folder/'freeze-model.json',freeze);frozen_hash=sha(folder/'freeze-model.json')
        print(model,'FROZEN',best['id'],'evaluating',len(ids),'frames',flush=True)
        replay=[];rows=[]
        for sid in ids:
            f=frames[sid];sp=specs[sid];ref=np.array(sp['reference_bbox']);preds={}
            for key,pose in [('old_pca',pca),('old_refinement',refine),('box_guided',T)]:
                p=f.box(dense,pose,details=True);p['agreement']=metrics(p,ref);preds[key]=p
            if sp['role']=='fit':
                sparse,_=f.box(points,T);replay.append(dict(sample=sid,max_edge_difference_px=float(np.max(np.abs(sparse-preds['box_guided']['unclipped_bbox'])))))
            name,prov=render(ds,f,ref,preds,sp['role'],OUT/'frames');assert prov['raw']['sha256']==sp['source_sha256']
            rows.append(dict(sample=sid,recording=f.row['recording'],model=model,role=sp['role'],reference_bbox=ref.tolist(),predictions=preds,image='frames/'+name,world_from_sonar=f.ws.tolist(),geometry=f.geom.description(),source_reference=sp,provenance=f.provenance|prov))
            if len(rows)%40==0:print(model,'evaluated',len(rows),flush=True)
        assert sha(folder/'freeze-model.json')==frozen_hash
        summary=aggregate(rows);byrec={r:aggregate([x for x in rows if x['recording']==r]) for r in sorted({x['recording'] for x in rows})}
        models[model]=dict(summary=summary,by_recording=byrec,freeze_sha256=frozen_hash,fit_dense_replay=replay,max_sparse_dense_edge_difference_px=max(x['max_edge_difference_px'] for x in replay),elapsed_seconds=time.perf_counter()-start)
        save(folder/'evaluation.json',dict(frames=rows,**models[model]));allrows+=rows
        print(model,json.dumps(summary),flush=True)
    for r in allrows:ds.validate_provenance(r['provenance'],full_hash=True)
    assert all(sha(p)==h for p,h in tracked.items())
    save(OUT/'results.json',dict(run='sonar_box_guided_full_trajectory',models=models,frames=allrows,formal_gt_generated=0,physical_registration_validated=False))
    save(OUT/'verification.json',dict(input_hashes=tracked,inputs_unchanged=True,frame_provenance_checked=len(allrows),fit_check_disjoint=True,all_samples_in_allowed_development_manifest=True,test_access=False,training_runs=0,original_labels_changed=False))
    with (OUT/'metrics.csv').open('w',newline='',encoding='utf-8-sig') as f:
        wr=csv.writer(f);wr.writerow(['sample','model','recording','role','old_pca_iou','old_refinement_iou','box_guided_iou'])
        for r in allrows:wr.writerow([r['sample'],r['model'],r['recording'],r['role']]+[r['predictions'][k]['agreement']['iou'] for k in ['old_pca','old_refinement','box_guided']])
    cards=[]
    for r in allrows:
        score=r['predictions']['box_guided']['agreement']['iou']
        cards.append(f'<article data-role="{r["role"]}" data-model="{r["model"]}"><h3>{r["sample"]} · {r["role"]} · IoU {score:.3f}</h3><a href="{r["image"]}"><img loading="lazy" src="{r["image"]}"></a></article>')
    table='<table><tr><th>类别</th><th>检查组</th><th>N</th><th>旧PCA</th><th>旧注册</th><th>框约束注册</th><th>IoU≥0.5比例</th></tr>'
    for model,d in models.items():
        for role,s in d['summary'].items():table+=f'<tr><td>{model}</td><td>{role}</td><td>{s["box_guided"]["n"]}</td>'+''.join(f'<td>{s[k]["median_iou"]:.3f}</td>' for k in ['old_pca','old_refinement','box_guided'])+f'<td>{s["box_guided"]["fraction_iou_ge_05"]:.1%}</td></tr>'
    table+='</table>'
    doc='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>已审核框辅助3D投影注册</title><style>body{font:16px system-ui;margin:28px;background:#f5f6f8;color:#182234}table{border-collapse:collapse;background:white}td,th{border:1px solid #ccd3dd;padding:10px}img{width:100%;max-width:1600px}article{background:white;padding:12px;margin:20px 0}select{padding:9px;margin:12px}</style><h1>已审核框辅助固定3D投影注册</h1><p>绿色：既有助手框；橙色：旧PCA；紫色：旧near-surface注册；蓝色：本次框约束注册。三者同一完整模型投影框定义。每类一套固定姿态，尺度/gantry/时间/外参不变。</p><p>IoU是与助手可见回波框的一致度，不是AP或物理标定认证。fit与检查分开；跨录音检查不用来选择参数。bomb没有已接受框，本轮不拟合。±7°裁剪诊断保存在JSON。</p>'''+table+'''<p><a href="results.json">完整结果</a> · <a href="metrics.csv">逐帧CSV</a> · <a href="verification.json">来源核验</a> · <a href="selection.json">拟合与检查清单</a></p><select id="role"><option value="">全部检查组</option><option>fit</option><option>same_recording_check</option><option>cross_recording_check</option></select><select id="model"><option value="">全部类别</option><option>mortar_shell</option><option>incindiary</option></select>'''+''.join(cards)+'''<script>function filter(){document.querySelectorAll('article').forEach(a=>a.hidden=(role.value&&a.dataset.role!==role.value)||(model.value&&a.dataset.model!==model.value));}const role=document.getElementById('role'),model=document.getElementById('model');role.onchange=filter;model.onchange=filter;</script></html>'''
    (OUT/'index.html').write_text(doc,'utf-8');print('COMPLETE',len(allrows),flush=True)
def info_category(model):return {'mortar_shell':'mortar_shell','incindiary':'incindiary_grenade'}[model]
if __name__=='__main__':main()
