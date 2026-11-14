"""Independently confirm training scene coverage; never alter candidate members."""
from expand_paired_recording_pool import *

BASE=ROOT/'DataSet/scene_stratified_mortar_recovered_candidate'
DEST=ROOT/'DataSet/train_scene_coverage_confirmation'
ROLES=('train','val','test')
def scene(r):return '|'.join(r[k] for k in ('category','placement','trajectory'))
def exact(r):return '|'.join(str(r[k]) for k in ('category','placement','trajectory','z','tilt','roll','pan'))

def main():
    DEST.mkdir(exist_ok=True);assert not (DEST/'results.json').exists(),'Preserve completed audit'
    paths=[BASE/'manifest.json',BASE/'recordings.json',BASE/'protocol.json',BASE/'scene-coverage.json',OUT/'inventory.json',
       ROOT/'DataSet/scene_stratified_recording_candidate/source-shortfalls.json',DATA/'data_processed/matches.csv',DATA/'uxo-full/split_manifest.json',
       ROOT/'experiment/archive/train-scene-coverage-confirmation-plan.md']
    fixed={str(p):sha(p) for p in paths};items=read(paths[0]);rs=read(paths[1]);inventory=read(paths[4]);extra=read(paths[5])['additional_metadata_only_sources']
    pool=inventory+extra;assert len(pool)==len({r['recording'] for r in pool})==62
    legacy=read(paths[7])['recordings'];matches={Path(r['aris_file']).name:r for r in csv.DictReader(paths[6].open(encoding='utf-8-sig'))}
    rmap={r['recording']:r for r in rs};train=[r for r in rs if r['role']=='train'];groups=defaultdict(set)
    for r in pool:
        assert legacy[r['recording']]['split']!='test'
        raw=nominal(matches[r['recording']]['notes'])
        for k in ('placement','trajectory','z','tilt','roll','pan'):assert r[k]==raw[k],(r['recording'],k)
    for r in rs:
        assert any(t['recording']==r['recording'] for t in pool)
        raw=nominal(matches[r['recording']]['notes'])
        for k in ('placement','trajectory','z','tilt','roll','pan'):assert r[k]==raw[k]
        groups[r['group_id']].add(r['role'])
    assert len(groups)==31 and all(len(v)==1 for v in groups.values())
    counts=defaultdict(Counter)
    for x in items:
        r=rmap[x['recording']];assert x['role']==r['role'] and x['scene_id']==scene(r) and x['membership']=='selected'
        counts[x['scene_id']][x['role']]+=1
    assert len(items)==4081 and sum(c['train'] for c in counts.values())==2472
    train_scenes={scene(r) for r in train};candidate_scenes={scene(r) for r in rs};pool_scenes={scene(r) for r in pool}
    assert train_scenes==candidate_scenes==pool_scenes and len(train_scenes)==8
    current_coverage={c['scene_id']:c for c in read(BASE/'scene-coverage.json')};table=[]
    for sid in sorted(pool_scenes):
        rr=[r for r in rs if scene(r)==sid];tr=[r for r in train if scene(r)==sid]
        row=dict(scene_id=sid,name=current_coverage[sid]['name'],
            train_recordings=[r['recording'] for r in tr],train_source_groups=len({r['group_id'] for r in tr}),
            role_pairs={role:counts[sid][role] for role in ROLES},
            known_pool_recordings=[r['recording'] for r in pool if scene(r)==sid],train_present=bool(tr))
        table.append(row)
        for role in ROLES:assert row['role_pairs'][role]==current_coverage[sid]['role_pairs'][role]
    missing=[]
    for r in rs:
        if r['role']=='train':continue
        tt=[t for t in train if scene(t)==scene(r)]
        fields={k:dict(holdout_value=r[k],training_values=sorted({t[k] for t in tt})) for k in ('z','tilt','roll','pan','transmit') if r[k]!='unknown' and r[k] not in {t[k] for t in tt}}
        settings={k:sorted(set(v)-{a for t in tt for a in t['settings'][k]}) for k,v in r['settings'].items()}
        settings={k:v for k,v in settings.items() if v}
        if fields or settings:missing.append(dict(recording=r['recording'],role=r['role'],scene_id=scene(r),missing_fields=fields,missing_setting_values=settings))
    primary_current={exact(r) for r in rs};primary_train={exact(r) for r in train};primary_pool={exact(r) for r in pool}
    exactmissing=[dict(condition=e,recordings=[r['recording'] for r in rs if exact(r)==e],roles=sorted({r['role'] for r in rs if exact(r)==e})) for e in sorted(primary_current-primary_train)]
    cocochecks={}
    for role in ROLES:
        xs={x['sample']:x for x in items if x['role']==role}
        assert (BASE/f'{role}-selected.txt').read_text(encoding='utf-8').splitlines()==list(xs)
        for mod in ('camera','sonar'):
            path=BASE/mod/f'coco_{role}.json';fixed[str(path)]=sha(path);co=read(path)
            assert len(co['images'])==len(co['annotations'])==len(xs)
            assert {i['sample'] for i in co['images']}==set(xs)
            for i in co['images']:
                x=xs[i['sample']];assert i['recording']==x['recording'] and i['scene']==x['scene_id'] and i['file_name']==x[mod+'_image']
            cocochecks[f'{mod}_{role}']=dict(images=len(xs),scenes=len({x['scene_id'] for x in xs.values()}))
    result=dict(passed=True,candidate=str(BASE),known_non_original_test_recordings=62,candidate_recordings=37,train_recordings=21,train_pairs=2472,
       scene_definition=['category','placement','trajectory'],known_pool_scenes=len(pool_scenes),candidate_scenes=len(candidate_scenes),train_scenes=len(train_scenes),
       missing_known_pool_scenes_in_train=sorted(pool_scenes-train_scenes),holdout_scenes_absent_from_train=sorted(candidate_scenes-train_scenes),
       scene_coverage=table,exact_nominal_condition_definition=['category','placement','trajectory','z','tilt','roll','pan'],
       known_pool_exact_conditions=len(primary_pool),candidate_exact_conditions=len(primary_current),train_exact_conditions=len(primary_train),
       candidate_exact_conditions_absent_from_train=exactmissing,holdout_recordings_with_missing_marginal_fields_or_settings=missing,
       original_notes_nominal_fields_checked=True,all_six_coco_and_lists_checked=cocochecks,recording_and_source_group_disjoint=True,
       source_hashes_unchanged=True,members_labels_or_roles_changed=False,original_test_content_opened=False,training=False,inference=False,
       physical_pose_all_coverage_certified=False,user_approval_scope='Candidate direction accepted; user requested train scene coverage confirmation, not individual box/expert or sync certification, not training authorization',input_sha256=fixed)
    for p,h in fixed.items():assert sha(p)==h,p
    save(DEST/'results.json',result);csvout(DEST/'scene-coverage.csv',table)
    print(json.dumps({k:result[k] for k in ['passed','train_pairs','known_non_original_test_recordings','train_scenes','known_pool_scenes','candidate_exact_conditions','train_exact_conditions','missing_known_pool_scenes_in_train','holdout_scenes_absent_from_train','holdout_recordings_with_missing_marginal_fields_or_settings']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
