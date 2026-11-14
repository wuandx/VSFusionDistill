"""Fit one fixed mortar rigid pose using only three frozen fit observations.

This module never loads check observations or check images. It saves every
start, dense fit diagnostics, and a frozen candidate set for later evaluation.
"""
from __future__ import annotations
from pathlib import Path
import csv
import hashlib
import json
import math
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/_sonar_audit_deps'))
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from check_official_sonar_coordinates import Geometry, load_beam_tables, beam_count

OUT = ROOT / 'DataSet/mortar_fixed_registration'
FIT_IDS = ['2023-09-21_100927_0087', '2023-09-21_100927_0451', '2023-09-21_100927_0811']
CHECK_IDS = ['2023-09-21_101131_0103', '2023-09-21_101131_0509', '2023-09-21_101131_0909']
SEED = 20261111
SAMPLE_COUNT = 12000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def arrsha(arr):
    return hashlib.sha256(np.ascontiguousarray(arr, dtype='<f8').tobytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def read_obj(path):
    vs, faces = [], []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        s = line.split()
        if not s:
            continue
        if s[0] == 'v':
            vs.append(list(map(float, s[1:4])))
        elif s[0] == 'f':
            ids = [int(x.split('/')[0]) for x in s[1:]]
            ids = [i - 1 if i > 0 else len(vs) + i for i in ids]
            faces.extend([[ids[0], ids[i], ids[i+1]] for i in range(1, len(ids)-1)])
    return np.array(vs, dtype=float), np.array(faces, dtype=np.int32)


def prepare_model():
    obj = ROOT / 'related_work/sonar-projection-audit-assets/data_export_3dmodels/3d_models/mortar_shell.obj'
    anchor_path = ROOT / 'DataSet/sonar_registration_methods/anchors/geometry.json'
    anchor = next(m for m in read(anchor_path)['models'] if m['model'] == 'mortar_shell')
    vs, faces = read_obj(obj)
    area_axes = np.asarray(anchor['area_pca_axes_rows'])
    axes = np.diag([-1., 1., -1.]) @ area_axes
    assert np.linalg.det(axes) > .999999999
    centroid = np.asarray(anchor['area_centroid_raw'])
    centered_axes = (vs-centroid) @ axes.T
    midpoint = (centered_axes.max(0)+centered_axes.min(0))/2
    scale = .580/np.ptp(centered_axes[:, 0])
    model = scale*(centered_axes-midpoint)
    similarity = np.eye(4)
    similarity[:3,:3] = scale*axes
    similarity[:3,3] = -scale*(axes@centroid+midpoint)
    tri = model[faces]
    areas = np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    # Stratify by mesh area, not image data. Barycentric draws use a fixed seed.
    targets = (np.arange(SAMPLE_COUNT)+.5)/SAMPLE_COUNT*areas.sum()
    face_ids = np.searchsorted(np.cumsum(areas),targets,side='left')
    random = np.random.default_rng(SEED).random((SAMPLE_COUNT,2))
    root_u = np.sqrt(random[:,0])
    weights = np.c_[1-root_u,root_u*(1-random[:,1]),root_u*random[:,1]]
    sampled = np.einsum('ni,nij->nj',weights,tri[face_ids])
    extremes = np.unique(np.r_[np.argmin(model,axis=0),np.argmax(model,axis=0)])
    sampled = np.concatenate([sampled,model[extremes]])
    dense = np.concatenate([model,tri.mean(1),(tri[:,0]+tri[:,1])/2,
                            (tri[:,1]+tri[:,2])/2,(tri[:,2]+tri[:,0])/2])
    info = dict(obj_path=str(obj),obj_sha256=sha(obj),anchor_path=str(anchor_path),anchor_sha256=sha(anchor_path),
                length_m=.580,canonical_axes_rows=axes.tolist(),area_pca_axes_rows=area_axes.tolist(),
                area_centroid_raw=centroid.tolist(),extrema_midpoint_after_centered_axes=midpoint.tolist(),
                scale_m_per_obj_unit=float(scale),raw_obj_to_model_similarity=similarity.tolist(),
                model_origin='area-PCA-coordinate extrema midpoint; parameterization, not official target origin',
                semantic_positive_x='mortar pointed tip is negative end of prior area-PCA x, so flip x and z',
                bounds_model_m=[model.min(0).tolist(),model.max(0).tolist()],vertex_count=len(model),triangle_count=len(faces),
                sampling=dict(seed=SEED,area_samples=SAMPLE_COUNT,extra_vertex_indices=extremes.tolist(),
                              sampled_model_points_sha256=arrsha(sampled),sampled_point_count=len(sampled),
                              dense_point_count=len(dense),dense_model_points_sha256=arrsha(dense),
                              dense_order='all vertices, triangle centroids, edge01 midpoints, edge12 midpoints, edge20 midpoints'))
    return model, sampled, dense, info


def bbox(uv, width=None, height=None):
    if not len(uv):
        return None
    lo, hi = uv.min(0),uv.max(0)
    if width is not None:
        lo=np.maximum(lo,[0.,0.]);hi=np.minimum(hi,[float(width),float(height)])
    if np.any(hi<=lo):
        return None
    return np.r_[lo,hi].tolist()


def interval_violation(value,interval):
    lo,hi=interval
    return min(0.,value-lo)+max(0.,value-hi)


def huber(value):
    v=np.abs(np.asarray(value))
    return np.where(v<=1.,.5*v*v,v-.5)


class FitFrame:
    def __init__(self,observation,pose,meta,beams):
        self.sample=observation['sample']
        self.observation=observation
        self.world_from_sonar=np.asarray(pose['world_from_sonar'])
        self.sonar_from_world=np.linalg.inv(self.world_from_sonar)
        self.geom=Geometry(meta,beams,1000.)
        self.points=np.asarray([p['raw_uv_edge'] for p in observation['points']],dtype=float)
        self.tolerances=np.asarray([p.get('tolerance_uv',[1.,2.]) for p in observation['points']],dtype=float)
        assert len(self.points)>=3 and self.points.shape==self.tolerances.shape and np.all(self.tolerances>0)
        assert np.all(self.points[:,0]>=0) and np.all(self.points[:,0]<=self.geom.w)
        assert np.all(self.points[:,1]>=0) and np.all(self.points[:,1]<=self.geom.h)
        self.groups=[]
        for tau in np.unique(self.tolerances,axis=0):
            ix=np.where(np.all(self.tolerances==tau,axis=1))[0]
            self.groups.append((tau,ix))
        self.boundaries=[]
        for name,interval in observation.get('boundary_intervals',{}).items():
            if interval is not None:
                assert name in ('left','right','top','bottom')
                if isinstance(interval,dict):
                    assert interval.get('physical_boundary_reliable',False)
                    interval=interval['interval']
                assert len(interval)==2 and interval[1]>=interval[0]
                self.boundaries.append((name,interval))

    def project(self,model_points,world_from_model):
        world=model_points@world_from_model[:3,:3].T+world_from_model[:3,3]
        p=world@self.sonar_from_world[:3,:3].T+self.sonar_from_world[:3,3]
        ranges=np.linalg.norm(p,axis=1)
        beta=-np.degrees(np.arctan2(p[:,0],p[:,2]))
        elevation=np.degrees(np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2])))
        uv=self.geom.points_to_raw_edges(ranges,beta)
        horizontal=(p[:,2]>0)&(ranges>=self.geom.r0)&(ranges<=self.geom.data_range)&(beta>=self.geom.beams[0,1])&(beta<=self.geom.beams[-1,2])
        visible=horizontal&(np.abs(elevation)<=7.)
        return dict(p=p,ranges=ranges,beta=beta,elevation=elevation,uv=uv,horizontal=horizontal,visible=visible)

    def distances(self,projected):
        supports=projected['uv'][projected['visible']]
        components=np.full_like(self.points,100.)
        closest=np.full_like(self.points,np.nan)
        if len(supports):
            for tau,indices in self.groups:
                tree=cKDTree(supports/tau)
                points=self.points[indices]/tau
                nearest,_=tree.query(points,k=1)
                # A smaller rectangle-gap distance cannot occur outside this
                # center radius: ||center|| <= ||gap|| + sqrt(2).
                lists=tree.query_ball_point(points,nearest+math.sqrt(2)+1e-10)
                for local_ix,choices in enumerate(lists):
                    j=indices[local_ix]
                    diffs=(supports[choices]-self.points[j])/tau
                    gaps=np.sign(diffs)*np.maximum(np.abs(diffs)-1.,0.)
                    pick=int(np.argmin(np.sum(gaps*gaps,axis=1)))
                    components[j]=gaps[pick]
                    closest[j]=supports[choices[pick]]
        norms=np.linalg.norm(components,axis=1)
        boundary_values=[]
        if self.boundaries:
            box=bbox(supports)
            for name,interval in self.boundaries:
                coord={'left':0,'top':1,'right':2,'bottom':3}[name]
                sigma=1. if name in ('left','right') else 2.
                error=100. if box is None else interval_violation(box[coord],interval)/sigma
                boundary_values.append(dict(name=name,interval=interval,predicted=None if box is None else box[coord],normalized_violation=float(error)))
        return dict(norms=norms,components=components,closest=closest,support_count=len(supports),boundaries=boundary_values)

    def residual(self,projected):
        d=self.distances(projected)
        residual=np.sqrt(2*huber(d['norms'])/len(d['norms']))
        if d['boundaries']:
            boundary=np.array([b['normalized_violation'] for b in d['boundaries']])
            residual=np.r_[residual,np.sqrt(2*huber(boundary)/len(boundary))]
        return residual

    def summarize(self,projected):
        d=self.distances(projected)
        g=self.geom;uv=projected['uv'];vis=projected['visible'];horiz=projected['horizontal']
        vis75=horiz&(np.abs(projected['elevation'])<=7.5)
        polar=g.points_to_polar_index(projected['ranges'],projected['beta'])+.5
        point_reports=[]
        for i,norm in enumerate(d['norms']):
            nearest=None if not np.isfinite(d['closest'][i]).all() else d['closest'][i].tolist()
            delta_uv=None if nearest is None else (d['closest'][i]-self.points[i]).tolist()
            obs_range,obs_beta=g.raw_edges_to_points(self.points[i])
            if nearest is None:
                delta_range=delta_beta=None
            else:
                nearest_range,nearest_beta=g.raw_edges_to_points(d['closest'][i])
                delta_range=float(nearest_range-obs_range);delta_beta=float(nearest_beta-obs_beta)
            point_reports.append(dict(observed_raw_uv_edge=self.points[i].tolist(),tolerance_uv=self.tolerances[i].tolist(),
                                      closest_sample_raw_uv_edge=nearest,witness_delta_raw_uv=delta_uv,
                                      witness_delta_range_m=delta_range,witness_delta_beam_deg=delta_beta,
                                      normalized_gap_components=d['components'][i].tolist(),normalized_gap=float(norm)))
        boundary_cost=float(np.mean(huber([b['normalized_violation'] for b in d['boundaries']]))) if d['boundaries'] else 0.
        return dict(sample=self.sample,world_from_sonar=self.world_from_sonar.tolist(),geometry=g.description(),
                    range_m=[float(projected['ranges'].min()),float(projected['ranges'].max())],
                    beam_angle_deg=[float(projected['beta'].min()),float(projected['beta'].max())],
                    elevation_deg=[float(projected['elevation'].min()),float(projected['elevation'].max())],
                    full_raw_bbox=bbox(uv),horizontal_raw_bbox=bbox(uv[horiz],g.w,g.h),
                    visible_raw_bbox_7deg=bbox(uv[vis],g.w,g.h),visible_raw_bbox_7_5deg=bbox(uv[vis75],g.w,g.h),
                    visible_polar_bbox_7deg=bbox(polar[vis],g.W,g.H),no_elevation_polar_bbox=bbox(polar[horiz],g.W,g.H),
                    bbox_padding_raw_beam_bin=0.,polar_bbox_convention='pixel edge coords: continuous official index +0.5; no padding',
                    support_count=int(vis.sum()),horizontal_support_count=int(horiz.sum()),visible_fraction=float(vis.mean()),
                    point_count=len(self.points),point_residuals=point_reports,
                    point_huber_mean=float(huber(d['norms']).mean()),boundary_huber_mean=boundary_cost,
                    objective=float(huber(d['norms']).mean())+boundary_cost,
                    point_gap_median=float(np.median(d['norms'])),point_gap_p95=float(np.quantile(d['norms'],.95)),point_gap_max=float(d['norms'].max()),
                    fraction_inside_original_observation_band=float(np.mean(d['norms']<=1e-9)),
                    witness_delta_note='Nearest sampled surface support witness under rectangle-gap metric, not a known physical point correspondence',
                    boundary_intervals=d['boundaries'])


