"""Persist completed root visual observations, not algorithmic quality labels."""
from pathlib import Path
import json,hashlib,collections
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'DataSet/sonar_fixed_registration_refinement/incindiary'
# Each row was inspected in full-height raw/old/new contact sheets. Strong
# recordings were rechecked at gain=1, weak recordings at gain=3.
R='reviewable';N='needs_revision';M='misaligned';U='uncertain'
records={
'120653':[(N,N,'0163：可辨近端亮弧在左上；两框均有局部左侧漏包，新框远距离空余较多。'),(N,N,'0551：连续主弧清楚；新框左边改善但仍漏掉左端，旧框漏段更长。'),(N,N,'0933：新框朝向/近端位置改善；右下空余及弱后段归属仍需修订，旧框漏左近端。')],
'120912':[(N,N,'0120：近端双弧及侧面可辨，两框左侧仍漏；新框过窄并延伸到后方。'),(N,N,'0461：主弧左端在两框外，新框仍需左扩，旧框左漏更大。'),(N,N,'0802：新框大体顺着斜向本体，但左上端仍超出；旧框左漏更大。')],
'121124':[(N,M,'0035：gain1确认左侧大片本体超出；新框变窄，只覆盖本体右侧部分。'),(N,N,'0383：主弧与条状后方回波可区分，两框均漏左侧端部；新框较接近。'),(N,N,'0731：斜向本体近端在框左上方，新框比旧框左移但仍漏，支架下延不作本体边界。')],
'121327':[(N,M,'0072：与同姿态0035相似，gain1可见宽本体；新框仅包右侧窄片。'),(N,N,'0441：横向主弧左端两版均漏包，新版改善但未完整。'),(N,N,'0810：新框包住主体更多，左上头部仍露在外，旧框更偏右。')],
'121539':[(N,N,'0072：新框方向与主体更一致，左上环状部仍有漏包；旧框明显偏右。'),(M,R,'0460：端视环状/弧状本体完整落入新框，周边余量合理；旧框偏右只包部分主体。'),(N,N,'0848：目标已左侧截断，新框仍未包括画面内的左侧主体，旧框左漏更大。')],
'122608':[(N,M,'0066：gain1可辨的本体向左扩展，新窄框遗漏大部分左部；旧框也需左扩。'),(N,N,'0444：横向本体左端仍在新旧框外，新版较旧版改善；下方条带不全部归本体。'),(N,N,'0822：新框包住斜向主部且比旧框左移，但近端左沿仍需补入。')],
'122855':[(N,N,'0088：斜向本体可辨，新框比旧框少漏，但左上圆端仍超出。'),(M,R,'0492：新框包含紧凑端视主弧且不追入左下支架；旧框偏右只包弧尾。'),(N,N,'0896：本体在左边界截断，新旧框都漏掉画面内的左上段，新框漏段较少。')],
'123500':[(N,N,'0077：gain3可辨近端环和下延主体，新框偏右下且过窄，旧框也漏左侧。'),(N,N,'0442：gain3的主弧左端在框外，新框近边较贴主弧但仍需左扩。'),(N,N,'0807：gain3可辨斜向主弧，新框改善近端位置但左上和后方范围仍需人确认/修订。')],
'123841':[(N,M,'0080：gain1中主体宽度明显大于新框，新框偏右下并裁去左/上部。'),(N,N,'0456：横向本体左端两版均漏，主部已对上。'),(N,N,'0832：新框比旧框接近，左上近端仍小幅漏包，底部支架不纳入目标。')],
'124039':[(N,M,'0057：宽本体左上被新窄框切掉；旧框仍需左扩但错漏较轻。'),(N,N,'0454：可辨横向本体左端外漏，两版均需修订。'),(N,N,'0851：新框对上斜向主体，左上端仍在外；旧框偏右更多。')],
'124915':[(M,M,'0062：原图有清楚的环状/端视目标回波，但两版7度裁剪后都无框。'),(N,N,'0146：两框都只覆盖可辨本体的一部分，新框偏下，旧框偏右上。'),(N,N,'0230：新框横向覆盖改善但近距离边切掉上方一段，旧框偏右。')],
'125048':[(U,U,'0150：可见底部宽弧及极弱上方散射，无法可靠指定本体回波；两版无框不作为负样本证据。'),(N,M,'0275：端视亮环清楚；新框缩成亮环下方小片，旧框也需扩到完整主环。'),(U,U,'0400：目标区域与横向强条带/多径叠加，现有观察不能可靠划定本体范围；不以框存在判合格。')]
}
def main():
    dest=OUT/'visual-qa.json'
    if dest.exists():raise RuntimeError('Preserve visual record')
    source=OUT/'evaluation-results.json';data=json.loads(source.read_text('utf-8'));rows=[]
    for rec in sorted({x['recording'] for x in data['frames']}):
        frames=[x for x in data['frames'] if x['recording']==rec];items=records[rec[-6:]];assert len(frames)==len(items)==3
        for f,(old,new,reason) in zip(frames,items):
            rows.append(dict(sample=f['sample'],recording=rec,role=f['role'],old_status=old,new_status=new,reason=reason,observer='assistant/root',user_accepted=False,source_contact=f'evaluation/{rec}-contact.jpg',gain1_contact=f'review-gain1/{rec}.jpg'))
    summary={k:dict(collections.Counter(x[k+'_status'] for x in rows)) for k in ['old','new']}
    result=dict(model_name='incindiary',observer='assistant/root; not independent of fit observations',not_expert_truth=True,frame_count=len(rows),evaluation_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),summary=summary,frames=rows,policy='experiment/sonar-registration-refinement-visual-qa.md',note='Main model frozen before cross-recording images. No changes to fitting, user reviews, or labels. Reviewable means eligible for user inspection only.')
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
