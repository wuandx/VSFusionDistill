"""Exploratory pose-matched return extent audit; no registration or label mutation."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json,hashlib,subprocess
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image,ImageDraw
from scipy.spatial.transform import Rotation
from fit_box_guided_sonar_registration import read,save,sha
BASE=ROOT/'DataSet/sonar_box_guided_full_trajectory';OUT=ROOT/'DataSet/sonar_projection_root_cause/pose_matched_returns'
def main():
    assert not OUT.exists();OUT.mkdir();data=read(BASE/'results.json')['frames'];low=sorted([r for r in data if r['recording']=='2023-09-21_123500'],key=lambda r:r['sample']);results=[]
    for rec in ['2023-09-21_123841','2023-09-21_124039']:
        high=[r for r in data if r['recording']==rec];pairs=[]
        for r in low:
            T=np.array(r['world_from_sonar']);matches=[]
            for q in high:
                U=np.array(q['world_from_sonar']);distance=float(np.linalg.norm(T[:3,3]-U[:3,3]));angle=float(Rotation.from_matrix(T[:3,:3].T@U[:3,:3]).magnitude()*180/np.pi);matches.append((distance/.02+angle/.5,distance,angle,q))
            score,distance,angle,q=min(matches,key=lambda x:x[0])
            if distance>=.02 or angle>=.5:continue
            a=np.array(r['reference_bbox']);b=np.array(q['reference_bbox']);pa=np.array(r['predictions']['box_guided']['bbox_xyxy']);pb=np.array(q['predictions']['box_guided']['bbox_xyxy'])
            pairs.append(dict(low_sample=r['sample'],high_sample=q['sample'],translation_difference_m=distance,rotation_difference_deg=angle,reference_width_ratio=float((b[2]-b[0])/(a[2]-a[0])),projected_width_ratio=float((pb[2]-pb[0])/(pa[2]-pa[0])),reference_edge_shift=(b-a).tolist(),predicted_edge_shift=(pb-pa).tolist(),low_reference=a.tolist(),high_reference=b.tolist(),low_source=r['provenance']['raw'],high_source=q['provenance']['raw'],low_prediction=pa.tolist(),high_prediction=pb.tolist(),not_independent_pairs=True))
        # Largest difference is a diagnostic example, explicitly not random QA.
        ordered=sorted(pairs,key=lambda p:abs(p['reference_width_ratio']-p['projected_width_ratio']),reverse=True)
        for i,p in enumerate(ordered[:3]):
            canvas=Image.new('RGB',(1280,640),'white');d=ImageDraw.Draw(canvas)
            ys=[p[k][j] for k in ['low_reference','high_reference'] for j in [1,3]];lo=max(0,int(min(ys))-30);hi=min(441,int(max(ys))+30)
            for j,prefix in enumerate(['low','high']):
                source=p[prefix+'_source'];assert sha(source['path'])==source['sha256'];raw=np.array(Image.open(source['path']));box=p[prefix+'_reference'];pred=p[prefix+'_prediction']
                # Gain=1 avoids introducing artificial saturation in this diagnostic.
                im=Image.fromarray(raw).convert('RGB').crop((0,lo,raw.shape[1],hi)).resize((640,520));dd=ImageDraw.Draw(im)
                for b,color in [(box,'lime'),(pred,'cyan')]:dd.rectangle((b[0]*5,(b[1]-lo)*520/(hi-lo),b[2]*5,(b[3]-lo)*520/(hi-lo)),outline=color,width=2)
                canvas.paste(im,(j*640,60));d.text((j*640+8,8),p[prefix+'_sample']+' | raw gain 1',fill='black')
                roi=raw[int(box[1]):int(box[3]),int(box[0]):int(box[2])];p[prefix+'_raw_intensity']=dict(median=float(np.median(roi)),p95=float(np.percentile(roi,95)),fraction_255=float((roi==255).mean()),fraction_saturated_at_display_gain25=float((roi>=102).mean()))
            d.text((8,590),f'Pose difference {p["translation_difference_m"]*1000:.1f} mm / {p["rotation_difference_deg"]:.3f} deg. Box width ratio {p["reference_width_ratio"]:.3f}, projected {p["projected_width_ratio"]:.3f}',fill='black');d.text((8,610),'Green: existing visible-return box. Cyan: same frozen model. Pose uses released metadata, not independently certified.',fill='black')
            name=rec+f'-difference-{i}.png';canvas.save(OUT/name);p['image']=name
        results.append(dict(high_recording=rec,match_count=len(pairs),pairs=pairs,median_reference_width_ratio=float(np.median([p['reference_width_ratio'] for p in pairs])),median_projected_width_ratio=float(np.median([p['projected_width_ratio'] for p in pairs])),largest_difference_examples=ordered[:3]))
    ambiguity=[]
    for model in ['mortar_shell','incindiary']:
        f=read(BASE/model/'freeze-model.json');T=np.array(f['chosen']['world_from_model']);near=[c for c in f['candidates'] if c['fit_cost']<=f['chosen']['fit_cost']*1.05]
        ambiguity.append(dict(model=model,criterion='within 5% of best objective, not posterior uncertainty',candidates=[dict(id=c['id'],cost=c['fit_cost'],rotation_distance_deg=float(Rotation.from_matrix(np.array(c['world_from_model'])[:3,:3]@T[:3,:3].T).magnitude()*180/np.pi),translation_distance_m=float(np.linalg.norm(np.array(c['world_from_model'])[:3,3]-T[:3,3]))) for c in near]))
    save(OUT/'results.json',dict(records=results,pose_observation='Released metadata distance <20mm and rotation <0.5deg; approximate, not independent synchronization proof',hypothesis='Different transmit/gain conditions and visible-return annotation extent may explain part of cross-recording box discrepancy; not isolated causal proof',pose_ambiguity=ambiguity))
    inventory=subprocess.run(['rg','--files','D:/pby/data_processed','-g','*.bag','-g','*.mcap','-g','*.db3','-g','*.obj','-g','*.stl','-g','*calib*','-g','*pose*'],capture_output=True,text=True)
    save(OUT/'supplied-root-inventory.json',dict(user_supplied_root='D:/pby/data_processed',top_level=[p.name for p in Path('D:/pby/data_processed').iterdir()],extra_raw_calibration_paths=inventory.stdout.splitlines(),rg_returncode=inventory.returncode,scope='Filename inventory only; no test sample contents read',used_sources=['matches.csv','gantry/*.csv for five allowed development recordings','aris/<five allowed recordings>/*_frames.csv'],note='Intermediate processed dataset already supplies current mapping; no additional bag/calibration/OBJ found under this root by selected filename patterns'))
    print(json.dumps([dict(recording=r['high_recording'],pairs=r['match_count'],median_width_ratio=r['median_reference_width_ratio'],median_projected_ratio=r['median_projected_width_ratio'],examples=[dict(low=p['low_sample'],high=p['high_sample'],reference=p['reference_width_ratio'],predicted=p['projected_width_ratio']) for p in r['largest_difference_examples']]) for r in results],indent=2))
if __name__=='__main__':main()
