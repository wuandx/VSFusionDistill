"""Near-anchor paired additions, explicit visual review required, original data read-only."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent/'_sonar_audit_deps'))
from expand_paired_recording_pool import read,sha,save,run,ROOT,Image,ImageDraw,ImageFont,np,csv
from expand_scene_stratified_pairs import raw_array
OUT=ROOT/'DataSet/paired_expanded_resplit_review'
BASE=ROOT/'DataSet/scene_stratified_mortar_recovered_candidate'

def main():
    OUT.mkdir(exist_ok=False)
    old=read(BASE/'manifest.json');pool=read(ROOT/'DataSet/paired_expansion_capacity_audit/candidate-frames.json')
    recs={r['recording']:r for r in csv.DictReader((BASE/'recordings.csv').open(encoding='utf-8-sig'))}
    sources=[];summary=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    for rec,meta in recs.items():
        if meta['role']!='train':continue
        anchors=sorted([r for r in old if r['recording']==rec],key=lambda x:int(x.get('aris_frame',x.get('frame',x['sample'].rsplit('_',1)[1]))))
        af=np.array([int(x.get('aris_frame',x.get('frame',x['sample'].rsplit('_',1)[1]))) for x in anchors])
        proposals=[]
        for r in [x for x in pool if x['recording']==rec]:
            f=int(r['sample'].rsplit('_',1)[1]);j=int(np.searchsorted(af,f))
            if not 0<j<len(af):continue
            lo,hi=anchors[j-1],anchors[j];a,b=int(af[j-1]),int(af[j])
            if min(f-a,b-f)>2 or b-a>12:continue
            alpha=(f-a)/(b-a);box=np.rint((1-alpha)*np.array(lo['sonar_bbox_xyxy'])+alpha*np.array(hi['sonar_bbox_xyxy'])).astype(int).tolist()
            # Reject inconsistent anchor identities/geometries rather than hiding them by clipping.
            if lo['sonar_size_wh']!=hi['sonar_size_wh']:continue
            w,h=lo['sonar_size_wh']
            if not (0<=box[0]<box[2]<=w and 0<=box[1]<box[3]<=h):continue
            proposals.append(dict(r,frame=f,proposal_xyxy=box,anchor_samples=[lo['sample'],hi['sample']],anchor_frames=[a,b],anchor_boxes=[lo['sonar_bbox_xyxy'],hi['sonar_bbox_xyxy']],alpha=alpha,sonar_size_wh=[w,h],scene_id=meta['scene_id'],group_id=meta['group_id'],category=meta['category'],source_role_before_resplit='train',decision='unreviewed',precision_sync_certified=False,expert_verified=False))
        if not proposals:continue
        n=min(40,len(proposals));take=[proposals[round(i*(len(proposals)-1)/(n-1))] for i in range(n)] if n>1 else proposals
        folder=OUT/rec;folder.mkdir();sheets=[]
        pending=[r for r in take if not r.get('camera_source')]
        if pending:
            sd=folder/'sd';sd.mkdir();indices=sorted({r['sd_index'] for r in pending});expr='+'.join(f'eq(n\\,{i})' for i in indices)
            run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',pending[0]['camera_clip'],'-vf','select='+expr,'-fps_mode','passthrough','-q:v','2','-start_number','0',str(sd/'%04d.jpg')])
            files=sorted(sd.glob('*.jpg'));assert len(files)==len(indices);lookup=dict(zip(indices,files))
            for r in pending:r['camera_source']=str(lookup[r['sd_index']])
        for j,r in enumerate(take):
            r['ordinal']=j;r['camera_sha256']=sha(r['camera_source']);r['sonar_sha256']=sha(r['sonar_source'])
            if j%20==0:
                canvas=Image.new('RGB',(1800,2285),'#f4f6fa');d=ImageDraw.Draw(canvas)
                d.text((5,4),rec+' | NEW paired near-anchor proposals | NOT accepted | sonar display gain2.5',font=font,fill='black')
            x=j%20%4*450;y=30+j%20//4*450
            d.text((x+3,y),f'{j} f{r["frame"]} anchors {r["anchor_frames"]}',font=font,fill='black')
            cam=Image.open(r['camera_source']).convert('RGB');assert cam.size==(640,360)
            ImageDraw.Draw(cam).rectangle(r['camera_box'],outline='#00ff40',width=2);canvas.paste(cam.resize((446,251)),(x,y+22))
            arr=raw_array(r['sonar_source']);assert list(arr.shape[::-1])==r['sonar_size_wh']
            son=Image.fromarray(np.clip(arr.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB');box=r['proposal_xyxy'];ImageDraw.Draw(son).rectangle(box,outline='#00ff40',width=1)
            canvas.paste(son.resize((108,165)),(x,y+280))
            l=max(0,box[1]-25);u=min(son.height,box[3]+25);canvas.paste(son.crop((0,l,128,u)).resize((334,165)),(x+112,y+280))
            if j%20==19 or j==len(take)-1:
                path=folder/f'page-{j//20:02d}.jpg';canvas.save(path,quality=96);sheets.append(dict(path=str(path.relative_to(OUT)),sha256=sha(path)))
            r['sheet']=str((folder/f'page-{j//20:02d}.jpg').relative_to(OUT))
            sources.append(r)
        save(folder/'proposals.json',take);summary.append(dict(recording=rec,eligible_near_anchor=len(proposals),proposals=len(take),sheets=sheets,scene_id=meta['scene_id']))
    save(OUT/'proposals.json',sources);save(OUT/'recordings.json',summary)
    save(OUT/'inputs.json',dict(original_manifest_sha256=sha(BASE/'manifest.json'),capacity_manifest_sha256=sha(ROOT/'DataSet/paired_expansion_capacity_audit/candidate-frames.json'),method='linear interpolation only between existing accepted boxes <=12 ARIS frames apart, candidate within2 frames of an accepted anchor; max40/recording; requires new dual visual review',accepted_new_pairs=0))
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><h1>Paired near-anchor proposals, not accepted</h1>'+''.join('<h2>'+r['recording']+'</h2>'+''.join('<img loading="lazy" style="max-width:100%" src="'+s['path']+'">' for s in r['sheets']) for r in summary),encoding='utf-8')
    print(dict(proposals=len(sources),recordings=len(summary),pages=sum(len(r['sheets']) for r in summary)))
if __name__=='__main__':main()
