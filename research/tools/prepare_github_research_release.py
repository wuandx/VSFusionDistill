"""Export an auditable, lightweight research snapshot into a separate Git checkout.

Only reads the workflow. Does not run experiments, access original test data,
or modify the original code checkout. Large artifacts remain local.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import unquote


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    checkout = args.destination.resolve()
    assert (checkout / ".git").exists(), "Destination must be a separate Git checkout"
    assert checkout != source and "声呐目标检测_workflow" in str(checkout)
    target = checkout / "research"
    assert not target.exists(), "Refuse to overwrite an existing research snapshot"
    selected = set()

    def select(path):
        if path.is_file():
            selected.add(path)

    for name in ["dataset.md", "handoff.md", "brainstorm.md"]:
        select(source / name)
    for folder in ["tools", "experiment", "paper", "复现", "related_work"]:
        for path in (source / folder).rglob("*"):
            rel = path.relative_to(source)
            if set(rel.parts) & {"__pycache__", "_audit_deps", "_sonar_audit_deps", ".git", "source", "downloads", "uxo-upstream-history"}:
                continue
            if not path.is_file():
                continue
            if folder == "tools" and len(rel.parts) != 2:
                continue
            suffixes = {".md", ".py", ".sh", ".ps1", ".json", ".csv", ".yaml", ".yml", ".toml"}
            if path.suffix.lower() in suffixes and path.stat().st_size <= 4_000_000:
                select(path)
            if folder == "复现" and path.suffix.lower() in {".jpg", ".png"} and path.stat().st_size <= 500_000:
                select(path)
    for folder in ["docs", "engine", "plugin", "tests", "tools"]:
        for path in (source / "sonar_llm_annotation" / folder).rglob("*"):
            if "__pycache__" not in path.parts and path.suffix in {".md", ".py", ".yaml", ".yml", ".json"} and path.is_file() and path.stat().st_size <= 200_000:
                select(path)
    for name in ["README.md", "BRIEF.md"]:
        select(source / "sonar_llm_annotation" / name)
    for path in (source / "runs").rglob("*"):
        if not path.is_file() or set(path.parts) & {"__pycache__", "vis_data"}:
            continue
        if path.suffix in {".md", ".py", ".json", ".csv"} and path.name != "predictions.json" and path.stat().st_size <= 4_000_000:
            select(path)
        if path.suffix in {".png", ".jpg"} and "review" in str(path.parent) and path.stat().st_size <= 500_000:
            select(path)
    metadata_names = {
        "README.md", "protocol.json", "summary.json", "recordings.csv", "recordings.json",
        "scene-coverage.json", "verification.json", "independent-verification.json",
        "user-split-confirmation.json", "review-decisions-final.json", "review-summary-final.json",
        "allocation.json", "role-changes.csv", "role-changes.json", "pan-support.json", "search.json",
        "startup-verification.json",
    }
    for directory in (source / "DataSet").iterdir():
        if directory.is_dir():
            for name in metadata_names:
                path = directory / name
                if path.is_file() and path.stat().st_size <= 1_000_000:
                    select(path)
    current = source / "DataSet" / "paired_weak_scene_coverage_pan_split"
    for name in ["train.txt", "val.txt", "test.txt", "artifact-sha256.json"]:
        select(current / name)
    for path in (current / "provenance").iterdir():
        select(path)
    for path in (source / "DataSet" / "camera_weak_coverage_trainval").glob("*.json"):
        select(path)
    for path in (source / "assets").rglob("*.py"):
        select(path)
    for path in (source / "assets").rglob("*.json"):
        if path.stat().st_size <= 100_000:
            select(path)

    records = []
    for path in sorted(selected):
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        records.append({"source": path.relative_to(source).as_posix(),
                        "published": destination.relative_to(checkout).as_posix(),
                        "source_sha256": sha(path), "transformation": "copy"})

    manifest = current / "manifest.json"
    compressed = target / "DataSet" / current.name / "manifest.json.gz"
    with compressed.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as archive:
        with manifest.open("rb") as stream:
            shutil.copyfileobj(stream, archive)
    records.append({"source": manifest.relative_to(source).as_posix(),
                    "published": compressed.relative_to(checkout).as_posix(),
                    "source_sha256": sha(manifest), "transformation": "gzip; original JSON bytes preserved"})
    shutil.copyfile(source / "AGENTS.md", target / "workflow-instructions-snapshot.md")
    records.append({"source": "AGENTS.md", "published": "research/workflow-instructions-snapshot.md",
                    "source_sha256": sha(source / "AGENTS.md"), "transformation": "renamed historical instructions"})
    shutil.copyfile(checkout / "README.md", checkout / "README.legacy.md")
    write(target / "README.md", RESEARCH_README)
    write(target / "REPRODUCIBILITY.md", REPRODUCIBILITY)
    write(checkout / "README.md", ROOT_README)
    write(target / "paper" / "README.md", PAPER_README)
    for name in ["dataset.md", "baseline.md"]:
        path = target / "paper" / name
        write(path, "> 版本提示：这是历史论文草稿，内容对应较早的数据/实验版本，尚未更新为当前5229对划分。当前事实以[研究进展入口](../README.md)及其链接的冻结记录为准。\n\n" + path.read_text(encoding="utf-8"))
    for rel, note in [
        ("复现/camera-baseline/README.md", "这是早期审计总报告，后续训练和数据版本已经推进；最新进展见[研究入口](../../README.md)。"),
        ("runs/weak_coverage_camera_m_teacher/README.md", "运行位置更正：本地尝试已停止并迁移至5090。此处保留本地记录，最新位置见[部署报告](../../复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)。本次发布未实时查询远端训练。"),
    ]:
        path = target / rel
        write(path, "> " + note + "\n\n" + path.read_text(encoding="utf-8"))

    omitted = {}
    rewrites = []
    pattern = re.compile(r"(!?)\[([^\]\n]*)\]\(([^)\n]+)\)")
    for path in sorted(target.rglob("*.md")):
        original = path.read_text(encoding="utf-8-sig")

        def replace(match):
            image, label, href = match.groups()
            href = href.strip()
            if href.startswith(("https://", "http://", "mailto:", "#", "app://", "codex://")):
                return match.group(0)
            href = href.removeprefix("<").removesuffix(">")
            plain = unquote(href.split("#", 1)[0]).replace("\\", "/")
            dest = (path.parent / plain).resolve()
            if dest.exists() and dest.is_relative_to(checkout):
                return match.group(0)
            if dest == target / "DataSet" / current.name / "manifest.json":
                return f"[{label}（gzip）]({href}.gz)"
            intended = os.path.relpath(dest, target).replace("\\", "/")
            key = hashlib.sha256(intended.encode("utf-8")).hexdigest()[:12]
            omitted[key] = intended
            replacement = os.path.relpath(target / "ARTIFACTS.md", path.parent).replace("\\", "/")
            rewrites.append({"file": path.relative_to(checkout).as_posix(), "original_target": href,
                             "published_target": replacement + "#artifact-" + key})
            return f"[{('图：' if image else '') + label}（本地产物说明）]({replacement}#artifact-{key})"

        updated = pattern.sub(replace, original)
        if updated != original:
            write(path, updated)
    lines = ["# 数据与本地产物", "", "GitHub包含研究记录、脚本、冻结清单和精选结果；全量图像、视频、权重、原论文文件及旧浏览页的依赖资源继续保存在本地。本次没有建立这些大文件的公开下载地址。", "", "原始UXO来源：[官方仓库](https://github.com/dfki-ric/uxo-dataset2024) / [Zenodo v1.1](https://zenodo.org/records/13778485)。我方新增标注、筛选和划分不能用原始数据下载代替。", "", "当前完整配对manifest以`DataSet/paired_weak_scene_coverage_pan_split/manifest.json.gz`提供；解压后与冻结源JSON逐字节相同。图像和模型权重未上传。", "", "历史报告中的未随仓库发布的文件链接已改为指向下列说明，原始目标保存在`publication-link-rewrites.json`。以下是本地定位信息，不表示文件已公开或可在线浏览。", ""]
    for key, intended in sorted(omitted.items(), key=lambda item: item[1]):
        lines.extend([f'<a id="artifact-{key}"></a>', f"- `{intended}`", ""])
    write(target / "ARTIFACTS.md", "\n".join(lines))
    write(target / "publication-link-rewrites.json", json.dumps(rewrites, ensure_ascii=False, indent=2) + "\n")
    for record in records:
        path = checkout / record["published"]
        record["published_sha256"] = sha(path)
        if record["transformation"] == "copy" and record["source_sha256"] != record["published_sha256"]:
            record["transformation"] = "publication banner and/or local-link rewrite; historical content retained"
    report = {"snapshot_date": "2026-11-14", "source_code_commit": "4fadd06829c6c738977639a55b6e44ad0e35ac44",
              "workflow_source": str(source), "records": records,
              "omitted_link_count": len(rewrites), "omitted_artifact_count": len(omitted),
              "scope": "publication only; no training, inference, or original test access"}
    write(target / "publication-manifest.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    write(checkout / ".gitattributes", "* text=auto\n*.md text eol=lf\n*.py text eol=lf\n*.sh text eol=lf\n*.ps1 text eol=lf\n*.json text eol=lf\n*.csv text eol=lf\n*.gz binary\n*.png binary\n*.jpg binary\n# Preserve imported source bytes and the hashes in publication-manifest.json.\nresearch/** -text\n")
    with (checkout / ".gitignore").open("a", encoding="utf-8") as stream:
        stream.write("\n# Research snapshots: large/runtime artifacts stay outside Git\n**/__pycache__/\n*.pth\n*.pt\n*.onnx\n*.7z\n*.tar\n*.mp4\n*.avi\n*.pyd\nresearch/**/images/\nresearch/**/previews/\nresearch/**/vis_data/\n")
    print(json.dumps({"copied_files": len(records), "rewritten_links": len(rewrites),
                      "published_bytes": sum(f.stat().st_size for f in target.rglob('*') if f.is_file()),
                      "destination": str(checkout)}, ensure_ascii=False))


ROOT_README = """# UXO声呐目标检测与camera-only teacher基线

