import json, zipfile, pickletools, hashlib, pathlib, subprocess, statistics, ast, datetime
root=pathlib.Path(r'D:\agent_workspace\水下\声呐目标检测')
repo=root/'code/VSFusionDistill'
out=pathlib.Path(r'D:\agent_workspace\水下\声呐目标检测_workflow\复现\camera-baseline\evidence\implementation-audit.json')
manifest={'date':'2026-11-10','mode':'read-only explicit non-test whitelist; no model execution','git':{},'files':{},'metrics':{},'checkpoint':{}}
for key,args in [('head',['rev-parse','HEAD']),('branch',['rev-parse','--abbrev-ref','HEAD']),('status',['status','--porcelain=v1']),('latest_changed_files',['show','--format=','--name-only','HEAD'])]:
    manifest['git'][key]=subprocess.check_output(['git','--no-optional-locks',*args],cwd=repo,text=True,encoding='utf-8').strip()
files=[repo/'configs/repro_cmold/teachers/t_camera_s_yoloxs.py',repo/'configs/repro_cmold/teachers/t_camera_s_stretch_yoloxs.py',repo/'configs/repro_cmold/uxo_frame_split.py',repo/'tools/test.py',repo/'configs/_base_/schedules/schedule_f2.py',repo/'aodet/models/data_preprocessors/paired_preprocessor.py',repo/'aodet/datasets/transforms/paired_geometric.py',repo/'configs/f2/e11_bcam_camera_only_yoloxs.py',root/'configs/f2/e13_bcam_camera_only_dense_yoloxs.py']
for model,runid in [('t_camera_s','20261109_022400'),('t_camera_s_stretch','20261109_092259')]:
    run=repo/'work_dirs/repro_cmold_teacher'/model
    files.extend([run/'run_meta.txt',run/f'{model}_yoloxs.py',run/runid/'vis_data/config.py',run/runid/f'{runid}.log'])
    pth=run/'epoch_200.pth'
    with zipfile.ZipFile(pth) as zf:
        pkname=next(n for n in zf.namelist() if n.endswith('/data.pkl'))
        pk=zf.read(pkname)
    strings=[(pos, arg) for op,arg,pos in pickletools.genops(pk) if op.name in ('BINUNICODE','SHORT_BINUNICODE','UNICODE')]
    interesting=[{'offset':pos,'value':arg} for pos,arg in strings if arg in ('ema_state_dict','state_dict','mmengine_version','epoch','iter') or (isinstance(arg,str) and (arg.startswith('0.10.') or arg.startswith('module.camera_backbone.stem.conv.conv.weight')))]
    manifest['checkpoint'][model]={'path':str(pth),'bytes':pth.stat().st_size,'sha256':hashlib.file_digest(pth.open('rb'),'sha256').hexdigest(),'zip_pickle':pkname,'pickle_bytes':len(pk),'selected_string_opcodes':interesting,'method':'pickletools.genops only; no unpickling, torch.load or tensor/model execution'}
for name,rel in [('camera','repro_cmold/t_camera_s/eval_val'),('p1_mismatch','repro_cmold/t_camera_s/eval_val_stretch'),('p2_stretch','repro_cmold/t_camera_s_stretch/eval_val'),('e13_matching_geometry','xeval/e13cam_on_ourval_stretch')]:
    folder=repo/'results'/rel
    summary=json.loads((folder/'ap_summary.json').read_text())
    breakdown=json.loads((folder/'ap_breakdown.json').read_text())
    pooled=next(r for r in breakdown if r['branch']=='camera' and r['level']=='d0' and r['gt']=='all' and r['recording']=='all' and r['category']=='all')
    perrec=[r for r in breakdown if r['branch']=='camera' and r['level']=='d0' and r['gt']=='all' and r['recording']!='all' and r['category']=='all']
    predfile=folder/'pred.camera.d0.json'
    preds=json.loads(predfile.read_text()) if predfile.exists() else None
    assert all(abs(summary[0][k]-pooled[k])<1e-12 for k in ('AP','AP50','AP75','AR@100'))
    manifest['metrics'][name]={'summary':summary,'pooled':pooled,'recordings':len(perrec),'per_recording_AP_arithmetic_mean':statistics.mean(r['AP'] for r in perrec),'worst_recording':min(perrec,key=lambda r:r['AP']),'zero_AP_recordings':[r['recording'] for r in perrec if r['AP']==0],'pred_json_count':len(preds) if preds is not None else None}
    files.extend([folder/'ap_summary.json',folder/'ap_breakdown.json'])
    if predfile.exists(): files.append(predfile)
