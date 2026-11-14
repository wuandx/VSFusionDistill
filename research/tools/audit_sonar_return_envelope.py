"""Frozen-pose front-return envelope and padding controls, no optimization."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from fit_box_guided_sonar_registration import Frame,read,save,sha,clipped,iou,REG,CAL
from fit_sonar_fixed_registration_refinement import prepare_model
from sonar_manual_curation_server import DatasetSource
BASE=ROOT/'DataSet/sonar_box_guided_full_trajectory';CAUSE=ROOT/'DataSet/sonar_projection_root_cause';OUT=CAUSE/'return_envelope_control'
def envelope(uv,p,h,w,gate):
    el=np.degrees(np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2])));mask=(p[:,2]>0)
    if gate:mask&=abs(el)<=7
    xy=uv[mask];order=np.argsort(xy[:,0]);xy=xy[order];curve=[]
    for u in np.arange(.125,w,.25):
        a,b=np.searchsorted(xy[:,0],[u-.75,u+.75]);q=xy[a:b]
        if len(q)>=3:curve.append([float(u),float(q[:,1].min())])
    if len(curve)<2:return dict(bbox_xyxy=None,curve=[])
    curve=np.array(curve);box=np.r_[curve.min(0)-[2,5],curve.max(0)+[2,5]]
    return dict(bbox_xyxy=clipped(box,w,h),curve=curve.tolist())
def main():
    assert not OUT.exists();OUT.mkdir();ds=DatasetSource();rows=read(BASE/'results.json')['frames'];statics={k:np.array(v) for k,v in read(CAL)['versions']['release_current']['parent_from_child_matrices'].items()};registry=read(REG)['models'];cache={};out=[]
    for r in rows:
        model=r['model'];sid=r['sample']
        if model not in cache:cache[model]=(prepare_model(registry[model])[1],{'box_only':np.array(read(BASE/model/'freeze-model.json')['chosen']['world_from_model']),'box_plus_curve':np.array(read(CAUSE/'curve_control'/model/'freeze-model.json')['chosen']['world_from_model'])})
        points,poses=cache[model];f=Frame(ds,sid,statics);variants={}
        for name,T in poses.items():
            uv,p=f.project(points,T);box=np.r_[uv.min(0)-[2,5],uv.max(0)+[2,5]];variants[name+'_full_padded']=dict(bbox_xyxy=clipped(box,f.geom.w,f.geom.h))
            for mode,gate in [('front',False),('front_gate7',True)]:variants[name+'_'+mode]=envelope(uv,p,f.geom.h,f.geom.w,gate)
        for v in variants.values():v['iou']=iou(v['bbox_xyxy'],r['reference_bbox'])
        out.append(dict(sample=sid,recording=r['recording'],role=r['role'],model=model,reference_bbox=r['reference_bbox'],variants=variants,provenance=r['provenance']))
        if len(out)%100==0:print('evaluated',len(out),flush=True)
    summary=[]
    for rec in sorted({r['recording'] for r in out}):
        rr=[r for r in out if r['recording']==rec and r['role']!='fit'];summary.append(dict(recording=rec,n=len(rr),medians={k:float(np.median([r['variants'][k]['iou'] for r in rr])) for k in out[0]['variants']}))
    save(OUT/'results.json',dict(frames=out,summary=summary,plan_sha256=sha(ROOT/'experiment/sonar-return-envelope-control-plan.md'),physical_accuracy_validated=False));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