def matrix_from_parameters(x,origin,base_yaw,base_roll):
    # x=[translation offset m, delta yaw deg, absolute pitch deg, delta roll deg].
    yaw=base_yaw+x[3];pitch=x[4];roll=base_roll+x[5]
    matrix=np.eye(4)
    matrix[:3,:3]=Rotation.from_euler('xyz',[roll,pitch,yaw],degrees=True).as_matrix()
    matrix[:3,3]=origin+x[:3]
    return matrix


def raw_loss(frames,samples,T):
    return np.concatenate([f.residual(f.project(samples,T)) for f in frames])


def safe_svd(matrix):
    sv=np.linalg.svd(matrix,compute_uv=False)
    tol=float(sv[0]*1e-8) if len(sv) else 0.
    rank=int((sv>tol).sum())
    return dict(singular_values=sv.tolist(),threshold=tol,rank=rank,
                condition_number=None if not len(sv) or sv[-1]<=0 else float(sv[0]/sv[-1]),
                caveat='Local numerical residual Jacobian only; tolerance dead zones and visibility jumps invalidate precision interpretations')


def numerical_controls(frames,samples,origin):
    truth=matrix_from_parameters(np.array([.025,-.018,.012,12.,5.,20.]),origin,0.,0.)
    direct=[]
    for f in frames:
        proj=f.project(samples,truth)
        direct_matrix=f.sonar_from_world@truth
        independently=(direct_matrix@np.c_[samples,np.ones(len(samples))].T).T[:,:3]
        direct.append(float(np.max(np.abs(independently-proj['p']))))
    # Test the support-interval objective using exact generated visible samples.
    synthetic=[]
    for f in frames:
        p=f.project(samples,truth)
        visible=p['uv'][p['visible']]
        assert len(visible)>=10
        selected=visible[np.linspace(0,len(visible)-1,12,dtype=int)]
        obs=dict(sample=f.sample,points=[dict(raw_uv_edge=v.tolist(),tolerance_uv=[.1,.2]) for v in selected],boundary_intervals={})
        synthetic.append(FitFrame(obs,dict(world_from_sonar=f.world_from_sonar),f.geom.metadata,f.geom.beams))
    exact=raw_loss(synthetic,samples,truth)
    displaced=truth.copy();displaced[0,3]+=.15
    shifted=raw_loss(synthetic,samples,displaced)
    assert np.max(np.abs(exact))<1e-10 and float(shifted@shifted)>1.
    # A small fixed-budget exact-control recovery checks optimizer wiring only.
    x0=np.array([.035,-.018,.012,12.,5.,20.])
    lower=np.array([-.35,-.35,-.20,-180.,-60.,-180.])
    upper=-lower
    fn=lambda x: raw_loss(synthetic,samples,matrix_from_parameters(x,origin,0.,0.))
    fit=least_squares(fn,x0,bounds=(lower,upper),x_scale=[.05,.05,.05,30,15,30],max_nfev=60,diff_step=1e-4,ftol=1e-7,xtol=1e-7,gtol=1e-7)
    initial=float(fn(x0)@fn(x0)/2);final=float(fit.fun@fit.fun/2)
    assert final<initial or final<1e-8
    return dict(homogeneous_projection_max_difference_m=max(direct),truth_interval_max_residual=float(np.max(np.abs(exact))),
                displaced_control_objective=float(shifted@shifted/2),recovery_initial_objective=initial,
                recovery_final_objective=final,recovery_nfev=fit.nfev,recovery_success=bool(fit.success),
                caveat='Generated points exercise numerical wiring; they do not certify real echo identity or unique pose recovery')


