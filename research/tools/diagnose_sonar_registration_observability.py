"""Ideal-correspondence sensitivity; no image/echo fitting and no GT output."""
from pathlib import Path
import ast
import hashlib
import json
import math
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DEST = ROOT / 'DataSet/sonar_registration_methods/observability'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rotvec(v):
    a = np.linalg.norm(v)
    if a < 1e-14:
        return np.eye(3)
    k = v / a
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K


def describe(J):
    if J.shape[0] == 0:
        return dict(rows=0, rank=0, singular_values=[], condition=None, weakest_direction=None)
    _, s, vt = np.linalg.svd(J, full_matrices=True)
    sv = np.pad(s, (0, max(0, 7 - len(s))))
    rank = int(np.sum(sv > sv[0] * 1e-8)) if sv[0] else 0
    return dict(rows=len(J), rank=rank, singular_values=sv.tolist(),
                condition=float(sv[0] / sv[-1]) if rank == 7 else None,
                weakest_direction=vt[-1].tolist())


def main():
    result_path = DEST / 'results.json'
    if result_path.exists():
        raise RuntimeError('Preserve the previous run')
    DEST.mkdir(parents=True, exist_ok=True)
    fixed_path = ROOT / 'DataSet/sonar_fixed_mesh/fixed-mesh-transforms.json'
    rows_path = ROOT / 'DataSet/sonar_fixed_mesh/results.json'
    select_path = ROOT / 'DataSet/sonar_independent_registration/selection.json'
    manifest_path = ROOT / 'DataSet/camera_temporal_all/manifest-resolved.json'
    beam_path = ROOT / 'related_work/uxo-upstream-history/scripts/common/aris_definitions.py'
    models = read(fixed_path)['models']
    rows = read(rows_path)['outputs']
    selection = read(select_path)['samples']
    allowed = {x['sample']: x for x in read(manifest_path)['items'] if x.get('paired_role') in ['train', 'val', 'val_id']}
    assert len(rows) == len(selection) == 18
    assert {x['sample'] for x in rows} == {x['sample'] for x in selection}
    assert all(x['sample'] in allowed for x in rows)
    arrays = {}
    for node in ast.parse(beam_path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in ['BeamWidthsAris3000_64', 'BeamWidthsAris3000_128']:
                    arrays[int(t.id.split('_')[-1])] = np.array(ast.literal_eval(node.value))
    inputs = [fixed_path, rows_path, select_path, manifest_path, beam_path, Path(__file__), ROOT / 'experiment/sonar-registration-methods-plan.md']
    inputs += [Path(m['source']) for m in models.values()]
    before = {str(p): sha(p) for p in inputs}
    params = ['world_tx / 1cm', 'world_ty / 1cm', 'world_tz / 1cm', 'world_rx / 1deg', 'world_ry / 1deg', 'world_rz / 1deg', 'log_scale / 0.01']
    all_results = {}
    for name, model in models.items():
        vertices = []
        for line in Path(model['source']).read_text(encoding='utf-8').splitlines():
            if line.startswith('v '):
                vertices.append([float(x) for x in line.split()[1:4]])
        vertices = np.array(vertices)
        S = np.array(model['mesh_to_target_similarity'])
        target = vertices @ S[:3, :3].T + S[:3, 3]
        ids = sorted(set(np.r_[target.argmin(axis=0), target.argmax(axis=0)].tolist()))
        landmarks = target[ids]
        W = np.array(model['world_from_target'])
        delta_world = landmarks @ W[:3, :3].T
        center = W[:3, 3]
        model_rows = [r for r in rows if r['model'] == name]
        recs = list(dict.fromkeys(r['recording'] for r in model_rows))
        Jall = []
        Jvis = []
        frame_results = []
        max_rel_error = 0.
        for row in model_rows:
            SW = np.array(row['sonar_from_world'])
            P = (delta_world + center) @ SW[:3, :3].T + SW[:3, 3]
            r = np.linalg.norm(P, axis=1)
            b = -np.rad2deg(np.arctan2(P[:, 0], P[:, 2]))
            e = np.rad2deg(np.arctan2(P[:, 1], np.hypot(P[:, 0], P[:, 2])))
            beam = arrays[row['raw_shape_hw'][1]]
            ib = np.clip(np.searchsorted(beam[:, 0], b) - 1, 0, len(beam) - 2)
            sigma_b = beam[ib + 1, 0] - beam[ib, 0]
            dr = row['range_bin_m']
            valid = (P[:, 2] > 0) & (r >= row['range_start_m']) & (r <= row['range_end_m']) & (b >= beam[0, 1]) & (b <= beam[-1, 2]) & (np.abs(e) <= 7)
            dW = np.zeros((len(P), 3, 7))
            for i in range(3):
                dW[:, i, i] = .01
                dW[:, :, i + 3] = np.cross(np.eye(3)[i], delta_world) * np.pi / 180
            dW[:, :, 6] = delta_world * .01
            dP = np.einsum('ab,nbk->nak', SW[:3, :3], dW)
            grad_r = P / r[:, None] / dr
            grad_b = np.zeros_like(P)
            denom = P[:, 0] ** 2 + P[:, 2] ** 2
            grad_b[:, 0] = -P[:, 2] / denom * 180 / np.pi / sigma_b
            grad_b[:, 2] = P[:, 0] / denom * 180 / np.pi / sigma_b
            Ja = np.stack([np.einsum('na,nak->nk', grad_r, dP), np.einsum('na,nak->nk', grad_b, dP)], axis=1).reshape(-1, 7)

            def observe(x):
                points = (delta_world * np.exp(x[6] * .01)) @ rotvec(x[3:6] * np.pi / 180).T + center + x[:3] * .01
                pp = points @ SW[:3, :3].T + SW[:3, 3]
                return np.stack([np.linalg.norm(pp, axis=1) / dr, -np.rad2deg(np.arctan2(pp[:, 0], pp[:, 2])) / sigma_b], axis=1).ravel()

            errors = []
            for step in [.01, .005]:
                Jf = np.empty_like(Ja)
                for k in range(7):
                    x = np.eye(7)[k] * step
                    Jf[:, k] = (observe(x) - observe(-x)) / (2 * step)
                errors.append(float(np.max(np.abs(Ja - Jf)) / max(1., np.max(np.abs(Ja)))))
            max_rel_error = max(max_rel_error, *errors)
            assert max(errors) < 1e-5
            Jall.append(Ja)
            Jvis.append(Ja[np.repeat(valid, 2)])
            frame_results.append(dict(sample=row['sample'], visible_landmarks=int(valid.sum()), landmarks=len(P),
                                      finite_difference_relative_errors=errors, all_ideal=describe(Ja), visible_ideal=describe(Jvis[-1])))
        groups = {}
        for label, inds in [('single_frame', [0]), ('first_recording', [i for i, rr in enumerate(model_rows) if rr['recording'] == recs[0]]), ('both_recordings', list(range(len(model_rows))))]:
            groups[label] = dict(all_ideal=describe(np.concatenate([Jall[i] for i in inds])), visible_ideal=describe(np.concatenate([Jvis[i] for i in inds])))
        all_results[name] = dict(vertex_ids=ids, landmark_points_target_m=landmarks.tolist(), recording_order=recs, frames=frame_results, groups=groups, max_analytic_difference=max_rel_error)
    assert before == {str(p): sha(p) for p in inputs}
    data = dict(run='sonar_registration_methods/registration_observability', status='completed ideal-correspondence diagnostic, not registration',
                parameter_normalization=params, observation_normalization='range / one range bin; beam-table angle / local adjacent-beam spacing, frozen at nominal point',
                caveats=['Six extremal vertices have assumed known cross-frame identities. Real sonar highlights do not supply these correspondences.',
                         'all_ideal includes points outside the image; visible_ideal uses nominal range/beam and assumed +/-7deg elevation.',
                         'Rank is not a claim of practical identifiability; roll and head-tail ambiguity of unlabeled near-symmetric shapes remain.',
                         'Both recordings were previously observed; this is development geometry and no model was fit.',
                         'With fixed observation rows and normalization, a global bearing sign reversal only reverses Jacobian rows. Recomputing beam spacing or visibility can change the SVD; neither procedure establishes the physical sign.'],
                models=all_results, input_hashes=before, inputs_unchanged=True, fits=0, new_gt=0, test_access=False)
    result_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    for ax, (name, result) in zip(axes, all_results.items()):
        for label, group in result['groups'].items():
            s = group['visible_ideal']['singular_values']
            if s:
                ax.semilogy(range(1, 8), np.maximum(s, 1e-7), marker='o', label=label.replace('_', ' '))
        ax.set(title=name, xlabel='Singular value index', ylabel='Sensitivity in bin/beam units')
        ax.grid(True, alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle('Ideal labeled mesh points: visibility-limited geometric sensitivity\nAssumed point identities, not measured sonar registration accuracy', fontsize=11)
    fig.tight_layout()
    fig.savefig(DEST / 'sensitivity.png', dpi=170)
    plt.close(fig)
    lines = ['# 理想对应点的注册可观测性诊断', '', '不是回波拟合，也不是GT认证；采用既有固定模型与18帧位姿。', '', '| 模型 | 组 | 可见观测行 | 秩 | 条件数 |', '|---|---|---:|---:|---:|']
    for name, rr in all_results.items():
        for label, g in rr['groups'].items():
            d = g['visible_ideal']; condition = f"{d['condition']:.2f}" if d['condition'] is not None else '不可定'
            lines.append(f"| {name} | {label} | {d['rows']} | {d['rank']} | {condition} |")
    lines += ['', '参数单位：世界平移每1cm、世界旋转每1°、log尺度每0.01；观测单位：每帧一个range bin和局部相邻beam角距。',
              '', '每个模型取6个轴向极值顶点，假设其跨帧身份已知。现实声呐高光不是这些可匹配点，因此满秩只表示理想几何有信息，不能证明实际注册唯一或精度合格。',
              '', '可见性按旧模型名义位置与±7°检查；当前模型本就未注册，此处不能证明实际目标不可见。全点/可见点两套结果及每帧SVD摘要都保存在results.json；不保存完整Jacobian矩阵。',
              '', '轴对称的roll、头尾以及mesh形状和目标位置之间的混淆仍需语义锚点、受限参数和跨轨迹检查；符号翻转不改变此SVD的结果，不能用它判断beam正负。',
              '', '解析导数与两步长中心差分通过，输入hash不变。未拟合模型、未读新声呐图或test，正式标签输出0。']
    (DEST / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({n: r['groups'] for n, r in all_results.items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
