"""Readable index for all saved motion diagnostics (no source-image access)."""
from pathlib import Path
import json, html
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'DataSet/sonar_view_consistency'
j=json.loads((OUT/'motion-evidence-review.json').read_text(encoding='utf-8'))
parts=['<!doctype html><html lang="zh"><meta charset="utf-8"><title>换视角失配：图像运动核查</title><style>body{font:16px system-ui;max-width:1320px;margin:24px auto;padding:0 16px;background:#121820;color:#edf1f5}img{width:100%;height:auto}article{background:#202a35;margin:18px 0;padding:16px;border-radius:8px}p{line-height:1.7}a{color:#91c8ff}summary{cursor:pointer}b{color:#ffd57b}</style><h1>换视角失配：图像运动核查</h1><p>当前成像参数、时间和位姿的组合存在局部不相容证据；不能唯一归因给同步、内参或外参。正式声呐GT继续HOLD。原注册不变。</p><p>26对可用局部图像对，8对越界保留；排除中心帧目标轮廓外扩10px后17对仍≥24点，但22/26对的homography支持≥90%，平面退化限制位姿解释。所有误差为SD像素。</p><p>下方F检查沿用已做全点RANSAC筛选的点，属于内部复核；轮廓外点不保证静止。图片显示原始全部内点，包括目标；背景统计另列。</p><p><a href="../../复现/camera-baseline/sonar-view-consistency.md">完整报告</a> · <a href="motion-evidence-review.json">复核JSON</a> · <a href="local-motion.json">原始局部点对</a></p>']
for o in j['outputs']:
    title=html.escape(f"{o['recording']} · SD {o['index_a']} → {o['index_b']}")
    parts.append('<article><h2>'+title+'</h2>')
    if 'subsets' not in o:
        parts.append('<p>越界，未替换样本。</p></article>');continue
    s=o['subsets']['outside_target']
    text=f"全部内点 {o['ransac_inliers']}；全部点位姿误差 {o['all_source_median_px']:.3f}；目标外点 {s['count']}"
    if 'source_median_px' in s:text+=f"；目标外位姿误差 {s['source_median_px']:.3f}；覆盖 {s['hull_fraction']:.1%}；homography支持 {s['homography_support_fraction']:.1%}"
    if 'split_F_check_median_px' in s:text+=f"；分点F检查 {s['split_F_check_median_px']:.3f} / 同检查点位姿 {s['split_source_check_median_px']:.3f}"
    name=f"{o['recording']}_{o['index_a']:04d}_{o['index_b']:04d}.jpg"
    assert (OUT/'local-matches'/name).is_file()
    parts.append('<p>'+text+'</p><img loading="lazy" src="local-matches/'+name+'" alt="SIFT局部点对"><details><summary>数据</summary><pre>'+html.escape(json.dumps(s,ensure_ascii=False,indent=2))+'</pre></details></article>')
parts.append('</html>');(OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8')
print('Wrote index.html, entries:',len(j['outputs']))
