"""Three simultaneous faces, rigid bundle fit and held-face prediction."""
from fit_sonar_tag_camera_models import *

IDS = [141, 20, 21]
OUTM = OUT / 'multiface'
PLAN = ROOT / 'experiment/sonar-tag-multiface-plan.md'


def geom(g):
    h = g.reshape(2, 7)
    return np.vstack([OBJ, *((OBJ * np.exp(v[6])) @ Rotation.from_rotvec(v[:3]).as_matrix().T + v[3:6] for v in h)])


def camera(q):
    f = float(np.exp(q[0]))
    return dict(name='image_fit_shared_focal_brown', kind='brown', K=[[f,0,q[1]],[0,f,q[2]],[0,0,1]], D=[q[3],q[4],0,0,0])


def forward(points, poses, model):
    poses = np.atleast_2d(poses)
    p = np.einsum('nij,pj->npi', Rotation.from_rotvec(poses[:,:3]).as_matrix(), points) + poses[:,None,3:]
    xy = p[:,:,:2] / p[:,:,2,None]
    r2 = np.sum(xy**2,axis=-1)
    d = np.asarray(model['D'])
    if model['kind']=='fisheye':
        r = np.sqrt(r2); t = np.arctan(r); t2 = t*t
        fac = np.divide(t,r,out=np.ones_like(t),where=r>1e-12)*(1+t2*(d[0]+t2*(d[1]+t2*(d[2]+t2*d[3]))))
        xy *= fac[:,:,None]
    elif model['kind']=='brown': xy *= (1+r2*(d[0]+r2*d[1]))[:,:,None]
    k = np.asarray(model['K']); return xy*np.diag(k)[:2]+k[:2,2], p[:,:,2]


def initial(r, model):
    p = [np.array(pose_solutions(np.array(c), model)[0]['parameters']) for c in np.array(r['corners']).reshape(3,4,2)]
    a = Rotation.from_rotvec(p[0][:3]); out=[]
    for v in p[1:]:
        scale = np.clip(p[0][5]/v[5], .65, 1.55)
        out.append(np.r_[(a.inv()*Rotation.from_rotvec(v[:3])).as_rotvec(), a.inv().apply(scale*v[3:]-p[0][3:]), np.log(scale)])
    return p[0],out


def fit(rows, model, free=False):
    n=len(rows); obs=np.array([r['corners'] for r in rows]); init=[initial(r,model) for r in rows]; s=np.array([a[1] for a in init]); g=np.median(s,axis=0)
    for i in range(2):g[i,:3]=Rotation.from_rotvec(s[:,i,:3]).mean().as_rotvec()
    q=np.r_[np.log(np.mean(np.diag(np.asarray(model['K']))[:2])),np.asarray(model['K'])[:2,2],0,0] if free else np.array([])
    nq=len(q); ns=14+nq
    x=np.r_[g.ravel(),q,np.array([a[0] for a in init]).ravel()]
    lo=np.r_[np.tile([-7,-7,-7,-5,-5,-5,np.log(.5)],2),([np.log(400),480,270,-2,-3] if free else []),np.tile([-10,-10,-10,-100,-100,.05],n)]
    hi=np.r_[np.tile([7,7,7,5,5,5,np.log(2.)],2),([np.log(4000),1440,810,2,3] if free else []),np.tile([10,10,10,100,100,1000],n)]
    def residual(v):return (forward(geom(v[:14]),v[ns:].reshape(n,6),camera(v[14:ns]) if free else model)[0]-obs).reshape(n,24)
    def jac(v):
        y=residual(v); j=np.zeros((n*24,len(v))); eps=1e-6
        for i in range(ns):
            w=v.copy();w[i]+=eps;j[:,i]=((residual(w)-y)/eps).ravel()
        for i in range(6):
            w=v.copy();w[ns+i::6]+=eps;change=(residual(w)-y)/eps
            for k in range(n):j[24*k:24*k+24,ns+6*k+i]=change[k]
        return j
    opt=least_squares(lambda v:residual(v).ravel(),np.clip(x,lo+1e-7,hi-1e-7),jac=jac,bounds=(lo,hi),tr_solver='exact',max_nfev=250,ftol=1e-8,xtol=1e-8,gtol=1e-8,x_scale='jac')
    m=camera(opt.x[14:ns]) if free else model; p=geom(opt.x[:14]); poses=opt.x[ns:].reshape(n,6); pred,z=forward(p,poses,m)
    j=opt.jac;profile=[]
    for i in range(n):
        a=j[24*i:24*i+24,:ns];b=j[24*i:24*i+24,ns+6*i:ns+6*i+6];profile.append(a-b@np.linalg.lstsq(b,a,rcond=1e-8)[0])
    ss=np.linalg.svd(np.vstack(profile),compute_uv=False)
    return dict(model=m,fit_ids=[r['sample'] for r in rows],g=opt.x[:14].tolist(),points=p.tolist(),poses=poses.tolist(),fit_rms_px=float(np.sqrt(np.mean(np.sum((pred-obs)**2,axis=-1)))),success=bool(opt.success),message=opt.message,nfev=opt.nfev,optimality=float(opt.optimality),positive_depth=bool((z>0).all()),near_shared_bound=(((opt.x-lo)<.001*(hi-lo))|((hi-opt.x)<.001*(hi-lo)))[:ns].tolist(),profile_singular_values=ss.tolist())


