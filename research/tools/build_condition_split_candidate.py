import csv
from collections import Counter,defaultdict
import hashlib
import html
import itertools
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
DATA=Path('D:/pby') if os.name=='nt' else Path('/mnt/d/pby')
OUT=ROOT/'DataSet/paired_recording_condition_coverage_candidate'
SEED=42
CLASS_NAMES={'100lbs_aircraft_bomb':'炸弹','mortar_shell':'迫击炮','incindiary_grenade':'燃烧弹'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())
def hashkey(value):return hashlib.sha256(f'{SEED}|{value}'.encode()).hexdigest()
def number(notes,key):
    match=re.search(r'\b'+key+r'\s*:\s*(-?\d+(?:\.\d+)?)',notes,re.I)
    return match[1] if match else 'unknown'
def writecsv(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    OUT.mkdir(exist_ok=True)
    assert not (OUT/'manifest.json').exists(),'Do not overwrite candidate; create a separate version'
    old=ROOT/'DataSet/paired_recording_split'
    source_paths=[old/'recordings.csv',old/'manifest.json',DATA/'data_processed/matches.csv']
    inputs={str(p):sha(p) for p in source_paths}
    recordings=list(csv.DictReader(source_paths[0].open(encoding='utf-8-sig')))
    items=json.loads(source_paths[1].read_text(encoding='utf-8'))
    byrec=defaultdict(list)
    for x in items:byrec[x['recording']].append(x)
    bycond=defaultdict(list); audit=[]
    for r in recordings:
        rec=r['recording'];notes=r['notes']
        placement='floor' if '(floor)' in notes.lower() else 'standard'
        trajectory='ellipse' if 'ellipse' in notes.lower() else 'flyby' if 'flyby' in notes.lower() else 'L_to_R' if 'l to r' in notes.lower() else 'unknown'
        z,tilt,roll,pan=[number(notes,k) for k in ['z','tilt','roll','pan']]
        # Missing pan is retained as unknown, never inferred as physically zero.
        primary='|'.join([placement,trajectory,'z='+z,'tilt='+tilt,'roll='+roll,'pan='+pan])
        roots=[p/rec for p in (DATA/'uxo-full/extracted/recordings').iterdir() if p.is_dir() and (p/rec).is_dir()]
        assert len(roots)==1,(rec,roots)
        meta=roots[0]/'aris_frame_meta.csv';notespath=roots[0]/'notes.txt'
        inputs[str(meta)]=sha(meta);inputs[str(notespath)]=sha(notespath)
        selected=[x for x in byrec[rec] if x['membership']=='selected'];assert len(selected)==100
        frameids={int(x['sample'].rsplit('_',1)[1]) for x in selected}
        with meta.open(encoding='utf-8-sig',newline='') as f:
            frames=[x for x in csv.DictReader(f) if int(x['FrameIndex']) in frameids]
        assert len(frames)==100,(rec,len(frames))
        def values(field):return sorted({x[field] for x in frames},key=float)
        def interval(field):
            vs=[float(x[field]) for x in frames];return [min(vs),max(vs)]
        settings={k:values(k) for k in ['ReceiverGain','SamplesPerBeam','SamplePeriod','FrequencyHiLow','Enable150V']}
        # Exported COCO identity is matched by sample name; no model metrics used.
        boxes=[]
        for x in selected:
            label=roots[0]/'labels'/f"{x['sample']}.json"
            # Use delivered original camera labels; upstream label directory layouts vary.
            label=ROOT/'DataSet/paired_assistant_truncated_review/export/camera/original_labels'/f"{x['sample']}.json"
            a=json.loads(label.read_text());boxes.append(a)
        record=dict(recording=rec,category=r['category'],group_id=r['group_id'],old_role=r['role'],placement=placement,trajectory=trajectory,
                    nominal_z=z,nominal_tilt=tilt,nominal_roll=roll,nominal_pan=pan,primary_condition=primary,
                    selected=100,reserve=int(r['reserve']),notes=notes,transmit_note='Min' if 'min transmit' in notes.lower() else 'Max' if 'max transmit' in notes.lower() else 'unknown',
                    notes_gain=re.search(r'(\d+)\s*dB',notes,re.I)[1] if re.search(r'(\d+)\s*dB',notes,re.I) else 'unknown',
                    sonar_settings=settings,selected_frame_min=min(frameids),selected_frame_max=max(frameids),
                    selected_duration_s=(max(int(x['FrameTime']) for x in frames)-min(int(x['FrameTime']) for x in frames))/1e6,
                    selected_pan_values=[float(x['SonarPan']) for x in frames],selected_pan_range=interval('SonarPan'),selected_tilt_range=interval('SonarTilt'),selected_roll_range=interval('SonarRoll'),
                    window_start_range=interval('WindowStart'),window_length_range=interval('WindowLength'),
                    camera_bottom_touch=sum(a['y_max']>=359 for a in boxes),camera_any_boundary_touch=sum(a['x_min']<=1 or a['y_min']<=1 or a['x_max']>=639 or a['y_max']>=359 for a in boxes),
                    history='all_recordings_previously_developed;old_test_results_inspected',source_metadata=str(meta))
        audit.append(record);bycond[r['category'],primary].append(record)
    newroles={}; search=[]
    for cat in sorted(CLASS_NAMES):
        rs=[r for r in audit if r['category']==cat]
        groups=sorted({r['group_id'] for r in rs}); group_rows={g:[r for r in rs if r['group_id']==g] for g in groups}
        allconds={r['primary_condition'] for r in rs}
        def secondary(rows):
            tags=set()
            for r in rows:
                tags.add('transmit:'+r['transmit_note'])
                for key,vs in r['sonar_settings'].items():tags.update(key+':'+v for v in vs)
            return tags
        allsettings=secondary(rs);candidates=[]
        def pan_support(hold,training):
            peers=[t for t in training if t['primary_condition']==hold['primary_condition']]
            values=[v for t in peers for v in t['selected_pan_values']]
            def dist(a,b): return abs((a-b+180)%360-180)
            count=sum(any(dist(v,t)<=5 for t in values) for v in hold['selected_pan_values'])
            return count
        for n in range(1,len(groups)-1):
            for chosen in itertools.combinations(groups,n):
                train=[r for g in chosen for r in group_rows[g]]
                if {r['primary_condition'] for r in train}!=allconds:continue
                rest=[g for g in groups if g not in chosen]
                if len(rest)<2:continue
                if allsettings-secondary(train):continue
                support=[pan_support(r,train) for r in rs if r['group_id'] in rest]
                if any(count<95 for count in support):continue
                score=(len(train),sum(100-count for count in support),hashkey(cat+'|'+'|'.join(chosen)))
                candidates.append((score,chosen,rest))
        assert candidates,cat
        score,chosen,rest=min(candidates)
        rest.sort(key=lambda g:hashkey(cat+'|holdout|'+g))
        # Balanced val/test counts; odd extra independent group goes to test.
        nv=len(rest)//2;val=set(rest[:nv]);test=set(rest[nv:])
        for r in rs:newroles[r['recording']]='train' if r['group_id'] in chosen else 'val' if r['group_id'] in val else 'test'
        search.append(dict(category=cat,feasible_train_subsets=len(candidates),chosen_train_groups=list(chosen),objective_train_recordings=score[0],secondary_values_missing_in_train=sorted(allsettings-secondary([r for r in rs if newroles[r['recording']]=='train']))))
    for r in audit:
        r['role']=newroles[r['recording']]
        cond=bycond[r['category'],r['primary_condition']]
        r['condition_recordings']=len(cond)
        r['condition_groups']=len({x['group_id'] for x in cond})
        r['same_condition_pan_support_count']=pan_support(r,[t for t in audit if t['category']==r['category'] and newroles[t['recording']]=='train']) if newroles[r['recording']]!='train' else 100
        r['reason']='unique_source_group_train_only' if r['condition_groups']==1 else 'train_condition_representative' if r['role']=='train' else 'repeated_condition_recording_holdout'
    coverage=[]
    for (cat,key),rs in sorted(bycond.items()):
        counts={role:sum(newroles[r['recording']]==role for r in rs) for role in ['train','val','test']}
        assert counts['train']>=1
        coverage.append(dict(category=cat,condition=key,total_recordings=len(rs),source_groups=len({r['group_id'] for r in rs}),**counts,recordings=[r['recording'] for r in rs]))
    overlay=[dict(x,old_role=x['role'],role=newroles[x['recording']]) for x in items]
    for role in ['train','val','test']:
        for membership in ['selected','reserve']:
            names=sorted(x['sample'] for x in overlay if x['role']==role and x['membership']==membership)
            (OUT/f'{role}-{membership}.txt').write_bytes(('\n'.join(names)+'\n').encode())
    for group in {r['group_id'] for r in audit}:assert len({r['role'] for r in audit if r['group_id']==group})==1
    assert len(overlay)==3398 and sum(x['membership']=='selected' for x in overlay)==3000
    for mod in ['camera','sonar']:
        hashes=defaultdict(set)
        for x in overlay:hashes[x[mod+'_image_sha256']].add(x['role'])
        assert all(len(roles)==1 for roles in hashes.values())
    for role in ['val','test']:
        for r in audit:
            if r['role']==role:assert any(t['role']=='train' and t['category']==r['category'] and t['primary_condition']==r['primary_condition'] for t in audit)
    dump(OUT/'manifest.json',overlay);dump(OUT/'condition-audit.json',audit);dump(OUT/'coverage.json',coverage)
    flat=[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in audit]
    writecsv(OUT/'recordings.csv',flat);writecsv(OUT/'coverage.csv',[dict(x,recordings=';'.join(x['recordings'])) for x in coverage])
    summary={role:dict(recordings=sum(r['role']==role for r in audit),selected=sum(x['role']==role and x['membership']=='selected' for x in overlay),reserve=sum(x['role']==role and x['membership']=='reserve' for x in overlay),per_class={cat:sum(r['role']==role and r['category']==cat for r in audit) for cat in sorted(CLASS_NAMES)}) for role in ['train','val','test']}
    dump(OUT/'protocol.json',dict(name='condition_aware_recording_split',status='candidate_pending_user_review',seed=SEED,primary_fields=['placement','trajectory','nominal_z','nominal_tilt','nominal_roll','nominal_pan'],algorithm='enumerate all train group subsets covering all primary conditions; require all marginal electronic setting values/Tx in train and holdout pan support >=95/100 within circular5deg from same-primary train; minimize train recording count then unsupported pan sample count then seeded hash; remaining whole groups hash-ordered, floor(half) val, remainder test',search=search,input_sha256=inputs,model_metrics_used_in_assignment=False,development_after_old_test_inspection=True,untouched_final_test=False,training_started=False))
    # Verify metadata and old split remained untouched.
    assert inputs=={p:sha(Path(p)) for p in inputs}
    dump(OUT/'verification.json',dict(passed=True,summary=summary,primary_conditions_total=len(coverage),all_primary_conditions_in_train=True,holdout_primary_conditions_all_present_in_train=True,holdout_recorded_pan_support_min95within5deg=all(r['same_condition_pan_support_count']>=95 for r in audit if r['role']!='train'),unique_group_conditions=sum(c['source_groups']==1 for c in coverage),all_3398_identities_preserved=True,selected_3000_unchanged=True,recording_and_source_group_disjoint=True,cross_role_image_hash_duplicates=0,old_split_and_source_hash_unchanged=True))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
