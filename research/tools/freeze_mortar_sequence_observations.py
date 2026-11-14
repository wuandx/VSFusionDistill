"""Freeze assistant visual observations and gated ridge digitization; no fitting."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image

OUT = ROOT/'DataSet/sonar_mortar_sequence_observations'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, d): Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def main():
    if (OUT/'observations-freeze.json').exists(): raise RuntimeError('Frozen observations must not be overwritten')
    display = json.loads((OUT/'display-provenance.json').read_text(encoding='utf-8'))
    gates_path = OUT/'curve-digitization-plan.json'
    gates = json.loads(gates_path.read_text(encoding='utf-8'))
    curves = []
    for frame in gates['frames']:
        source = OUT/'images'/f"{frame['sample']}-raw.png"
        a = np.asarray(Image.open(source), dtype=float)
        points = []
        for gate in frame['gates']:
            u = gate['beam']; lo, hi = gate['range_interval']
            rows = np.arange(lo, hi)
            score = np.array([a[v-1:v+2, u-1:u+2].mean() for v in rows])
            at = int(np.argmax(score)); v = int(rows[at]); edge = at in (0,len(rows)-1)
            points.append(gate | dict(raw_uv_edge=[u+.5,v+.5], observation_box_raw_edges=[u-1.,float(lo),u+2.,float(hi)],
                                     native_intensity_mean_3x3=float(score[at]), peak_at_gate_edge=edge,
                                     eligible_for_main_curve=gate['eligible_for_main_curve'] and not edge,
                                     correspondence='echo ridge only; no identified physical mesh point'))
        curves.append(dict(sample=frame['sample'], source=str(source), source_sha256=sha(source), points=points,
                           eligible_point_count=sum(p['eligible_for_main_curve'] for p in points),
                           constraint='Use frozen beam/range intervals; point is a digitization witness, not exact physical first arrival'))
    save(OUT/'center-main-echo-curves.json', dict(observer='assistant', expert_gt=False, gates_source=str(gates_path),
         gates_sha256=sha(gates_path), frames=curves, model_projection_exposure=False,
         nearest_surface_interpretation='unverified acoustic approximation for a future diagnostic fit',
         dark_region_exclusion_constraints=[], physical_endpoint_constraints=[]))

    # These intervals were estimated from the unboxed full-frame raw/polar views.
    # They are search/observation ranges, never complete-object training boxes.
    manual = {
        87: ([34,112,74,241], [48,142,61,168], [34,43], [65,75], '主斜向回波与上端横向小团、下方稀疏延伸跨3帧连续；强点只覆盖局部，尾段/支架归属不明。'),
        91: ([36,113,75,240], [51,142,63,168], [36,45], [66,76], '与0087结构连续，主亮点稍向右移；下段散点持续但不能确认完整本体端点。'),
        95: ([38,112,78,238], [55,143,67,166], [38,47], [69,79], '与前两帧的斜弧方向一致；上端分叉与弱下段仍不能定头尾。'),
        443: ([1,144,126,180], [25,145,101,170], [0,16], [112,128], '近距离横向主弧连续且清楚；右侧range约170–205有分离分支，不并入可靠本体曲线。'),
        447: ([2,144,127,181], [26,145,103,170], [0,17], [113,128], '主弧稳定；右侧与中下方散射团随帧变化，不能单凭相机支架确认声呐分支。'),
        451: ([2,144,128,182], [27,145,105,171], [0,18], [114,128], '横向主弧为最可靠观察；左右弱延伸接近视场边界，消退位置不能作为物理端点。'),
        455: ([3,144,128,182], [28,145,106,171], [0,19], [115,128], '主弧连续；右端弱散射与旁支边界不稳定，不据其强度截断确定目标全长。'),
        459: ([4,144,128,182], [29,145,108,171], [1,20], [116,128], '主弧仍稳定、右侧更弱；图像右边界不能排除回波未完整覆盖。'),
        803: ([24,113,103,270], [33,120,57,150], [24,35], [92,104], '近距离斜向短亮弧清楚，延伸至range约260的弯曲散射较弱；只确认同一结构持续，不确认全属本体。'),
        807: ([24,113,103,270], [33,120,57,150], [24,35], [92,104], '强近段稳定；远段斑点较弱，支架/尾翼/杂波之间不可分。'),
        811: ([25,113,104,272], [34,121,58,151], [25,36], [93,105], '强近段与0803/0807一致；远端小亮点和整段弧不能自动当物理尾端。')
    }
    records = []
    for f in display['frames']:
        n = f['aris_frame']; envelope, core, left, right, note = manual[n]
        middle = f['window_center'] == 451
        records.append(dict(sample=f['sample'], aris_frame=n, window_center=f['window_center'], paired_role=f['paired_role'],
            observation_status='partial_body_echo_observed', target_identity_confidence='medium',
            identity_basis='same coherent structure across allowed neighboring frames; central unboxed SD confirms mortar and a support pole, not sonar point correspondence',
            echo_search_extent_xyxy=envelope, echo_search_extent_is_training_box=False,
            core_body_echo_region_xyxy=core, core_confidence='high' if middle else 'medium',
            core_confidence_basis='persistent main ridge visible at native gain and fixed gain3; stronger than changing background speckle',
            echo_left_disappearance_beam_interval=left, echo_right_disappearance_beam_interval=right,
            echo_edge_confidence='low', echo_edge_source='visual gradual fade / branch ambiguity; interval is not a physical endpoint',
            possible_horizontal_fov_censoring=middle, complete_body_bbox_xyxy=None,
            physical_head_endpoint=None, physical_tail_endpoint=None, physical_boundary_status='unknown',
            support_structure_camera_status='support pole present in central SD', support_structure_sonar_status='unknown',
            ambiguous_returns_raw_regions=([{'xyxy':[72,168,120,220], 'meaning':'secondary branch / tail / support / reverberation unresolved'}] if middle else
                                          [{'xyxy':[34,175,60,270], 'meaning':'weak far-range branch attribution unresolved'}] if n<100 else
                                          [{'xyxy':[60,170,106,275], 'meaning':'weak curved far-range continuation attribution unresolved'}]),
            no_echo_exclusion_constraints=[], physical_endpoint_constraints=[], notes=note,
            evidence_images=dict(raw=f['raw_review'], polar=f['polar_output'], contact=str(OUT/f"window-{f['window_center']:04d}-contact.png")),
            raw_source=f['raw_source'], raw_source_sha256=f['raw_sha256']))
    obs = dict(name='sonar_mortar_sequence_observations', observer='assistant / cmhd_evidence', expert_gt=False,
        created_at=datetime.now(timezone.utc).isoformat(), task='independent unboxed sequence observation before new fixed-registration fit',
        previous_exposure='central frames were historical development observations; not a blind test. No new model projection, old box or fitted parameter product was read in this observation task.',
        source_scope='2023-09-21_100927 only; 11 allowed native sonar frames and 3 central SD images',
        coordinate_convention='raw pixel-edge xy; approximate visual ranges, not exact silhouette or segmentation',
        frames=records, skipped=display['skipped'], complete_physical_boundary_frames=0,
        main_echo_curves='center-main-echo-curves.json', model_inputs_read=False, check_images_read=False,
        conclusion='Sequence continuity strengthens echo attribution and the middle main ridge. It does not identify full physical endpoints or cleanly separate support/tail returns. The frozen main-echo intervals can support a diagnostic first-surface acoustic approximation; complete model boxes remain independently unverified.',
        candidate_detection_definition='An observable echo box may enclose only attributable visible returns. A complete model box may include dark surfaces. They are different annotation policies and neither is certified here.',
        formal_training_labels_written=0, production_reviews_written=0)
    save(OUT/'observations.json', obs)
    checked_sources = {p:sha(p) for p in display['input_hashes']}
    assert checked_sources == display['input_hashes'], 'Original rendering inputs changed before observation freeze'
    outputs = [p for p in OUT.rglob('*') if p.is_file() and p.name != 'observations-freeze.json']
    save(OUT/'observations-freeze.json', dict(frozen_at=datetime.now(timezone.utc).isoformat(), observation_sha256=sha(OUT/'observations.json'),
        curves_sha256=sha(OUT/'center-main-echo-curves.json'), source_hashes_unchanged=True,
        source_hashes=checked_sources, output_sha256={str(p.relative_to(OUT)):sha(p) for p in outputs},
        curve_points_total=sum(len(c['points']) for c in curves), eligible_main_curve_points=sum(c['eligible_point_count'] for c in curves),
        no_fit_or_projection_results_consulted=True))
    print(json.dumps(dict(frames=len(records), eligible_points=[(c['sample'],c['eligible_point_count']) for c in curves], frozen=True)))


if __name__ == '__main__': main()