本仓库保存VSFusionDistill模型代码，以及基于公开UXO数据的相机—声呐数据整理、基线复现和实验记录。当前阶段先固定数据、标注、recording-level split与测评协议，验证camera-only teacher，再推进相机到声呐的知识蒸馏。

**研究快照：2026-11-14。** 建议老师先读[最新进展与结果](research/README.md)，再按需查看证据。

| 当前工作 | 状态与入口 |
|---|---|
| 数据构建与扩充 | 当前5229对、42条录音、35个保守来源组；[构建与更正记录](research/复现/camera-baseline/four-recording-paired-expansion-5229.md) |
| 当前划分 | train4138 / val573 / test518；[覆盖与限制](research/复现/camera-baseline/weak-scene-coverage-resplit-5229.md) |
| 已完成的开发baseline | 旧4081对划分下camera-M val mAP89.37%、sonar-S val mAP51.38%；[完整结果](research/复现/camera-baseline/scene-expanded-baselines-final-results.md) |
| 最新camera-only YOLOX-M | 最新划分下已启动并迁移至5090；发布依据是18:09启动记录，未实时查询或确认完成；[部署证据](research/复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md) |
| 论文与下一步 | [草稿版本说明](research/paper/README.md)；完成最新教师训练核验后，登记当前划分val结果，再决定后续蒸馏 |

