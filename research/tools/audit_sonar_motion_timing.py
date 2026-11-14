"""Six allowed source-metadata records; no image access or timing optimization."""
from pathlib import Path
import sys,json,csv,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np,yaml
BASE=Path('D:/pby/data_processed');OUT=ROOT/'DataSet/sonar_motion_timing'
RECS=['2023-09-20_171105','2023-09-20_173329','2023-09-21_100927','2023-09-21_101131','2023-09-21_120653','2023-09-21_120912']
hashes={}
def track(p):hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def rows(p):
    with track(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    OUT.mkdir(exist_ok=True);assert not (OUT/'results.json').exists()
    matches={Path(r['aris_file']).name:r for r in rows(BASE/'matches.csv') if Path(r['aris_file']).name in RECS};meta={r['file']:r for r in rows(BASE/'gantry/gantry_metadata.csv')};res=[]
    for rec in RECS:
        m=matches[rec];gp=BASE/m['gantry_file'];gg=rows(gp);am=rows(BASE/m['aris_file']/(rec+'_frames.csv'));marks=yaml.safe_load(track(BASE/m['aris_file']/(rec+'_marks.yaml')).read_text('utf-8'));flow=rows(BASE/m['aris_file']/(rec+'_flow.csv'))
        g=np.array([[float(r[k]) for k in ['timestamp_us','x','y','z']] for r in gg]);t=g[:,0];xyz=g[:,1:];d=np.diff(xyz[:,:2],axis=0);norm=np.linalg.norm(d,axis=1);ss=d.sum(1);ii=np.flatnonzero(norm>1e-10);jj=np.flatnonzero(ss!=0);first=int(ii[0]+1);official=int(jj[0]+1)
        onset=t[first]-t[0];off=float(m['gantry_offset']);gm=meta[gp.name];at=np.array([int(r['FrameTime']) for r in am]);indices=np.array([int(r['FrameIndex']) for r in am]);oi=int(np.where(indices==int(m['aris_onset']))[0][0]);elapsed=(at-at[oi])/1e6
        mapped=t[0]+off+(at-at[oi]);valid=(mapped>=t[0])&(mapped<=t[-1]);ipos=np.column_stack([np.interp(mapped,t,xyz[:,k]) for k in range(3)])
        moving=norm>1e-5;xy=xyz[1:,:2][moving];coef=np.linalg.lstsq(np.c_[2*xy,np.ones(len(xy))],(xy*xy).sum(1),rcond=None)[0];center=coef[:2];radius=np.sqrt(coef[2]+center@center);raderr=np.linalg.norm(xy-center,axis=1)-radius
        pan=np.array([float(r['SonarPan']) for r in am]);heading=np.degrees(np.arctan2(center[1]+.174-(ipos[:,1]+.174),center[0]-ipos[:,0]));beamheading=180-pan;err=(beamheading-heading+180)%360-180
        # Circle center is in gantry coordinates; adding fixed .174 to both leaves angle unchanged.
        active=valid&(mapped>=t[first])&(np.linalg.norm(ipos[:,:2]-center,axis=1)>.1)
        flowvals=np.array([[float(v) for v in r.values()] for r in flow]);frange={}
        for name,mask in [('before',(elapsed>=-2)&(elapsed<0)),('after',(elapsed>=0)&(elapsed<2))]:
            ids=np.flatnonzero(mask);ids=ids[ids<len(flowvals)]
            frange[name]=dict(frames=len(ids),column_medians=np.median(flowvals[ids],axis=0).tolist() if len(ids) else None)
        result=dict(recording=rec,match=m,gantry_rows=len(g),aris_rows=len(am),gantry_vector_onset_offset_us=float(onset),gantry_official_sum_onset_offset_us=float(t[official]-t[0]),metadata_onset_offset_us=float(gm['onset_us'])-float(gm['start_us']),match_gantry_offset_us=off,match_minus_vector_onset_seconds=(off-onset)/1e6,aris_match_onset=int(m['aris_onset']),aris_marks=marks,gantry_timestamp_nonpositive=int((np.diff(t)<=0).sum()),aris_timestamp_nonpositive=int((np.diff(at)<=0).sum()),gantry_dt_median_ms=float(np.median(np.diff(t))/1000),aris_dt_median_ms=float(np.median(np.diff(at))/1000),sum_cancels_xy_movement=int(((ss==0)&(norm>1e-10)).sum()),trajectory_circle_center_xy_m=center.tolist(),trajectory_radius_m=float(radius),circle_radial_rms_m=float(np.sqrt(np.mean(raderr**2))),pan_minus_circle_bearing_deg_percentiles=np.percentile(err[active],[5,50,95]).tolist(),flow_columns=list(flow[0]),flow_onset_windows=frange,clamping_full_recording_frames=int((~valid).sum()),note='Circle is descriptive; pan follows target manually, not necessarily circle center. Full ARIS metadata includes frames outside native annotation subset; no images read.')
        res.append(result)
        print(rec,'offset-onset seconds',result['match_minus_vector_onset_seconds'],'circle',center,'r',radius,'panerror',result['pan_minus_circle_bearing_deg_percentiles'],'flow',frange)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    (OUT/'results.json').write_text(json.dumps(dict(records=res,input_hashes=hashes,inputs_unchanged=True,test_images_read=0,new_parameters_fitted_for_deployment=0),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
