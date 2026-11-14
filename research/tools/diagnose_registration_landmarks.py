"""Independent visible end-centre ray diagnostic, no mesh or old labels in fit."""
from pathlib import Path
import sys,json,csv,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares
from PIL import Image,ImageDraw
OUT=ROOT/'DataSet/sonar_independent_registration'
landmarks={
'2023-09-20_171105_0622':[[388,175],[253,249]],
'2023-09-20_171105_0981':[[417,213],[185,211]],
'2023-09-20_171105_1336':[[391,285],[281,181]],
'2023-09-20_173329_0154':[[366,170],[281,278]],
'2023-09-20_173329_0456':[[458,181],[243,251]],
'2023-09-20_173329_0916':[[400,267],[269,203]],
'2023-09-21_120653_0163':[[354,201],[310,263]],
'2023-09-21_120653_0551':[[411,267],[245,265]],
'2023-09-21_120912_0120':[[365,208],[294,262]],
'2023-09-21_120912_0463':[[403,276],[243,265]],
'2023-09-21_120912_0802':[[320,218],[359,307]],
'2023-09-21_100927_0087':[[370,198],[300,290]],
'2023-09-21_100927_0451':[[409,264],[199,269]],
'2023-09-21_100927_0811':[[341,311],[272,223]],
'2023-09-21_101131_0103':[[343,198],[279,289]],
'2023-09-21_101131_0509':[[415,267],[207,265]],
'2023-09-21_101131_0909':[[472,337],[398,236]],
}
ann=dict(author='assistant visual inspection, not expert-reviewed',
    definitions={'100lbs_aircraft_bomb':'A closed rounded forward pole (approximate on smooth/rounded surface); B rear neck opening centre',
                 'incindiary_grenade':'A narrower/torn end centre; B broad open end centre; deformation makes correspondence approximate',
                 'mortar_shell':'A fuze/nose endpoint; B tail hub centre, excluding fin extremities'},
    uncertainty='approximately 3-5 SD px on end centres; smooth front pole and deformed end correspondence can shift with view',
    use='ray consistency diagnostic only, cannot establish complete 3D registration',points=landmarks)
(OUT/'landmarks.json').write_text(json.dumps(ann,ensure_ascii=False,indent=2),encoding='utf-8')
rows=json.loads((OUT/'selection.json').read_text(encoding='utf-8'))['samples']
versions=json.loads((ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json').read_text(encoding='utf-8'))['versions']
K=np.array(json.loads((OUT/'results.json').read_text(encoding='utf-8'))['K_sd']);invK=np.linalg.inv(K)
def camera_pose(row,tf):
    with Path(row['meta_source']).open(encoding='utf-8',newline='') as f:m=next(r for r in csv.DictReader(f) if int(r['FrameIndex'])==row['aris_frame'])
    with Path(row['gantry_source']).open(encoding='utf-8',newline='') as f:g=next(r for r in csv.DictReader(f) if int(r['aris_frame_idx'])==row['aris_frame'])
    wa=np.eye(4);wa[:3,3]=np.array([float(g[k]) for k in 'xyz'])+tf['setup/ar3'][:3,3]
    wa[:3,:3]=tf['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
    return wa@tf['setup/gopro_mounting_hole']@tf['setup/gopro_mounting_axis']@tf['setup/camera']
out=[]
for cat in sorted({r['category'] for r in rows}):
    rr=[r for r in rows if r['category']==cat and r.get('camera_copy')];fit=[r for r in rr if r['role']=='registration_fit']
    for version in ['release_current','notebook_20240723']:
        tf={k:np.array(v) for k,v in versions[version]['parent_from_child_matrices'].items()}
        poses={r['sample']:camera_pose(r,tf) for r in rr};points=[];diagnostics=[]
        for index in [0,1]:
            origins=[];directions=[]
            for r in fit:
                pose=poses[r['sample']];direction=pose[:3,:3]@invK@np.r_[landmarks[r['sample']][index],1]
                direction/=np.linalg.norm(direction);directions.append(direction);origins.append(pose[:3,3])
            origins=np.array(origins);directions=np.array(directions)
            A=np.column_stack([directions[0],-directions[1]]);coef=np.linalg.lstsq(A,origins[1]-origins[0],rcond=None)[0]
            q0=origins[0]+coef[0]*directions[0];q1=origins[1]+coef[1]*directions[1]
            def project(p,r):
                cam=np.linalg.inv(poses[r['sample']]);c=cam[:3,:3]@p+cam[:3,3];u=K@c
                return u[:2]/u[2]
            def residual(p):return np.concatenate([project(p,r)-landmarks[r['sample']][index] for r in fit])
            result=least_squares(residual,(q0+q1)/2,max_nfev=200)
            points.append(result.x)
            controls=[]
            for r in rr:
                uv=project(result.x,r);error=np.linalg.norm(uv-landmarks[r['sample']][index])
                controls.append(dict(sample=r['sample'],role=r['role'],predicted_uv=uv.tolist(),observed_uv=landmarks[r['sample']][index],euclidean_error_px=float(error)))
            diagnostics.append(dict(endpoint='AB'[index],point_world_m=result.x.tolist(),ray_closest_distance_m=float(np.linalg.norm(q0-q1)),
                angle_between_rays_deg=float(np.rad2deg(np.arccos(np.clip(directions[0]@directions[1],-1,1)))),
                ray_distances_m=coef.tolist(),fit_coordinate_rms_px=float(np.sqrt(np.mean(result.fun**2))),controls=controls))
        out.append(dict(category=cat,version=version,endpoint_distance_m=float(np.linalg.norm(points[0]-points[1])),endpoints=diagnostics))
        if version=='release_current':
            sheet=Image.new('RGB',(1280,1200),'white');d=ImageDraw.Draw(sheet)
            for i,r in enumerate(rr):
                x=i%2*640;y=i//2*400;sheet.paste(Image.open(r['camera_copy']),(x,y+30));d.text((x+5,y+5),r['sample']+' | '+r['role'],fill='black')
                for index in [0,1]:
                    a,b=landmarks[r['sample']][index];d.ellipse((x+a-4,y+b+26,x+a+4,y+b+34),outline=(255,60,100),width=2);d.text((x+a+6,y+b+30),'AB'[index],fill=(255,60,100))
                    c=next(c for c in diagnostics[index]['controls'] if c['sample']==r['sample']);a,b=c['predicted_uv']
                    d.line((x+a-5,y+b+30,x+a+5,y+b+30),fill=(0,255,150),width=2);d.line((x+a,y+b+25,x+a,y+b+35),fill=(0,255,150),width=2)
            sheet.save(OUT/(cat+'-landmark-rays.jpg'),quality=96)
result=dict(status='diagnostic, no registered model approved',outputs=out,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(OUT/'landmark-diagnostics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
for r in out:
    print(r['category'],r['version'],'distance',r['endpoint_distance_m'],'ray_skew_m',[e['ray_closest_distance_m'] for e in r['endpoints']],
          'fit_rms',[e['fit_coordinate_rms_px'] for e in r['endpoints']])