def view_pose(p, xy, m):
    k=np.array(m['K']);d=np.array(m['D']); obs=np.ascontiguousarray(xy.reshape(-1,1,2));p=np.ascontiguousarray(p)
    if m['kind']=='fisheye':u=cv2.fisheye.undistortPoints(obs,k,d.reshape(4,1))
    elif m['kind']=='brown':u=cv2.undistortPoints(obs,k,d)
    else:u=cv2.undistortPoints(obs,k,None)
    if not np.isfinite(u).all():return None
    ok,rv,tv=cv2.solvePnP(p,u,np.eye(3),None,flags=cv2.SOLVEPNP_SQPNP)
    if not ok or tv[2,0]<=.05:return None
    def residual(v):return (forward(p,v,m)[0][0]-xy).ravel()
    ans=least_squares(residual,np.r_[rv.ravel(),tv.ravel()],max_nfev=60,bounds=([-np.inf]*5+[.05],[np.inf]*6));return ans.x if ans.success and (forward(p,ans.x,m)[1]>0).all() else None


def score(bundle, rows):
    p=np.array(bundle['points']);m=bundle['model'];out=[]
    for r in rows:
        xy=np.array(r['corners']);allpose=view_pose(p,xy,m);e=[]
        for face,t in enumerate(IDS):
            h=(np.arange(12)//4)==face; pose=view_pose(p[~h],xy[~h],m); pred,z=forward(p,pose,m) if pose is not None else (None,None)
            e.append(dict(tag=t,pose=pose.tolist() if pred is not None else None,errors_px=np.linalg.norm(pred[0,h]-xy[h],axis=-1).tolist() if pred is not None and (z>0).all() else None))
        out.append(dict(sample=r['sample'],held_faces=e,all_12_rms_px=float(np.sqrt(np.mean(np.sum((forward(p,allpose,m)[0][0]-xy)**2,axis=-1)))) if allpose is not None else None))
    vals=[x for r in out for e in r['held_faces'] for x in (e['errors_px'] or [])];summary=dict(views=len(rows),predicted_corners=len(vals),requested_corners=12*len(rows),median_px=float(np.median(vals)),p90_px=float(np.percentile(vals,90)),per_face={str(t):dict(n=len(v),median_px=float(np.median(v)),p90_px=float(np.percentile(v,90))) for t in IDS if (v:=[x for r in out for e in r['held_faces'] if e['tag']==t for x in (e['errors_px'] or [])])})
    return dict(views=out,summary=summary)


def angle(r):return float(np.degrees(Rotation.from_matrix(r).magnitude()))


def synth(rows, model):
    g=np.r_[[0,np.pi/2,0,-.64,0,-.64,np.log(.94)],[np.pi/2,0,0,0,.64,-.64,np.log(1.05)]];p=geom(g)
    # Known geometry, view sweep of roughly the real image scale.
    poses=np.array([[.28+.23*np.sin(t),.35+.22*np.cos(t),.21*np.sin(t*2),1.5*np.cos(t),.7*np.sin(t),12+2*np.cos(t)] for t in np.linspace(0,4,len(rows))]);rng=np.random.default_rng(892)
    xy,z=forward(p,poses,model); xy+=rng.normal(0,.2,xy.shape);assert (z>0).all()
    synthetic=[dict(r,corners=x.tolist()) for r,x in zip(rows,xy)];bundle=fit([r for r in synthetic if r['role']=='fit'],model);checks=[r for r in synthetic if r['role']=='check']; good=score(bundle,checks)
    neg=list(checks); v=np.array(neg[0]['corners']);v[:4]=np.array(neg[-1]['corners'])[:4];neg[0]=dict(neg[0],corners=v.tolist());bad=score(bundle,neg);a,b=good['views'][0]['held_faces'][0],bad['views'][0]['held_faces'][0]
    return dict(bundle=bundle,truth_points=p.tolist(),point_rmse=float(np.sqrt(np.mean(np.sum((p-np.array(bundle['points']))**2,axis=-1)))),check=good,negative_control=dict(sample=neg[0]['sample'],clean_errors_px=a['errors_px'],swapped_errors_px=b['errors_px'],unchanged_pose=a['pose']==b['pose']))


def main():
    assert not OUTM.exists();OUTM.mkdir();d=read(OUT/'detections.json');s=read(OUT/'selection.json');source={r['sample']:r for r in s['frames']};src={r['sample']:{t['id']:t for t in r['tags']} for r in d['frames']}; eligible=[]
    for sid,tags in src.items():
        if all(i in tags and tags[i]['minimum_edge_px']>=30 and tags[i]['border_clearance_px']>=5 for i in IDS):eligible.append(dict(sample=sid,aris_frame=source[sid]['aris_frame'],corners=[c for i in IDS for c in tags[i]['corners']]))
    first,last=eligible[0]['aris_frame'],eligible[-1]['aris_frame'];rows=[];prev=-1000
    for r in eligible:
        a=r['aris_frame']; block=min(5,int((a-first)/(last-first)*6))
        if a!=788 and a-prev<12:continue
        prev=a;rows.append(dict(r,block=block,role='fit' if block%2==0 and abs(a-788)>12 else 'check'))
    a,b=[s['recording']+'_'+k for k in ['0392','0788']];assert b in {r['sample'] for r in rows if r['role']=='check'}
    save(OUTM/'selection-before-fit.json',dict(tag_order=IDS,eligible=len(eligible),frames=rows,source_detection_sha256=sha(OUT/'detections.json'),plan_sha256=sha(PLAN)))
    fitrows=[r for r in rows if r['role']=='fit'];check=[r for r in rows if r['role']=='check'];models=fixed_models();out=[]
    z=lambda sid:np.array(source[sid]['world_from_camera'])[:3,:3]
    expected=z(b).T@z(a)
    byframe={r['aris_frame']:r['sample'] for r in s['frames']}
    sensitivity=[dict(offset_frames=i,published_angle_deg=angle(z(byframe[788+i]).T@z(byframe[392+i]))) for i in range(-12,13)]
    for initial_model,free in [(m,False) for m in models]+[(models[2],True)]:
        bnd=fit(fitrows,initial_model,free);m=bnd['model'];p=np.array(bnd['points']); ev=score(bnd,check); va=[np.array(pose_solutions(np.array(src[sid][141]['corners']),m)[0]['rotation_camera_from_tag']) for sid in [a,b]]
        both=va[1]@va[0].T; b_obs=next(r for r in ev['views'] if r['sample']==b); alt=b_obs['held_faces'][0]['pose']; alt_r=Rotation.from_rotvec(np.array(alt)[:3]).as_matrix()@va[0].T if alt else None
        normal=np.vstack([[0,0,1],Rotation.from_rotvec(np.array(bnd['g']).reshape(2,7)[:,:3]).apply([0,0,1])]); dot=np.clip(normal@normal.T,-1,1)
        result=dict(bundle=bnd,check=ev,face_normal_angles_deg=np.degrees(np.arccos(dot)).tolist(),anchors=dict(single141_angle_deg=angle(both),single141_difference_deg=angle(both@expected.T),held_141_at_0788_errors_px=b_obs['held_faces'][0]['errors_px'],twoface_0788_angle_deg=angle(alt_r) if alt is not None else None,twoface_0788_difference_deg=angle(alt_r@expected.T) if alt_r is not None else None))
        out.append(result);save(OUTM/(m['name']+'.json'),result);print(m['name'],bnd['fit_rms_px'],bnd['nfev'],bnd['success'],ev['summary'],result['anchors'],flush=True)
    split=[]
    for item in out[:3]:
        m=item['bundle']['model'];early=fit([r for r in fitrows if r['block'] in (0,2)],m);late=fit([r for r in fitrows if r['block']==4],m); aa,bb=[np.array(x['g']).reshape(2,7) for x in [early,late]]
        change=[angle(Rotation.from_rotvec(y[:3]).as_matrix()@Rotation.from_rotvec(x[:3]).as_matrix().T) for x,y in zip(aa,bb)]
        shift=np.linalg.norm(np.array(early['points'])-np.array(late['points']),axis=-1)
        row=dict(name=m['name'],early=early,late=late,rotation_change_deg=change,corner_change_in_tag141_side=shift.tolist(),max_corner_change_in_tag141_side=float(shift.max()));split.append(row);print('block',m['name'],change,shift.max(),flush=True)
    sy=synth(rows,models[2]);save(OUTM/'synthetic-control.json',sy);print('synthetic',sy['point_rmse'],sy['check']['summary'],sy['negative_control'],flush=True)
    save(OUTM/'results.json',dict(models=out,split_geometry=split,anchor_local_published_sensitivity=sensitivity,published_anchor_angle_deg=angle(expected),selection_sha256=sha(OUTM/'selection-before-fit.json'),script_sha256=sha(__file__),physical_calibration_approved=False))


if __name__=='__main__': main()
