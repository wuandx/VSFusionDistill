"""Verify saved intermediate evidence and deliver a negative-result gallery."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json,ast,re
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image
from prepare_sonar_rgb_pose_pilot import OUT,read,save,sha
from audit_sonar_rgb_tag_rotation import OBJ

def main():
    rows=read(OUT/'selection.json')['samples'];views=read(OUT/'views.json');first=read(OUT/'pose/results.json');pooled=read(OUT/'pooled/results.json');tag=read(OUT/'tag-rotation.json');tags=read(OUT/'pooled/tag-detections.json')['frames'];checks={};max_surface_error=0.;images=0
    for r in rows:
        for path,digest in [(r['original_fhd'],r['fhd_sha256']),(r['sd']['path'],r['sd']['sha256']),(r['source_label'],r['label_sha256'])]:assert sha(path)==digest
        with Image.open(OUT/r['image']) as im:assert im.size==(960,540)
    for view in views:
        data=np.load(OUT/view['path']);T=data['camera_from_model'];assert np.max(abs(T[:3,:3].T@T[:3,:3]-np.eye(3)))<1e-10 and abs(np.linalg.det(T[:3,:3])-1)<1e-10
        p=data['xyz']@T[:3,:3].T+T[:3,3];proj=p[:,:2]/p[:,2:]*650+256
        # Surface coordinate is the nearest occupied integer render pixel, not exact subpixel SIFT center.
        err=float(np.max(np.abs(proj-data['xy']))) if len(p) else 0;max_surface_error=max(max_surface_error,err);assert err<1.1
        assert np.isfinite(data['descriptors']).all() and np.isfinite(data['xyz']).all()
    for model in ['mortar_shell','incindiary']:
        provenance=read(OUT/'render'/model/'provenance.json');assert sha(provenance['source'])==provenance['obj_sha256'];assert sha(provenance['texture'])==provenance['texture_sha256']
    synthetic=[]
    for r in first['synthetic_controls']:
        q=r['chosen'][0];xyz=np.array(q['xyz']);xy=np.array(q['xy']);T=np.array(q['camera_from_model']);p=xyz@T[:3,:3].T+T[:3,3];pred=p[:,:2]/p[:,2:]*650+256;err=np.linalg.norm(pred-xy,axis=1)
        assert np.max(abs(err-q['errors_px']))<1e-8;assert set(q['fit_indices']).isdisjoint(q['check_indices']);assert q['rgb_numeric_gate'];synthetic.append(dict(sample=r['sample'],rotation_error_deg=q['truth_rotation_error_deg'],translation_error_model_scale_m=q['truth_translation_error_m'],withheld_median_px=q['check_median_px'],withheld_p90_px=q['check_p90_px']))
    assert all(not q['rgb_numeric_gate'] for r in first['frames'] for q in r['chosen']);assert all(not q['rgb_numeric_gate'] for r in pooled['frames'] for q in r['variants'])
    for r in first['frames']:
        rr=read(OUT/'pose'/(r['sample']+'.json'))
        for cm in ['pinhole','fisheye']:
            a=[q for q in rr['attempts'] if q['camera_model']==cm];best=max(a,key=lambda q:(q['fit_inliers'],-q.get('fit_median_px',1e6),q['match_count']));stored=next(q for q in r['chosen'] if q['camera_model']==cm);assert best['view']==stored['view']
    a=read(OUT/'camera-assumptions.json');K=np.array(a['K_960x540']);K[:2]*=2;D=np.array(a['raw_four_coefficients']);scale_errors=[];trace_errors=[]
    for variant in tag['variants']:
        for xy in tag['corners_fhd']:
            xy=np.array(xy);pts=xy if variant['camera_model']=='pinhole' else cv2.fisheye.undistortPoints(xy.reshape(-1,1,2),K,D.reshape(4,1),P=K).reshape(-1,2)
            aa=cv2.solvePnPGeneric(OBJ,pts,K,None,flags=cv2.SOLVEPNP_IPPE_SQUARE);bb=cv2.solvePnPGeneric(OBJ*2,pts,K,None,flags=cv2.SOLVEPNP_IPPE_SQUARE)
            for r1,r2,t1,t2 in zip(aa[1],bb[1],aa[2],bb[2]):
                err=float(np.max(abs(cv2.Rodrigues(r1)[0]-cv2.Rodrigues(r2)[0])));scale_errors.append(err);assert err<1e-9 and np.max(abs(t2-2*t1))<1e-9
        for q in variant['all_solution_combinations']:
            R0=np.array(variant['solutions'][0][q['first_solution']]['rotation_camera_from_tag']);R1=np.array(variant['solutions'][1][q['second_solution']]['rotation_camera_from_tag']);delta=R1@R0.T@np.array(tag['released_camera_relative_rotation']).T
            error=float(np.degrees(np.arccos(np.clip((np.trace(delta)-1)/2,-1,1))));trace_errors.append(abs(error-q['difference_from_released_pose_deg']));assert trace_errors[-1]<1e-9
    for p in OUT.rglob('*'):
        if p.suffix.lower() in ['.jpg','.png']:
            with Image.open(p) as im:im.verify();images+=1
    summary=[]
    for row in rows:
        f=next(r for r in first['frames'] if r['sample']==row['sample'])['chosen'][0];p=next(r for r in pooled['frames'] if r['sample']==row['sample']);summary.append(dict(sample=row['sample'],single_view_matches=f['match_count'],pooled_matches=p['variants'][0]['match_count'],maximum_fit_inliers=max(q['fit_inliers'] for q in p['variants']),accepted_pose=False))
    save(OUT/'summary.json',dict(frames=summary,synthetic_controls=synthetic,accepted_object_poses=0,sonar_projections_generated=0,reason='RGB correspondence gate failed before sonar transfer',tag_rotation_is_conditional_not_physical_ground_truth=True))
    header='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>RGB估姿试验</title><style>body{font:16px system-ui;max-width:1500px;margin:28px auto;padding:16px;background:#f2f4f7;color:#182334}img{width:100%;height:auto}article{background:white;padding:16px;margin:24px 0}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px}summary{cursor:pointer;padding:12px}a{color:#155eab}</style><h1>RGB辅助3D注册：六帧试验结果</h1><p><b>真实六帧均未通过RGB姿态门槛，未生成新的声呐投影或GT。</b>两类各48个固定纹理渲染视角；合成控制通过，真实对应不足或几何不一致。下方保留失败匹配，不把匹配线当正确对应。</p><p><a href="../../复现/camera-baseline/sonar-rgb-pose-pilot.md">完整报告</a> · <a href="summary.json">汇总</a> · <a href="verification.json">验证</a> · <a href="tag-rotation.json">无尺寸旋转检查</a></p><table><tr><th>身份</th><th>单视图候选</th><th>合并候选</th><th>最多fit内点</th><th>姿态准入</th></tr>'''
    header+=''.join(f'<tr><td>{r["sample"]}</td><td>{r["single_view_matches"]}</td><td>{r["pooled_matches"]}</td><td>{r["maximum_fit_inliers"]}</td><td>未通过</td></tr>' for r in summary)+'</table>'
    parts=[header,'<h2>物理特征可辨性</h2><p>相机框仅定位搜索区。弹头、环带、尾翼、孔洞可见，但轴对称、重复孔洞和轮廓切点使独立3D对应仍有歧义，未人工编造六点。</p><img src="camera/physical-feature-review.jpg">']
    for model in ['mortar_shell','incindiary']:parts.append(f'<details><summary>{model}：48视角纹理及3D表面映射</summary><img loading="lazy" src="render/{model}/overview.jpg"></details>')
    for row in rows:
        sid=row['sample'];parts.append(f'<article><h2>{sid}</h2><p>单视图匹配（红线并非已确认对应）</p><img loading="lazy" src="pose/{sid}-pinhole.jpg"><details><summary>合并匹配与另一相机假设</summary><img loading="lazy" src="pooled/{sid}-pinhole.jpg"><img loading="lazy" src="pooled/{sid}-fisheye.jpg"></details></article>')
    parts.append('<h2>合成控制</h2><p>不同于参考库的视角、距离及颜色增益；只能验证同源纹理下的程序链，不能证明水下域匹配可用。</p>')
    for s in first['synthetic_controls']:parts.append(f'<img loading="lazy" src="{s["chosen"][0]["image"]}">')
    parts.append('<h2>AprilTag独立线索</h2><p>3/6帧检测到标记。同录音两帧tag141的相对旋转与发布姿态链差约21.6°（pinhole）或15.2°（fisheye假设）。不需要实际尺寸；但方块静止、实际相机模型均未独立确认，不能据此确定gantry错误。图中有悬挂线索，必须保留标记可能运动的解释。没有估计米制位置，也没有用此差异修正投影。</p>')
    for t in tags:
        if t.get('image'):parts.append(f'<p>{t["sample"]}：{t["ids"]}</p><img loading="lazy" src="{t["image"]}">')
    (OUT/'index.html').write_text(''.join(parts)+'</html>','utf-8')
    scripts=['prepare_sonar_rgb_pose_pilot.py','fit_sonar_rgb_pose_pilot.py','fit_sonar_rgb_pose_pooled.py','audit_sonar_rgb_tag_rotation.py',Path(__file__).name]
    for s in scripts:ast.parse((ROOT/'tools'/s).read_text('utf-8-sig'))
    links=[]
    for target in re.findall(r'(?:href|src)="([^"]+)"',(OUT/'index.html').read_text('utf-8')):
        # Report and verification are finalized immediately after this run.
        if target.endswith('sonar-rgb-pose-pilot.md') or target=='verification.json':continue
        assert (OUT/target).is_file(),target;links.append(target)
    save(OUT/'verification.json',dict(source_camera_and_label_hashes_verified=True,mesh_and_texture_hashes_verified=True,render_views_checked=len(views),max_surface_mapping_coordinate_error_px=max_surface_error,synthetic_reprojection_independently_recomputed=True,fit_check_disjoint=True,selection_uses_fit_only=True,real_pose_acceptances=0,tag_rotation_invariant_to_double_side_length=True,max_scale_rotation_matrix_error=max(scale_errors),max_independent_trace_angle_error_deg=max(trace_errors),images_decoded=images,script_parse_checks=len(scripts),local_links_resolved=len(links),browser_rendering_verified=False,physical_registration_validated=False))
    paths=[ROOT/'tools'/s for s in scripts]+[ROOT/'experiment'/s for s in ['sonar-rgb-pose-pilot-plan.md','sonar-rgb-pose-pooled-plan.md','sonar-rgb-tag-rotation-plan.md']]
    save(OUT/'source-hashes.json',{str(p):sha(p) for p in paths});print(read(OUT/'verification.json'))

if __name__=='__main__':main()
