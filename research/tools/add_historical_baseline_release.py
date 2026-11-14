"""Add historical baseline metrics and their frozen dataset metadata to a release.

Reads allowlisted existing outputs only; never executes training or evaluation.
"""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil


SOURCE = Path(__file__).resolve().parents[1]
CHECKOUT = SOURCE / 'publication/VSFusionDistill'
RESEARCH = CHECKOUT / 'research'
ORIGINAL = SOURCE.parent / '声呐目标检测/code/VSFusionDistill'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    manifest_path = RESEARCH / 'publication-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = {row['published']: row for row in manifest['records']}
    copies = {}

    def publish(src, rel=None, compress=False, source_root=SOURCE):
        rel = rel or src.relative_to(SOURCE).as_posix()
        dest = RESEARCH / (rel + ('.gz' if compress else ''))
        data = src.read_bytes()
        dest.parent.mkdir(parents=True, exist_ok=True)
        if compress:
            with dest.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
                stream.write(data)
        else:
            dest.write_bytes(data)
        key = dest.relative_to(CHECKOUT).as_posix()
        origin = src.relative_to(source_root).as_posix()
        if source_root == ORIGINAL:
            origin = 'original-code/' + origin
        elif source_root != SOURCE:
            origin = str(src)
        records[key] = {'source': origin, 'published': key, 'source_sha256': sha(data),
                        'published_sha256': sha(dest.read_bytes()),
                        'transformation': 'gzip; original JSON bytes preserved' if compress else 'copy'}
        copies[rel] = dest.relative_to(RESEARCH).as_posix()
        return dest

    # Exact metadata for the data versions actually used by completed baselines.
    for folder in ['camera_recording_baseline', 'workstation_baselines',
                   'scene_expanded_baseline_trainval', 'scene_baseline_test715']:
        for path in (SOURCE / 'DataSet' / folder).glob('*.json'):
            publish(path, compress=path.stat().st_size > 500_000)
    for folder in ['paired_recording_split', 'scene_stratified_mortar_recovered_candidate']:
        directory = SOURCE / 'DataSet' / folder
        publish(directory / 'manifest.json', compress=True)
        for path in directory.glob('*.txt'):
            publish(path)
    # This original split is the already-audited 4152-frame train+val pool.
    split = Path('D:/pby/uxo-full/repro/frame_split.json')
    publish(split, 'legacy_code_data/frame_split.json', source_root=split.parent)
    # Original-code outputs: explicit non-test allowlist; no image/annotation access.
    legacy = [
        ('t_camera_s', 'eval_val'),
        ('t_camera_s_stretch', 'eval_val'),
        ('t_camera_s', 'eval_val_stretch'),
    ]
    rows = []
    for run, evaluation in legacy:
        base = ORIGINAL / 'results/repro_cmold' / run / evaluation
        for name in ['ap_summary.json', 'ap_breakdown.json']:
            publish(base / name, f'legacy_code_results/repro_cmold/{run}/{evaluation}/{name}', source_root=ORIGINAL)
        config = ORIGINAL / 'work_dirs/repro_cmold_teacher' / run
        for name in ['run_meta.txt', f'{run}_yoloxs.py']:
            path = config / name
            if path.exists():
                publish(path, f'legacy_code_configs/{run}/{name}', source_root=ORIGINAL)
        summary = json.loads((base / 'ap_summary.json').read_text(encoding='utf-8'))[0]
        rows.append({'dataset_version': 'legacy_frame_split_4152', 'run': run + '/' + evaluation,
                     'model': 'camera YOLOX-S', 'split': 'val', 'images': 830, 'epochs': 200,
                     'weights': 'historical evaluator checkpoint; not new actual-raw evaluation',
                     'mAP': summary['AP'] * 100, 'AP50': summary['AP50'] * 100,
                     'AP75': summary['AP75'] * 100, 'AR1': None, 'AR100': summary['AR@100'] * 100,
                     'metrics_file': f'legacy_code_results/repro_cmold/{run}/{evaluation}/ap_summary.json'})
    specs = [
        ('recording_split_3000', 'camera_recording_baseline', 'camera YOLOX-S 640x384', 'train', 1800),
        ('recording_split_3000', 'camera_recording_baseline', 'camera YOLOX-S 640x384', 'val', 600),
        ('recording_split_3000', 'camera_recording_baseline', 'camera YOLOX-S 640x384', 'test', 600),
        ('recording_split_3000', 'camera_recording_m', 'camera YOLOX-M 640x384', 'val', 600),
        ('scene_split_4081', 'scene_camera_m_baseline/after_pilot', 'camera YOLOX-M fixed640', 'train', 2472),
        ('scene_split_4081', 'scene_camera_m_baseline/after_pilot', 'camera YOLOX-M fixed640', 'val', 894),
        ('scene_split_4081', 'scene_camera_m_baseline/after_pilot', 'camera YOLOX-M fixed640', 'test', 715),
        ('scene_split_4081', 'scene_sonar_s_baseline/after_pilot', 'sonar YOLOX-S fixed640', 'train', 2472),
        ('scene_split_4081', 'scene_sonar_s_baseline/after_pilot', 'sonar YOLOX-S fixed640', 'val', 894),
        ('scene_split_4081', 'scene_sonar_s_baseline/after_pilot', 'sonar YOLOX-S fixed640', 'test', 715),
    ]
    for version, run, model, role, count in specs:
        rel = f'runs/{run}/train/{role}_actual_raw_epoch200/metrics.json'
        result = json.loads((SOURCE / rel).read_text(encoding='utf-8'))
        pooled = result['pooled']
        rows.append({'dataset_version': version, 'run': run, 'model': model,
                     'split': role, 'images': count, 'epochs': 200, 'weights': 'epoch200 actual raw',
                     **{key: pooled[key] * 100 for key in ['mAP', 'AP50', 'AP75', 'AR1', 'AR100']},
                     'metrics_file': rel})
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    write(RESEARCH / 'baselines.csv', output.getvalue())
    write(RESEARCH / 'baselines.json', json.dumps({'units': 'percent', 'source': 'existing outputs; no reevaluation',
                                                 'rows': rows}, ensure_ascii=False, indent=2) + '\n')
    sections = [BASELINE_INTRO]
    for version, title in [('legacy_frame_split_4152', '早期原代码：同录音val'),
                           ('recording_split_3000', '3000对recording-level split'),
                           ('scene_split_4081', '4081对scene扩充版')]:
        sections.extend(['\n## ' + title + '\n',
                         '| 模型 / 条件 | 集合 | 图像数 | mAP | AP50 | AP75 | AR@1 | AR@100 | 原始结果 |',
                         '|---|---|---:|---:|---:|---:|---:|---:|---|'])
        for row in rows:
            if row['dataset_version'] != version:
                continue
            label = row['model']
            if 'eval_val_stretch' in row['run']:
                label += '，仅评测stretch（诊断）'
            elif 't_camera_s_stretch' in row['run']:
                label += '，train/eval stretch（诊断）'
            vals = ['N/A' if row[k] is None else f'{row[k]:.2f}' for k in ['mAP', 'AP50', 'AP75', 'AR1', 'AR100']]
            sections.append('| ' + ' | '.join([label, row['split'], str(row['images']), *vals,
                                               f"[JSON]({row['metrics_file']})"]) + ' |')
    sections.append(BASELINE_TAIL)
    write(RESEARCH / 'BASELINES.md', '\n'.join(sections))
    write(RESEARCH / 'DATASETS.md', DATASETS)
    # Give existing artifact notices direct links to subsequently added metadata.
    artifact = RESEARCH / 'ARTIFACTS.md'
    content = artifact.read_text(encoding='utf-8')
    for original, published in copies.items():
        token = f'- `{original}`\n'
        if token in content:
            content = content.replace(token, token + f'\n  本次已补充[仓库副本]({published})，gzip文件解压后为原始JSON。\n')
    write(artifact, content)
    # Main entry points lead with the two requested historical baseline indexes.
    for rel in ['research/README.md']:
        path = CHECKOUT / rel
        text = path.read_text(encoding='utf-8')
        prefix = 'research/' if rel == 'README.md' else ''
        lines = text.split('\n', 1)
        notice = f'\n\n**历史baseline入口：[模型结果汇总]({prefix}BASELINES.md) · [对应数据集与划分]({prefix}DATASETS.md) · [指标CSV]({prefix}baselines.csv)。**\n'
        write(path, lines[0] + notice + '\n' + lines[1].lstrip())
    # Include this exporter as a reproducible source artifact.
    publish(Path(__file__).resolve())
    manifest['records'] = sorted(records.values(), key=lambda row: row['published'])
    manifest['additional_scope'] = 'historical baseline results and frozen dataset metadata requested by user; no full image upload'
    write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'baseline_result_rows': len(rows), 'additional_metadata_files': len(copies),
                      'total_import_records': len(records)}, ensure_ascii=False))