def main():
    plan=ROOT/'experiment/mortar-fixed-registration-plan.md'
    observations_path=OUT/'observations/fit-observations.json'
    assert plan.exists() and observations_path.exists()
    if (OUT/'freeze-model.json').exists() or (OUT/'fit-results.json').exists():
        raise RuntimeError('Preserve an existing completed run')
    OUT.mkdir(parents=True,exist_ok=True)
    obs=read(observations_path)
    obs_by_id={f['sample']:f for f in obs['frames']}
    assert set(obs_by_id)==set(FIT_IDS)
    assert all(f.get('role')=='fit' for f in obs_by_id.values())
    selection_path=ROOT/'DataSet/sonar_independent_registration/selection.json'
    selection={r['sample']:r for r in read(selection_path)['samples'] if r['sample'] in FIT_IDS}
    assert set(selection)==set(FIT_IDS)
    manifest_path=ROOT/'DataSet/camera_temporal_all/manifest-resolved.json'
    allowed={r['sample']:r for r in read(manifest_path)['items'] if r.get('paired_role') in ('train','val','val_id') and r['sample'] in FIT_IDS}
    assert set(allowed)==set(FIT_IDS)
    pose_path=ROOT/'DataSet/sonar_fixed_mesh/results.json'
    poses={r['sample']:r for r in read(pose_path)['outputs'] if r['sample'] in FIT_IDS}
    frozen_old=ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json'
    world_target=np.asarray(read(frozen_old)['models']['mortar_shell']['world_from_target'])
    origin=world_target[:3,3]
    model,samples,dense,model_info=prepare_model()
    tables=load_beam_tables();frames=[]
    paths={plan,observations_path,selection_path,manifest_path,pose_path,frozen_old,Path(__file__),
           ROOT/'tools/check_official_sonar_coordinates.py',Path(model_info['obj_path']),Path(model_info['anchor_path']),
           ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'}
    for sid in FIT_IDS:
        row=selection[sid];paths.add(Path(row['meta_source']))
        with open(row['meta_source'],encoding='utf-8',newline='') as file:
            matches=[r for r in csv.DictReader(file) if int(r['FrameIndex'])==row['aris_frame']]
        assert len(matches)==1
        meta=matches[0]
        assert int(meta['FrameTime'])==allowed[sid]['aris_time_us'] and row['aris_frame']==allowed[sid]['aris_frame']
        frames.append(FitFrame(obs_by_id[sid],poses[sid],meta,tables[beam_count(meta['PingMode'])]))
    before={str(p):sha(p) for p in sorted(paths)}
    save(OUT/'fit-inputs-before.json',before)
    save(OUT/'model-definition.json',model_info)
    np.save(OUT/'sampled-model-points.npy',np.asarray(samples,dtype='<f8'),allow_pickle=False)
    controls=numerical_controls(frames,samples,origin)
    save(OUT/'numerical-controls.json',controls)
    lower=np.array([-.35,-.35,-.20,-180.,-60.,-180.]);upper=-lower
    candidates=[];start_index=0
    for yaw in (0.,180.):
        for pitch in (-10.,0.,10.):
            for roll in (0.,90.,180.,270.):
                cid=f'start-{start_index:02d}';start_index+=1
                x0=np.array([0.,0.,0.,0.,pitch,0.])
                count=[0]
                def fn(x):
                    count[0]+=1
                    return raw_loss(frames,samples,matrix_from_parameters(x,origin,yaw,roll))
                started=time.perf_counter()
                initial=fn(x0);failure=None
                try:
                    result=least_squares(fn,x0,bounds=(lower,upper),x_scale=[.05,.05,.05,30.,15.,30.],
                                         max_nfev=800,diff_step=1e-4,ftol=1e-7,xtol=1e-7,gtol=1e-7)
                    x=result.x;success=bool(result.success)
                    detail=dict(status=int(result.status),message=result.message,nfev=int(result.nfev),
                                njev=None if result.njev is None else int(result.njev),actual_residual_calls=count[0],
                                optimality=float(result.optimality),active_mask=result.active_mask.tolist(),
                                jacobian_svd=safe_svd(result.jac*np.array([.01,.01,.01,1.,1.,1.])))
                except Exception as exc:
                    x=x0.copy();success=False;failure=repr(exc)
                    detail=dict(status=-99,message=failure,nfev=None,njev=None,actual_residual_calls=count[0],jacobian_svd=None)
                T=matrix_from_parameters(x,origin,yaw,roll)
                coarse=[f.summarize(f.project(samples,T)) for f in frames]
                full=[f.summarize(f.project(dense,T)) for f in frames]
                cost=float(np.mean([f['objective'] for f in coarse]))
                dense_cost=float(np.mean([f['objective'] for f in full]))
                physical_ix=[0,1,2,4]
                hit=any(min(abs(x[i]-lower[i]),abs(upper[i]-x[i]))<1e-4 for i in physical_ix)
                feasible=success and not hit and all(f['point_gap_p95']<=1. and f['point_gap_max']<=2. and
                           all(abs(b['normalized_violation'])<=1. for b in f['boundary_intervals']) for f in full)
                world_obj=T@np.asarray(model_info['raw_obj_to_model_similarity'])
                entry=dict(id=cid,initial_yaw_pitch_roll_deg=[yaw,pitch,roll],initial_parameters=x0.tolist(),
                           final_parameters=x.tolist(),parameter_order=['dx_m','dy_m','dz_m','delta_yaw_deg','pitch_deg','delta_roll_deg'],
                           final_yaw_pitch_roll_deg=[float((yaw+x[3]+180)%360-180),float(x[4]),float((roll+x[5]+180)%360-180)],
                           solver_success=success,bound_hit=hit,periodic_angle_endpoint_hit=bool(abs(x[3])>179.9999 or abs(x[5])>179.9999),
                           solver=detail,failure=failure,elapsed_seconds=time.perf_counter()-started,
                           initial_objective=float(initial@initial/2/len(frames)),fit_objective=cost,dense_fit_objective=dense_cost,
                           world_from_model=T.tolist(),target_from_model=(np.linalg.inv(world_target)@T).tolist(),
                           world_from_obj_similarity=world_obj.tolist(),fit_metrics_coarse=coarse,fit_metrics_dense=full,
                           feasible_before_near_optimal_filter=bool(feasible),approved_for_training_gt=False)
                candidates.append(entry)
                save(OUT/f'{cid}.json',entry)
                print(cid,'cost',round(cost,4),'dense',round(dense_cost,4),'success',success,'boundary',hit,'feasible',feasible,'calls',count[0],flush=True)
                assert all(sha(p)==h for p,h in before.items())
    feasible=[c for c in candidates if c['feasible_before_near_optimal_filter']]
    best=min(candidates,key=lambda c:c['fit_objective'])
    best_feasible=min((c['fit_objective'] for c in feasible),default=None)
    eligible=[c['id'] for c in feasible if c['fit_objective']<=best_feasible+.25] if feasible else []
    rules=dict(fit_frame_weight='Each frame contributes mean point Huber + mean boundary Huber; saved cost averages the three frames equally. Solver minimizes the sum, which has the same optimum.',
               huber_delta=1.,support='fixed 12000 stratified area samples plus 6 axis-extreme vertices; dense final replay',
               interval_distance='minimum Euclidean norm of anisotropic rectangle violation to visible projected surface samples',
               visibility='forward z>0; r0<=r<=r0+h*dr; beam table endpoints; abs(elevation)<=7 degrees',
               empty_support_normalized_component_penalty=100.,visibility_discontinuity='hard membership; all solver diagnostics retained',
               parameterization='T_world_from_model R=Rz(yaw) Ry(pitch) Rx(roll); one fixed translation for all frames',
               yaw_roll_bounds='base value plus delta in [-180,180] per start, one full period; periodic endpoints not physical bounds',
               physical_bounds=dict(translation_offset_m=[[-.35,.35],[-.35,.35],[-.20,.20]],pitch_deg=[-60.,60.]),
               candidate_rule='solver_success and no translation/pitch bound hit; each dense frame p95 gap<=1, max gap<=2, all boundary violations<=1; coarse balanced Huber cost<=best feasible+0.25',
               bound_hit_tolerance_native_units=1e-4,max_nfev_per_start=800,starts=24,
               no_physical_axis_certification=True,known_point_to_sample_tolerance='frozen per-point raw uv intervals; not estimated from residuals')
    result=dict(run='mortar_fixed_registration',status='fit_complete_candidates_frozen_for_check',fit_samples=FIT_IDS,
                check_samples_not_used=CHECK_IDS,check_observations_loaded=False,check_images_loaded=False,check_projections_generated=False,
                source_hashes=before,observation_sha256=sha(observations_path),solver_sha256=sha(Path(__file__)),
                model=model_info,official_world_from_target=world_target.tolist(),rules=rules,numerical_controls=controls,
                best_display_candidate_id=best['id'],eligible_candidate_ids=eligible,candidates=candidates,
                inputs_unchanged=True,test_access=False,training_runs=0,new_formal_gt=0)
    save(OUT/'fit-results.json',result)
    freeze=dict(run=result['run'],status='frozen_before_check',fit_results_sha256=sha(OUT/'fit-results.json'),
                fit_samples=FIT_IDS,check_samples_not_used=CHECK_IDS,source_hashes=before,
                observation_sha256=result['observation_sha256'],solver_sha256=result['solver_sha256'],
                model=model_info,official_world_from_target=world_target.tolist(),fixed_imaging=dict(beta='-degrees(atan2(x,z))',range='norm(xyz)',elevation='degrees(atan2(y,hypot(x,z)))',main_elevation_limit_deg=7.,sensitivity_elevation_limit_deg=7.5,raw_bbox_padding=0.,polar_bbox_padding=0.),
                rules=rules,best_display_candidate_id=best['id'],eligible_candidate_ids=eligible,candidates=candidates,
                approved_for_training_gt=False,check_used_for_selection=False)
    save(OUT/'freeze-model.json',freeze)
    save(OUT/'freeze-model.sha256.json',dict(path=str(OUT/'freeze-model.json'),sha256=sha(OUT/'freeze-model.json'),
                                          frozen_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    print('FROZEN',best['id'],'eligible',eligible,'sha256',sha(OUT/'freeze-model.json'),flush=True)


if __name__=='__main__':
    main()
