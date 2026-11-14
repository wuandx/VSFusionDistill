"""Frozen temporal sample and tag36h11 observations on allowed reconstructed FHD."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image,ImageDraw
from scipy.spatial.transform import Rotation
from sonar_manual_curation_server import DatasetSource
OUT=ROOT/'DataSet/sonar_tag_continuous_camera';REC='2023-09-21_123500'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')

def main():
    assert not OUT.exists();OUT.mkdir();(OUT/'observations').mkdir();(OUT/'features').mkdir()
    ds=DatasetSource();temporal=read(ds.manifest_path);allrows=sorted([r for r in temporal['items'] if r['recording']==REC],key=lambda r:r['aris_frame']);ids={r['sample'] for i,r in enumerate(allrows) if i%3==0}
    ids.update(r['sample'] for r in allrows if any(abs(r['aris_frame']-a)<=12 for a in [392,788]));ids.update([REC+'_0392',REC+'_0788']);rows=[r for r in allrows if r['sample'] in ids];mm,gg,mp,gp=ds.recording_metadata(REC)
    statics={k:np.array(v) for k,v in read(ds.calibration_path)['versions']['release_current']['parent_from_child_matrices'].items()};selected=[]
    for r in rows:
        ds.require(r['sample']);m=mm[r['aris_frame']];g=gg[r['aris_frame']];T=np.eye(4);T[:3,:3]=statics['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix();T[:3,3]=[float(g[k]) for k in 'xyz'];T[:3,3]+=statics['setup/ar3'][:3,3]
        for key in ['setup/gopro_mounting_hole','setup/gopro_mounting_axis','setup/camera']:T=T@statics[key]
        source=ds.camera_root/r['image'] if r.get('image') else None
        item=dict(sample=r['sample'],aris_frame=r['aris_frame'],aris_time_us=r['aris_time_us'],sd_pts=r.get('sd_pts'),fhd_pts=r.get('fhd_pts'),fhd_index=r.get('fhd_index'),source_path=str(source) if source else None,source_sha256=r.get('image_sha256'),boxes_fhd_xywh=r['boxes_fhd_xywh'],world_from_camera=T.tolist(),status='ready' if source else 'missing_fhd',roles='dense_anchor_window' if any(abs(r['aris_frame']-a)<=12 for a in [392,788]) else 'regular_every3')
        selected.append(item)
    save(OUT/'selection.json',dict(recording=REC,frames=selected,full_manifest_count=len(allrows),sample_rule='every third approved manifest row plus original anchors +-12 ARIS frames',manifest_sha256=ds.manifest_hash,metadata=mp,gantry=gp,calibration_path=str(ds.calibration_path),calibration_sha256=sha(ds.calibration_path),plan_sha256=sha(ROOT/'experiment/sonar-tag-continuous-camera-plan.md')))
    params=cv2.aruco.DetectorParameters();params.detectInvertedMarker=True;params.cornerRefinementMethod=cv2.aruco.CORNER_REFINE_SUBPIX;det=cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11),params);output=[];sift=cv2.SIFT_create(nfeatures=2400,contrastThreshold=.025)
    for r in selected:
        if r['status']!='ready':output.append(dict(sample=r['sample'],status=r['status'],tags=[]));continue
        p=Path(r['source_path']);assert sha(p)==r['source_sha256'];im=np.array(Image.open(p).convert('RGB'));assert im.shape==(1080,1920,3);gray=cv2.cvtColor(im,cv2.COLOR_RGB2GRAY);corners,ids,rejected=det.detectMarkers(gray);tags=[]
        for k,c in zip([] if ids is None else ids.ravel(),corners):
            xy=c.reshape(4,2);area=abs(cv2.contourArea(xy));tags.append(dict(id=int(k),corners=xy.tolist(),area_px2=float(area),minimum_edge_px=float(np.min(np.linalg.norm(xy-np.roll(xy,1,axis=0),axis=1))),border_clearance_px=float(np.min(np.r_[xy.ravel(),1920-xy[:,0],1080-xy[:,1]]))))
        # Mask target/support vicinity, all detected cube faces and their vicinity, borders.
        mask=np.full(gray.shape,255,np.uint8);mask[:20]=0;mask[-20:]=0;mask[:,:20]=0;mask[:,-20:]=0
        for b in r['boxes_fhd_xywh']:
            x,y,w,h=map(int,b);pad=60;mask[max(0,y-pad):min(1080,y+h+pad),max(0,x-pad):min(1920,x+w+pad)]=0
        for t in tags:
            xy=np.array(t['corners']);lo=np.maximum(xy.min(0).astype(int)-55,0);hi=np.minimum(xy.max(0).astype(int)+56,[1920,1080]);mask[lo[1]:hi[1],lo[0]:hi[0]]=0
        # Full-resolution SIFT retains scratched wall/floor features.
        kp,des=sift.detectAndCompute(gray,mask);xy=np.array([k.pt for k in kp],np.float32).reshape(-1,2);np.savez_compressed(OUT/'features'/(r['sample']+'.npz'),xy=xy,des=des if des is not None else np.empty((0,128),np.float32))
        overlay=im.copy()
        if ids is not None:cv2.aruco.drawDetectedMarkers(overlay,corners,ids)
        path=OUT/'observations'/(r['sample']+'.jpg');Image.fromarray(overlay).resize((960,540)).save(path,quality=90)
        output.append(dict(sample=r['sample'],status='detected' if tags else 'none',tags=tags,rejected_count=len(rejected),background_features=len(kp),image=str(path.relative_to(OUT)),source_sha256=r['source_sha256']))
        if len(output)%30==0:print('processed',len(output),'/',len(selected),flush=True)
    save(OUT/'detections.json',dict(frames=output,opencv=cv2.__version__,detector='tag36h11 detectInvertedMarker SUBPIX; same as prior pilot',script_sha256=sha(__file__),selection_sha256=sha(OUT/'selection.json')))
    for j in range(0,len(output),24):
        page=output[j:j+24];sheet=Image.new('RGB',(1600,1200),'white');d=ImageDraw.Draw(sheet)
        for i,r in enumerate(page):
            x=i%4*400;y=i//4*200
            if r.get('image'):sheet.paste(Image.open(OUT/r['image']).resize((356,200)),(x,y))
            d.rectangle((x,y,x+399,y+20),fill='white');d.text((x+3,y+2),r['sample'].split('_')[-1]+' '+str([t['id'] for t in r['tags']]),fill='black')
        sheet.save(OUT/f'overview-{j//24:02d}.jpg',quality=91)
    print(json.dumps(dict(selected=len(selected),ready=sum(r['status']=='ready' for r in selected),tag_positive=sum(bool(r['tags']) for r in output),tag141=sum(any(t['id']==141 for t in r['tags']) for r in output))))

if __name__=='__main__':main()
