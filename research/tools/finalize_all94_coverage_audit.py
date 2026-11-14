"""Record actual21-sheet/11-clip review, source coverage and material checks."""
from audit_all94_coverage import *
BLOCKED={'2023-09-20_173329','2023-09-21_100927','2023-09-21_101131','2023-09-21_120653','2023-09-21_120912','2023-09-21_110229','2023-09-21_110411'}
NOTES={
'2023-09-20_173329':'三帧相机目标及较弱声呐主体均可见；历史连续配对不足不因三帧清楚自动解除。可补z750/tilt−22/roll90。',
'2023-09-20_173615':'相机目标和主回波可见；原相机框红框越界并覆盖大片支架，需重标；notes明确repeat previous，和173329保守同组。',
'2023-09-20_180126':'三帧两端主体清楚，原相机标签缺失；优先补两端框，补bomb z500/tilt−34/roll90联合条件。',
'2023-09-21_100927':'三帧相机清楚、声呐为较弱细弧；历史运动对应检查未通过，需连续对应证据，不直接批准。',
'2023-09-21_101131':'三帧相机清楚、声呐弱细弧可定位；重复100927同组，连续配对未决。',
'2023-09-21_110229':'相机主体在中间窗口可见，声呐主要细线/弱斑，难稳定定义主体；官方impossible to match警告保持。',
'2023-09-21_110411':'中间帧声呐强斑可见，首末时段弱；相机进出视野，官方impossible to match未解决，需连续时序恢复。',
'2023-09-21_120653':'相机目标与声呐弱弧可见，历史连续配对不足，不能用同类别图像替代对应证据。',
'2023-09-21_120912':'相机目标和弱弧可见，repeat120653同组，连续配对不足仍待恢复。',
'2023-09-21_124241':'三帧两端清楚；无原相机框，值得优先补两端标注，新增grenade z250/tilt−42/roll90及Max0条件。',
'2023-09-21_124440':'三帧两端清楚，声呐比124241弱但细弧可辨；无原相机框，补相同姿态下Min15条件。',
'2023-09-21_125924':'相机清楚，声呐弱弧可辨；无原相机框，增加z750/tilt−22/roll0的Min15来源，非新增宽场景。',
'2023-09-21_162055':'首段有清楚主体回波；中后段与地面强线混合、相机目标退出，不能整条当有效帧。优先只恢复双端共同可见窗口。',
'2023-09-21_122115':'声呐三帧呈左右扫掠式变化；原notes写flyby/tilt−90，与本次原始SonarPan/Tilt metadata冲突。不能计为已找到额外−90 flyby。'
}
CLIP_NOTES={
'20230921_GX010014_06.mp4':'燃烧弹支架上左右扫视，中心目标近竖向；可追121739等缺相机来源，非已恢复对应。',
'20230921_GX010014_09.mp4':'燃烧弹左右扫视的短段14.85秒，内容可辨；需查是否其他长段子片段，不能当新增独立录音。',
'20230921_GX010014_10.mp4':'燃烧弹支架左右扫视，中心竖向；可追roll90缺失来源。',
'20230921_GX010018_05.mp4':'地面bomb纵向经过相机的flyby样片段；重点与缺相机地面flyby候选核对，具体录音未知。',
'20230921_GX010018_07.mp4':'地面bomb经过视野，后段含转向/另一姿态；可能跨多个运动阶段，不直接认定一条录音。',
'20230921_GX020012_08.mp4':'mortar片段前段横向截断经过，后段出现不同朝向；可能含运动往返/过渡，需查完整时间线与裁剪来源。',
'20230921_GX020014_01.mp4':'燃烧弹支架左右扫视，中心竖向；可追未配对roll90来源。',
'20230921_GX020014_12.mp4':'燃烧弹纵向穿过视野，flyby样；具体ARIS来源未定，不能自动配给122115。',
'20230921_GX020014_13.mp4':'燃烧弹反方向纵向经过，flyby样；具体ARIS来源未定，可能为往返阶段。',
'20230921_GX030012_04.mp4':'mortar自下向上经过视野，flyby样；需与已映射02/03及raw连续时间对照，不能直接新增ID。',
'20230921_GX030012_05.mp4':'mortar反向经过视野，flyby样；与04可能往返，需对应而非只按片段顺序配对。'
}