BASELINE_INTRO = """# 历史模型baseline结果

2026-11-14整理。数值直接读取既有结果JSON，没有重新运行模型或COCOeval。全部指标为百分数，mAP为pooled COCO AP@[.5:.95]，AR@1与AR@100分列。每一行链接到原结果，数据版本见[数据集索引](DATASETS.md)；另提供[CSV](baselines.csv)与[完整精度JSON](baselines.json)。

不同划分、几何、GT与权重身份的结果分别列出，不合成模型排名。val、train自评、已使用test分开；train自评不能代替泛化证据。

早期原代码表沿用历史评测器加载的epoch200 checkpoint，不冒称本次补评的actual raw；后两表采用已经单独核验的epoch200 actual raw。旧目录`val_raw_epoch200`实际可能为EMA，主表只引用`val_actual_raw_epoch200`。"""

BASELINE_TAIL = """
## 对应实验材料与尚无最终结果的项目

- 3000对S/M的[逐类AP/AR](复现/camera-baseline/per-class-baseline-results.md)、[S权重更正](runs/camera_recording_baseline/train/evaluation-weight-correction.json)、[M权重更正](runs/camera_recording_m/train/evaluation-weight-correction.json)。S/M预训练来源不同，不能作纯容量因果比较。
- 4081对的[逐类/录音/场景分析](复现/camera-baseline/scene-expanded-baselines-final-results.md)、[已使用715 test报告](复现/camera-baseline/scene-baselines-test715-results.md)。相机与声呐使用各自GT，指标差不能称蒸馏收益。
- 10epoch camera-M pilot是独立诊断，不与200epoch run拼接；见[pilot报告](复现/camera-baseline/camera-m-pilot-distribution.md)。
- 早期workstation camera-S fixed640 / sonar-S在本次发布依据的记录中没有最终actual raw结果，不能补写成完成，见[部署记录](DataSet/workstation_baselines/README.md)。
- 最新5229对camera-M仅有启动与迁移证据，本次未实时确认完成，无该版最终AP可填，见[最新进展](README.md)。
- 更早的E11、R0/R1/R2、多seed及融合历史保留在原代码[实验台账](../doc/experiments.md)与[历史日志](../doc/logs/)。这些记录涉及不同blob/all、val/val_id、平台与任务；本次没有重新核验全部原始产物，不搬入上方统一口径表。

这张表只登记已有模型成绩，不把完美GT/错类合成控制的AP当成训练模型指标。所有test结果均来自已有评价文件，当前整理没有读取原研究test图像或标注、没有新评价或调参。
"""

