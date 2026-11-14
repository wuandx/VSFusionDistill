"""Independent projection/IoU replay and artifact integrity checks for two frozen runs."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json,hashlib,re
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image,ImageDraw
import cv2
from fit_sonar_fixed_registration_refinement import prepare_model
from check_official_sonar_coordinates import load_beam_tables
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def independent_iou(a,b):
    if a is None:return 0.
    x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]));ab=x*y
    return ab/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-ab)
def main():
    tables=load_beam_tables();reg=read(ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json')['models']
    points={m:prepare_model(reg[m])[1] for m in ['mortar_shell','incindiary']}
    results={}
    for run in ['sonar_box_guided_registration','sonar_box_guided_full_trajectory']:
        out=ROOT/'DataSet'/run;data=read(out/'results.json');sel=read(out/'selection.json')['samples'];rows=data['frames']
        assert len(rows)==len(sel)==len({r['sample'] for r in rows})
        model_poses={m:np.array(read(out/m/'freeze-model.json')['chosen']['world_from_model']) for m in points}
        for m,T in model_poses.items():
            assert np.max(abs(T[:3,:3].T@T[:3,:3]-np.eye(3)))<1e-10 and abs(np.linalg.det(T[:3,:3])-1)<1e-10
            frozen=read(out/m/'freeze-model.json');assert frozen['chosen']['fit_cost']==min(c['fit_cost'] for c in frozen['candidates'])
            assert set(frozen['fit_samples'])=={r['sample'] for r in rows if r['model']==m and r['role']=='fit'}
        max_iou=0
        for r in rows:
            with Image.open(out/r['image']) as im:im.verify()
            for p in r['predictions'].values():max_iou=max(max_iou,abs(independent_iou(p['bbox_xyxy'],r['reference_bbox'])-p['agreement']['iou']))
        assert max_iou<1e-12
        groups=sorted({(r['model'],r['recording'],r['role']) for r in rows});chosen=[]
        for group in groups:
            rr=sorted([r for r in rows if (r['model'],r['recording'],r['role'])==group],key=lambda r:r['sample'])
            chosen += [rr[i] for i in sorted({0,len(rr)//2,len(rr)-1})]
        replay=[];mesh_cards=[];qa=out/'qa';qa.mkdir(exist_ok=True)
        for r in chosen:
            p=points[r['model']];T=model_poses[r['model']];ws=np.array(r['world_from_sonar'])
            # World points then inverse rigid pose, separately from fitter's combined matrix.
            world=(T[:3,:3]@p.T).T+T[:3,3];sonar=(world-ws[:3,3])@ws[:3,:3]
            dist=np.sqrt((sonar**2).sum(axis=1));ang=np.rad2deg(np.arctan2(-sonar[:,0],sonar[:,2]));g=r['geometry']
            h,w=g['raw_shape_hw'];b=tables[w];xp=np.r_[np.column_stack([b[:,1],b[:,0]]).ravel(),b[-1,2]];fp=np.arange(len(xp))/2
            u=np.interp(ang,xp,fp)
            for mask,i,j in [(ang<xp[0],0,1),(ang>xp[-1],-2,-1)]:u[mask]=fp[i]+(ang[mask]-xp[i])*(fp[j]-fp[i])/(xp[j]-xp[i])
            v=(dist-g['range_start_m'])/g['sample_bin_m'];box=np.array([u.min(),v.min(),u.max(),v.max()]);stored=np.array(r['predictions']['box_guided']['unclipped_bbox'])
            err=float(abs(box-stored).max());assert err<1e-8;replay.append(dict(sample=r['sample'],max_edge_error_px=err))
            raw=np.array(Image.open(r['provenance']['raw']['path']));base=Image.fromarray(np.minimum(raw.astype(float)*2.5,255).astype('uint8')).convert('RGB')
            ref=r['reference_bbox'];lo=max(0,int(min(ref[1],box[1]))-25);hi=min(h,int(max(ref[3],box[3]))+25)
            tile=base.crop((0,lo,w,hi)).resize((640,500));draw=ImageDraw.Draw(tile)
            uv=np.column_stack([u,v]);hull=cv2.convexHull(uv.astype('float32')).reshape(-1,2)
            points2=[(float(x*640/w),float((y-lo)*500/(hi-lo))) for x,y in hull]
            draw.line(points2+[points2[0]],fill='#00cfff',width=2)
            for b,color in [(ref,'#50ff60'),(r['predictions']['box_guided']['bbox_xyxy'],'#00cfff')]:
                if b:draw.rectangle((b[0]*640/w,(b[1]-lo)*500/(hi-lo),b[2]*640/w,(b[3]-lo)*500/(hi-lo)),outline=color,width=2)
            canvas=Image.new('RGB',(1280,560),'white');canvas.paste(base.crop((0,lo,w,hi)).resize((640,500)),(0,40));canvas.paste(tile,(640,40));dd=ImageDraw.Draw(canvas)
            dd.text((8,8),r['sample']+' | '+r['role']+' | '+run,fill='black');dd.text((8,542),'Unboxed / projected full-mesh convex envelope (cyan), existing assistant box (green). Not an acoustic silhouette.',fill='black')
            filename=r['sample']+'-mesh.png';canvas.save(qa/filename);mesh_cards.append(f'<h3>{r["sample"]} {r["role"]}</h3><img style="width:100%;max-width:1280px" src="{filename}">')
        for path in re.findall(r'(?:src|href)="([^"]+)"',(out/'index.html').read_text('utf-8')):assert (out/path).is_file(),path
        summary=dict(run=run,frames=len(rows),images_decoded=len(rows),iou_checks=len(rows)*3,max_iou_difference=max_iou,independent_projection_checks=replay,max_projection_error_px=max(x['max_edge_error_px'] for x in replay),rigid_matrices_valid=True,minimum_fit_cost_selection_verified=True,html_local_links_resolve=True,browser_rendering_verified=False)
        (out/'independent-verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8');results[run]=summary
        # Review sheets are ordered first/middle/last by each declared role and recording.
        qa=out/'qa';qa.mkdir(exist_ok=True)
        for m,rec,role in groups:
            rr=[r for r in chosen if (r['model'],r['recording'],r['role'])==(m,rec,role)]
            canvas=Image.new('RGB',(1600,750*len(rr)),'white')
            for i,r in enumerate(rr):canvas.paste(Image.open(out/r['image']),(0,i*750))
            canvas.save(qa/f'{rec}-{role}.jpg',quality=93)
        (qa/'selection.json').write_text(json.dumps([dict(sample=r['sample'],recording=r['recording'],role=r['role']) for r in chosen],indent=2),'utf-8')
        (qa/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>完整3D模型投影抽查</h1><p>每个录音/检查组按身份首中末取样。蓝色为模型表面投影的凸包及框，不是声学可见表面预测。图中纵横缩放仅用于显示。</p>'+''.join(mesh_cards),'utf-8')
    first=read(ROOT/'DataSet/sonar_box_guided_registration/results.json');second=read(ROOT/'DataSet/sonar_box_guided_full_trajectory/results.json');lookup={r['sample']:r for r in first['frames']};comparison=[]
    for group in sorted({(r['model'],r['role']) for r in second['frames'] if r['role']!='fit'}):
        rows=[r for r in second['frames'] if (r['model'],r['role'])==group and r['sample'] in lookup and lookup[r['sample']]['role']!='fit']
        comparison.append(dict(model=group[0],role=group[1],n=len(rows),first_median_iou=float(np.median([lookup[r['sample']]['predictions']['box_guided']['agreement']['iou'] for r in rows])),second_median_iou=float(np.median([r['predictions']['box_guided']['agreement']['iou'] for r in rows])),sample_ids=[r['sample'] for r in rows]))
    (ROOT/'DataSet/sonar_box_guided_full_trajectory/common-check-comparison.json').write_text(json.dumps(comparison,indent=2),'utf-8')
    print(json.dumps({k:dict(frames=v['frames'],max_projection_error_px=v['max_projection_error_px']) for k,v in results.items()},indent=2))
if __name__=='__main__':main()
