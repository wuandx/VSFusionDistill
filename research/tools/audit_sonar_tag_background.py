"""Independent background/tag epipolar diagnostic on frozen temporal frames.

No metric tag size, mesh, sonar label, or time/extrinsic correction is fitted.
Raw-image F needs no K but still only approximates projective geometry under
unknown lens/refraction/image processing. Homography error is never a motion test.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image,ImageDraw
from scipy.spatial.transform import Rotation

BASE=ROOT/'DataSet/sonar_tag_continuous_camera';OUT=BASE/'background'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def angle(R):return float(Rotation.from_matrix(R).magnitude()*180/np.pi)
def summarize(a):
    a=np.asarray(a,dtype=float)
    return None if not len(a) else dict(n=len(a),median=float(np.median(a)),p90=float(np.percentile(a,90)),maximum=float(a.max()))
def errors(F,a,b):
    a=np.c_[a,np.ones(len(a))];b=np.c_[b,np.ones(len(b))]
    la=(F.T@b.T).T;lb=(F@a.T).T;s=np.sum(b*lb,axis=1)
    na=np.maximum(np.sum(la[:,:2]**2,axis=1),1e-15);nb=np.maximum(np.sum(lb[:,:2]**2,axis=1),1e-15)
    return dict(sampson=np.abs(s)/np.sqrt(na+nb),symmetric_rms=np.sqrt(s*s*(1/na+1/nb)/2),first_line=np.abs(s)/np.sqrt(na),second_line=np.abs(s)/np.sqrt(nb))
def coverage(a):
    if len(a)<3:return dict(hull_fraction=0.,span_fraction=[0.,0.])
    hull=abs(cv2.contourArea(cv2.convexHull(np.asarray(a,np.float32))))/(1920*1080)
    return dict(hull_fraction=float(hull),span_fraction=(np.ptp(a,axis=0)/[1920,1080]).tolist())
def matches(a,b):
    if min(len(a['des']),len(b['des']))<2:return np.empty((0,2)),np.empty((0,2)),[]
    bf=cv2.BFMatcher(cv2.NORM_L2);forward=bf.knnMatch(a['des'],b['des'],k=2);back=bf.match(b['des'],a['des']);reverse={m.queryIdx:m.trainIdx for m in back};mm=[]
    for pair in forward:
        if len(pair)!=2:continue
        m,n=pair
        if m.distance<.75*n.distance and reverse.get(m.trainIdx)==m.queryIdx:mm.append((float(m.distance/n.distance),m.queryIdx,m.trainIdx))
    kept=[];aa=[];bb=[]
    for ratio,i,j in sorted(mm):
        x=a['xy'][i];y=b['xy'][j]
        if any(np.linalg.norm(x-p)<3 or np.linalg.norm(y-q)<3 for p,q in zip(aa,bb)):continue
        aa.append(x);bb.append(y);kept.append(dict(first_index=i,second_index=j,ratio=ratio))
    return np.asarray(aa,np.float64).reshape(-1,2),np.asarray(bb,np.float64).reshape(-1,2),kept
def evaluate(a,b,ta,tb,partition=None):
    n=len(a);result=dict(match_count=n,status='insufficient_matches')
    if n<24:return result,None
    if partition is None:
        order=np.lexsort((a[:,1],np.floor(a[:,0]/64)));check=order[::3];checkset=set(check);fit=np.array([i for i in order if i not in checkset])
    else:fit,check=map(lambda a:np.array(a,dtype=int),partition)
    result.update(fit_indices=fit.tolist(),check_indices=check.tolist(),first_points=a.tolist(),second_points=b.tolist())
    if len(fit)<16:return result,None
    cv2.setRNGSeed(20261113);F,mask=cv2.findFundamentalMat(a[fit],b[fit],cv2.USAC_MAGSAC,2.,.999,10000)
    if F is None or F.shape!=(3,3):result['status']='fundamental_fit_failed';return result,None
    inliers=fit[mask.ravel()>0];result.update(status='evaluated',F=F.tolist(),fit_inlier_indices=inliers.tolist(),fit_inlier_count=len(inliers),fit_coverage_first=coverage(a[inliers]),fit_coverage_second=coverage(b[inliers]))
    er=errors(F,a[check],b[check]);tagerr=errors(F,ta,tb);result.update(background_check_errors={k:summarize(v) for k,v in er.items()},tag_errors={k:summarize(v) for k,v in tagerr.items()},tag_sampson_per_corner_px=tagerr['sampson'].tolist(),tag_symmetric_rms_per_corner_px=tagerr['symmetric_rms'].tolist())
    cv2.setRNGSeed(20261113);H,hm=cv2.findHomography(a[fit],b[fit],cv2.USAC_MAGSAC,2.,maxIters=10000,confidence=.999)
    if H is not None:
        hinliers=fit[hm.ravel()>0];homogeneous=np.c_[a,np.ones(n)]@H.T;pred=homogeneous[:,:2]/homogeneous[:,2:];dist=np.linalg.norm(pred-b,axis=1)
        result['homography']=dict(fit_inlier_count=len(hinliers),fit_inlier_fraction=float(len(hinliers)/len(fit)),support_among_F_inliers_fraction=float(np.mean(dist[inliers]<=2)) if len(inliers) else None,check_transfer_px=summarize(dist[check]),note='Support diagnoses possible planar/low-parallax geometry; tag homography residual is not used as a motion test.')
    bg=result['background_check_errors']['sampson'];hfrac=result.get('homography',{}).get('support_among_F_inliers_fraction',1)
    adequate=bool(len(inliers)>=30 and len(check)>=12 and bg['median']<=1.5 and bg['p90']<=3 and min(result['fit_coverage_first']['hull_fraction'],result['fit_coverage_second']['hull_fraction'])>=.03)
    nonplanar=bool(hfrac is not None and hfrac<.85)
    result['screen']=dict(background_validation_adequate=adequate,homography_degeneracy_flag=not nonplanar,nonplanar_screen_passed=adequate and nonplanar,tag_high_epipolar_residual=bool(adequate and nonplanar and np.median(tagerr['sampson'])>max(3.,5*bg['median'])),caveat='Screen is conditional on central/projective approximation and correct correspondences; epipolar agreement cannot rule out motion along epipolar direction.')
    return result,F
def line_segment(line,w=960,h=540):
    aa,bb,cc=line;points=[]
    if abs(bb)>1e-10:
        for x in [0,w-1]:
            y=-(aa*x+cc)/bb
            if 0<=y<h:points.append((x,y))
    if abs(aa)>1e-10:
        for y in [0,h-1]:
            x=-(bb*y+cc)/aa
            if 0<=x<w:points.append((x,y))
    return points[:2]
def draw(pair,result,selection,tags,suffix=''):
    aa,bb=pair['first'],pair['second'];im1=Image.open(selection[aa]['source_path']).convert('RGB').resize((960,540));im2=Image.open(selection[bb]['source_path']).convert('RGB').resize((960,540));canvas=Image.new('RGB',(1920,620),'white');canvas.paste(im1,(0,55));canvas.paste(im2,(960,55));d=ImageDraw.Draw(canvas)
    d.text((8,7),aa+' -> '+bb+' | '+','.join(pair['roles']),fill='black');text=f"matches={result['match_count']} status={result['status']}"
    if result['status']=='evaluated':text+=f"; F inliers={result['fit_inlier_count']}; bg check median={result['background_check_errors']['sampson']['median']:.3f}px tag={result['tag_errors']['sampson']['median']:.3f}px"
    d.text((8,27),text,fill='black')
    for offset,sid in [(0,aa),(960,bb)]:
        pts=np.array(tags[sid])/2
        for j,p in enumerate(pts):d.ellipse((offset+p[0]-4,p[1]+51,offset+p[0]+4,p[1]+59),outline='cyan',width=2);d.text((offset+p[0]+4,p[1]+55),str(j),fill='cyan')
    if result['status']=='evaluated':
        F=np.array(result['F']);a=np.array(result['first_points']);b=np.array(result['second_points']);fitset=set(result['fit_inlier_indices'])
        for i in list(result['fit_inlier_indices'])[::max(1,len(fitset)//40)]:
            p=a[i]/2;q=b[i]/2;d.line((p[0],p[1]+55,q[0]+960,q[1]+55),fill='#60ca50',width=1)
        ta=np.c_[np.array(tags[aa]),np.ones(4)];lines=ta@F.T
        for line in lines:
            seg=line_segment(np.array([line[0]*2,line[1]*2,line[2]]))
            if len(seg)==2:d.line((960+seg[0][0],55+seg[0][1],960+seg[1][0],55+seg[1][1]),fill='#ff7070',width=2)
    d.text((8,602),'Cyan: tag141 corners. Green: selected background F inliers. Red: tag epipolar lines on second image. Raw distortion is uncorrected.',fill='black');p=OUT/'qa'/(aa+'--'+bb+suffix+'.jpg');canvas.save(p,quality=92);return str(p.relative_to(OUT))
def anchor_models(a,b,ta,tb,expected):
    assumptions=read(ROOT/'DataSet/sonar_rgb_pose_pilot/camera-assumptions.json');K=np.array(assumptions['K_960x540']);K[:2]*=2
    histK=np.array([[397.77105952,0.,323.01645778],[0.,393.9965825,181.94773453],[0.,0.,1.]]);histK[:2]*=3;histD=np.array([.22602159,.34004099,-.39509882,.66812696]);models=[]
    for name,kk,dd in [('current_linear_K_pinhole',K,None),('historical_wide_fisheye_SD_times3',histK,histD)]:
        def und(p):return p if dd is None else cv2.fisheye.undistortPoints(p.reshape(-1,1,2),kk,dd.reshape(4,1),P=kk).reshape(-1,2)
        x,y,u,v=map(und,[a,b,ta,tb]);ev,F=evaluate(x,y,u,v);entry=dict(model=name,K=kk.tolist(),D=None if dd is None else dd.tolist(),F_control=ev,essential_rotation_estimated=False)
        if ev.get('screen',{}).get('nonplanar_screen_passed'):
            fit=np.array(ev['fit_indices']);cv2.setRNGSeed(20261113);E,mask=cv2.findEssentialMat(x[fit],y[fit],kk,cv2.USAC_MAGSAC,.999,2.,10000)
            if E is not None and E.shape==(3,3):
                n,R,t,posemask=cv2.recoverPose(E,x[fit],y[fit],kk,mask=mask);entry['essential_rotation_estimated']=True;entry['essential']=dict(cheirality_inliers=int(n),rotation=R.tolist(),rotation_deg=angle(R),difference_from_released_pose_deg=angle(R@expected.T),note='Conditional background visual relative rotation, not a new physical calibration.')
        models.append(entry)
    return models

def distortion_controls():
    path=OUT/'distortion-controls.json';assert not path.exists();baseline=read(OUT/'results.json');detection=read(BASE/'detections.json');tags={r['sample']:np.array(next(t['corners'] for t in r['tags'] if t['id']==141)) for r in detection['frames'] if any(t['id']==141 for t in r['tags'])}
    assumptions=read(ROOT/'DataSet/sonar_rgb_pose_pilot/camera-assumptions.json');K=np.array(assumptions['K_960x540']);K[:2]*=2;D=np.array(assumptions['raw_four_coefficients']);histK=np.array([[397.77105952,0.,323.01645778],[0.,393.9965825,181.94773453],[0.,0.,1.]]);histK[:2]*=3;histD=np.array([.22602159,.34004099,-.39509882,.66812696]);results=[]
    for name,kk,dd in [('historical_wide_fisheye_SD_times3',histK,histD),('prior_linear_four_fisheye',K,D)]:
        pp=[]
        def und(a):return cv2.fisheye.undistortPoints(np.array(a).reshape(-1,1,2),kk,dd.reshape(4,1),P=kk).reshape(-1,2)
        for r in baseline['pairs']:
            item={k:r[k] for k in ['first','second','roles','match_count','aris_frame_gap','fhd_pts_gap_s']}
            if r['status']!='evaluated':item['control']=dict(status=r['status'],reason='same insufficient frozen correspondences as baseline');pp.append(item);continue
            a,b,ta,tb=map(und,[r['first_points'],r['second_points'],tags[r['first']],tags[r['second']]])
            control,F=evaluate(a,b,ta,tb,partition=(r['fit_indices'],r['check_indices']))
            # Point membership follows the raw fixed spatial partition, not the altered undistorted x order.
            if control.get('fit_indices')!=r['fit_indices']:
                control['partition_changed_under_undistortion']=True
            else:control['partition_changed_under_undistortion']=False
            item['control']=control;pp.append(item)
        ee=[r['control'] for r in pp if r['control']['status']=='evaluated'];nn=[r for r in ee if r['screen']['nonplanar_screen_passed']];hh=[r for r in ee if r['screen']['tag_high_epipolar_residual']]
        summary=dict(total_pairs=len(pp),evaluated=len(ee),background_validation_adequate=sum(r['screen']['background_validation_adequate'] for r in ee),nonplanar_screen_passed=len(nn),conditional_tag_high_epipolar_residual=len(hh),all_evaluated_tag_median_sampson_px=summarize([r['tag_errors']['sampson']['median'] for r in ee]),nonplanar_tag_median_sampson_px=summarize([r['tag_errors']['sampson']['median'] for r in nn]),nonplanar_bg_check_median_sampson_px=summarize([r['background_check_errors']['sampson']['median'] for r in nn]),partition_changes=sum(r.get('partition_changed_under_undistortion',False) for r in ee))
        results.append(dict(model=name,K=kk.tolist(),D=dd.tolist(),summary=summary,pairs=pp));print(name,json.dumps(summary),flush=True)
    save(path,dict(models=results,baseline_results_sha256=sha(OUT/'results.json'),source_detections_sha256=sha(BASE/'detections.json'),script_sha256=sha(__file__),note='Same frozen correspondence sets; camera model hypotheses only. No tag motion or stillness certified.'))

def quality_audit():
    path=OUT/'quality-audit.json';assert not path.exists();baseline=read(OUT/'results.json');controls=read(OUT/'distortion-controls.json');selection={r['sample']:r for r in read(BASE/'selection.json')['frames']};detection=read(BASE/'detections.json');tags={r['sample']:np.array(next(t['corners'] for t in r['tags'] if t['id']==141)) for r in detection['frames'] if any(t['id']==141 for t in r['tags'])};allmodels=[dict(model='raw_uncorrected',pairs=[dict(first=r['first'],second=r['second'],control=r) for r in baseline['pairs']])]+controls['models'];histK=np.array([[397.77105952,0.,323.01645778],[0.,393.9965825,181.94773453],[0.,0.,1.]]);histK[:2]*=3;histD=np.array([.22602159,.34004099,-.39509882,.66812696]);modelresults=[];raw={(r['first'],r['second']):r for r in baseline['pairs']}
    for model in allmodels:
        name=model['model'];records=[]
        for item in model['pairs']:
            r=item['control']
            if r.get('status')!='evaluated':continue
            key=(item['first'],item['second']);original=raw[key];ta,tb=tags[key[0]],tags[key[1]]
            if name!='raw_uncorrected':
                kk=np.array(model['K']);dd=np.array(model['D']);ta,tb=[cv2.fisheye.undistortPoints(p.reshape(-1,1,2),kk,dd.reshape(4,1),P=kk).reshape(-1,2) for p in [ta,tb]]
            a=np.array(r['first_points']);b=np.array(r['second_points']);ii=np.array(r['fit_inlier_indices']);hulla=cv2.convexHull(a[ii].astype(np.float32));hullb=cv2.convexHull(b[ii].astype(np.float32));inside=[cv2.pointPolygonTest(hulla,tuple(p),False)>=0 for p in ta]+[cv2.pointPolygonTest(hullb,tuple(p),False)>=0 for p in tb];local=[int(np.sum(np.linalg.norm(points-corners.mean(0),axis=1)<=300)) for points,corners in [(a[ii],ta),(b[ii],tb)]]
            row=dict(first=key[0],second=key[1],tag_all_corners_inside_background_inlier_hulls=bool(all(inside)),tag_corner_hull_membership=inside,background_inliers_within300px_of_tag_center=local,original_nonplanar_screen=r['screen']['nonplanar_screen_passed'],original_high_tag_residual=r['screen']['tag_high_epipolar_residual'])
            if r['screen']['nonplanar_screen_passed']:
                fit=np.array(r['fit_indices']);check=np.array(r['check_indices']);rng=np.random.default_rng(20261113);measurements=[];failures=[]
                for trial in range(12):
                    chosen=rng.choice(fit,max(16,round(len(fit)*.75)),replace=False);cv2.setRNGSeed(20261113+trial)
                    try:F,mask=cv2.findFundamentalMat(a[chosen],b[chosen],cv2.USAC_MAGSAC,2.,.999,10000)
                    except cv2.error as ex:failures.append(dict(trial=trial,error=str(ex)));continue
                    if F is None or F.shape!=(3,3):continue
                    measurements.append(dict(tag_median_sampson_px=float(np.median(errors(F,ta,tb)['sampson'])),background_check_median_px=float(np.median(errors(F,a[check],b[check])['sampson'])),background_check_p90_px=float(np.percentile(errors(F,a[check],b[check])['sampson'],90))))
                adequate=[m for m in measurements if m['background_check_median_px']<=1.5 and m['background_check_p90_px']<=3]
                row['fit_subsample_audit']=dict(trials=12,valid_fits=len(measurements),background_validated_trials=len(adequate),tag_median_sampson_p5_p50_p95_px=np.percentile([m['tag_median_sampson_px'] for m in adequate],[5,50,95]).tolist() if adequate else None,trials_data=measurements,failures=failures,all_adequate_trials_tag_above3px=bool(len(adequate)>=8 and all(m['tag_median_sampson_px']>3 for m in adequate)))
            if name=='raw_uncorrected' and r['screen']['tag_high_epipolar_residual']:
                row['posthoc_high_residual_visual']=draw(dict(first=key[0],second=key[1],roles=['posthoc_high_residual_diagnostic']),r,selection,tags,suffix='-posthoc-high')
            records.append(row)
        modelresults.append(dict(model=name,pairs=records,summary=dict(evaluated=len(records),tag_all_corners_inside_hulls=sum(r['tag_all_corners_inside_background_inlier_hulls'] for r in records),nonplanar_and_tag_inside_hulls=sum(r['original_nonplanar_screen'] and r['tag_all_corners_inside_background_inlier_hulls'] for r in records),nonplanar_subsample_tag_above3_all_adequate=sum(r.get('fit_subsample_audit',{}).get('all_adequate_trials_tag_above3px',False) for r in records))))
        print(name,modelresults[-1]['summary'],flush=True)
    save(path,dict(models=modelresults,baseline_sha256=sha(OUT/'results.json'),distortion_controls_sha256=sha(OUT/'distortion-controls.json'),script_sha256=sha(__file__),scope='Posthoc geometry quality audit of existing fits, not changed main thresholds; 12 fixed 75% fit subsamples only on original nonplanar-screen pairs.',physical_motion_proven=False))

def main():
    assert not OUT.exists();OUT.mkdir();(OUT/'qa').mkdir();sel=read(BASE/'selection.json');selection={r['sample']:r for r in sel['frames']};det=read(BASE/'detections.json');tags={r['sample']:np.array(next(t['corners'] for t in r['tags'] if t['id']==141)) for r in det['frames'] if any(t['id']==141 for t in r['tags'])};selected=[r['sample'] for r in sel['frames']];eligible=[s for s in selected if s in tags];pairs={}
    def add(a,b,role):
        key=(a,b)
        if key not in pairs:pairs[key]=dict(first=a,second=b,roles=[],aris_frame_gap=selection[b]['aris_frame']-selection[a]['aris_frame'],fhd_pts_gap_s=selection[b]['fhd_pts']-selection[a]['fhd_pts'])
        pairs[key]['roles'].append(role)
    for a,b in zip(selected[:-1],selected[1:]):
        if a in tags and b in tags:add(a,b,'adjacent_selected')
    for i in range(0,len(eligible),10):
        for lag in [10,30]:
            if i+lag<len(eligible):add(eligible[i],eligible[i+lag],f'eligible_lag{lag}')
    anchors=['2023-09-21_123500_0392','2023-09-21_123500_0788'];assert all(s in tags for s in anchors);add(*anchors,'original_anchor_pair');ordered=list(pairs.values());save(OUT/'pairs.json',dict(pairs=ordered,selection_sha256=sha(BASE/'selection.json'),detection_sha256=sha(BASE/'detections.json'),rule='adjacent selected frames where both tag141; every tenth eligible first frame -> eligible +10,+30; original392/788'))
    # Fixed visual examples are selected before model fitting.
    qa=set();neighbours=[p for p in ordered if 'adjacent_selected' in p['roles']];longs=[p for p in ordered if len(p['roles'])>1 or any('lag' in r for r in p['roles'])]
    for collection in [neighbours,longs]:
        if collection:
            for i in np.linspace(0,len(collection)-1,min(7,len(collection))).round().astype(int):qa.add((collection[i]['first'],collection[i]['second']))
    qa.add(tuple(anchors));features={};results=[]
    for i,pair in enumerate(ordered):
        aa,bb=pair['first'],pair['second']
        for sid in [aa,bb]:
            if sid not in features:features[sid]=np.load(BASE/'features'/(sid+'.npz'))
        a,b,mm=matches(features[aa],features[bb]);r,F=evaluate(a,b,tags[aa],tags[bb]);r.update(pair);r['matches']=mm
        if (aa,bb) in qa:r['image']=draw(pair,r,selection,tags)
        if [aa,bb]==anchors:
            expected=np.array(selection[bb]['world_from_camera'])[:3,:3].T@np.array(selection[aa]['world_from_camera'])[:3,:3];r['anchor_camera_controls']=anchor_models(a,b,tags[aa],tags[bb],expected)
        results.append(r)
        if (i+1)%25==0:print('background pairs',i+1,'/',len(ordered),flush=True)
    evaluated=[r for r in results if r['status']=='evaluated'];adequate=[r for r in evaluated if r['screen']['background_validation_adequate']];nonplanar=[r for r in evaluated if r['screen']['nonplanar_screen_passed']];high=[r for r in evaluated if r['screen']['tag_high_epipolar_residual']]
    summary=dict(total_pairs=len(results),evaluated=len(evaluated),background_validation_adequate=len(adequate),nonplanar_screen_passed=len(nonplanar),conditional_tag_high_epipolar_residual=len(high),all_evaluated_tag_median_sampson_px=summarize([r['tag_errors']['sampson']['median'] for r in evaluated]),nonplanar_tag_median_sampson_px=summarize([r['tag_errors']['sampson']['median'] for r in nonplanar]),nonplanar_bg_check_median_sampson_px=summarize([r['background_check_errors']['sampson']['median'] for r in nonplanar]),physical_tag_motion_proven=False,tag_stillness_certified=False,reason='Raw F agreement only checks conditional projective epipolar compatibility; unknown lens and planar/low-parallax degeneracy remain. No homography-tag test is used.')
    save(OUT/'results.json',dict(summary=summary,pairs=results,script_sha256=sha(__file__),plan_sha256=sha(ROOT/'experiment/sonar-tag-continuous-camera-plan.md'),pairs_sha256=sha(OUT/'pairs.json'),input_feature_hashes={sid:sha(BASE/'features'/(sid+'.npz')) for sid in features},source_selection_sha256=sha(BASE/'selection.json'),source_detections_sha256=sha(BASE/'detections.json')))
    cards=['<!doctype html><meta charset="utf-8"><title>Background/tag rigidity diagnostic</title><style>body{font:16px system-ui;margin:24px}img{width:100%;max-width:1920px}</style><h1>Background/tag141 epipolar diagnostic</h1><p>Fixed temporal pairs. A tag homography residual is not a motion test; raw F still assumes approximately projective imaging. Low parallax/planar backgrounds are flagged, and agreement does not certify tag stillness.</p><a href="results.json">All pair results</a><pre>'+json.dumps(summary,indent=2)+'</pre>']
    for r in results:
        if r.get('image'):cards.append('<h3>'+r['first']+' -> '+r['second']+'</h3><img src="'+r['image']+'">')
    (OUT/'index.html').write_text(''.join(cards),'utf-8');print(json.dumps(summary,indent=2))

if __name__=='__main__':
    if '--quality-audit' in sys.argv:quality_audit()
    elif '--distortion-controls' in sys.argv:distortion_controls()
    else:main()
