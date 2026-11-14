"""Verify saved camera audit and render representative independently held faces."""
from audit_sonar_tag_multiface import IDS, OUTM, OUT, ROOT, read, save, sha
from pathlib import Path
from PIL import Image, ImageDraw
from html.parser import HTMLParser
import ast
import csv
import math
import numpy as np
import cv2


def angle(r):
    return math.degrees(math.acos(np.clip((np.trace(r)-1)/2,-1,1)))


def project(points, pose, m):
    k=np.array(m['K']); d=np.array(m['D']); a=np.array(pose[:3]); b=np.array(pose[3:]); pts=np.array(points)
    if m['kind']=='fisheye':return cv2.fisheye.projectPoints(pts.reshape(-1,1,3),a,b,k,d)[0][:,0]
    return cv2.projectPoints(pts,a,b,k,d if m['kind']=='brown' else None)[0][:,0]


def matrix(pose):return cv2.Rodrigues(np.array(pose[:3]))[0]


def euler_aris(r):
    x,y,z=(math.radians(float(r[k])) for k in ('SonarRoll','SonarTilt','SonarPan'))
    a,b,c=math.cos(x),math.cos(y),math.cos(z);s,t,u=math.sin(x),math.sin(y),math.sin(z)
    return np.array([[c,-u,0],[u,c,0],[0,0,1]]) @ np.array([[b,0,t],[0,1,0],[-t,0,b]]) @ np.array([[1,0,0],[0,a,-s],[0,s,a]])


class Links(HTMLParser):
    def __init__(self):super().__init__();self.items=[]
    def handle_starttag(self, tag, attrs):
        self.items.extend(v for k,v in attrs if k in ('href','src') and v and not v.startswith(('#','http')))


