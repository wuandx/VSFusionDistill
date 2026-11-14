"""Visualize frozen eligible poses on fit raw frames only; never reproject/refit."""
from pathlib import Path
import hashlib
import json
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageFont

OUT=ROOT/'DataSet/mortar_fixed_registration'
EXPECTED_FREEZE='e3e4e61835655c52ebb2e6c32df08751df69b8e5c2f54f0aeb013d6ba6279a8b'
FIT_IDS=['2023-09-21_100927_0087','2023-09-21_100927_0451','2023-09-21_100927_0811']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def font(size,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',size)


def box_iou(a,b):
    a=np.asarray(a);b=np.asarray(b)
    inter=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return float(inter/((a[2:]-a[:2]).prod()+(b[2:]-b[:2]).prod()-inter))


def main():
    destination=OUT/'candidate-ambiguity.jpg'
    if destination.exists():
        raise RuntimeError('Preserve the completed visualization')
    frozen_path=OUT/'freeze-model.json'
    assert sha(frozen_path)==EXPECTED_FREEZE
    frozen=read(frozen_path)
    assert frozen['fit_samples']==FIT_IDS
    eligible=[c for c in frozen['candidates'] if c['id'] in frozen['eligible_candidate_ids']]
    assert len(eligible)==15
    best=next(c for c in eligible if c['id']==frozen['best_display_candidate_id'])
    obs_path=OUT/'observations/fit-observations.json'
    observations={f['sample']:f for f in read(obs_path)['frames']}
    assert set(observations)==set(FIT_IDS)
    selection_path=ROOT/'DataSet/sonar_independent_registration/selection.json'
    selection={r['sample']:r for r in read(selection_path)['samples'] if r['sample'] in FIT_IDS}
    assert set(selection)==set(FIT_IDS)
    paths=[Path(__file__),frozen_path,obs_path,selection_path]+[Path(selection[s]['raw_sonar_source']) for s in FIT_IDS]
    before={str(p):sha(p) for p in paths}
    canvas=Image.new('RGB',(1880,1180),'#141d27')
    draw=ImageDraw.Draw(canvas)
    draw.text((36,20),'15 个合格拟合候选，仍给出不同的框',font=font(36,True),fill='#f3f6fb')
    draw.text((36,75),'同一尺度、同一声呐位姿、同一组 19 个支持点；仅展示拟合轨迹，未使用检查轨迹',font=font(21),fill='#b8c9dc')
    legend_y=118
    draw.line((36,legend_y+13,84,legend_y+13),fill='#65a9f0',width=2)
    draw.text((94,legend_y),'全部 15 个候选框',font=font(20),fill='#dbe7f6')
    draw.line((348,legend_y+13,396,legend_y+13),fill='#55f19c',width=4)
    draw.text((406,legend_y),'最低 fit cost 显示解 start-00',font=font(20),fill='#dbe7f6')
    draw.ellipse((810,legend_y+8,820,legend_y+18),fill='#ffcb61')
    draw.text((833,legend_y),'冻结支持点（不是完整边界）',font=font(20),fill='#dbe7f6')
    frame_metrics=[]
    group_width=596;panel_width=268;panel_height=680;group_gap=24;image_top=222
    for fi,sid in enumerate(FIT_IDS):
        x0=36+fi*(group_width+group_gap)
        row=selection[sid]
        raw=cv2.imdecode(np.frombuffer(Path(row['raw_sonar_source']).read_bytes(),np.uint8),cv2.IMREAD_GRAYSCALE)
        assert raw is not None and raw.ndim==2
        height,width=raw.shape
        shown=np.clip(raw.astype(np.float32)*3,0,255).astype(np.uint8)
        base=Image.fromarray(shown).convert('RGB').resize((panel_width,panel_height),Image.Resampling.NEAREST)
        overlay=base.copy();lines=Image.new('RGBA',overlay.size,(0,0,0,0));ld=ImageDraw.Draw(lines)
        sx=panel_width/width;sy=panel_height/height
        boxes=[]
        for candidate in eligible:
            metric=next(m for m in candidate['fit_metrics_dense'] if m['sample']==sid)
            box=metric['visible_raw_bbox_7deg'];assert box is not None
            boxes.append(box)
            xx=[box[0]*sx,box[1]*sy,box[2]*sx,box[3]*sy]
            ld.rectangle(xx,outline=(104,174,248,160),width=1)
        overlay=Image.alpha_composite(overlay.convert('RGBA'),lines).convert('RGB')
        od=ImageDraw.Draw(overlay)
        best_box=next(m for m in best['fit_metrics_dense'] if m['sample']==sid)['visible_raw_bbox_7deg']
        od.rectangle([best_box[0]*sx,best_box[1]*sy,best_box[2]*sx,best_box[3]*sy],outline='#55f19c',width=3)
        for point in observations[sid]['points']:
            u,v=point['raw_uv_edge'];x=u*sx;y=v*sy
            od.ellipse((x-3,y-3,x+3,y+3),fill='#ffcb61',outline='#332711',width=1)
        draw.text((x0,165),f'{sid}  ·  {len(observations[sid]["points"])} 个支持点',font=font(21,True),fill='#f0f5ff')
        draw.text((x0+18,196),'原始 raw · 固定 gain 3',font=font(18),fill='#aebed1')
        draw.text((x0+panel_width+40,196),'同图叠加冻结候选框',font=font(18),fill='#aebed1')
        canvas.paste(base,(x0+18,image_top));canvas.paste(overlay,(x0+panel_width+40,image_top))
        minimum=min((box_iou(a,b),eligible[i]['id'],eligible[j]['id']) for i,a in enumerate(boxes) for j,b in enumerate(boxes) if i<j)
        arr=np.array(boxes);spans=np.ptp((arr[:,:2]+arr[:,2:])/2,axis=0)
        draw.text((x0+18,925),f'候选框最小两两 IoU：{minimum[0]:.3f}',font=font(22,True),fill='#ffcb61')
        draw.text((x0+18,961),f'框中心跨度：{spans[0]:.2f} beams / {spans[1]:.2f} bins',font=font(19),fill='#c9d8e8')
        frame_metrics.append(dict(sample=sid,raw_shape_hw=[height,width],display_shape_hw=[panel_height,panel_width],
                                  minimum_pairwise_iou=minimum[0],minimum_pair_ids=minimum[1:],bbox_center_span_uv=spans.tolist()))
    draw.line((36,1015,1844,1015),fill='#35485b',width=1)
    draw.text((36,1036),'“合格”仅指通过预登记 fit 残差条件；这些框尚未稳定，也不是已准入的训练标签。',font=font(23,True),fill='#e3ebf5')
    draw.text((36,1080),'完整 raw 高度保留，距离向下增加；横纵显示倍率不同。框为密集表面采样、±7° 假设、无 padding。',font=font(20),fill='#aebed1')
    draw.text((36,1116),'此图只读取冻结数值和三张 fit 原图，没有再次投影、拟合、改符号或读取 check。',font=font(20),fill='#aebed1')
    canvas.save(destination,quality=96,subsampling=0)
    assert all(sha(p)==h for p,h in before.items())
    report=dict(run='mortar_candidate_ambiguity_visualization',freeze_sha256=EXPECTED_FREEZE,input_hashes=before,
                eligible_ids=[c['id'] for c in eligible],best_display=best['id'],frames=frame_metrics,
                raw_gain=3,resize='nearest, full image extent, explicitly nonuniform display scales',
                new_projections=0,new_parameter_fits=0,check_access=False,test_access=False,inputs_unchanged=True,
                output=str(destination),output_sha256=sha(destination))
    (OUT/'candidate-ambiguity-provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
