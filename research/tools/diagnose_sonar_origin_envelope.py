"""Read frozen development products; separate origin localization from mesh orientation."""
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image,ImageDraw
from check_official_sonar_coordinates import load_beam_tables,linear_extrapolate

OUT=ROOT/'DataSet/sonar_origin_envelope'
BASE=ROOT/'DataSet/sonar_fixed_registration_refinement'
tracked={}
def read(p):
    p=Path(p);tracked[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text('utf-8-sig'))
def arc_distance(center,r,beta,limit):
    az=-np.deg2rad(beta);axis=np.array([np.sin(az),0.,np.cos(az)])
    e=np.clip(np.arctan2(center[1],center@axis),-limit,limit)
    p=r*(np.cos(e)*axis+np.sin(e)*np.array([0.,1.,0.]))
    return float(np.linalg.norm(center-p)),float(np.rad2deg(e)),p
def pixel(p,g,table):
    beta=-np.rad2deg(np.arctan2(p[...,0],p[...,2]));r=np.linalg.norm(p,axis=-1)
    knots=np.r_[np.column_stack([table[:,1],table[:,0]]).ravel(),table[-1,2]]
    return np.stack([linear_extrapolate(beta,knots,np.arange(2*len(table)+1)/2),(r-g['range_start_m'])/g['sample_bin_m']],axis=-1)
