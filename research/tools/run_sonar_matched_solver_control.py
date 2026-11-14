"""Single registered legacy-loss comparison with matched stopping tolerances."""
import csv
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True
import run_sonar_registration_solver_controls as control
import numpy as np


def main():
    out=control.OUT;name='legacy_interval_stable_difference_matched_tolerances'
    if (out/(name+'.json')).exists(): raise RuntimeError('Do not overwrite a completed control')
    points_path=control.ROOT/'DataSet/mortar_fixed_registration/sampled-model-points.npy'
    meta_path=Path('D:/pby/uxo-full/extracted/recordings/15cm_mortar/2023-09-21_100927/aris_frame_meta.csv')
    paths=[Path(__file__),Path(control.__file__),control.PLAN,out/'synthetic-fixture.json',points_path,meta_path]
    before={str(p):control.sha(p) for p in paths}
    fixture=control.read(out/'synthetic-fixture.json');points=np.load(points_path,allow_pickle=False)
    origin=np.array(fixture['origin_world_m']);tables=control.load_beam_tables();frames=[]
    metadata={int(r['FrameIndex']):r for r in csv.DictReader(meta_path.open(encoding='utf-8-sig',newline='')) if int(r['FrameIndex']) in control.FIT_INDICES}
    for row in fixture['frames']:
        m=metadata[row['metadata_frame_index']]
        obs=dict(sample=row['sample'],points=[dict(raw_uv_edge=uv,tolerance_uv=[.1,.2]) for uv in row['legacy_uv']])
        frames.append(control.legacy.FitFrame(obs,dict(world_from_sonar=row['world_from_sonar']),m,tables[control.beam_count(m['PingMode'])]))
    original=control.least_squares
    def matched(*args,**kwargs):
        kwargs.update(ftol=1e-7,xtol=1e-7,gtol=1e-7)
        return original(*args,**kwargs)
    control.least_squares=matched
    fn=lambda x:control.legacy.raw_loss(frames,points,control.matrix(x,origin))
    result=control.run_fit(name,control.STARTS[0],fn,origin,frames,points,time.perf_counter(),stable=True,max_nfev=60)
    after={str(p):control.sha(p) for p in paths};assert before==after
    control.save(out/'matched-tolerances-verification.json',dict(status='completed',case=name,
                 ftol=1e-7,xtol=1e-7,gtol=1e-7,input_hashes=before,input_hashes_unchanged=True,
                 final_objective=result['final_objective'],real_observation_reads=0,image_reads=0,
                 note='Original stricter-tolerance case remains preserved as a separate executed configuration'))


if __name__=='__main__':main()
