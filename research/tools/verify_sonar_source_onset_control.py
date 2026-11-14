from pathlib import Path
import sys,json,csv,bisect,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image
def read(p):return json.loads(p.read_text('utf-8'))
def main():
    out=ROOT/'DataSet/sonar_source_onset_control';result=read(out/'results.json');audit=read(ROOT/'DataSet/sonar_motion_timing/results.json');byrec={r['recording']:r for r in audit['records']};errors=[];cache={}
    for f in result['frames']:
        rec=f['recording'];a=byrec[rec]
        if rec not in cache:
            with (Path('D:/pby/data_processed')/a['match']['gantry_file']).open(encoding='utf-8-sig') as src:g=list(csv.DictReader(src))
            ts=[float(r['timestamp_us']) for r in g];pos=np.array([[float(r[k]) for k in 'xyz'] for r in g]);first=next(i for i in range(1,len(pos)) if any(abs(pos[i,k]-pos[i-1,k])>1e-10 for k in [0,1]));assert ts[first]-ts[0]==a['gantry_vector_onset_offset_us'];cache[rec]=(ts,pos)
        ts,pos=cache[rec];t=f['source_onset_time_us'];i=max(0,min(bisect.bisect_right(ts,t)-1,len(ts)-2));alpha=np.clip((t-ts[i])/(ts[i+1]-ts[i]),0,1);xyz=pos[i]*(1-alpha)+pos[i+1]*alpha;errors.append(float(np.max(abs(xyz-np.array(f['gantry_xyz_m'])))))
        assert not f['source_onset_clamped']
    for source in (result,audit):assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in source['input_hashes'].items())
    for p in out.glob('*.png'):
        with Image.open(p) as im:im.load()
    assert max(errors)<1e-12
    control=[]
    for cat in ['incindiary_grenade','mortar_shell']:
        rows=[r for r in result['camera'] if r['category']==cat];error=abs(rows[0]['check_median_px']-rows[1]['check_median_px']);assert error<1e-5;control.append(dict(category=cat,unchanged_check_median_difference_px=error))
    report=dict(passed=True,poses_checked=len(errors),independent_interpolation_max_error_m=max(errors),selected_frames_clamped=0,all_hashes_unchanged=True,images_decoded=6,unchanged_controls=control,physical_sync_certified=False)
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
if __name__=='__main__':main()