上述旧baseline结果不属于最新5229对划分，不能直接用来证明扩充收益。当前划分受旧val/test诊断启发，属于开发协议，不能称未触碰盲测；新增393对的相机框为助手补标，非官方原标注或专家GT。细节见[测评协议](research/experiment/evaluation.md)。

## 阅读与代码入口

- [研究进展、数据版本与指标](research/README.md)
- [实验登记](research/experiment/results.md) / [测评协议](research/experiment/evaluation.md)
- [数据说明](research/dataset.md) / [最新录音划分表](research/DataSet/paired_weak_scene_coverage_pan_split/recordings.csv)
- [模型代码](aodet/) / [已有配置](configs/) / [研究处理脚本](research/tools/)
- [复现输入与运行边界](research/REPRODUCIBILITY.md) / [数据与本地产物](research/ARTIFACTS.md)
- [早期架构与运行说明](README.legacy.md) / [历史中文说明](README.zh-CN.md)

`research/`是本地workflow的精选发布快照；完整图像、视频、权重和历史浏览页资源保存在本地。代码历史继续保留，历史记录中的结论以较新的明确更正为准。原仓库的早期融合/退化研究说明保留在历史入口中。
"""

RESEARCH_README = """# 研究进展与证据入口

更新日期：2026-11-14。本页用于阶段汇报；详细原始记录和更正继续保留。数据处理、已完成模型结果和最新训练分别列出。

