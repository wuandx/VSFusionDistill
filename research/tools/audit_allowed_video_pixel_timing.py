from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,json,numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'复现/camera-baseline/annotation-issues/full-source-timing'
SOURCE=Path(r'D:\pby\data_processed\gopro')
def decode(path,expected):
    r=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(path),'-vf','scale=160:90','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','gray','pipe:1'],capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[:500])
    array=np.frombuffer(r.stdout,dtype=np.uint8).reshape((-1,14400)).astype(np.float32)
    assert len(array)==expected,(str(path),len(array),expected)
    array-=array.mean(axis=1)[:,None]
    return array,r.stderr.decode(errors='replace')
def check(row):
    try:
        sd,se=decode(SOURCE/'clips_sd'/row['clip'],row['sd_frames'])
        fhd,fe=decode(SOURCE/'clips_fhd'/row['clip'],row['fhd_frames'])
        delta=round(row['fhd_minus_sd_frames_from_pts'])
        idx=np.arange(0,min(len(fhd),len(sd)),20)
        idx=idx[(idx+delta>=0)&(idx+delta<len(sd))]
        if not len(idx):raise RuntimeError('no common comparison indices')
        a=np.mean((fhd[idx]-sd[idx+delta])**2,axis=1)
        b=np.mean((fhd[idx]-sd[idx])**2,axis=1)
        result={'recording':row['recording'],'clip':row['clip'],'delta_frames_from_metadata':delta,'pairs':len(idx),'timestamp_aligned_mse_median':float(np.median(a)),'same_index_mse_median':float(np.median(b)),'aligned_lower_than_same_index':bool(np.median(a)<np.median(b)),'decode_count_verified':True,'stderr':se+fe}
        print(json.dumps(result),flush=True);return result
    except Exception as e:
        result={'recording':row['recording'],'error':repr(e)};print(json.dumps(result),flush=True);return result
def main():
    rows=json.loads((BASE/'summary.json').read_text(encoding='utf-8'))['rows']
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(check,rows))
    (BASE/'pixel-correspondence.json').write_text(json.dumps({'method':'40 allowed recording pairs; every20th FHD frame; no bbox or offset fitting; centered grayscale160x90; passthrough frame counts verified','rows':results},indent=2),encoding='utf-8')
if __name__=='__main__':main()
