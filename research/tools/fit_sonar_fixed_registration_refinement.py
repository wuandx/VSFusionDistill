"""Fixed six-DOF near-surface refinement using frozen fit observations only."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import sys
import time

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import scipy
from scipy.optimize import differential_evolution,minimize
from scipy.spatial.transform import Rotation
from check_official_sonar_coordinates import Geometry,load_beam_tables,beam_count
from fit_mortar_fixed_registration import read_obj,bbox,huber,interval_violation,arrsha

BASE=ROOT/'DataSet/sonar_fixed_registration_refinement'
PLAN=ROOT/'experiment/sonar-fixed-registration-refinement-plan.md'
MODELS={'100lbs':('100lbs_aircraft_bomb','2023-09-20_171105','target/100lbs'),
        'incindiary':('incindiary_grenade','2023-09-21_120653','target/incendiary'),
        'mortar_shell':('mortar_shell','2023-09-21_100927','target/mortar_shell')}
PARAMETER_SCALE=np.array([.25,.25,.25,180.,75.,180.])
SEEDS=[20261112,20261113,20261114]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def transform(parameters,origin):
    T=np.eye(4);T[:3,:3]=Rotation.from_euler('xyz',[parameters[5],parameters[4],parameters[3]],degrees=True).as_matrix()
    T[:3,3]=origin+parameters[:3]
    return T


def prepare_model(info):
    vertices,faces=read_obj(info['source'])
    similarity=np.asarray(info['mesh_to_target_similarity'])
    model=vertices@similarity[:3,:3].T+similarity[:3,3]
    triangles=model[faces]
    areas=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)/2
    face_ids=np.searchsorted(np.cumsum(areas),(np.arange(12000)+.5)/12000*areas.sum())
    random=np.random.default_rng(20261112).random((12000,2));root=np.sqrt(random[:,0])
    weights=np.c_[1-root,root*(1-random[:,1]),root*random[:,1]]
    sampled=np.einsum('ni,nij->nj',weights,triangles[face_ids])
    extremes=np.unique(np.r_[np.argmin(model,axis=0),np.argmax(model,axis=0)])
    sampled=np.r_[sampled,model[extremes]]
    dense=np.concatenate([model,triangles.mean(1),(triangles[:,0]+triangles[:,1])/2,
                          (triangles[:,1]+triangles[:,2])/2,(triangles[:,2]+triangles[:,0])/2])
    definition=dict(obj_path=info['source'],obj_sha256=sha(info['source']),raw_obj_to_model_similarity=similarity.tolist(),
                    nominal_length_m=info['nominal_length_m'],scale_m_per_obj_unit=info['scale_m_per_obj_unit'],
                    parameterization='unchanged frozen old PCA mesh_to_target; optimized fixed world_from_model',
                    sample_seed=20261112,sample_count=len(sampled),sampled_points_sha256=arrsha(sampled),
                    dense_count=len(dense),dense_points_sha256=arrsha(dense),vertex_count=len(model),triangle_count=len(faces),
                    dense_order='vertices, triangle centers, edge01, edge12, edge20 midpoints')
    return sampled,dense,definition


def adapt_observations(model,observations,companion):
    extras={r['sample']:r for r in companion.get('frames',[])} if companion else {}
    frames=[]
    for row in observations['frames']:
        selected=[];excluded=[]
        for p in row['points']:
            if p.get('eligible_for_main_curve',True) is not True:
                excluded.append(p);continue
            box=p.get('observation_box_raw_edges')
            if box is not None:
                window=[float(box[0]),float(box[2])];interval=[float(box[1]),float(box[3])]
                interpretation='frozen beam/range observation interval; intensity peak is not exact surface'
            elif p.get('near_range_bin_interval') is not None:
                uv=p['raw_uv_edge'];window=[float(uv[0])-1.5,float(uv[0])+1.5]
                interval=list(map(float,p['near_range_bin_interval']))
                interpretation='frozen near-range interval; witness is not exact physical surface'
            else:
                uv=p['raw_uv_edge'];window=[float(uv[0])-1.5,float(uv[0])+1.5]
                interval=[float(uv[1]),float(uv[1])]
                interpretation='frozen near-return ridge proxy; range error normalized by 4 bins'
            selected.append(dict(beam_window=window,range_interval=interval,witness_raw_uv_edge=p['raw_uv_edge'],
                                 interpretation=interpretation,source_point=p))
        if not selected:continue
        extra=extras.get(row['sample'],{})
        censored=bool(extra.get('possible_horizontal_fov_censoring',False) or row.get('possible_horizontal_fov_censoring',False) or row.get('possible_fov_truncation',False))
        edges=row.get('visible_echo_edge_intervals',row.get('lateral_visible_echo_edge_intervals_raw_u'))
        if edges is None:
            edges=dict(left=extra.get('echo_left_disappearance_beam_interval'),right=extra.get('echo_right_disappearance_beam_interval'))
        if censored:edges=dict(left=None,right=None)
        frames.append(dict(sample=row['sample'],points=selected,excluded_point_count=len(excluded),
                           weak_echo_edges=edges,fov_censored=censored,role='fit',
                           edges_interpretation='weak detection initialization only; never physical endpoints',
                           source_record=row))
    return dict(model_name=model,frames=frames,point_count=sum(len(r['points']) for r in frames),
                excluded_point_count=sum(r['excluded_point_count'] for r in frames),
                observation_semantics='near-surface acoustic approximation; no exact point correspondence')


class FrontFrame:
    def __init__(self,observation,metadata,world_from_sonar,beams):
        self.sample=observation['sample'];self.observation=observation
        self.world_from_sonar=np.asarray(world_from_sonar);self.sonar_from_world=np.linalg.inv(self.world_from_sonar)
        self.geom=Geometry(metadata,beams,1000.)

    def project(self,points,T):
        combined=self.sonar_from_world@T;p=points@combined[:3,:3].T+combined[:3,3]
        ranges=np.linalg.norm(p,axis=1);beta=-np.degrees(np.arctan2(p[:,0],p[:,2]))
        elevation=np.degrees(np.arctan2(p[:,1],np.hypot(p[:,0],p[:,2])))
        visible=(p[:,2]>0)&(ranges>=self.geom.r0)&(ranges<=self.geom.data_range)&(beta>=self.geom.beams[0,1])&(beta<=self.geom.beams[-1,2])&(np.abs(elevation)<=7.)
        uv=self.geom.points_to_raw_edges(ranges,beta)
        return dict(uv=uv,visible=visible,ranges=ranges,beta=beta,elevation=elevation)

    def loss(self,projected,details=False):
        uv=projected['uv'][projected['visible']]
        errors=[];reports=[];edge_reports=[]
        if len(uv):
            order=np.argsort(uv[:,0]);support=uv[order];u=support[:,0];v=support[:,1]
        for point in self.observation['points']:
            lo,hi=point['beam_window'];middle=(lo+hi)/2
            if len(uv):
                left,right=np.searchsorted(u,[lo,hi],side='left')
                right=int(np.searchsorted(u,hi,side='right'))
                if right>left:
                    index=left+int(np.argmin(v[left:right]));beam_gap=0.;covered=True
                else:
                    index=int(np.argmin(np.abs(u-middle)));beam_gap=max(lo-u[index],u[index]-hi,0.)/1.5;covered=False
                predicted=[float(u[index]),float(v[index])]
                range_gap=interval_violation(predicted[1],point['range_interval'])/4.
            else:
                predicted=None;beam_gap=100.;range_gap=100.;covered=False
            errors.append(float(huber(range_gap)+huber(beam_gap)))
            if details:reports.append(dict(**point,predicted_near_surface_uv=predicted,beam_window_supported=covered,
                                           normalized_range_error=float(range_gap),normalized_missing_beam_error=float(beam_gap)))
        edges=[]
        for name,coordinate in [('left',0),('right',2)]:
            interval=self.observation['weak_echo_edges'].get(name)
            if interval is not None:
                predicted=None if not len(uv) else float(uv[:,0].min() if name=='left' else uv[:,0].max())
                gap=100. if predicted is None else interval_violation(predicted,interval)/4.
                edges.append(float(huber(gap)))
                if details:edge_reports.append(dict(name=name,interval=interval,predicted=predicted,normalized_gap=gap,
                                                    physical_boundary=False))
        front=float(np.mean(errors));edge=float(np.mean(edges)) if edges else 0.
        objective=front+.1*edge
        if not details:return objective
        return dict(objective=objective,near_surface_objective=front,weak_edge_objective=edge,weak_edge_weight=.1,
                    near_surface_points=reports,weak_visible_echo_edges=edge_reports,visible_support_count=len(uv))

    def summarize(self,points,T):
        projected=self.project(points,T);vis=projected['visible'];g=self.geom
        polar=g.points_to_polar_index(projected['ranges'][vis],projected['beta'][vis])+.5
        return dict(sample=self.sample,world_from_sonar=self.world_from_sonar.tolist(),geometry=g.description(),
                    visible_raw_bbox_7deg=bbox(projected['uv'][vis],g.w,g.h),visible_polar_bbox_7deg=bbox(polar,g.W,g.H),
                    full_raw_bbox=bbox(projected['uv']),bbox_padding_raw_beam_bin=0.,point_count=len(points),
                    **self.loss(projected,details=True))


def execute(model,observation_path,companion_path=None,freeze_path=None):
    observation_path=observation_path.resolve()
    companion_path=companion_path.resolve() if companion_path else None
    freeze_path=freeze_path.resolve() if freeze_path else None
    out=BASE/model
    if out.exists():raise RuntimeError('Preserve existing run directory: '+str(out))
    out.mkdir(parents=True)
    started=time.perf_counter()
    save(out/'run-state.json',dict(status='initializing',model_name=model))
    (out/'plan-before-fit.md').write_bytes(PLAN.read_bytes())
    (out/'solver-before-fit.py').write_bytes(Path(__file__).read_bytes())
    manifest_path=ROOT/'DataSet/camera_temporal_all/manifest-resolved.json';manifest=read(manifest_path)
    registry_path=ROOT/'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json';registry=read(registry_path)
    calibration_path=ROOT/'DataSet/sonar_model_registration_consistency/calibration-versions.json'
    statics={k:np.asarray(v) for k,v in read(calibration_path)['versions']['release_current']['parent_from_child_matrices'].items()}
    observations=read(observation_path);companion=read(companion_path) if companion_path else None
    if model=='100lbs':
        assert sha(observation_path)=='3c4ef2bec5bd216880f778a54fd18bdb2ec2f3c880174e9cc023b442317df257'
    if freeze_path:
        frozen=read(freeze_path)
        if frozen.get('curves_sha256'):assert sha(observation_path)==frozen['curves_sha256']
        if companion_path and frozen.get('observation_sha256'):assert sha(companion_path)==frozen['observation_sha256']
    adapted=adapt_observations(model,observations,companion);save(out/'adapted-fit-observations.json',adapted)
    category,recording,target_frame=MODELS[model];allowed={r['sample']:r for r in manifest['items']}
    assert len(adapted['frames'])>=2
    samples=[];records={};paths={manifest_path,registry_path,calibration_path,observation_path,out/'plan-before-fit.md',out/'solver-before-fit.py',
                  ROOT/'tools/check_official_sonar_coordinates.py',ROOT/'tools/fit_mortar_fixed_registration.py',
                  ROOT/'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'}
    if companion_path:paths.add(companion_path)
    if freeze_path:paths.add(freeze_path)
    for observation in adapted['frames']:
        row=allowed[observation['sample']]
        assert row['recording']==recording and row['category']==category and row.get('paired_role') in (None,'train','val','val_id')
        directory=Path(row['original_image']).parent.parent
        records[row['sample']]=row;samples.append(row['sample'])
        paths.update([directory/'aris_frame_meta.csv',directory/'gantry.csv',directory/'aris_raw'/f"{row['aris_frame']:04d}.pgm"])
    info=registry['models'][model];paths.add(Path(info['source']))
    assert sha(info['source'])==info['source_sha256']
    before={str(p):sha(p) for p in sorted(paths)};save(out/'inputs-before.json',before)
    for observation in adapted['frames']:
        row=records[observation['sample']];directory=Path(row['original_image']).parent.parent
        original=observation['source_record']
        raw_path=directory/'aris_raw'/f"{row['aris_frame']:04d}.pgm"
        if original.get('raw_source_sha256'):assert before[str(raw_path)]==original['raw_source_sha256']
        declared=original.get('source')
        if isinstance(declared,dict):
            for kind in ('raw_source','metadata','gantry'):
                item=declared.get(kind)
                if item:assert before[item['path']]==item['sha256']
    sampled,dense,definition=prepare_model(info);save(out/'model-definition.json',definition)
    np.save(out/'sampled-model-points.npy',sampled,allow_pickle=False)
    origin=statics[target_frame][:3,3];tables=load_beam_tables();frames=[]
    directory=Path(next(iter(records.values()))['original_image']).parent.parent
    wanted={r['aris_frame'] for r in records.values()}
    metadata={int(r['FrameIndex']):r for r in csv.DictReader((directory/'aris_frame_meta.csv').open(encoding='utf-8-sig',newline='')) if int(r['FrameIndex']) in wanted}
    gantry={int(r['aris_frame_idx']):r for r in csv.DictReader((directory/'gantry.csv').open(encoding='utf-8-sig',newline='')) if int(r['aris_frame_idx']) in wanted}
    for observation in adapted['frames']:
        row=records[observation['sample']];index=row['aris_frame'];m=metadata[index];g=gantry[index]
        assert int(m['FrameTime'])==row['aris_time_us']
        wa=np.eye(4);wa[:3,:3]=statics['setup/ar3'][:3,:3]@Rotation.from_euler('xyz',[float(m[k]) for k in ['SonarRoll','SonarTilt','SonarPan']],degrees=True).as_matrix()
        wa[:3,3]=np.array([float(g[k]) for k in 'xyz'])+statics['setup/ar3'][:3,3]
        frames.append(FrontFrame(observation,m,wa@statics['setup/aris']@statics['setup/sonar'],tables[beam_count(m['PingMode'])]))
    def objective(q):
        T=transform(np.asarray(q)*PARAMETER_SCALE,origin)
        return float(np.mean([f.loss(f.project(sampled,T)) for f in frames]))
    candidates=[];baseline=objective(np.zeros(6))
    save(out/'run-state.json',dict(status='fitting',model_name=model,baseline_fit_objective=baseline,fit_samples=samples))
    for seed in SEEDS:
        cid=f'de-{seed}';calls=0;trace=[];best=float('inf');stage_started=time.perf_counter()
        def tracked(q):
            nonlocal calls,best
            calls+=1;value=objective(q)
            if value<best:
                best=value;trace.append(dict(call=calls,objective=value,parameters=(q*PARAMETER_SCALE).tolist()))
            return value
        generation=[0]
        def callback(q,convergence):
            generation[0]+=1
            if generation[0]%20==0:print(model,cid,'generation',generation[0],'best',best,'calls',calls,flush=True)
            return False
        failure=None;de=None;polish=None;q=np.zeros(6)
        try:
            de=differential_evolution(tracked,[(-1.,1.)]*6,seed=seed,popsize=8,maxiter=120,tol=1e-7,
                                      polish=False,strategy='best1bin',mutation=(.5,1.),recombination=.7,
                                      init='latinhypercube',x0=np.zeros(6),callback=callback,workers=1,updating='immediate')
            q=de.x.copy()
            polish=minimize(tracked,de.x,method='Powell',bounds=[(-1.,1.)]*6,
                            options=dict(maxfev=2000,xtol=1e-4,ftol=1e-6))
            if np.isfinite(polish.fun) and polish.fun<de.fun:q=polish.x.copy()
        except Exception as exc:failure=repr(exc)
        T=transform(q*PARAMETER_SCALE,origin)
        coarse=[f.summarize(sampled,T) for f in frames];full=[f.summarize(dense,T) for f in frames]
        fit_cost=float(np.mean([m['objective'] for m in coarse]));dense_cost=float(np.mean([m['objective'] for m in full]))
        de_data=None if de is None else dict(success=bool(de.success),message=str(de.message),fun=float(de.fun),nit=int(de.nit),nfev=int(de.nfev),
                     parameters=(de.x*PARAMETER_SCALE).tolist(),population_parameters=(de.population*PARAMETER_SCALE).tolist(),population_energies=de.population_energies.tolist())
        polish_data=None if polish is None else dict(success=bool(polish.success),message=str(polish.message),fun=float(polish.fun),nit=int(polish.nit),nfev=int(polish.nfev),parameters=(polish.x*PARAMETER_SCALE).tolist())
        entry=dict(candidate_id=cid,id=cid,seed=seed,parameters=(q*PARAMETER_SCALE).tolist(),world_from_model=T.tolist(),
                   world_from_obj_similarity=(T@np.asarray(definition['raw_obj_to_model_similarity'])).tolist(),
                   fit_objective=fit_cost,dense_fit_objective=dense_cost,fit_metrics_coarse=coarse,fit_metrics_dense=full,
                   de=de_data,powell=polish_data,failure=failure,actual_objective_calls=calls,improvement_trace=trace,
                   elapsed_seconds=time.perf_counter()-stage_started,approved_for_training_gt=False)
        candidates.append(entry);save(out/(cid+'.json'),entry)
        assert all(sha(p)==expected for p,expected in before.items())
        print('FINISHED',model,cid,'coarse',fit_cost,'dense',dense_cost,'calls',calls,flush=True)
    best=min(candidates,key=lambda c:c['fit_objective'])
    common=dict(run='sonar_fixed_registration_refinement',model_name=model,fit_sample_ids=samples,check_used_for_selection=False,
                source_hashes=before,observation_sha256=sha(observation_path),solver_sha256=sha(out/'solver-before-fit.py'),
                model=definition,raw_obj_to_model_similarity=definition['raw_obj_to_model_similarity'],
                fixed_imaging=dict(beta='-degrees(atan2(x,z))',main_elevation_limit_deg=7.,raw_bbox_padding=0.,polar_bbox_padding=0.),
                parameter_order=['dx_m','dy_m','dz_m','yaw_deg','pitch_deg','roll_deg'],origin_world_m=origin.tolist(),target_frame=target_frame,
                objective='frame mean [point mean Huber(range/4)+Huber(missing beam/1.5) + 0.1 weak echo edge Huber(interval gap/4)]',
                baseline_old_pca_fit_objective=baseline,candidates=candidates,candidate_id=best['candidate_id'],
                fit_objective=best['fit_objective'],dense_fit_objective=best['dense_fit_objective'],world_from_model=best['world_from_model'],
                world_from_obj_similarity=best['world_from_obj_similarity'],approved_for_training_gt=False,physical_registration_validated=False,
                fixed_detection_candidate_produced=True,selection_rule='lowest sampled fit objective only; dense and check not used for selection',
                scipy_version=scipy.__version__,numpy_version=np.__version__,elapsed_seconds=time.perf_counter()-started)
    save(out/'fit-results.json',common|dict(status='fit_complete'))
    save(out/'freeze-model.json',common|dict(status='frozen_for_cross_recording_check'))
    save(out/'inputs-after.json',{str(p):sha(p) for p in paths})
    save(out/'freeze-model.sha256.json',dict(path=str(out/'freeze-model.json'),sha256=sha(out/'freeze-model.json')))
    save(out/'run-state.json',dict(status='frozen',model_name=model,candidate_id=best['candidate_id'],fit_objective=best['fit_objective'],
                                 dense_fit_objective=best['dense_fit_objective'],input_hashes_unchanged=True,elapsed_seconds=time.perf_counter()-started))
    print('FROZEN',model,best['candidate_id'],best['fit_objective'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=list(MODELS),required=True)
    parser.add_argument('--observations',type=Path,required=True);parser.add_argument('--companion',type=Path);parser.add_argument('--freeze',type=Path)
    args=parser.parse_args()
    try:execute(args.model,args.observations,args.companion,args.freeze)
    except Exception as exc:
        out=BASE/args.model
        if out.exists():save(out/'failure.json',dict(error=repr(exc),stage='fit',preserve_all_partial_outputs=True))
        raise