## 已完成的工作

1. 审计CMOLD/CMHD论文与原实现，区分论文事实、原始产物复算和我方选择；[文献核验](related_work/paper-evidence-review.md)。
2. 追查相机SD/FHD时间对应问题，保留原标签与重建血缘；[完整源审计](复现/camera-baseline/annotation-issues/full-source-timing-cause-audit.md)。
3. 扩充配对数据、双端审阅、补标与独立核验，当前5229对、42录音、35保守来源组；[四录音扩充报告](复现/camera-baseline/four-recording-paired-expansion-5229.md)。
4. 完成一版camera-M与sonar-S开发baseline，并按类、录音、场景分析失败；[完整结果](复现/camera-baseline/scene-expanded-baselines-final-results.md)。
5. 针对已知薄弱条件重划分，并在最新train/val启动camera-only YOLOX-M；[划分报告](复现/camera-baseline/weak-scene-coverage-resplit-5229.md)、[启动与迁移](复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)。

## 当前数据版本

权威版本：`paired_weak_scene_coverage_pan_split`。保守来源组整体分配，不在不同集合之间拆开。

| 集合 | 配对数 | 录音数 | 保守来源组数 |
|---|---:|---:|---:|
| train | 4138 | 33 | 27 |
| val | 573 | 5 | 5 |
| test | 518 | 4 | 3 |
| 总计 | 5229 | 42 | 35 |

八种已登记scene进入train，27种已有scene×z×tilt×roll联合条件覆盖；这不等于覆盖所有设置、视图或物理姿态。floor ellipse和两种bomb flyby无独立留出，test只有三个保守来源组。旧val/test曾用于开发，重新划分不会消除这段历史。新增393对含助手相机标注；7个未决候选没有纳入训练，也不作为负样本。

证据：[协议](DataSet/paired_weak_scene_coverage_pan_split/protocol.json)、[录音表](DataSet/paired_weak_scene_coverage_pan_split/recordings.csv)、[独立核验](DataSet/paired_weak_scene_coverage_pan_split/independent-verification.json)、[完整manifest压缩副本](DataSet/paired_weak_scene_coverage_pan_split/manifest.json.gz)。

## 已完成结果：旧4081对数据版本

两模型均seed0、200epoch、固定epoch200 actual raw，train2472 / val894。指标为pooled COCOeval百分数，各模态使用各自图像和GT。

| 模型 | val mAP@[.5:.95] | val AP50 | val AP75 | val AR@1 |
|---|---:|---:|---:|---:|
| camera-only YOLOX-M | 89.37 | 97.35 | 95.68 | 91.17 |
| sonar-only YOLOX-S | 51.38 | 84.30 | 48.27 | 58.30 |

上述分数不属于最新5229对划分，两个模态的分数差也不代表蒸馏收益。train自评mAP均100%，但flyby和部分录音存在明显val落差。未验证唯一原因。[逐类/逐录音/场景结果](复现/camera-baseline/scene-expanded-baselines-final-results.md)、[原始汇总JSON](runs/scene_baselines_after_pilot_review/results.json)。

旧715对test已按事前方案评价，此后属于已使用测试集：[历史test报告](复现/camera-baseline/scene-baselines-test715-results.md)。新旧test与原研究保留test必须分开，不将其表述为未触碰最终盲测。

## 最新教师训练：尚无本次确认的最终指标

最新camera-only YOLOX-M采用train4138 / val573，COCO-M fresh backbone/neck、随机三类head、seed0、batch8、200epoch/103600次更新、无增广。固定epoch200 actual raw为主结果，每10epoch仅监测val，EMA单列。

最新已保存的远端启动记录来自2026-11-14 18:09，位置为epoch2的200/518；本地尝试已停止，远端从COCO重新开始，两次日志不拼接。本次发布只整理既有材料，没有实时查询远端，也不据启动记录推断当前仍在训练或已经完成。

证据：[预登记](experiment/archive/weak-coverage-camera-m-training-plan.md)、[数据冻结](runs/weak_coverage_camera_m_teacher/dataset-freeze.json)、[部署报告](复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)、[独立启动核验](DataSet/weak_coverage_camera_m_5090_deployment/startup-verification.json)。

