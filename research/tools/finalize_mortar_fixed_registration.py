"""Record completed manual review, present frozen results, and check delivery.

No projection, fitting, source-image decoding, or new annotation is performed.
"""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'DataSet/mortar_fixed_registration'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    p = Path(p)
    assert not p.exists(), f'Preserve existing artifact: {p}'
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        self.targets.extend(v for k, v in attrs if k in ('href', 'src'))


def main():
    frozen = read(OUT / 'freeze-model.json')
    evaluation = read(OUT / 'evaluation-results.json')
    fit_verify = read(OUT / 'independent-fit-verification.json')
    check_verify = read(OUT / 'independent-check-verification.json')
    independent_qa = read(OUT / 'independent-visual-qa.json')
    zero = read(OUT / 'zero-cost-ambiguity.json')
    assert fit_verify['passed'] and check_verify['passed']
    assert sha(OUT / 'freeze-model.json') == evaluation['freeze_sha256'] == zero['source_freeze_sha256']
    assert sha(OUT / 'observations/check-observations.json') == read(OUT / 'observations/freeze-check-observations.json')['sha256'] == evaluation['check_observations_sha256']
    ids = frozen['fit_samples'] + frozen['check_samples_not_used']
    assert [f['sample'] for f in evaluation['frames']] == ids
    notes = [
        '中间四个观察点位于局部亮支持；上方分散亮部及低beam侧向弱延伸在框外，归属未定。完整框仍不确定。',
        '主亮弧与候选范围基本相容；两端的弱延伸及下方结构没有可靠完整边界证据。',
        '近端亮支持与向远处的弱延伸可解释；远端零星点不能独立确定物理端部。',
        '中间亮支持位于候选内；近距离上方亮部与低beam弱延伸仍有类似0087的归属/姿态疑点。',
        '新旧两框均覆盖记录的主亮弧支持；下方弱纹与两侧端部归属未知，未据所有亮点扩框。',
        '原图未见可靠可归属目标；左侧几何候选不是目标存在的证据。保留uncertain，不作负样本。',
    ]
    items = []
    for sid, note in zip(ids, notes):
        image_path = OUT / 'review' / (sid + '.jpg')
        assert image_path.exists()
        items.append(dict(sample=sid, state='uncertain' if sid.endswith('0909') else 'unresolved',
                          reason=note, image=str(image_path), image_sha256=sha(image_path)))
    qa = dict(reviewer='root assistant', not_expert_ground_truth=True,
              model_frozen_before_review=True, frozen_model_sha256=sha(OUT / 'freeze-model.json'),
              review_method='Actually viewed all six four-panel full-height raw/prior/frozen-best/polar2 images after freeze.',
              independence='Root had read independent-review notes and numerical results; these two QA records are not mutually blinded.',
              independent_reviewer_did_not_read_check_observations=True,
              counts={'unresolved': 5, 'uncertain': 1}, formal_gt_approved=0,
              manual_boxes_created=0, test_access=False, items=items)
    save(OUT / 'root-visual-qa.json', qa)

    # Keep the evaluator-produced page as provenance; presentation changes only.
    index_path = OUT / 'index.html'
    original = index_path.read_text(encoding='utf-8')
    backup = OUT / 'index-generated.html'
    assert not backup.exists()
    backup.write_text(original, encoding='utf-8')
    intro = '''<section style="padding:20px;background:#edf4f8;border:1px solid #b7d0df;margin:24px 0">
<h2>已运行：24 组固定注册；完整框仍不稳定</h2>
<p>15 个候选通过首轨迹 fit 残差规则。第二轨迹两帧的 12 个观察支持点都进入冻结解容许带；末帧无可靠目标，保留 uncertain。主与独立 assistant 均为 5 unresolved / 1 uncertain，正式训练 GT 为 0。</p>
<p>仅两个粗、密采样都严格零损失的解，三个 fit 帧框 IoU 仍为 0.680 / 0.791 / 0.877。支持点可解释，不等于完整框已确定。图中绿色只是一项按 fit 冻结的显示解，不能代表唯一正确姿态。</p>
<a href="candidate-ambiguity.jpg"><img src="candidate-ambiguity.jpg" alt="15个候选在相同支持点下仍给出不同框"></a>
<p><a href="zero-cost-ambiguity.json">零损失多解与计数更正</a> · <a href="root-visual-qa.json">主复核</a> · <a href="independent-review/after-overlay-notes.md">独立复核理由</a> · <a href="independent-check-verification.json">独立数值核验</a> · <a href="run-summary.json">最终状态</a></p>
<p>数值核验通过只证明计算一致。合成近邻恢复未达到零损失；完整物理边界均未知，未生成专家框。0909 的空观察不计为零误差，不作负样本。</p>
</section>'''
    assert '<article>' in original
    updated = original.replace('<article>', intro + '<article>', 1)
    # Format display-only metrics and unknowns without changing numeric evidence.
    for row in evaluation['frames']:
        val = row['candidate_metrics']['start-00']['point_gap_p95']
        minimum = row['candidate_box_stability']['minimum_pairwise_iou']
        updated = updated.replace('最佳解带外p95 ' + str(val) + '；候选框最小IoU ' + str(minimum) + '；框稳定 False',
                                  '冻结解带外 p95 ' + ('不适用（无可靠观察）' if val is None else f'{val:.3f}') +
                                  '；15 候选框最小 IoU ' + f'{minimum:.3f}' + '；框稳定性：未通过')
    index_path.write_text(updated, encoding='utf-8')

    summary = dict(run='mortar_fixed_registration', status='completed_not_admitted_for_training_gt',
                   completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   fit_samples=frozen['fit_samples'], check_samples=frozen['check_samples_not_used'],
                   data_role='previously observed development samples, not blind or final test',
                   starts=24, eligible_candidates=15, best_display_candidate='start-00',
                   model_sha256=sha(OUT / 'freeze-model.json'), model_changed_for_check=False,
                   fit_observation_count=19, check_observation_counts=[4, 8, 0],
                   check_observation_sha256=evaluation['check_observations_sha256'],
                   fit_minimum_candidate_iou=[f['candidate_box_stability']['minimum_pairwise_iou'] for f in evaluation['frames'][:3]],
                   check_minimum_candidate_iou=[f['candidate_box_stability']['minimum_pairwise_iou'] for f in evaluation['frames'][3:]],
                   coarse_exact_zero_count=2, coarse_below_1e_minus_12_count=4, dense_exact_zero_count=7,
                   synthetic_nearby_pose_recovery_passed=False,
                   root_qa_counts=qa['counts'], independent_qa_counts=independent_qa['counts'],
                   fit_numerical_verification_passed=True, check_numerical_verification_passed=True,
                   approved_for_training_gt=False, new_formal_gt_count=0, new_training_runs=0,
                   manual_boxes_created=0, test_access=False, split_changed=False,
                   interpretation='Under the fixed imaging/visibility/scale and discrete support definition, the observed inclusion bands permit different complete boxes; support fit is not registration truth.',
                   report='../../复现/camera-baseline/mortar-fixed-registration.md')
    save(OUT / 'run-summary.json', summary)

    # Delivery checks include all already-recorded source inputs and all links.
    source_groups = {'fit': frozen['source_hashes'], 'evaluation': evaluation['source_hashes'],
                     'independent_check': check_verify['source_hashes']}
    checks = {}
    for group, mapping in source_groups.items():
        mismatches = [name for name, expected in mapping.items() if sha(name) != expected]
        assert not mismatches, (group, mismatches)
        checks[group] = dict(count=len(mapping), all_match=True)
    parser = Links(); parser.feed(updated)
    checked_links = []
    for target in parser.targets:
        if target.startswith(('http:', 'https:', '#', 'data:')):
            continue
        path = (OUT / target.split('#')[0]).resolve()
        assert path.exists(), path
        checked_links.append(str(path))
    report = ROOT / '复现/camera-baseline/mortar-fixed-registration.md'
    report_text = report.read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^)]+)\)', report_text):
        if target.startswith(('http:', 'https:', '#')):
            continue
        path = (report.parent / target).resolve()
        assert path.exists(), path
        checked_links.append(str(path))
    repo = ROOT.parent / '声呐目标检测/code/VSFusionDistill'
    git_state = subprocess.check_output(['git', '--no-optional-locks', 'status', '--porcelain'], cwd=repo, text=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    assert git_state == '', git_state
    deliverables = [report, index_path, OUT / 'root-visual-qa.json', OUT / 'run-summary.json', OUT / 'zero-cost-ambiguity.json',
                    ROOT / 'handoff.md', ROOT / 'experiment/results.md', ROOT / 'experiment/evaluation.md',
                    ROOT / 'brainstorm.md', ROOT / 'dataset.md', Path(__file__)]
    save(OUT / 'delivery-verification.json', dict(passed=True, source_hash_checks=checks,
         frozen_model_sha256=sha(OUT / 'freeze-model.json'), unchanged_fit_and_check_observations=True,
         six_expected_identities=True, local_links_checked=len(checked_links), missing_links=[],
         original_repository_head=head, original_repository_status=git_state,
         delivery_hashes={str(p): sha(p) for p in deliverables},
         test_access=False, training=False, new_formal_gt_count=0,
         verification_scope='Recorded input hashes, approved identities, completed independent numerical reports, linked files and root manual visual review. No claim of expert physical ground truth.'))
    print(json.dumps({'passed': True, 'hash_groups': checks, 'links': len(checked_links), 'source_repo_clean': True}))


if __name__ == '__main__':
    main()
