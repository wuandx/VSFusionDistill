"""RGB-only correspondence/PnP pilot with held-out 2D locations and synthetic control."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image,ImageDraw
from scipy.spatial.transform import Rotation
from prepare_sonar_rgb_pose_pilot import OUT,read,save,sha,view_pose,render,gray_features

def match(reference,query):
    a=reference['descriptors'];b=query['descriptors']
    if len(a)<2 or len(b)<2:return []
    bf=cv2.BFMatcher(cv2.NORM_L2);forward=bf.knnMatch(a,b,k=2);back=bf.match(b,a);mutual={m.queryIdx:m.trainIdx for m in back};matches=[]
    for pair in forward:
        if len(pair)!=2:continue
        m,n=pair
        if m.distance<.75*n.distance and mutual.get(m.trainIdx)==m.queryIdx:matches.append(dict(reference_index=m.queryIdx,query_index=m.trainIdx,ratio=float(m.distance/n.distance)))
    # SIFT can have duplicate orientations at the same point; do not count them twice.
    kept=[];xy=[]
    for m in sorted(matches,key=lambda m:m['ratio']):
        p=query['xy'][m['query_index']]
        if not xy or min(np.linalg.norm(p-q) for q in xy)>=3:kept.append(m);xy.append(p)
    return kept

def solve(reference,query,matches,K,D,model):
    result=dict(matches=matches,match_count=len(matches),fit_inliers=0,pose_available=False,rgb_numeric_gate=False)
    if len(matches)<12:result['reason']='fewer than 12 unique correspondences for 8 fit / 4 check';return result
    xyz=np.array([reference['xyz'][m['reference_index']] for m in matches],np.float64);xy=np.array([query['xy'][m['query_index']] for m in matches],np.float64)
    # Deterministic spatial order, every third point withheld before RANSAC.
    order=np.lexsort((xy[:,1],np.floor(xy[:,0]/48)));check=order[::3];fit=np.array([i for i in order if i not in set(check)]);norm=xy
    if model=='fisheye':norm=cv2.fisheye.undistortPoints(xy.reshape(-1,1,2),K,D.reshape(4,1),P=K).reshape(-1,2)
    cv2.setRNGSeed(20261113)
    ok,rv,tv,inliers=cv2.solvePnPRansac(xyz[fit],norm[fit],K,None,iterationsCount=3000,reprojectionError=3,confidence=.999,flags=cv2.SOLVEPNP_EPNP)
    result.update(fit_indices=fit.tolist(),check_indices=check.tolist(),xyz=xyz.tolist(),xy=xy.tolist())
    if not ok or inliers is None:result['reason']='RANSAC no pose';return result
    ii=fit[inliers.ravel()];result['fit_inliers']=len(ii)
    if len(ii)<6:result['reason']='insufficient RANSAC inliers';return result
    rv,tv=cv2.solvePnPRefineLM(xyz[ii],norm[ii],K,None,rv,tv);R=cv2.Rodrigues(rv)[0];T=np.eye(4);T[:3,:3]=R;T[:3,3]=tv.ravel()
    if model=='fisheye':pred=cv2.fisheye.projectPoints(xyz.reshape(-1,1,3),rv,tv,K,D.reshape(4,1))[0].reshape(-1,2)
    else:pred=cv2.projectPoints(xyz,rv,tv,K,None)[0].reshape(-1,2)
    err=np.linalg.norm(pred-xy,axis=1);depth=(xyz@R.T+tv.ravel())[:,2];checkerr=err[check];span=xyz[ii].max(0)-xyz[ii].min(0);singular=np.linalg.svd(xyz[ii]-xyz[ii].mean(0),compute_uv=False)
    result.update(pose_available=True,camera_from_model=T.tolist(),inlier_indices=ii.tolist(),predicted_xy=pred.tolist(),errors_px=err.tolist(),fit_median_px=float(np.median(err[ii])),check_median_px=float(np.median(checkerr)),check_p90_px=float(np.percentile(checkerr,90)),check_within3px=int((checkerr<=3).sum()),positive_depth=bool((depth>0).all()),inlier_xyz_span_m=span.tolist(),inlier_xyz_singular_values=singular.tolist(),inlier_xy_span_px=np.ptp(xy[ii],axis=0).tolist())
    result['rgb_numeric_gate']=bool(len(ii)>=8 and (checkerr<=3).sum()>=4 and np.median(checkerr)<=3 and np.percentile(checkerr,90)<=6 and (depth>0).all())
    result['reason']='numeric gate only; coverage and actual correspondence review still required' if result['rgb_numeric_gate'] else 'held-out reprojection or inlier gate failed'
    return result

def draw(name,im,reference_im,reference,query,result,path):
    canvas=Image.new('RGB',(1536,640),'white');canvas.paste(Image.fromarray(reference_im),(0,60));canvas.paste(Image.fromarray(im),(560,60));d=ImageDraw.Draw(canvas)
    d.text((8,8),name,fill='black');d.text((8,26),f"matches={result['match_count']}; fit inliers={result['fit_inliers']}; numeric gate={result['rgb_numeric_gate']}",fill='black')
    for i,m in enumerate(result['matches']):
        a=reference['xy'][m['reference_index']];b=query['xy'][m['query_index']];color='red'
        if i in result.get('inlier_indices',[]):color='lime'
        if i in result.get('check_indices',[]):color='cyan'
        d.line((a[0],a[1]+60,b[0]+560,b[1]+60),fill=color,width=1);d.ellipse((b[0]+558,b[1]+58,b[0]+562,b[1]+62),outline=color,width=1)
    d.text((8,615),'Reference textured surface / actual RGB. Green: RANSAC fit; cyan: withheld points; red: other or insufficient matches.',fill='black');canvas.save(path,quality=93)

def run_query(sid,model,im,query,K,D,views,folder,synthetic=False,truth=None):
    attempts=[];cache={};variants=['pinhole'] if synthetic else ['pinhole','fisheye']
    for view in views:
        if view['model']!=model:continue
        reference=np.load(OUT/view['path']);matches=match(reference,query);cache[view['view']]=(reference,matches,view)
        for camera_model in variants:
            r=solve(reference,query,matches,K,D,camera_model);r.update(view=view['view'],camera_model=camera_model);attempts.append(r)
    chosen=[]
    for cm in variants:
        # check values are expressly excluded from selection.
        rr=[r for r in attempts if r['camera_model']==cm];best=max(rr,key=lambda r:(r['fit_inliers'],-r.get('fit_median_px',1e6),r['match_count']))
        ref,matches,v=cache[best['view']];pic=np.array(Image.open(OUT/v['image']));name=sid+'-'+cm;draw(name,im,pic,ref,query,best,folder/(name+'.jpg'));best=dict(best);best['image']=str((folder/(name+'.jpg')).relative_to(OUT))
        if truth is not None and best['pose_available']:
            T=np.array(best['camera_from_model']);best['truth_rotation_error_deg']=float(Rotation.from_matrix(T[:3,:3]@truth[:3,:3].T).magnitude()*180/np.pi);best['truth_translation_error_m']=float(np.linalg.norm(T[:3,3]-truth[:3,3]))
        chosen.append(best)
    save(folder/(sid+'.json'),dict(sample=sid,model=model,selection='max fit inliers then min fit median; no check or sonar used',attempts=attempts,chosen=chosen,synthetic=synthetic))
    print(sid,[(r['camera_model'],r['match_count'],r['fit_inliers'],r.get('check_median_px'),r['rgb_numeric_gate']) for r in chosen],flush=True)
    return dict(sample=sid,model=model,chosen=chosen,synthetic=synthetic)

def main():
    folder=OUT/'pose';assert not folder.exists();folder.mkdir();syntheticfolder=folder/'synthetic';syntheticfolder.mkdir();views=read(OUT/'views.json');assumptions=read(OUT/'camera-assumptions.json');K=np.array(assumptions['K_960x540']);D=np.array(assumptions['raw_four_coefficients']);synthetics=[]
    for model in ['mortar_shell','incindiary']:
        surface=np.load(OUT/'render'/model/'surface.npz');info=read(OUT/'render'/model/'provenance.json');T=view_pose(85,15,info['nominal_length_m']*2.1);im,mapping,mask=render(surface['xyz'],surface['colors'],T);im=np.clip(im.astype(float)*[.8,1.,.9],0,255).astype('uint8');kp,des=gray_features(im,cv2.erode(mask,np.ones((5,5),np.uint8)));query=dict(xy=np.array([k.pt for k in kp],np.float32),descriptors=des)
        sk=np.array([[650.,0,256],[0,650.,256],[0,0,1.]])
        synthetics.append(run_query('synthetic-'+model,model,im,query,sk,np.zeros(4),views,syntheticfolder,True,T))
    results=[]
    for r in read(OUT/'selection.json')['samples']:
        query=np.load(OUT/'camera'/(r['sample']+'-features.npz'));im=np.array(Image.open(OUT/r['image']));results.append(run_query(r['sample'],r['model'],im,query,K,D,views,folder))
    save(folder/'results.json',dict(frames=results,synthetic_controls=synthetics,source_selection_sha256=sha(OUT/'selection.json'),views_sha256=sha(OUT/'views.json'),camera_assumptions_sha256=sha(OUT/'camera-assumptions.json'),script_sha256=sha(__file__),physical_registration_validated=False,sonar_images_used_in_pose_fitting=False))

if __name__=='__main__':main()