后续先确认最新run实际完成、epoch200权重身份与val结果，再评估教师可用性与后续蒸馏方案。本次发布没有启动实验、改变划分或新增模型评价。

## 更多记录

- [实验结果登记](experiment/results.md) / [测评协议](experiment/evaluation.md)
- [数据演进与标注来源](dataset.md) / [历史计划](experiment/archive/)
- [论文草稿版本说明](paper/README.md) / [完整交接记录](handoff.md)
- [复现输入与运行边界](REPRODUCIBILITY.md) / [本地产物说明](ARTIFACTS.md)

`publication-manifest.json`记录每个导入文件的源hash与发布hash；`publication-link-rewrites.json`记录本地链接在发布时的改写。历史报告正文保留，发布横幅和链接调整可追踪。正文中的绝对路径是历史运行位置，不能据此认为其他电脑可以直接运行。
"""

REPRODUCIBILITY = """# 复现输入与运行边界

本次发布是研究记录与脚本快照，不是已经验证的一键训练发行版。模型代码来自原工作区commit `4fadd06829c6c738977639a55b6e44ad0e35ac44`；原目录保持原位。

## 已提供

- `../aodet/`、`../configs/`与原训练/评测代码及其Git历史。
- `tools/`中的workflow处理、训练、评价、核验脚本与相关runtime；脚本原文保留，不在发布过程中执行。
- 当前5229对划分的train/val/test身份列表、录音/保守来源组表、协议、核验与完整manifest压缩副本。
- 当前相机train/val的COCO、dataset与成员/文件hash记录；这些JSON不包含图像文件。
- 已完成开发baseline的结果JSON、逐类/逐录音表、权重身份记录；最新run的冻结、配置与启动证据。

## 仍需准备

原始UXO图像/视频可从[官方来源](https://zenodo.org/records/13778485)取得。我方筛选后的配对图像、助手补标及图像恢复结果仍在本地workflow；仓库没有提供其独立下载地址。仅下载原始UXO不能自动得到我方完整训练输入。

完整manifest位于`DataSet/paired_weak_scene_coverage_pan_split/manifest.json.gz`，解压后SHA256应为`744aff50c0a6d69b4e79003c78262df9c2f1100ee438380cc71f44cc22ba26a5`。相机train/val图像需与`DataSet/camera_weak_coverage_trainval/files-sha256.json`核对。COCO-M初始化权重不随Git发布，身份见冻结与部署记录。

最新部署记录的环境为Python对应远端环境、Torch2.7.1+cu128、torchvision0.22.1+cu128、MMCV2.1.0、MMEngine0.10.7、MMDetection3.3.0、NumPy1.26.4、pycocotools2.0.11、Pillow12.3.0。以[启动核验](DataSet/weak_coverage_camera_m_5090_deployment/startup-verification.json)和[部署报告](复现/camera-baseline/weak-coverage-camera-m-5090-deployment.md)为证据；旧`../env/`属于原代码环境，不能把两者混为同一环境。

## 路径与执行

导入脚本通常以`research/`为ROOT，部分历史脚本含Windows、WSL或远端绝对路径。运行前必须逐项准备数据、核对输入hash并调整部署路径；发布时没有验证跨机器可移植性。部分脚本使用`--repo`、`--checkpoint`等参数，需显式指向对应代码与初始化权重。

有数据导出或服务启动作用的脚本不得仅为阅读仓库而执行；部分产物有防覆盖约束。最新教师任务已有启动记录，发布操作不应重复注册、重启或生成新run。本仓库没有新增训练授权。

actual raw与EMA按实际checkpoint结构区分，不能按目录名推定。旧val/test开发使用史、模态GT区别、数据版本和单seed边界见[测评协议](experiment/evaluation.md)。
"""

PAPER_README = """# 论文草稿

当前保留[数据集双语草稿](dataset.md)与[基线草稿](baseline.md)，均来自较早阶段，尚未同步当前5229对数据版本及最新实验进展。它们是写作材料，不是当前数据规模或结果的权威入口。

当前数据与实验事实见[研究进展](../README.md)、[数据报告](../复现/camera-baseline/weak-scene-coverage-resplit-5229.md)和[结果登记](../experiment/results.md)。本次发布标明草稿版本，没有代写未经验证的最终论文结果。
"""


if __name__ == "__main__":
    main()
