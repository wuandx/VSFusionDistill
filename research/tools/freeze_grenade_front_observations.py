"""Freeze assistant-observed near echo bands before any refinement projection."""
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2

OUT=ROOT/'DataSet/sonar_grenade_sequence_observations'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

windows={
163:[(u,141,157) for u in (33,38,43,48)]+[(u,154,177) for u in (53,58,63,67)],
551:[(u,132,163) for u in (7,16,26,36,46,56,66,76,86,96,106,112)],
933:[(u,103,119) for u in (39,44,49)]+[(u,112,135) for u in (55,61,67,73)]}
fades={163:{'left':[29,36],'right':[64,73]},551:{'left':[2,9],'right':[109,117]},933:{'left':[34,42],'right':[72,82]}}
def main():
    target=OUT/'front-observations.json'
    if target.exists():raise RuntimeError('Preserve frozen observations')
    manifest=json.loads((OUT/'manifest.json').read_text('utf-8'))
    frames=[]
    for idx,bands in windows.items():
        sid=f'2023-09-21_120653_{idx:04d}'
        entry=next(x for x in manifest['frames'] if x['sample']==sid)
        raw=cv2.imdecode(np.frombuffer((OUT/entry['raw_file']).read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
        points=[]
        for u,lo,hi in bands:
            # Fixed 3-column mean and a 3-bin moving average inside an observed
            # echo band; never search the whole image or follow a model box.
            profile=raw[lo:hi+1,u-1:u+2].astype(float).mean(axis=1)
            sm=np.convolve(profile,np.ones(3)/3,mode='same')
            peak=int(np.argmax(sm));v=lo+peak+.5
            points.append(dict(raw_uv_edge=[u+.5,v],tolerance_uv=[1.5,4.],observed_band=[u-1,lo,u+2,hi+1],peak_intensity=float(sm[peak])))
        frames.append(dict(sample=sid,role='fit',points=points,visible_echo_edge_intervals=fades[idx],
            physical_boundary_intervals={'left':None,'right':None,'top':None,'bottom':None},
            core_confidence='high' if idx==551 else 'medium',
            near_surface_assumption='Strong near-range curve interpreted as directly facing body return; acoustic approximation to be checked across recordings.',
            notes='551 broadside body arc is clear; 163/933 compact strong curves recur across neighbors. Weaker rear/lower branches may include support, reverberation or dark body; no far boundary or no-target constraint assigned.',
            source=entry))
    doc=dict(observer='assistant/root; not expert or user truth',frames=frames,observation_method='unboxed full raw/polar2 sequence and SD identity context; fixed local peak extraction',
             input_manifest_sha256=sha(OUT/'manifest.json'),script_sha256=sha(__file__),new_projection_seen=False,
             caveat='Visible echo fade edges are not physical silhouette measurements; not eligible as exact mesh endpoint correspondences.')
    target.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'front-observations.sha256.json').write_text(json.dumps({'sha256':sha(target)},indent=2),encoding='utf-8')
    print(json.dumps({f['sample']:[p['raw_uv_edge'] for p in f['points']] for f in frames}))
if __name__=='__main__':main()
