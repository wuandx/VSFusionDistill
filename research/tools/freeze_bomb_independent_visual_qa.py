"""Freeze already completed manual assistant visual decisions; no model mutation."""
from pathlib import Path
import sys,json,hashlib,collections
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'DataSet/sonar_fixed_registration_refinement/100lbs'
STATUSES=['reviewable','needs_revision','misaligned','uncertain']
ZH=dict(reviewable='可审',needs_revision='需修',misaligned='错位',uncertain='不确定')
def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def counts(fs):
    return {'denominator':len(fs),**{v:{s:sum(f[v]['status']==s for f in fs) for s in STATUSES} for v in ('old','new')}}
def main():
    final=BASE/'independent-visual-qa.json';assert not final.exists(),'Preserve frozen QA'
    ep=BASE/'evaluation-results.json';ev=read(ep)
    dp=BASE/'independent-qa-displays/display-provenance.json';display=read(dp)
    draft=read(BASE/'independent-visual-qa-draft.json')
    assert sha(ep)==display['inputs_sha256'][str(ep)]
    assert sha(BASE/'freeze-model.json')==ev['freeze_sha256']
    assert all(sha(p)==h for p,h in display['inputs_sha256'].items())
    lookup={f['sample']:f for f in ev['frames']}
    assert len(draft['frames'])==36 and len({f['sample'] for f in draft['frames']})==36
    assert {f['sample'] for f in draft['frames']}==set(lookup)
    frames=[]
    for row in draft['frames']:
        f=lookup[row['sample']]
        assert all(row[v]['status'] in STATUSES and len(row[v]['reason'])>10 for v in ('old','new'))
        row.update({k:f[k] for k in ('recording','aris_frame','role','target_frame','floor_extrapolation','candidate_id')})
        row.update(camera_present=bool(f['provenance']['camera']),raw_shape_hw=f['geometry']['raw_shape_hw'],display_gains_reviewed=[1,3],unboxed_and_camera_viewed_before_boxes=True,expert_ground_truth=False,user_acceptance=False)
        for v in ('old','new'):row[v]['bbox_xyxy']=f[v]['bbox_xyxy']
        row['unboxed_display']='independent-qa-displays/'+f['recording']+'-unboxed.png'
        row['bbox_display']='independent-qa-displays/'+f['recording']+'-boxes-gain1.png'
        row['original_comparison']='evaluation/'+f['sample']+'-comparison.jpg'
        frames.append(row)
    groups={
        'all':counts(frames),
        'fit':counts([f for f in frames if f['role']=='fit']),
        'development_check_including_floor':counts([f for f in frames if f['role']=='development_check']),
        'development_check_excluding_floor':counts([f for f in frames if f['role']=='development_check' and not f['floor_extrapolation']]),
        'floor_registration_transfer':counts([f for f in frames if f['floor_extrapolation']]),
    }
    display_files=sorted({f[k] for f in frames for k in ('unboxed_display','bbox_display')})
    output={
        'reviewer':'assistant /root/uxo_paper',
        'review_kind':'independent assistant visual QA of frozen candidate boxes; not expert ground truth or user acceptance',
        'date':'2026-11-12',
        'criteria_path':'experiment/sonar-registration-refinement-visual-qa.md',
        'criteria_sha256':sha(ROOT/'experiment/sonar-registration-refinement-visual-qa.md'),
        'evaluation_results_sha256':sha(ep),'freeze_model_sha256':ev['freeze_sha256'],
        'source_selection_sha256':ev['selection_sha256'],
        'model_name':'100lbs','frame_count':36,'recording_count':12,
        'protocol':[
            'All selected 36 bomb frames reviewed. Per recording, unboxed native gain1/gain3 and available SD were viewed before old/new bbox displays.',
            'Full raw height preserved. Gain1 has no intensity change; gain3 is display-only clipping after multiplication by 3. Bboxes displayed without hulls.',
            'A reviewable box only needs reasonable coverage of recognizable principal body. Unique 3D pose and bright mask matching are not prerequisites.',
            'Prior observations of the fit recording were known; this is independent of optimizer judgments, not blind or untouched-data validation.',
            'No other reviewer decisions were read before freezing this file. No fitting, beam changes, raw changes, user review writes, formal GT, test reads, training or split changes.',
            'Floor target transfer remains unvalidated and is reported separately. Missing SD at 160551_1450 is kept explicit; sonar QA does not admit this pair.',
        ],
        'counts':groups,
        'counts_by_recording':{rec:counts([f for f in frames if f['recording']==rec]) for rec in sorted({f['recording'] for f in frames})},
        'frames':frames,
        'reviewed_display_images_sha256':{p:sha(BASE/p) for p in display_files},
        'source_input_hash_count':len(display['inputs_sha256']),
        'source_inputs_unchanged_after_review':True,
        'new_formal_gt':0,'user_reviews_written':0,
    }
    save(final,output)
    lines=['# bomb 固定注册：独立逐帧助手 QA','',
        '2026-11-12；观察员：assistant `/root/uxo_paper`。12 条录音全部 36 帧，按已冻结规则先看无框 gain1/gain3 与可用 SD，再分别判断旧、新 bbox。使用全高原生 raw，未裁剪；不要求亮像素填满框，也不把唯一 3D 姿态作为可审条件。',
        '', '**结果：新候选未稳定改善跨录音框质量。** 旧框 2 可审、22 需修、11 错位、1 不确定；新框 1 可审、17 需修、17 错位、1 不确定。可审只表示可交用户保留审阅，不是专家真值、自动接受或注册已正确。需修仍有可见问题，不能计为原框通过。',
        '', '| 分组 | 帧数 | 旧：可审 / 需修 / 错位 / 不确定 | 新：可审 / 需修 / 错位 / 不确定 |','|---|---:|---|---|']
    labels={'all':'全部','fit':'fit','development_check_including_floor':'development_check（含 floor）','development_check_excluding_floor':'development_check（不含 floor）','floor_registration_transfer':'floor 注册迁移'}
    for key,g in groups.items():
        vals=[' / '.join(str(g[v][s]) for s in STATUSES) for v in ('old','new')]
        lines.append(f"| {labels[key]} | {g['denominator']} | {vals[0]} | {vals[1]} |")
    lines += ['', '代表例：', '',
        '- 新框可审：`2023-09-20_181139_0903`，主要弯曲回波已包住；很弱远端仍需用户确认。旧版该帧无有效框。',
        '- 旧框可审但新框退化：`2023-09-20_180506_0852`，新框过窄且偏右，左上亮帽和左半主体落框外。',
        '- fit 仍错位：`2023-09-20_171105_0622` 和 `_1336`，新框仍漏掉大段连续主体。`_0981` 需向右修边，不能直接保留。',
        '- 新框缺失：`2023-09-20_173615_0955`、`2023-09-20_175000_0927`，原图主体清楚但新投影无有效框。',
        '- 保留不确定：`2023-09-20_173329_0535`，相机有目标，但声呐 gain1/gain3 均无法可靠辨认主体；不视为负样本。',
        '- floor 三帧新框均错位；这是同一注册向 `target/100lbs_floor` 的迁移。`2023-09-21_160551_1450` 缺 SD，声呐框判断不等于配对准入。',
        '', '每条录音的原图与框显示如下；链接展示完整 raw 高度。gain3 饱和的 175905 与 floor 录音以 gain1 判定主体范围，未把长阴影、支架样线或重复反射直接当本体。', '',
        '| 录音 | 原图 + SD | gain1 旧/新 bbox |','|---|---|---|']
    for rec in sorted({f['recording'] for f in frames}):
        lines.append(f'| {rec} | [无框](independent-qa-displays/{rec}-unboxed.png) | [旧/新](independent-qa-displays/{rec}-boxes-gain1.png) |')
    lines += ['', '逐帧判断与可见理由（不同观察员分歧应并列保留，不覆盖本记录）：', '', '| 身份 / 角色 | 原图观察 | 旧框 | 新框 |','|---|---|---|---|']
    for f in frames:
        role=f['role']+(' / floor 注册迁移' if f['floor_extrapolation'] else '')
        lines.append(f"| [{f['sample']}]({f['original_comparison']}) · {role} | {f['observation']} | **{ZH[f['old']['status']]}**：{f['old']['reason']} | **{ZH[f['new']['status']]}**：{f['new']['reason']} |")
    lines += ['', '核验与边界：', '',
        f"- 冻结模型 SHA256：`{ev['freeze_sha256']}`。36 身份与 evaluation-results 完全一致，74 项输入哈希在显示生成前后及 QA 结束时一致；24 张实际查看的独立显示图哈希已保存。",
        '- 原始 raw 36 张、可用 SD 35 张；所有显示完整保留各自 raw 行数（常规帧 780 行，floor 以实际元数据行数为准）。',
        '- 这是一名助手的视觉判断，不是专家真值，不报告 GT IoU/AP。fit 录音已有先前观察，development_check 是开发检查，不是盲验或最终 test。',
        '- 没有拟合新模型、改变 beam 或尺度、写用户审阅、生成正式 GT、读取 test、训练或更改 split。',
        '- [机器可读记录](independent-visual-qa.json)；[显示来源与输入哈希](independent-qa-displays/display-provenance.json)。', '']
    (BASE/'independent-visual-qa.md').write_text('\n'.join(lines),encoding='utf-8')
    reread=read(final);assert reread['frame_count']==36 and len(reread['frames'])==36
    assert all(sum(g[v].values())==g['denominator'] for g in reread['counts'].values() for v in ('old','new'))
    verification={'qa_sha256':sha(final),'report_sha256':sha(BASE/'independent-visual-qa.md'),'all_36_selected_frames_have_two_decisions':True,'group_counts_close':True,'source_hash_count':len(display['inputs_sha256']),'source_inputs_unchanged':all(sha(p)==h for p,h in display['inputs_sha256'].items()),'freeze_model_unchanged':sha(BASE/'freeze-model.json')==ev['freeze_sha256'],'display_images_reviewed':len(display_files),'new_formal_gt':0,'user_reviews_written':0}
    assert verification['source_inputs_unchanged'] and verification['freeze_model_unchanged']
    save(BASE/'independent-visual-qa-verification.json',verification)
    print(json.dumps({'counts':groups,'verification':verification},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