def main():
    if OUT.exists():raise RuntimeError('Preserve completed audit')
    OUT.mkdir();tables=load_beam_tables()
    read(ROOT/'DataSet/sonar_fixed_registration_refinement/evaluation-selection.json')
    registry=read(ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json')['models']
    cal=read(ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json')['versions']['release_current']['parent_from_child_matrices']
    rows=[];controls=[];cards=[]
    rng=np.random.default_rng(17)
    for _ in range(24):
        r=rng.uniform(.5,3);beta=rng.uniform(-14,14);el=rng.uniform(-6,6)
        a=-np.deg2rad(beta);e=np.deg2rad(el)
        p=r*np.array([np.cos(e)*np.sin(a),np.sin(e),np.cos(e)*np.cos(a)])
        d,_,_=arc_distance(p,r,beta,np.deg2rad(7));assert d<1e-12
        controls.append(d)
    grid_error=[]
    for model in ('100lbs','incindiary','mortar_shell'):
        info=registry[model];radius=float(np.linalg.norm(np.max(np.abs(info['target_mesh_aabb_m']),axis=0)))
        frames=read(BASE/model/'evaluation-results.json')['frames']
        obs={f['sample']:f for f in read(BASE/model/'adapted-fit-observations.json')['frames']}
        frozen=read(BASE/model/'freeze-model.json')
        for f in frames:
            sid=f['sample'];g=f['geometry'];h,w=g['raw_shape_hw'];table=tables[w]
            ws=np.array(f['world_from_sonar']);sw=np.linalg.inv(ws);wt=np.array(cal[f['target_frame']])
            center=(sw@wt)[:3,3]
            new_world=wt@np.linalg.inv(np.array(info['world_from_target']))@np.array(frozen['world_from_model'])
            nc=(sw@new_world)[:3,3]
            uv=pixel(center,g,table);nuv=pixel(nc,g,table)
            row=dict(sample=sid,model=model,role=f['role'],target_frame=f['target_frame'],origin_sonar_xyz_m=center.tolist(),origin_raw_uv=uv.tolist(),origin_range_m=float(np.linalg.norm(center)),origin_elevation_deg=float(np.rad2deg(np.arctan2(center[1],np.hypot(center[0],center[2])))),new_center_raw_uv=nuv.tolist(),new_center_shift_m=float(np.linalg.norm(new_world[:3,3]-wt[:3,3])),orientation_independent_mesh_bound_radius_m=radius,observations=[])
            if sid in obs:
                for point in obs[sid]['points']:
                    u,v=point['witness_raw_uv_edge'];r=g['range_start_m']+v*g['sample_bin_m']
                    knots=np.r_[np.column_stack([table[:,1],table[:,0]]).ravel(),table[-1,2]]
                    beta=float(linear_extrapolate(u,np.arange(2*w+1)/2,knots))
                    values={}
                    for label,c in [('official_origin',center),('fitted_center',nc)]:
                        for name,lim in [('unrestricted',np.pi/2),('gate7',np.deg2rad(7))]:
                            d,e,p=arc_distance(c,r,beta,lim)
                            es=np.linspace(-lim,lim,20001);a=-np.deg2rad(beta)
                            ps=r*np.column_stack([np.cos(es)*np.sin(a),np.sin(es),np.cos(es)*np.cos(a)])
                            dg=float(np.linalg.norm(ps-c,axis=1).min());grid_error.append(abs(dg-d))
                            assert abs(dg-d)<.0003
                            values[label+'_'+name]=dict(distance_m=d,elevation_deg=e,outside_bound=d>radius)
                    row['observations'].append(dict(raw_uv=[u,v],range_m=r,beam_angle_deg=beta,**values))
                rawpath=BASE/model/'evaluation'/f'{sid}-raw.png'
                tracked[str(rawpath)]=hashlib.sha256(rawpath.read_bytes()).hexdigest()
                im=Image.open(rawpath).convert('L');im=Image.fromarray(np.clip(np.asarray(im).astype(float)*3,0,255).astype('uint8')).convert('RGB').resize((512,h))
                canvas=Image.new('RGB',(760,h+105),'white');canvas.paste(im,(0,45));d=ImageDraw.Draw(canvas)
                d.text((8,5),sid+' | raw gain 3; no fitting',fill='black')
                for box,color in [(f['old']['bbox_xyxy'],'orange'),(f['new']['bbox_xyxy'],'lime')]:
                    if box:d.rectangle((box[0]*512/w,box[1]+45,box[2]*512/w,box[3]+45),outline=color,width=2)
                for p,color in [(uv,'cyan'),(nuv,'magenta')]:
                    x,y=p[0]*512/w,p[1]+45
                    if 0<=x<512 and 45<=y<h+45:d.line((x-8,y,x+8,y),fill=color,width=3);d.line((x,y-8,x,y+8),fill=color,width=3)
                for p in row['observations']:
                    x,y=p['raw_uv'];x=x*512/w;y+=45;d.ellipse((x-3,y-3,x+3,y+3),fill='yellow')
                lines=['cyan: official origin','magenta: fitted center','orange: old mesh box','green: fitted mesh box','yellow: prior witnesses',f'bound radius: {radius:.3f} m',f'origin el: {row["origin_elevation_deg"]:.2f} deg',f'center shift: {row["new_center_shift_m"]:.3f} m','witnesses are NOT GT']
                for i,line in enumerate(lines):d.text((523,55+22*i),line,fill='black')
                canvas.save(OUT/f'{sid}.png');cards.append(f'<h3>{sid}</h3><img src="{sid}.png">')
            rows.append(row)
    summary={}
    for model in registry:
        rr=[r for r in rows if r['model']==model];pp=[p for r in rr for p in r['observations']]
        summary[model]=dict(frames=len(rr),witness_count=len(pp),origin_elevation_min_max_deg=[min(r['origin_elevation_deg'] for r in rr),max(r['origin_elevation_deg'] for r in rr)],center_shift_m=rr[0]['new_center_shift_m'],bound_radius_m=rr[0]['orientation_independent_mesh_bound_radius_m'],outside_bound={k:sum(p[k]['outside_bound'] for p in pp) for k in ['official_origin_unrestricted','official_origin_gate7','fitted_center_unrestricted','fitted_center_gate7']},official_unrestricted_distance_min_max_m=[min(p['official_origin_unrestricted']['distance_m'] for p in pp),max(p['official_origin_unrestricted']['distance_m'] for p in pp)])
    assert len(rows)==120 and sum(bool(r['observations']) for r in rows)==9
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in tracked.items())
    out=dict(run='sonar_origin_envelope',summary=summary,frames=rows,synthetic_controls_max_error_m=max(controls),dense_arc_control_max_error_m=max(grid_error),input_hashes=tracked,inputs_unchanged=True,new_fits=0,new_formal_gt=0,test_access=False,limitations=['witness points are previous assistant observations, not exact surfaces','bound radius assumes old nominal scale and target-centered mesh','outside counts use point witnesses, not whole tolerance intervals; not a GT rejection rule'])
    (OUT/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Origin diagnostic</title><h1>官方原点与已有回波观察：不是GT</h1><p>9个已有fit开发帧，120个原点数值见results.json。青色为官方原点，紫色为拟合中心，黄色为旧助手观察点。中心不要求落在回波亮边上。</p>'+''.join(cards),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2));print('control max m',max(grid_error))
if __name__=='__main__':main()
