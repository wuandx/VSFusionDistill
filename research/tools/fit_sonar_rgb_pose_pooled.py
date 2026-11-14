"""One frozen-library pooling control; no new features or sonar selection."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image,ImageDraw
from prepare_sonar_rgb_pose_pilot import OUT,read,save,sha
from fit_sonar_rgb_pose_pilot import solve

def main():
    folder=OUT/'pooled';assert not folder.exists();folder.mkdir();rows=read(OUT/'selection.json')['samples'];a=read(OUT/'camera-assumptions.json');K=np.array(a['K_960x540']);D=np.array(a['raw_four_coefficients']);results=[];tags=[]
    params=cv2.aruco.DetectorParameters();params.detectInvertedMarker=True;params.cornerRefinementMethod=cv2.aruco.CORNER_REFINE_SUBPIX;det=cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11),params)
    for row in rows:
        sid=row['sample'];query=np.load(OUT/'camera'/(sid+'-features.npz'));prior=read(OUT/'pose'/(sid+'.json'));pool=[]
        for attempt in prior['attempts']:
            if attempt['camera_model']!='pinhole':continue
            ref=np.load(OUT/'render'/row['model']/(attempt['view']+'.npz'))
            for m in attempt['matches']:pool.append(dict(**m,xyz=ref['xyz'][m['reference_index']].tolist(),render_xy=ref['xy'][m['reference_index']].tolist(),view=attempt['view']))
        kept=[]
        for m in sorted(pool,key=lambda x:x['ratio']):
            xy=query['xy'][m['query_index']]
            if any(np.linalg.norm(xy-query['xy'][q['query_index']])<3 for q in kept):continue
            equivalents=[q for q in pool if np.linalg.norm(query['xy'][q['query_index']]-xy)<3];m=dict(m);m['same_image_location_candidates']=len(equivalents);m['support_within_10mm']=int(sum(np.linalg.norm(np.array(q['xyz'])-m['xyz'])<.01 for q in equivalents));m['reference_index']=len(kept);kept.append(m)
        ref=dict(xyz=np.array([m['xyz'] for m in kept]));matches=[{k:m[k] for k in ['reference_index','query_index','ratio']} for m in kept];variants=[]
        for cm in ['pinhole','fisheye']:
            r=solve(ref,query,matches,K,D,cm);r['camera_model']=cm;variants.append(r)
            im=Image.open(OUT/row['image']).convert('RGB');d=ImageDraw.Draw(im)
            for i,m in enumerate(kept):
                p=query['xy'][m['query_index']];col='lime' if i in r.get('inlier_indices',[]) else ('cyan' if i in r.get('check_indices',[]) else 'red');d.ellipse((p[0]-3,p[1]-3,p[0]+3,p[1]+3),outline=col,width=2)
                if r['pose_available']:
                    q=r['predicted_xy'][i];d.line((p[0],p[1],q[0],q[1]),fill=col,width=1)
            d.rectangle((0,0,960,35),fill='white');d.text((6,6),sid+' '+cm+f" matches={len(kept)} fit={r['fit_inliers']} gate={r['rgb_numeric_gate']}",fill='black');path=folder/(sid+'-'+cm+'.jpg');im.save(path,quality=93);r['image']=str(path.relative_to(OUT))
        item=dict(sample=sid,model=row['model'],merged_correspondences=kept,variants=variants,selected_for_sonar_projection=False);save(folder/(sid+'.json'),item);results.append(item)
        image=np.array(Image.open(row['original_fhd']).convert('RGB'));corners,ids,rejected=det.detectMarkers(cv2.cvtColor(image,cv2.COLOR_RGB2GRAY));tag=dict(sample=sid,ids=[] if ids is None else ids.ravel().tolist(),corners_fhd=[x.reshape(4,2).tolist() for x in corners],rejected_count=len(rejected),metric_pose_estimated=False,physical_size_known=False)
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(image,corners,ids);p=folder/(sid+'-tags.jpg');Image.fromarray(image).resize((960,540)).save(p,quality=93);tag['image']=str(p.relative_to(OUT))
        tags.append(tag);print(sid,[(r['camera_model'],r['match_count'],r['fit_inliers'],r.get('check_median_px'),r['rgb_numeric_gate']) for r in variants], 'tags',tag['ids'],flush=True)
    save(folder/'results.json',dict(frames=results,plan_sha256=sha(ROOT/'experiment/sonar-rgb-pose-pooled-plan.md'),script_sha256=sha(__file__),physical_pose_approved=False,sonar_used=False));save(folder/'tag-detections.json',dict(frames=tags,user_has_extra_calibration_data=False,metric_pose_estimated=False))

if __name__=='__main__':main()