def main():
    s=read(OUT/'selection.json'); d=read(OUT/'detections.json'); mf=read(OUTM/'results.json'); sel=read(OUTM/'selection-before-fit.json'); cov=read(OUT/'camera_models/evaluation.json'); dense=read(OUT/'camera_solver_control/results.json'); csel=read(OUT/'camera_models/selection-before-fit.json'); older=read(ROOT/'DataSet/sonar_rgb_pose_pilot/tag-rotation.json')
    plan=ROOT/'experiment/sonar-tag-continuous-camera-plan.md';old_plan=OUT/'background/plan-at-background-baseline.md'
    assert s['plan_sha256']==sha(old_plan) and plan.read_bytes().startswith(old_plan.read_bytes()) and cov['plan_sha256']==sha(plan)
    assert d['selection_sha256']==sha(OUT/'selection.json') and d['script_sha256']==sha(ROOT/'tools/prepare_sonar_tag_continuous.py') and cov['data_sha256']==sha(OUT/'detections.json')
    assert dense['plan_sha256']==sha(ROOT/'experiment/sonar-tag-camera-solver-control-plan.md') and dense['script_sha256']==sha(ROOT/'tools/refine_sonar_tag_camera_solver.py') and dense['role_selection_sha256']==sha(OUT/'camera_models/selection-before-fit.json')
    assert mf['script_sha256']==sha(ROOT/'tools/audit_sonar_tag_multiface.py') and mf['selection_sha256']==sha(OUTM/'selection-before-fit.json') and sel['plan_sha256']==sha(ROOT/'experiment/sonar-tag-multiface-plan.md') and sel['source_detection_sha256']==sha(OUT/'detections.json')
    meta=s['metadata']; assert sha(meta['path'])==meta['sha256']; assert sha(s['gantry']['path'])==s['gantry']['sha256']; assert sha(s['calibration_path'])==s['calibration_sha256']; manifest=ROOT/'DataSet/camera_temporal_all/manifest-resolved.json';assert sha(manifest)==s['manifest_sha256']
    rows={r['sample']:r for r in s['frames']}; fitids={r['sample'] for r in sel['frames'] if r['role']=='fit'}; checkids={r['sample'] for r in sel['frames'] if r['role']=='check'};assert len(fitids)==18 and len(checkids)==16 and not(fitids&checkids);assert all(abs(rows[i]['aris_frame']-788)>12 for i in fitids)
    dmap={r['sample']:{t['id']:t for t in r['tags']} for r in d['frames']};assert set(dmap)==set(rows);assert sum(set(IDS)<=t.keys() for t in dmap.values())==sel['eligible']==149
    obs={r['sample']:np.array(r['corners']) for r in sel['frames']};
    for sid in obs:assert np.array_equal(obs[sid],np.vstack([dmap[sid][t]['corners'] for t in IDS]))
    a,b=older['samples'];assert b in checkids and a not in fitids|checkids; a_wc,b_wc=[np.array(rows[sid]['world_from_camera'])[:3,:3] for sid in [a,b]]; exp=b_wc.T@a_wc
    assert np.allclose(exp,np.array(older['released_camera_relative_rotation']),atol=1e-12)
    for sid,xy in zip(older['samples'],older['corners_fhd']):assert np.array_equal(xy,dmap[sid][141]['corners'])
    cf={r['sample'] for r in csel['frames'] if r['role']=='fit'};cc={r['sample'] for r in csel['frames'] if r['role']=='check'};assert len(cf)==25 and len(cc)==31 and not (cf&cc) and {a,b}<=cc; assert all(all(abs(rows[i]['aris_frame']-j)>12 for j in (392,788)) for i in cf)
    max_deg=max_px=0.; n_held=0; quad=[]
    for v in cov['models']:
        entries={r['sample']:r for r in v['frames']}; assert len(entries)==196 and all(r['image_continuity_branch']==0 for r in entries.values()); u,w=[np.array(entries[sid]['solutions'][0]['rotation_camera_from_tag']) for sid in [a,b]];max_deg=max(max_deg,abs(angle(w@u.T@exp.T)-v['anchor_image_best_difference_deg']));
    for group in dense['models']:
        for v in group['refined']:
            assert set(v['fit_sample_ids'])<=cf
            es={r['sample']:r for r in v['evaluation']};assert set(es)==cf|cc; u,w=[np.array(es[sid]['solutions'][0]['rotation_camera_from_tag']) for sid in [a,b]];max_deg=max(max_deg,abs(angle(w@u.T@exp.T)-v['anchor_difference_deg']))
    for v in mf['models']:
        m=v['bundle']['model']; p=np.array(v['bundle']['points']); assert set(v['bundle']['fit_ids'])==fitids and {r['sample'] for r in v['check']['views']}==checkids
        values=[]
        for row in v['check']['views']:
            for e in row['held_faces']:
                h=IDS.index(e['tag'])*4; c=project(p,e['pose'],m); err=np.linalg.norm(c[h:h+4]-obs[row['sample']][h:h+4],axis=-1); n_held+=4; values.extend(err.tolist()); max_px=max(max_px,float(np.max(np.abs(err-e['errors_px'])))); assert ((p @ matrix(e['pose']).T+e['pose'][3:])[:,2]>0).all()
                if row['sample']==b and e['tag']==141:quad.append((m['name'],c,err))
        assert np.allclose(np.percentile(values,[50,90]),[v['check']['summary']['median_px'],v['check']['summary']['p90_px']],atol=1e-9)
    with Path(meta['path']).open(encoding='utf-8-sig',newline='') as f:meta_by={int(r['FrameIndex']):r for r in csv.DictReader(f)}
    for v in mf['anchor_local_published_sensitivity']:
        q=v['offset_frames'];u,w=[euler_aris(meta_by[j+q]) for j in (392,788)];max_deg=max(max_deg,abs(angle(w.T@u)-v['published_angle_deg']))
    syn=read(OUTM/'synthetic-control.json');assert syn['negative_control']['unchanged_pose'] and syn['point_rmse']<.01 and min(syn['negative_control']['swapped_errors_px'])>100
    panels=Image.new('RGB',(1240,740),'white');
    im=Image.open(rows[b]['source_path']).convert('RGB'); crop=(930,310,1200,550); scale=1.35; size=(int((crop[2]-crop[0])*scale),int((crop[3]-crop[1])*scale)); pic=im.crop(crop).resize(size)
    for j,(name,pred,err) in enumerate(quad):
        x0,y0=j%2*620,j//2*370; panel=pic.copy(); qd=ImageDraw.Draw(panel); xy=obs[b];
        for idx,(u,w) in enumerate(zip(xy,pred)):
            u=(u-crop[:2])*scale;w=(w-crop[:2])*scale
            if idx<4:
                qd.line([tuple(u),tuple(w)],fill='#ffbf50',width=2);qd.ellipse([*(u-3),*(u+3)],outline='#65ffb5',width=2);qd.line([tuple(w-[4,0]),tuple(w+[4,0])],fill='#ff9a64',width=2);qd.line([tuple(w-[0,4]),tuple(w+[0,4])],fill='#ff9a64',width=2)
            else:qd.ellipse([*(u-2),*(u+2)],fill='#64c6ff')
        panels.paste(panel,(x0+12,y0+35)); qd=ImageDraw.Draw(panels); qd.text((x0+12,y0+7),name.replace('_',' '),fill='black');qd.text((x0+385,y0+58),'ARIS 0788\n\nBlue: pose inputs\nGreen: held 141 observed\nOrange: held 141 predicted\n\nPixel errors:\n'+', '.join(f'{x:.2f}' for x in err),fill='black')
    panels.save(OUTM/'anchor-held-face.png')
    images=[OUT/r['image'] for r in d['frames']]+list(OUT.glob('overview-*.jpg'))+[OUT/'temporal-pose-diagnostic.png',OUTM/'anchor-held-face.png'];assert len(images)==290
    for f in images:
        with Image.open(f) as im: im.load()
    links=Links();links.feed((OUT/'index.html').read_text(encoding='utf-8'));assert all((OUT/p).is_file() for p in links.items if p!='verification-delivery.json')
    scripts=list((ROOT/'tools').glob('*sonar_tag*py'))
    for f in scripts:ast.parse(f.read_text(encoding='utf-8-sig'))
    assert max_deg<1e-8 and max_px<1e-8
    save(OUT/'verification-delivery.json',dict(status='passed',decoded_images=len(images),static_links=len(links.items),scripts_checked=len(scripts),old_anchor_max_corner_difference_px=0,multiface_corners_reprojected=n_held,max_projection_discrepancy_px=max_px,max_angle_discrepancy_deg=max_deg,manifest_and_source_metadata_hashes_checked=True,multiface_result_sha256=sha(OUTM/'results.json'),background_verification_sha256=sha(OUT/'background/verification.json'),no_physical_registration_certification=True))


if __name__=='__main__':main()