DATASETS = """# 历史baseline对应的数据集与划分

本页把每组模型成绩对应到当时使用的数据版本。仓库发布成员身份、标签/框元数据、划分协议、文件hash及部分配置；全量图像、视频和模型权重仍保存在本地。本次没有建立这些大文件的下载地址，不能把本仓库称为开箱即用的完整数据集。

| 版本 | baseline模型 | train / val / test | 划分性质与入口 |
|---|---|---|---|
| 原代码4152帧train+val池 | t_camera_s、t_camera_s_stretch | 3322 / 830 / 本表不迁入原test | train/val共享37录音；[原frame_split](legacy_code_data/frame_split.json)、[原始审计](复现/camera-baseline/results-and-failure-evidence.md) |
| 3000对 | camera YOLOX-S/M 640×384；workstation S两模态 | 1800 / 600 / 600 | 每类6/2/2录音，122608/122855保守同组；[协议](DataSet/paired_recording_split/protocol.json)、[录音表](DataSet/paired_recording_split/recordings.csv)、[完整manifest](DataSet/paired_recording_split/manifest.json.gz) |
| 4081对 | scene camera-M / sonar-S after_pilot | 2472 / 894 / 715 | 37录音、31保守来源组；[协议](DataSet/scene_stratified_mortar_recovered_candidate/protocol.json)、[录音表](DataSet/scene_stratified_mortar_recovered_candidate/recordings.csv)、[完整manifest](DataSet/scene_stratified_mortar_recovered_candidate/manifest.json.gz) |
| 5229对当前版 | 最新weak_coverage_camera_m_teacher，尚无本次确认的最终结果 | 4138 / 573 / 518 | 42录音、35保守来源组；[协议](DataSet/paired_weak_scene_coverage_pan_split/protocol.json)、[录音表](DataSet/paired_weak_scene_coverage_pan_split/recordings.csv)、[完整manifest](DataSet/paired_weak_scene_coverage_pan_split/manifest.json.gz) |

## 训练与评测使用的标签元数据

- 3000对本地camera S/M：[train COCO压缩副本](DataSet/camera_recording_baseline/train-coco.json.gz)、[val COCO](DataSet/camera_recording_baseline/val-coco.json)、[历史test COCO](DataSet/camera_recording_baseline/test-coco.json)、[准备与身份核验](DataSet/camera_recording_baseline/verification.json)。相机输入640×384，与fixed640工作站分开。
- 3000对工作站相机/声呐：对应[数据目录](DataSet/workstation_baselines/)包含两模态train/val COCO与dataset压缩副本、成员表和文件hash；不含图像。其最终模型结果在本次依据的记录中仍缺失。
- 4081对正式baseline：对应[执行数据目录](DataSet/scene_expanded_baseline_trainval/)包含两模态train/val COCO、dataset、成员表和hash；[train camera COCO](DataSet/scene_expanded_baseline_trainval/camera-train-coco.json.gz)、[val camera COCO](DataSet/scene_expanded_baseline_trainval/camera-val-coco.json)、[val sonar COCO](DataSet/scene_expanded_baseline_trainval/sonar-val-coco.json)。[历史715 test元数据](DataSet/scene_baseline_test715/)另列。
- 最新5229对教师：[相机train/val执行副本元数据](DataSet/camera_weak_coverage_trainval/)、[run冻结](runs/weak_coverage_camera_m_teacher/dataset-freeze.json)。当前角色变更不适用于旧模型的结果表。

3000和4081对版本各自保留train/val/test身份列表。`.json.gz`解压后与发布清单中的源SHA256一致；原始JSON内的本机路径保留用于血缘追溯，换机器时需要准备图像并调整路径。标签由各自数据准备脚本生成，类别编号/名称和几何以相应COCO、dataset与配置为准，不跨版本直接替换。

## 图像、标注来源与历史边界

原始UXO来源：[官方仓库](https://github.com/dfki-ric/uxo-dataset2024) / [Zenodo v1.1](https://zenodo.org/records/13778485)。我方存在时间对应恢复、筛选、声呐可见回波框和助手补标，仅下载原数据不等于得到相同训练集。完整本地位置保存在各版本manifest、准备脚本与[数据演进记录](dataset.md)。

最新新增393对含助手相机标注，不能统称官方原标签或专家GT。原研究的历史声呐blob/projected标签与workflow的可见回波标签要分别标注。旧val/test已用于评价或开发诊断，重划分不能恢复盲测资格；[历史模型结果](BASELINES.md)按原版本列出，禁止用当前划分解释旧分数。

原研究保留test的图像与混合标注没有在此次发布整理中读取或上传。这里的历史600/715 test元数据来自workflow里此前已授权生成的独立产物，没有新推理或评价。
"""


if __name__ == '__main__':
    main()
