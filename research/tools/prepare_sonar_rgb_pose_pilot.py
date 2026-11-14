"""Frozen RGB-only feature preparation from photogrammetric texture and surface."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import sys,json,hashlib,re
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image,ImageDraw
OUT=ROOT/'DataSet/sonar_rgb_pose_pilot';BASE=ROOT/'DataSet/sonar_box_guided_full_trajectory'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def writeim(p,a):Image.fromarray(a).save(p)

def mesh(info):
    vv=[];uv=[];faces=[];texfaces=[]
    for line in Path(info['source']).read_text('utf-8').splitlines():
        s=line.split()
        if not s:continue
        if s[0]=='v':vv.append(list(map(float,s[1:4])))
        elif s[0]=='vt':uv.append(list(map(float,s[1:3])))
        elif s[0]=='f':
            tokens=[x.split('/') for x in s[1:]]
            for j in range(1,len(tokens)-1):
                tri=[tokens[k] for k in [0,j,j+1]];faces.append([int(t[0])-1 for t in tri]);texfaces.append([int(t[1])-1 for t in tri])
    vv=np.array(vv);uv=np.array(uv);faces=np.array(faces);texfaces=np.array(texfaces);S=np.array(info['mesh_to_target_similarity']);vv=vv@S[:3,:3].T+S[:3,3]
    return vv,uv,faces,texfaces

def surface(info):
    vv,uv,f,ft=mesh(info);tri=vv[f];areas=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    rng=np.random.default_rng(20261113);ids=np.searchsorted(np.cumsum(areas),(np.arange(900000)+.5)/900000*areas.sum());rr=rng.random((len(ids),2));r=np.sqrt(rr[:,0]);weights=np.c_[1-r,r*(1-rr[:,1]),r*rr[:,1]]
    xyz=np.einsum('ni,nij->nj',weights,tri[ids]);coords=np.einsum('ni,nij->nj',weights,uv[ft[ids]])
    texture=Path(info['source']).with_suffix('.jpg');im=np.array(Image.open(texture).convert('RGB'));h,w=im.shape[:2]
    # OBJ UV v increases upwards; image rows increase downwards.
    tx=np.clip(coords[:,0]*(w-1),0,w-1);ty=np.clip((1-coords[:,1])*(h-1),0,h-1)
    x=tx.astype(int);y=ty.astype(int);dx=(tx-x)[:,None];dy=(ty-y)[:,None]
    colors=(im[y,x]*(1-dx)*(1-dy)+im[y,np.minimum(x+1,w-1)]*dx*(1-dy)+im[np.minimum(y+1,h-1),x]*(1-dx)*dy+im[np.minimum(y+1,h-1),np.minimum(x+1,w-1)]*dx*dy).astype(np.uint8)
    return xyz.astype(np.float32),colors,dict(source=info['source'],obj_sha256=sha(info['source']),texture=str(texture),texture_sha256=sha(texture),texture_size=[w,h],surface_samples=len(xyz),sample_seed=20261113,texture_mapping='explicit same-stem jpg; OBJ/MTL old names preserved; v flipped',model_similarity=info['mesh_to_target_similarity'],nominal_length_m=info['nominal_length_m'])

def view_pose(alpha,phi,distance):
    a,p=np.radians([alpha,phi]);direction=np.array([np.cos(a),np.sin(a)*np.cos(p),np.sin(a)*np.sin(p)]);eye=direction*distance
    z=-direction;x=np.cross(z,[0,0,1.]);x/=np.linalg.norm(x);y=np.cross(z,x);R=np.vstack([x,y,z]);T=np.eye(4);T[:3,:3]=R;T[:3,3]=-R@eye
    return T

def render(xyz,colors,T,size=512,focal=650):
    p=xyz@T[:3,:3].T+T[:3,3];uv=p[:,:2]/p[:,2:]*focal+size/2;xy=np.rint(uv).astype(int);valid=(xy>=0).all(1)&(xy<size).all(1)&(p[:,2]>0);ids=np.where(valid)[0];idx=xy[valid,1]*size+xy[valid,0]
    # Lexicographic pixel then depth ordering: front sample at each occupied pixel.
    order=np.lexsort((p[ids,2],idx));idx=idx[order];ids=ids[order];first=np.r_[True,idx[1:]!=idx[:-1]];idx=idx[first];ids=ids[first]
    im=np.full((size*size,3),24,np.uint8);mapping=np.full(size*size,-1,np.int32);im[idx]=colors[ids];mapping[idx]=ids
    im=im.reshape(size,size,3);mapping=mapping.reshape(size,size);mask=(mapping>=0).astype(np.uint8)*255
    return im,mapping,mask

def gray_features(im,mask=None):
    gray=cv2.cvtColor(im,cv2.COLOR_RGB2GRAY);gray=cv2.createCLAHE(clipLimit=2,tileGridSize=(8,8)).apply(gray)
    return cv2.SIFT_create(nfeatures=1800,contrastThreshold=.015,edgeThreshold=12).detectAndCompute(gray,mask)

def main():
    assert not OUT.exists();OUT.mkdir();(OUT/'camera').mkdir();(OUT/'render').mkdir()
    rows=read(BASE/'results.json')['frames'];temporal={r['sample']:r for r in read(ROOT/'DataSet/camera_temporal_all/manifest-resolved.json')['items']};selection=[];excluded=[]
    for model,rec in [('mortar_shell','2023-09-21_103728'),('incindiary','2023-09-21_123500')]:
        rr=sorted([r for r in rows if r['recording']==rec and r['role']=='same_recording_check'],key=lambda r:r['sample']);eligible=[r for r in rr if temporal[r['sample']].get('image')]
        excluded.extend(r['sample'] for r in rr if not temporal[r['sample']].get('image'))
        for i in [0,len(eligible)//2,len(eligible)-1]:
            r=eligible[i];sid=r['sample'];t=temporal[sid];path=ROOT/'DataSet/camera_temporal_all'/t['image'];assert sha(path)==t['image_sha256'];im=Image.open(path).convert('RGB');assert im.size==(1920,1080);small=np.array(im.resize((960,540),Image.Resampling.LANCZOS));writeim(OUT/'camera'/f'{sid}.png',small)
            label=read(ROOT/'DataSet/camera_temporal_all'/t['label_copy']);b=np.array([label[k] for k in ['x_min','y_min','x_max','y_max']])*1.5;b=np.r_[np.maximum(b[:2]-10,[0,0]),np.minimum(b[2:]+10,[960,540])].astype(int)
            mask=np.zeros((540,960),np.uint8);mask[b[1]:b[3],b[0]:b[2]]=255;kps,des=gray_features(small,mask);points=np.array([k.pt for k in kps],dtype=np.float32).reshape(-1,2);np.savez_compressed(OUT/'camera'/f'{sid}-features.npz',xy=points,descriptors=des if des is not None else np.empty((0,128),np.float32))
            selection.append(dict(sample=sid,model=model,recording=rec,image='camera/'+sid+'.png',feature_count=len(kps),roi_bbox=b.tolist(),original_fhd=str(path),fhd_sha256=sha(path),sd=r['provenance']['camera'],source_label=str(ROOT/'DataSet/camera_temporal_all'/t['label_copy']),label_sha256=sha(ROOT/'DataSet/camera_temporal_all'/t['label_copy']),precision_sync_certified=False))
    save(OUT/'selection.json',dict(samples=selection,excluded_missing_rebuilt_fhd=excluded,rule='first/middle/last with rebuilt FHD from old same_recording_check; chosen before matching',source_results_sha256=sha(BASE/'results.json'),temporal_manifest_sha256=sha(ROOT/'DataSet/camera_temporal_all/manifest-resolved.json')))
    p=ROOT/'related_work/sonar-projection-audit-assets/data_export_calibration/calibration/camera_parameters/camera_parameter_linear.txt';s=p.read_text();K=np.array([float(x) for x in re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?',s.split('distortion')[0])]).reshape(3,3);K[:2]/=2;D=[float(x) for x in re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?',s.split('distortion')[1])]
    save(OUT/'camera-assumptions.json',dict(K_960x540=K.tolist(),raw_four_coefficients=D,source=str(p),sha256=sha(p),hypotheses=['linear_K_pinhole_zero_distortion','linear_K_four_coefficient_fisheye'],actual_capture_lens_mode_confirmed=False,source_distortion_model_confirmed=False,scaling_assumes_original_calibration_1920x1080=True))
    registry=read(ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json')['models'];allviews=[]
    for model in ['mortar_shell','incindiary']:
        folder=OUT/'render'/model;folder.mkdir();xyz,colors,provenance=surface(registry[model]);np.savez_compressed(folder/'surface.npz',xyz=xyz,colors=colors);save(folder/'provenance.json',provenance)
        previews=[]
        for alpha in [30,60,90,120]:
            for phi in range(0,360,30):
                name=f'a{alpha:03d}-p{phi:03d}';T=view_pose(alpha,phi,registry[model]['nominal_length_m']*2);im,mapping,mask=render(xyz,colors,T)
                # Guard SIFT centers from background and empty pixels.
                feature_mask=cv2.erode(mask,np.ones((5,5),np.uint8));kp,des=gray_features(im,feature_mask);ids=np.array([mapping[round(k.pt[1]),round(k.pt[0])] for k in kp],dtype=int);valid=ids>=0
                if len(ids):xy=np.array([k.pt for k in kp],np.float32)[valid];desc=des[valid];positions=xyz[ids[valid]]
                else:xy=np.empty((0,2),np.float32);desc=np.empty((0,128),np.float32);positions=np.empty((0,3),np.float32)
                np.savez_compressed(folder/(name+'.npz'),xy=xy,xyz=positions,descriptors=desc,camera_from_model=T);writeim(folder/(name+'.png'),im)
                entry=dict(model=model,view=name,alpha=alpha,phi=phi,features=len(xy),path=f'render/{model}/{name}.npz',image=f'render/{model}/{name}.png');allviews.append(entry)
                canvas=Image.fromarray(im).resize((256,256));d=ImageDraw.Draw(canvas);d.text((4,4),name+f' {len(xy)}',fill='white');previews.append(canvas)
            print(model,'alpha',alpha,'done',flush=True)
        sheet=Image.new('RGB',(1536,2048),'white')
        for j,im in enumerate(previews):sheet.paste(im,((j%6)*256,(j//6)*256))
        sheet.save(folder/'overview.jpg',quality=92)
    save(OUT/'views.json',allviews);save(OUT/'preparation.json',dict(plan_sha256=sha(ROOT/'experiment/sonar-rgb-pose-pilot-plan.md'),script_sha256=sha(__file__),views=len(allviews),camera_frames=len(selection),texture_previews_initially_saved='DataSet/sonar_projection_root_cause/*-texture-preview.jpg; new diagnostic images only, no prior files replaced'))
    print(json.dumps(dict(frames=[(r['sample'],r['feature_count']) for r in selection],views=len(allviews))))

if __name__=='__main__':main()
