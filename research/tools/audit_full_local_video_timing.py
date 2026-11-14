from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import csv,json,subprocess,collections
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(r'D:\pby\data_processed')
OUT=ROOT/'复现/camera-baseline/annotation-issues/full-source-timing'
def probe(task):
    rec,clip,res=task;p=SOURCE/'gopro'/f'clips_{res}'/clip
    r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_format','-of','json',str(p)],capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
    data=json.loads(r.stdout);s=data['streams'][0]
    (OUT/f'{rec}-{res}.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    return {'recording':rec,'clip':clip,'resolution':res,'path':str(p),'bytes':p.stat().st_size,'start':float(s['start_time']),'duration':float(s['duration']),'end':float(s['start_time'])+float(s['duration']),'fps':float(Fraction(s['avg_frame_rate'])),'fps_string':s['avg_frame_rate'],'frames':int(s['nb_frames']),'codec':s['codec_name'],'width':s['width'],'height':s['height'],'tags':s.get('tags',{})}
def main():
    OUT.mkdir(exist_ok=True,parents=True)
    allowed=set(json.loads((ROOT/'DataSet/camera_annotation_review/manifest.json').read_text(encoding='utf-8'))['provenance']['approved_recordings'])
    with (SOURCE/'matches.csv').open(encoding='utf-8',newline='') as f:matches={r['aris_file'].split('/')[-1]:r for r in csv.DictReader(f)}
    tasks=[(rec,Path(matches[rec]['gopro_file']).name,res) for rec in sorted(allowed) for res in ['sd','fhd','uhd']]
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(probe,tasks))
    grouped=collections.defaultdict(dict)
    for row in rows:grouped[row['recording']][row['resolution']]=row
    comparisons=[]
    for rec,v in grouped.items():
        sd,fhd,uhd=v['sd'],v['fhd'],v['uhd'];delta=fhd['start']-sd['start']
        comparisons.append({'recording':rec,'clip':sd['clip'],'sd_start':sd['start'],'fhd_start':fhd['start'],'uhd_start':uhd['start'],'sd_frames':sd['frames'],'fhd_frames':fhd['frames'],'uhd_frames':uhd['frames'],'sd_fps':sd['fps_string'],'fhd_fps':fhd['fps_string'],'uhd_fps':uhd['fps_string'],'fhd_minus_sd_seconds':round(delta,6),'fhd_minus_sd_frames_from_pts':round(delta*sd['fps'],4),'sd_minus_fhd_frame_count':sd['frames']-fhd['frames'],'sd_fhd_end_difference':round(fhd['end']-sd['end'],6),'exceeds_half_frame':abs(delta)*sd['fps']>.5,'fhd_has_more_frames_than_uhd':fhd['frames']>uhd['frames'],'pixel_correspondence_confirmed':rec in {'2023-09-21_101622','2023-09-21_103140'}})
    summary={'recordings':len(grouped),'videos':len(rows),'sd_fhd_start_differ_over_half_frame':sum(r['exceeds_half_frame'] for r in comparisons),'fhd_more_frames_than_uhd':sum(r['fhd_has_more_frames_than_uhd'] for r in comparisons),'fps_pairs_differ':sum(r['sd_fps']!=r['fhd_fps'] for r in comparisons),'scope':'40 approved development recordings; metadata only, no test or model evaluation','rows':comparisons}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    with (OUT/'recording-timing.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},ensure_ascii=False))
    print('largest_differences',json.dumps(sorted(comparisons,key=lambda x:abs(x['fhd_minus_sd_seconds']),reverse=True)[:6],ensure_ascii=False))
if __name__=='__main__':main()
