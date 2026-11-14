"""Count remaining paired-file candidates, never equate them with accepted sonar GT."""
import csv
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/paired_expansion_capacity_audit'
DATA=Path('D:/pby')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    OUT.mkdir(exist_ok=False)
    current=list(csv.DictReader((ROOT/'DataSet/scene_stratified_mortar_recovered_candidate/recordings.csv').open(encoding='utf-8-sig')))
    roles={r['recording']:r['role'] for r in current}
    used={r['sample'] for r in read(ROOT/'DataSet/scene_stratified_mortar_recovered_candidate/manifest.json')}
    inv=read(ROOT/'DataSet/recording_expansion_94_audit/inventory.json')
    temporal=read(ROOT/'DataSet/camera_temporal_all/manifest-resolved.json')['items']
    matches={Path(r['aris_file']).name:r for r in csv.DictReader((DATA/'data_processed/matches.csv').open(encoding='utf-8-sig'))}
    summaries=[];candidates=[]
    for meta in inv:
        rec=meta['recording'];state=meta['state']
        if state!='current_train' and state!='extra_existing_labels_camera_review':continue
        assert roles.get(rec) not in ['val','test'] and meta['original_role']!='test'
        native=DATA/'uxo-full/extracted/recordings'/meta['category_dir']/rec
        items=[r for r in temporal if r['recording']==rec];available=[];excluded=Counter()
        if items:
            for r in items:
                lab=ROOT/'DataSet/camera_temporal_all'/r['label_copy'];a=read(lab)
                b=[a[k] for k in ['x_min','y_min','x_max','y_max']]
                if not (0<=b[0]<b[2]<=640 and 0<=b[1]<b[3]<=360):excluded['bbox_out_of_bounds']+=1;continue
                if not r.get('reference_sd'):excluded['no_corrected_sd_reference']+=1;continue
                camera=ROOT/'DataSet/camera_temporal_all'/r['reference_sd']
                raw=native/'aris_raw'/f'{r["aris_frame"]:04d}.pgm'
                if not camera.is_file() or not raw.is_file():excluded['missing_camera_or_aris_file']+=1;continue
                available.append(dict(sample=r['sample'],recording=rec,sd_index=r['sd_index'],camera_source=str(camera),sonar_source=str(raw),camera_box=b,source='existing_corrected_SD',in_current=r['sample'] in used))
        else:
            pilot=read(ROOT/'DataSet/expanded_paired_recordings/pilots'/rec/'pilot.json')
            fps=float(Fraction(pilot['probe']['avg_frame_rate']));nf=int(pilot['probe']['nb_frames']);m=matches[rec]
            metadata=DATA/'data_processed/aris'/rec/(rec+'_frames.csv')
            md={int(r['FrameIndex']):r for r in csv.DictReader(metadata.open(encoding='utf-8-sig'))};onset=int(md[int(m['aris_onset'])]['FrameTime'])
            for lab in sorted((native/'labels').glob('*.json')):
                frame=int(lab.stem);a=read(lab);b=[a[k] for k in ['x_min','y_min','x_max','y_max']]
                if not (0<=b[0]<b[2]<=640 and 0<=b[1]<b[3]<=360):excluded['bbox_out_of_bounds']+=1;continue
                si=int((int(md[frame]['FrameTime'])-onset)/1e6*fps)+int(m['gopro_offset'])
                if not 0<=si<nf:excluded['sd_index_outside_clip']+=1;continue
                raw=native/'aris_raw'/f'{frame:04d}.pgm'
                if not raw.is_file():excluded['missing_aris_file']+=1;continue
                sample=f'{rec}_{frame:04d}'
                available.append(dict(sample=sample,recording=rec,sd_index=si,camera_clip=pilot['source_clip'],sonar_source=str(raw),camera_box=b,source='published_SD_index_pending_extraction',in_current=sample in used))
        additional=[r for r in available if not r['in_current']]
        unique=len({r['sd_index'] for r in additional})
        for r in additional:r.update(status='candidate_not_accepted_pair',prior_review=meta['prior_review']);candidates.append(r)
        summaries.append(dict(recording=rec,state=state,category=meta['category'],prior_review=meta['prior_review'],available_file_candidates=len(available),current_selected=sum(r['in_current'] for r in available),additional_frame_candidates=len(additional),additional_unique_sd_indices=unique,excluded=dict(excluded),notes=meta['notes']))
    train=[r for r in summaries if r['state']=='current_train'];extra=[r for r in summaries if r['state']!='current_train']
    summary=dict(current_train_recordings=21,current_train_pairs=2472,additional_frames_existing_train=sum(r['additional_frame_candidates'] for r in train),additional_unique_sd_existing_train=sum(r['additional_unique_sd_indices'] for r in train),additional_frames_extra_labelled_sources=sum(r['additional_frame_candidates'] for r in extra),additional_unique_sd_extra_sources=sum(r['additional_unique_sd_indices'] for r in extra),extra_labelled_sources_with_valid_candidates=sum(r['additional_frame_candidates']>0 for r in extra),extra_unlabelled_camera_sources=4,newly_accepted_pairs=0,all_counts_are_candidates_not_sonar_GT=True,no_new_test_content_read=True,metadata_and_path_checks_only=True)
    save(OUT/'summary.json',summary);save(OUT/'recordings.json',summaries);save(OUT/'candidate-frames.json',candidates)
    print(json.dumps(summary));print(json.dumps([r for r in summaries if r['state']!='current_train' or 'flyby' in r['notes'].lower()]))
if __name__=='__main__':main()