for f in files:
    manifest['files'][str(f)]={'bytes':f.stat().st_size,'sha256':hashlib.file_digest(f.open('rb'),'sha256').hexdigest()}
out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'git':manifest['git'],'checkpoints':manifest['checkpoint'],'metrics':{k:{'AP':v['summary'][0]['AP'],'AP50':v['summary'][0]['AP50'],'recordings':v['recordings'],'predictions':v['pred_json_count'],'zero_AP_recordings':v['zero_AP_recordings']} for k,v in manifest['metrics'].items()}},ensure_ascii=False,indent=2))


# Record exact framework source actually visible in the evaluation interpreter.
local_lib=pathlib.Path(r'\\wsl.localhost\Ubuntu-22.04\home\ty\mycode\VSFusionDistill\.venv-gpu\lib\python3.10\site-packages\mmengine')
wf=pathlib.Path(r'D:\agent_workspace\水下\声呐目标检测_workflow')
manifest['framework_sources']={}
for local_rel, saved_name in [('hooks/ema_hook.py','ema_hook_v0.10.7.py'),('runner/checkpoint.py','checkpoint_v0.10.7.py')]:
    local=local_lib/local_rel
    saved=wf/'related_work/mmengine/source'/saved_name
    a=hashlib.file_digest(local.open('rb'),'sha256').hexdigest()
    b=hashlib.file_digest(saved.open('rb'),'sha256').hexdigest()
    manifest['framework_sources'][local_rel]={'installed_path':str(local),'official_url':'https://raw.githubusercontent.com/open-mmlab/mmengine/v0.10.7/mmengine/'+local_rel,'local_copy':str(saved),'installed_sha256':a,'downloaded_sha256':b,'identical':a==b}

# Resolve only data expressions in the already resolved configs, without executing them.
def data_expr(n,env):
    if isinstance(n,ast.Constant): return n.value
    if isinstance(n,ast.Name): return env[n.id]
    if isinstance(n,(ast.List,ast.Tuple)): return [data_expr(x,env) for x in n.elts]
    if isinstance(n,ast.Dict): return {data_expr(k,env):data_expr(v,env) for k,v in zip(n.keys,n.values)}
    if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='dict' and not n.args:
        return {k.arg:data_expr(k.value,env) for k in n.keywords}
    raise ValueError(ast.dump(n))
def config_data(path):
    env={}
    for n in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            env[n.targets[0].id]=data_expr(n.value,env)
        elif isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant): pass
        else: raise ValueError(ast.dump(n))
    return env
def diff_data(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        r=[]
        for k in sorted(set(a)|set(b)):
            if k not in a or k not in b: r.append({'path':path+'.'+str(k),'before':a.get(k),'after':b.get(k)})
            else: r.extend(diff_data(a[k],b[k],path+'.'+str(k)))
        return r
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        return [x for i,(u,v) in enumerate(zip(a,b)) for x in diff_data(u,v,path+f'[{i}]')]
    return [] if a==b else [{'path':path,'before':a,'after':b}]
a=config_data(repo/'work_dirs/repro_cmold_teacher/t_camera_s/t_camera_s_yoloxs.py')
b=config_data(repo/'work_dirs/repro_cmold_teacher/t_camera_s_stretch/t_camera_s_stretch_yoloxs.py')
keys=['model','optim_wrapper','param_scheduler','train_cfg','train_dataloader','test_dataloader','custom_hooks','default_hooks','randomness']
manifest['p2_functional_config_diff']=[x for k in keys for x in diff_data(a.get(k),b.get(k),k)]
out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'framework_sources':manifest['framework_sources'],'p2_config_diff':manifest['p2_functional_config_diff']},ensure_ascii=False,indent=2))

# Actual reported terminal LR, rather than assuming configured eta_min was reached.
import re
log_path=repo/'work_dirs/repro_cmold_teacher/t_camera_s/20261109_022400/20261109_022400.log'
terminal=[]
for line_no,line in enumerate(log_path.read_text(encoding='utf-8').splitlines(),1):
    if 'Epoch(train) [200]' in line:
        match=re.search(r'base_lr: ([0-9.e+-]+) lr: ([0-9.e+-]+)',line)
        if match: terminal.append({'line':line_no,'base_lr':float(match[1]),'lr':float(match[2])})
manifest['terminal_lr']={'log':str(log_path),'configured_eta_min':0.00125*0.05,'last_reported_epoch200':terminal[-1],'cosine_begin_epoch':5,'cosine_end_epoch':185,'cosine_T_max':185,'constant_tail_factor':1}
out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