def main():
    rows=read(D/'inventory.json');pilots=read(D/'pilots.json');vids=read(D/'unassigned-clips.json');current=read(CURRENT/'recordings.json');decisions=[]
    # All21 pages and all11 5-frame clip sheets were actually opened and viewed.
    for name,h in read(D/'sheet-sha256.json').items():assert sha(D/name)==h
    for r in rows:
        rec=r['recording'];original_test=r['original_role']=='test';cylinder=r['category']=='test_cylinder'
        if original_test:state='original_test_metadata_only'
        elif cylinder:state='other_target_not_current_three_class'
        elif r['in_current']:state='current_accepted'
        elif not r['camera_clip_exists']:state='missing_published_camera_mapping'
        elif rec.endswith('173615'):state='needs_camera_relabel_and_sonar_annotation'
        elif rec in BLOCKED:state='needs_continuous_pairing_recovery'
        elif rec.endswith('162055'):state='needs_visible_window_sonar_boxes'
        else:state='priority_needs_both_modality_annotation'
        r['audit_result']=state;r['pilot_viewed']=not original_test
        r['visual_observation']=NOTES.get(rec,'原研究test仅metadata，未读图/标签内容。' if original_test else '三帧原始回波实际查看；其他目标test_cylinder不混入三类正例/背景。' if cylinder else '三帧相机/声呐及现有框实际查看，保留现有准入，不升级为整条全帧审核。' if r['in_current'] else '已查看三帧声呐，缺公开相机对应；需检索未分配视频，不能认定素材一定不存在。')
        rr=[t for t in current if t['scene_id']==r['scene_id']];tr=[t for t in rr if t['role']=='train'];joint=tuple(r[k] for k in ('z','tilt','roll'))
        r['same_scene_current_recordings']=[t['recording'] for t in rr];r['same_scene_train_recordings']=[t['recording'] for t in tr]
        r['nominal_pose_new_to_current']=not any(tuple(t[k] for k in ('z','tilt','roll'))==joint for t in rr)
        r['nominal_pose_new_to_train']=not any(tuple(t[k] for k in ('z','tilt','roll'))==joint for t in tr)
        if not original_test:
            metadata=DATA/'data_processed/aris'/rec/(rec+'_frames.csv');mm=list(csv.DictReader(metadata.open(encoding='utf-8-sig')));r['aris_metadata_sha256']=sha(metadata)
            pan=np.rad2deg(np.unwrap(np.deg2rad([float(m['SonarPan']) for m in mm])));tilt=np.array([float(m['SonarTilt']) for m in mm]);roll=np.array([float(m['SonarRoll']) for m in mm]);r['recorded_motion']=dict(pan_unwrapped_span_degrees=float(np.ptp(pan)),tilt_min=float(tilt.min()),tilt_max=float(tilt.max()),tilt_median=float(np.median(tilt)),roll_median=float(np.median(roll)),receiver_gain=sorted({m['ReceiverGain'] for m in mm}),enable150V=sorted({m['Enable150V'] for m in mm}))
            r['nominal_vs_metadata_warning']=r['trajectory']=='flyby' and float(np.ptp(pan))>30
            if r['pilot_sheet']:
                decisions.append(dict(recording=rec,scope=r['audit_scope'],sampled_frames=r['sampled_frames'],sheet=r['pilot_sheet'],sheet_sha256=sha(D/r['pilot_sheet']),author='assistant',observation=r['visual_observation'],new_pairs_accepted=0,full_recording_frame_review=False,precision_sync_certified=False))
    for v in vids:
        assert sha(D/v['sheet'])==v['sheet_sha256'];v.update(viewed=True,author='assistant',observation=CLIP_NOTES[v['name']],correspondence_status='unassigned_after_pilot_review',new_pairs_accepted=0,source_clip_sha256=sha(v['clip']))
    save(D/'decisions.json',decisions);save(D/'inventory-reviewed.json',rows);csvout(D/'inventory-reviewed.csv',rows);save(D/'unassigned-clips-reviewed.json',vids)
    # Potential source repeats outside current38, read from explicit original notes.
    groups=[['2023-09-20_173329','2023-09-20_173615'],['2023-09-21_100927','2023-09-21_101131'],['2023-09-21_120653','2023-09-21_120912']]
    save(D/'additional-source-groups.json',dict(groups=groups,evidence='original notes: repeat previous / repeat main data, conservative grouping required before future split; not actual physical object independence'))
    fixed=read(D/'inputs.json');assert all(sha(p)==h for p,h in fixed.items());assert len(rows)==len({r['recording'] for r in rows})==94 and len(decisions)==84 and len(pilots)==252
    summary=dict(total_recordings=94,target_three_class=72,other_target_test_cylinder=22,original_test_metadata_only=10,non_original_test_three_class=62,current_accepted=38,remaining_matched_camera_three_class=13,missing_published_camera_three_class=11,priority_unlabelled_sources=4,fixed_pilot_recordings_viewed=84,dual_pilot_recordings=55,sonar_only_pilot_recordings=29,pilot_frames_viewed=252,unassigned_camera_clips=11,unassigned_clip_frames_viewed=55,states=dict(Counter(r['audit_result'] for r in rows)),metadata_conflicts=[dict(recording=r['recording'],notes=r['notes'],recorded_motion=r['recorded_motion']) for r in rows if r.get('nominal_vs_metadata_warning')],new_pairs_accepted=0,current_4836_manifest_unchanged=sha(CURRENT/'manifest.json')==fixed[str(CURRENT/'manifest.json')],no_new_training=True,original_test_content_read=False,all_inputs_unchanged=True)
    save(D/'summary.json',summary)
    labels=['recording','category','audit_result','z','tilt','roll','camera_clip_exists','local_label_count','valid_original_sd_boxes','nominal_pose_new_to_train','visual_observation'];head='<table><tr>'+''.join('<th>'+x+'</th>' for x in labels)+'</tr>';table=head+''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(k,'')))+'</td>' for k in labels)+'</tr>' for r in rows)+'</table>'
    p=D/'index.html';page=p.read_text(encoding='utf-8');page=page.replace('<h1>94 metadata;', '<h1>已完成逐录音审计 / 94 metadata;');page=page.replace('Prepared pilots are not yet acceptance. See decisions.json for actual viewing and conclusions.','已实际查看84条非原研究test录音各3帧（55条双端、29条仅声呐）与11个未分配相机片段各5帧；10条原研究test仅metadata。不是全部帧标注验收，新增准入0。四条双端可辨但缺标签来源优先补标；未分配视频不能直接算独立录音。<a href="inventory-reviewed.csv">94条结果表</a> · <a href="summary.json">统计</a> · <a href="decisions.json">审阅事件</a> · <a href="unassigned-clips-reviewed.json">未分配视频判断</a>');page=page.replace('<h2>page-00.jpg</h2>',table+'<h2>page-00.jpg</h2>');page=page.replace('max-width:1500px','max-width:1800px').replace('pre{white-space:pre-wrap}','pre{white-space:pre-wrap}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #bbc;padding:6px}');p.write_text(page,encoding='utf-8')
    save(D/'verification.json',dict(passed=True,unique_metadata_rows=94,actual_review_recordings=84,fixed_frames=252,unassigned_videos_viewed=11,unassigned_frames=55,recording_sheet_hashes_preserved=True,input_hashes_preserved=True,original_test_pilot_content_count=0,current_dataset_changed=False))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
