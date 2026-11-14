"""Replay saved proposals and preserve annotation-boundary review flags."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,hashlib,json
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import expand_paired_visible as e
from PIL import Image,ImageDraw
ROOT=e.ROOT;CAUSE=ROOT/'DataSet/sonar_projection_root_cause';OUT=CAUSE/'proposal_provenance'

def mechanism(r,a):
    # Exact original unshuffled E branch, with intermediate values retained.
    np=e.np;cv=e.cv2;h,w=a.shape
    seed,diag=e.propose(a,r['overview_index'],35,4)
    sm=cv.GaussianBlur(a.astype(np.float32),(3,7),0);threshold=diag['bg']+max(35,4*diag['mad'])
    mask=(sm>threshold).astype(np.uint8);mask[:int(h*.04)]=0;mask[int(h*.96):]=0
    mask=cv.morphologyEx(mask,cv.MORPH_CLOSE,np.ones((9,3),np.uint8));n,lab,stats,_=cv.connectedComponentsWithStats(mask)
    sx0,sy0,sx1,sy1=seed;candidates=[]
    for k in range(1,n):
        overlap=int((lab[sy0:sy1,sx0:sx1]==k).sum())
        if stats[k,4]>=12 and overlap>=6:candidates.append((overlap,k))
    _,k=max(candidates);energy=np.maximum(sm-threshold,0)*(lab==k);cum=np.cumsum(energy.sum(axis=1))
    lo=int(np.searchsorted(cum,cum[-1]*.015));hi=int(np.searchsorted(cum,cum[-1]*.93))+1
    kept=(lab==k)&(np.arange(h)[:,None]>=lo)&(np.arange(h)[:,None]<hi)
    yy,xx=np.where(kept);box=[max(0,int(xx.min())-2),max(0,int(yy.min())-5),min(w,int(xx.max())+3),min(h,int(yy.max())+6)]
    rgb=np.repeat(a[:,:,None],3,axis=2);rgb[kept]=[255,100,60]
    image=Image.fromarray(rgb).crop((0,max(0,lo-20),w,min(h,hi+20))).resize((640,600))
    image.save(OUT/(r['sample']+'-component.png'))
    return dict(seed=seed,threshold=float(threshold),component_xywh_area=stats[k].tolist(),range_quantile_clip=[.015,.93],range_rows=[lo,hi],retained_component_x_extent=[int(xx.min()),int(xx.max())],bbox=box,column_energy_trimming=False,mask_image=r['sample']+'-component.png')

def main():
    assert not OUT.exists();OUT.mkdir()
    pairs=[p for rec in e.read(CAUSE/'pose_matched_returns/results.json')['records'] for p in rec['pairs']]
    manifests={r['sample']:r for r in e.read(ROOT/'DataSet/paired_visible_reviewed/export/manifest.json')}
    ids=sorted({p['high_sample'] for p in pairs});result=[];e.ZOOM_MODE=True
    examples={'2023-09-21_123841_0329','2023-09-21_124039_0233'}
    for sid in ids:
        r=manifests[sid];review=r['review'];sp=ROOT/'DataSet'/review['review_root']/Path(review['sheet']).with_suffix('.json')
        sheet=e.read(sp);s=next(x for x in sheet['items'] if x['sample']==sid);a=e.arr(r['source'])
        assert e.sha(r['source'])==review['source_sha256'];assert e.sha(sp.with_suffix('.jpg'))==review['sheet_sha256']
        opts=e.body_options(r,a,True);unshuffled=e.body_options(r,a,False)
        exact=opts==s['options'];selected=[k for k,b in opts.items() if b==r['sonar_bbox_xyxy']]
        families=[k for k,b in unshuffled.items() if b==r['sonar_bbox_xyxy']]
        row=dict(sample=sid,raw_sha256=review['source_sha256'],sheet=str(sp),sheet_sha256=e.sha(sp),all_options_exact=exact,selected_letters=selected,unshuffled_families=families,original_bbox=r['sonar_bbox_xyxy'],replayed_options=opts)
        if sid in examples:
            row['mechanism']=mechanism(r,a);assert row['mechanism']['bbox']==r['sonar_bbox_xyxy']
        result.append(row)
    queue=[]
    for sid in ids:
        pp=[p for p in pairs if p['high_sample']==sid]
        flagged=any(p['reference_width_ratio']>1.2 and .95<=p['projected_width_ratio']<=1.05 for p in pp)
        queue.append(dict(sample=sid,original_bbox=manifests[sid]['sonar_bbox_xyxy'],pose_width_screen=flagged,assistant_visual_status='needs_boundary_review' if sid in examples else 'not_reviewed_in_this_audit',eligible_as_geometry_constraint=False if sid in examples else None,corrected_bbox=None,user_accepted=False,reason='Two visually inspected cases include connected horizontal return; other flags are only a screen.' if flagged else 'Retained unscreened control'))
    e.save(OUT/'results.json',dict(frames=result,pair_count=len(pairs),unique_high_frames=len(ids),exact_replays=sum(r['all_options_exact'] for r in result),plan_sha256=e.sha(ROOT/'experiment/sonar-proposal-provenance-plan.md'),script_sha256=e.sha(__file__),proposal_script_sha256=e.sha(ROOT/'tools/expand_paired_visible.py'),seed_script_sha256=e.sha(ROOT/'tools/prepare_sonar_visible_candidates.py'),physical_echo_origin='unresolved'))
    e.save(OUT/'boundary-review-queue.json',dict(items=queue,original_labels_modified=False,automatic_relabeling=False,screen_rule='reference width ratio >1.2 and projected width ratio within [0.95,1.05]; exploratory, no acceptance threshold',screened_count=sum(r['pose_width_screen'] for r in queue)))
    print(json.dumps(dict(pairs=len(pairs),unique_frames=len(ids),exact=sum(r['all_options_exact'] for r in result),screened=sum(r['pose_width_screen'] for r in queue))))

if __name__=='__main__':main()
