"""Preserve subagent's 36 assessments and append root's 12 completed reviews."""
from pathlib import Path
import json,hashlib,collections
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'DataSet/sonar_fixed_registration_refinement/mortar_shell'
def readlines(p):return [json.loads(x) for x in p.read_text('utf-8').splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
N='needs_revision';M='misaligned';U='uncertain'
extra={
'2023-09-21_105856_0150':(M,M,'端视/尾翼样主回波清楚，但两版均无几何框。'),
'2023-09-21_105856_0253':(N,N,'gain1可见前方宽主团；两框都只覆盖右部，新框偏下，后方拖尾归属不明。'),
'2023-09-21_105856_0355':(N,N,'gain1中近团左部超出两框，新框也切到上边；不能把下方条带全当本体。'),
'2023-09-21_110049_0058':(U,U,'全高原图缺少可可靠归属的主回波，无框不作为负样本证据。'),
'2023-09-21_110049_0154':(N,N,'紧凑近弧可辨，旧框漏左段，新框还偏下；远点不用于补全边界。'),
'2023-09-21_110049_0250':(N,N,'近圆团可辨，两框左边略切主部且远距离余量大，新框上沿也需修订。'),
'2023-09-21_110229_0125':(U,U,'主要只有底部窄横条，无法确认本体与底部结构。'),
'2023-09-21_110229_0238':(U,U,'底部横回波延续，但不能据此指认目标，两版空框不认证负样本。'),
'2023-09-21_110229_0350':(M,M,'前方主弧宽于两版小框且部分在框下/侧方，框只包中间小片。'),
'2023-09-21_110411_0190':(U,U,'底部全宽亮结构和零星近点不足以可靠划定目标本体。'),
'2023-09-21_110411_0335':(N,N,'gain1可辨横向近主团，两框均漏左右范围；新框下移改善主体高度但未覆盖全宽。'),
'2023-09-21_110411_0480':(N,N,'gain1中T形近团可辨；旧框范围偏上，新框偏下并漏左上部，多层远条带保持未知。')}
def main():
    out=OUT/'independent-visual-qa.json'
    if out.exists():raise RuntimeError('Preserve existing result')
    assessment=OUT/'independent-qa-assessments.jsonl';rawnotes=OUT/'independent-qa-raw-notes.jsonl';ev=OUT/'evaluation-results.json'
    a=readlines(assessment);rn={x['sample']:x for x in readlines(rawnotes)};frames=json.loads(ev.read_text('utf-8'))['frames'];seen={x['sample'] for x in a}
    assert len(a)==36 and len(rn)==48 and not (seen&set(extra)) and seen|set(extra)==set(rn)
    mapped={x['sample']:x for x in a};rows=[]
    for f in frames:
        sid=f['sample']
        if sid in mapped:
            x=mapped[sid];old,new=x['old'],x['new'];oreason,nreason=x['old_reason'],x['new_reason'];observer='assistant/cmhd_evidence'
        else:
            old,new,reason=extra[sid];oreason=nreason=reason;observer='assistant/root (completion after subagent runtime failure)'
        rows.append(dict(sample=sid,recording=f['recording'],role=f['role'],observer=observer,observation=rn[sid]['note'],
                         old={'status':old,'reason':oreason},new={'status':new,'reason':nreason},
                         raw_notes_observer='assistant/cmhd_evidence',not_expert_truth=True,user_acceptance=False))
    counts={k:dict(collections.Counter(f[k]['status'] for f in rows)) for k in ['old','new']}
    result=dict(model_name='mortar_shell',frame_count=48,recording_count=16,counts=counts,frames=rows,
                completion_note='Subagent saved all 48 unboxed observations and 36 complete comparisons before its runtime failed. Root viewed the remaining 12 full-height gain1 original/old/new contacts and completed them without altering the preserved JSONL files.',
                independent_comparison_count=36,root_completed_comparison_count=12,
                source_hashes={str(p):sha(p) for p in [assessment,rawnotes,ev,OUT/'freeze-model.json']},
                not_expert_truth=True,user_reviews_written=0)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    text='# mortar 48帧助手QA\n\n前36帧比较来自独立子agent；其运行中断后，主agent查看剩余12帧完整原图/旧框/新框完成记录。48帧无框原始观察均由子agent预先保存。没有把主agent补完伪称为全部独立复核。\n\n'+json.dumps(counts,ensure_ascii=False)+'\n\n'+ '\n'.join(f"- {x['sample']}：旧{x['old']['status']}；新{x['new']['status']}。{x['new']['reason']}" for x in rows)
    (OUT/'independent-visual-qa.md').write_text(text,encoding='utf-8')
    print(json.dumps(counts,ensure_ascii=False))
if __name__=='__main__':main()
