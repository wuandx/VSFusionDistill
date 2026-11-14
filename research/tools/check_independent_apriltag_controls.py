"""Detect tag36h11 only on preselected, already exported development images."""
from pathlib import Path
import json,sys,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import cv2,numpy as np
OUT=ROOT/'DataSet/gopro_imaging_model';PRIOR=ROOT/'DataSet/sonar_independent_registration';TEMP=ROOT/'DataSet/camera_temporal_all'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
rows=read(PRIOR/'selection.json')['samples'];man={x['sample']:x for x in read(TEMP/'manifest-resolved.json')['items'] if x.get('paired_role') in ['train','val','val_id']}
assert all(x['sample'] in man for x in rows)
params=cv2.aruco.DetectorParameters();params.detectInvertedMarker=True
det=cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11),params)
outputs=[];before={str(p):sha(p) for p in [PRIOR/'selection.json',TEMP/'manifest-resolved.json',ROOT/'experiment/gopro-imaging-model-plan.md']};copies=OUT/'tag-controls';copies.mkdir(exist_ok=True)
for r in rows:
    for kind in ['sd','fhd']:
        e=dict(sample=r['sample'],recording=r['recording'],resolution=kind)
        if kind=='sd':path=Path(r['camera_copy']) if r.get('camera_copy') else None
        else:
            item=man[r['sample']];p=item.get('image')
            path=TEMP/p if item['status']=='candidate' and p else None
        if path is None:
            e['status']='unavailable';outputs.append(e);continue
        assert path.is_file(),str(path)
        before[str(path)]=sha(path);im=cv2.imdecode(np.frombuffer(path.read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
        assert im is not None
        corners,ids,rejected=det.detectMarkers(im)
        e.update(status='detected' if ids is not None else 'none',path=str(path),image_size=[im.shape[1],im.shape[0]],rejected_candidates=len(rejected),ids=[] if ids is None else ids.ravel().tolist(),corners=[x.reshape(4,2).tolist() for x in corners])
        if ids is not None:
            vis=cv2.cvtColor(im,cv2.COLOR_GRAY2BGR);cv2.aruco.drawDetectedMarkers(vis,corners,ids)
            dest=copies/(r['sample']+'-'+kind+'.png');dest.write_bytes(cv2.imencode('.png',vis)[1].tobytes());e['overlay']=str(dest)
        outputs.append(e)
assert all(sha(Path(p))==h for p,h in before.items())
res=dict(detector='OpenCV '+cv2.__version__+' DICT_APRILTAG_36h11 default; detectInvertedMarker=True',outputs=outputs,input_hashes=before,inputs_unchanged=True,poses_estimated=False,script_sha256=sha(Path(__file__)))
(OUT/'apriltag-controls.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
print('Available:',sum(x['status']!='unavailable' for x in outputs),'positive:',[(x['sample'],x['resolution'],x['ids']) for x in outputs if x['status']=='detected'])
