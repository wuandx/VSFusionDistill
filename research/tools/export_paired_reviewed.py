"""Export explicit per-pair visual decisions, with both modalities and labels."""
import collections
import json
import shutil
from pathlib import Path
import build_paired_paper_scale as b

ROOT=b.ROOT
OUT=ROOT/'DataSet/paired_visible_reviewed/export'
REVIEW_ROOTS=['paired_local_review','paired_local_review_weak']
CANDIDATE_FILES=[ROOT/'DataSet/paired_visible_expansion/candidates.json']

def main():
    assert not OUT.exists(), 'Named export already exists; preserve it'
    rows={}
    for candidate_file in CANDIDATE_FILES:
        for r in b.read(candidate_file):
            assert r['sample'] not in rows or rows[r['sample']]==r, 'Conflicting candidate provenance'
            rows[r['sample']]=r
    temporal=b.read(b.CAM/'manifest-resolved.json')
    allowed=set(temporal['identity']['recordings'])
    source={r['sample']:r for r in temporal['items']}
    accepted={};decisions=[]
    for name in REVIEW_ROOTS:
        folder=ROOT/'DataSet'/name
        if not (folder/'decisions.json').exists():continue
        for sample,d in b.read(folder/'decisions.json').items():
            entry=dict(d,review_root=name);decisions.append(entry)
            if d['decision']!='accepted':continue
            p=folder/d['sheet'];assert b.sha(p)==d['sheet_sha256']
            spec=b.read(p.with_suffix('.json'))
            s=next(x for x in spec['items'] if x['sample']==sample)
            assert s['proposed_box']==d['bbox_xyxy']
            if sample in accepted:assert accepted[sample]['bbox_xyxy']==d['bbox_xyxy']
            accepted[sample]=entry
    grouped=collections.defaultdict(list)
    for sample in accepted:grouped[rows[sample]['recording']].append(sample)
    selected=set();coverage=[]
    for rec,ids in sorted(grouped.items()):
        ids.sort(key=lambda x:rows[x]['aris_frame'])
        n=min(100,len(ids))
        chosen=[ids[round(j*(len(ids)-1)/(n-1))] for j in range(n)] if n>1 else ids
        selected.update(chosen)
        coverage.append(dict(recording=rec,category=rows[ids[0]]['category'],accepted=len(ids),selected=n,
            reserve=len(ids)-n,shortfall=max(0,100-n),precision_sync_certified=False))
    OUT.mkdir(parents=True)
    b.OUT=OUT
    cats=[dict(id=i+1,name=c) for i,c in enumerate(b.CLASSES)]
    coco={m:dict(images=[],annotations=[],categories=cats) for m in ['camera','sonar']}
    manifest=[]
    for ident,sample in enumerate(sorted(accepted),1):
        r=rows[sample];d=accepted[sample];m=source[sample]
        assert r['recording'] in allowed and r['source_paired_role'] in (None,'train','val','val_id')
        assert r['pairing']['eligible_for_review'] and not r['camera_issues']
        assert r['aris_frame']==m['aris_frame'] and r['reference_sd']==m['reference_sd']
        assert b.sha(r['source'])==d['source_sha256']
        assert b.sha(b.CAM/r['reference_sd'])==d['camera_sha256']
        assert b.sha(b.CAM/r['label_copy'])==m['original_label_sha256_before']
        camera=f'camera/images/{sample}.jpg';sonar=f'sonar/images/{sample}.png';label=f'camera/original_labels/{sample}.json'
        ch=b.copy_checked(b.CAM/r['reference_sd'],OUT/camera)
        lh=b.copy_checked(b.CAM/r['label_copy'],OUT/label)
        a=b.np.array(b.Image.open(r['source']));assert a.dtype==b.np.uint8 and a.ndim==2
        (OUT/sonar).parent.mkdir(parents=True,exist_ok=True);b.Image.fromarray(a).save(OUT/sonar)
        assert b.np.array_equal(a,b.np.array(b.Image.open(OUT/sonar)))
        h,w=a.shape;box=d['bbox_xyxy'];x0,y0,x1,y1=box
        assert 0<=x0<x1<=w and 0<=y0<y1<=h
        row=dict(r,camera_image=camera,camera_image_sha256=ch,sonar_image=sonar,sonar_image_sha256=b.sha(OUT/sonar),
            camera_original_label=label,camera_original_label_sha256=lh,sonar_bbox_xyxy=box,sonar_size_wh=[w,h],
            review=d,selected_for_100_per_recording=sample in selected,training_ready=False,
            precision_sync_certified=False,expert_verified=False)
        for modal,rel,size,boxes in [('camera',camera,(640,360),r['camera_boxes_xyxy']),('sonar',sonar,(w,h),[box])]:
            b.coco_add(coco[modal],ident,rel,size,boxes,r['category'])
            b.yolo(OUT/f'{modal}/labels_yolo/{sample}.txt',boxes,size,r['category'])
        row['preview']=b.preview(row);manifest.append(row)
    b.save(OUT/'manifest.json',manifest)
    for modal,data in coco.items():
        b.save(OUT/f'{modal}/coco_all_reviewed.json',data)
        ids={i['id'] for i in data['images'] if Path(i['file_name']).stem in selected}
        b.save(OUT/f'{modal}/coco_selected.json',dict(data,images=[i for i in data['images'] if i['id'] in ids],annotations=[a for a in data['annotations'] if a['image_id'] in ids]))
    b.save(OUT/'review-decisions-snapshot.json',decisions)
    old={r['sample']:r for r in b.read(ROOT/'DataSet/paired_paper_scale/manifest.json') if r['eligible_for_pairing_review']}
    overlap=set(old)&set(accepted)
    summary=dict(accepted_pairs=len(manifest),selected_pairs=len(selected),reserve_pairs=len(manifest)-len(selected),
        by_category=dict(collections.Counter(r['category'] for r in manifest)),recordings=coverage,
        recordings_with_100=sum(x['selected']==100 for x in coverage),paper_target_pairs=3000,
        selected_shortfall_to_3000=3000-len(selected),prior_review_eligible=825,
        overlap_with_prior_825=len(overlap),unique_union_with_prior_825=len(set(old)|set(accepted)),
        union_is_not_approved_gt=True,training_ready=False,precision_sync_certified=False,
        reason_encoding_replacement_count=sum('\ufffd' in x['reason'] for x in decisions))
    b.save(OUT/'summary.json',summary)
    merged=[dict(sample=s,recording=r['recording'],review_level='dual_view_assistant_reviewed' if s in accepted else 'prior_sonar_review_awaiting_dual_review',manifest=('manifest.json' if s in accepted else '../../paired_paper_scale/manifest.json')) for s,r in {**old,**{s:rows[s] for s in accepted}}.items()]
    b.save(OUT/'combined-review-levels.json',merged)
    page='''<!doctype html><meta charset="utf-8"><title>相机—声呐双端复核</title><style>body{font:16px sans-serif;max-width:1200px;margin:24px auto;background:#f1f4f7}img{width:100%;max-width:1040px}details{background:white;margin:10px 0;padding:12px}a{color:#0757a0}</style><h1>相机—声呐双端复核</h1>'''
    page+=f'<p>逐对助手复核 {len(manifest)} 对；按每录音最多 100 对选入 {len(selected)} 对，备用 {len(manifest)-len(selected)} 对。目标 3000 对尚未完成。</p><p>两侧同名图像与 COCO / YOLO 均已导出。相机为 SD 640×360，声呐为原始 raw 方向，左右与相机可能相反。框代表可见回波；未认证精密同步或专家 GT，未划分正式训练/测试集。</p><p><a href="manifest.json">来源及标注清单</a> · <a href="summary.json">数量</a> · <a href="verification.json">文件核验</a></p>'
    for rec in coverage:
        page+=f'<h2>{rec["recording"]} / {rec["category"]}: {rec["selected"]} + {rec["reserve"]} 备用</h2>'
        for r in manifest:
            if r['recording']!=rec['recording']:continue
            tag='选入' if r['selected_for_100_per_recording'] else '备用'
            page+=f'<details><summary>{r["sample"]} — {tag}</summary><img loading="lazy" src="{r["preview"]}" alt="camera and sonar paired boxes"></details>'
    (OUT/'index.html').write_text(page,'utf-8')
    print(json.dumps(summary,ensure_ascii=True))

if __name__=='__main__':main()
