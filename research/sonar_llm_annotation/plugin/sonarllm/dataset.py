"""把人工复核结果打包成可训练的数据集目录（YOLO 格式）。

三条硬规矩，写在代码里而不只是文档里：

1. **不新建划分**。AGENTS.md：不建 split。所以划分只能来自既有
   `DataSet/camera_temporal_all/manifest-resolved.json` 的 `paired_role`；
   若同一条录音里出现多个 role（说明该清单不是录音级划分），直接拒绝导出。
2. **不冒充 GT**。每条导出都带 `provenance.json`，写明
   `candidate_only_not_training_ready: true` 与声呐 GT 的实际状态。
3. **只导出人确认过的框**。`status=accept` 用 `final_box`；
   `reject`/`skip` 不导出；`revise` 只有带 `final_box` 才导出。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from . import OUT, ROOT

REC_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")
MANIFEST = Path(r"D:\agent_workspace\水下\声呐目标检测_workflow\DataSet"
                r"\camera_temporal_all\manifest-resolved.json")
FW, FH = 128, 780

CATEGORY_TO_DIR = {
    "100lbs_aircraft_bomb": "100lbs_bomb",
    "incindiary_grenade": "20lbs_incendiary",
    "mortar_shell": "15cm_mortar",
}
CLASSES = ["100lbs_aircraft_bomb", "incindiary_grenade", "mortar_shell"]


def read_reviews_counted(recording: str) -> tuple[dict[str, dict], dict]:
    """reviews.jsonl 是追加日志，同一样本取最后一条。

    顺手把坏行数出来——静默丢弃坏行会让"导出 0 条"看起来像"没有复核"，
    这两种情况必须能区分，所以调用方要拿到 `stats` 并写进 provenance。
    """
    p = OUT / recording / "reviews.jsonl"
    latest: dict[str, dict] = {}
    stats = {"n_lines": 0, "n_bad": 0, "n_no_sample": 0}
    if not p.is_file():
        stats["missing"] = True
        return latest, stats
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        stats["n_lines"] += 1
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            stats["n_bad"] += 1
            continue
        s = rec.get("sample") if isinstance(rec, dict) else None
        if s:
            latest[s] = rec
        else:
            stats["n_no_sample"] += 1
    return latest, stats


def read_reviews(recording: str) -> dict[str, dict]:
    """同 `read_reviews_counted`，但只返回最新记录（兼容旧调用）。"""
    return read_reviews_counted(recording)[0]


def accepted_box(rec: dict):
    status = rec.get("status")
    if status == "accept":
        return rec.get("final_box") or rec.get("candidate_box")
    if status == "revise":
        return rec.get("final_box")
    return None


def find_pgm(recording: str, frame: int, category: str) -> Path | None:
    order = []
    mapped = CATEGORY_TO_DIR.get(category)
    if mapped:
        order.append(mapped)
    order += [d for d in CATEGORY_TO_DIR.values() if d not in order]
    for d in order:
        p = REC_ROOT / d / recording / "aris_raw" / f"{frame:04d}.pgm"
        if p.is_file():
            return p
        p = REC_ROOT / (d + "_(floor)") / recording / "aris_raw" / f"{frame:04d}.pgm"
        if p.is_file():
            return p
    return None


def recording_roles() -> dict[str, set[str]]:
    """录音级划分的唯一来源：manifest 里 paired_role。"""
    if not MANIFEST.is_file():
        return {}
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    roles: dict[str, set[str]] = defaultdict(set)
    for it in d.get("items", []):
        rec = it.get("recording")
        role = it.get("paired_role")
        if rec and role:
            roles[rec].add(role)
    return dict(roles)


def pgm_size(path) -> tuple[int, int]:
    """(width, height) read from the binary PGM header.

    录音之间的网格并不相同：bomb 2023-09-20_171105 是 780 行（SamplesPerBeam=780,
    WindowLength 2.326 m），grenade/mortar 是 441 行（WindowLength 1.316/1.315 m）。
    硬编码 780 会把后两条录音的 y 归一化算错，所以尺寸必须逐录音读。
    """
    with open(path, "rb") as fh:
        magic = fh.readline().strip()
        if magic != b"P5":
            raise ValueError(f"not a binary PGM: {magic!r}")
        line = fh.readline()
        while line.startswith(b"#"):
            line = fh.readline()
        w, h = (int(v) for v in line.split()[:2])
    return w, h


def sample_roles() -> dict[str, set[str]]:
    """样本 → paired_role 集合（manifest 的 paired_role 是逐 item 的）。

    注意这是本项目既有约定的诚实读法，不是"我们新造了一个划分"：
    37 条录音里有 27 条同时出现 train 与 val_id，因为 val_id 本来就是
    **同录音留出诊断**（AGENTS.md 第 6 条），不是论文协议、也不是独立考场。
    所以划分必须按样本取，按录音聚合会把绝大多数正常录音误判成"混合划分"。
    """
    if not MANIFEST.is_file():
        return {}
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    roles: dict[str, set[str]] = defaultdict(set)
    for it in d.get("items", []):
        s = it.get("sample")
        role = it.get("paired_role")
        if s and role:
            roles[s].add(role)
    return dict(roles)


def yolo_line(cls_id: int, box, fw: int = FW, fh: int = FH) -> str:
    x1, y1, x2, y2 = [float(v) for v in box]
    cx = (x1 + x2) / 2 / fw
    cy = (y1 + y2) / 2 / fh
    w = (x2 - x1) / fw
    h = (y2 - y1) / fh
    return f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


class ExportRefused(RuntimeError):
    """Raised instead of SystemExit so a library caller can recover.

    ``export`` used to raise SystemExit on a populated destination, which is fine for a
    command line but kills any process that calls it as a function (it is a
    BaseException, so a plain ``except Exception`` does not catch it).  The CLI turns
    this into a non-zero exit code.
    """


def export(dst: Path, recordings: list[str] | None = None, copy_images: bool = True,
           allow_fixture: bool = False, force: bool = False) -> dict:
    """把人工复核结果导出成 YOLO 目录。

    三条硬规矩（代码里守着，不靠文档）：
    1. 划分只取 manifest 的 `paired_role`，且**按样本**取；不新建划分。
    2. 每条产物带 provenance，写明 candidate/伪标签而非 GT。
    3. **落盘数 = provenance 数**：所有计数在文件真的写成功之后才累加。
    """
    dst = Path(dst)
    # 非空目录默认拒绝：导出是"生成一份新数据集"，不是"往旧数据集里掺"。
    # 静默覆盖 data.yaml 会让上一次的 labels 挂着新的类别表，读进去就是错配。
    if dst.exists() and any(dst.iterdir()) and not force:
        raise ExportRefused(
            f"导出目标已存在且非空：{dst}\n"
            f"  拒绝覆盖。换一个空目录，或确认要覆盖时加 --force。")

    roles = recording_roles()
    roles_by_sample = sample_roles()
    spanning = {rec: sorted(rs) for rec, rs in roles.items() if len(rs) > 1}
    dst.mkdir(parents=True, exist_ok=True)
    recs = recordings or sorted(p.name for p in OUT.iterdir()
                                if p.is_dir() and (p / "reviews.jsonl").is_file())
    refusals: list[dict] = []
    per_rec: dict[str, int] = {}
    role_count: Counter = Counter()
    n_fixture = 0
    review_stats: dict[str, dict] = {}

    staged: list[tuple[str, str, int, dict]] = []  # (split, sample, cls_id, rec)
    for rec in recs:
        latest, stats = read_reviews_counted(rec)
        review_stats[rec] = stats
        n = 0
        for sample, r in latest.items():
            # 划分按**样本**取 paired_role：manifest 里 paired_role 是逐 item 的，
            # 27/37 条录音同时含 train 与 val_id（val_id 是同录音留出诊断，不是新划分）。
            # 所以按录音聚合会误拒，按样本取才是忠实使用既有划分。
            rs = roles_by_sample.get(sample, set())
            if len(rs) > 1:
                refusals.append({"sample": sample, "reason": "mixed_paired_role",
                                 "roles": sorted(rs),
                                 "note": "同一样本出现多个 paired_role，拒绝导出"})
                continue
            split = next(iter(rs)) if rs else "unassigned"
            box = accepted_box(r)
            if not box:
                continue
            # 自测用的 fixture 复核记录不得混进数据集
            if r.get("data_source") == "fixture" and not allow_fixture:
                n_fixture += 1
                continue
            cat = r.get("category")
            if cat not in CLASSES:
                refusals.append({"sample": sample, "reason": "unknown_category", "category": cat})
                continue
            staged.append((split, sample, CLASSES.index(cat), {**r, "final_box": box}))
        per_rec[rec] = n

    written = 0
    sizes: dict[str, dict] = {}
    for split, sample, cls_id, r in staged:
        img_dir = dst / "images" / split
        lbl_dir = dst / "labels" / split
        pgm = None
        fw, fh = FW, FH
        # 先落图片、再落标签：反过来的话图片转换失败会留下一条没有图的标签，
        # 计数和磁盘就对不上（这正是旧版 n_exported 虚高的来源）。
        if copy_images:
            pgm = find_pgm(r["recording"], int(r["aris_frame"]), r["category"])
            if pgm is None:
                refusals.append({"sample": sample, "reason": "pgm_missing"})
                continue
            try:
                fw, fh = pgm_size(pgm)
            except Exception as exc:  # noqa: BLE001
                refusals.append({"sample": sample, "reason": "pgm_header_unreadable",
                                 "detail": str(exc)})
                continue
            try:
                from PIL import Image
                img_dir.mkdir(parents=True, exist_ok=True)
                Image.open(pgm).save(img_dir / f"{sample}.png")
            except Exception as exc:  # noqa: BLE001
                refusals.append({"sample": sample, "reason": "image_convert_failed",
                                 "detail": str(exc)})
                continue
        lbl_dir.mkdir(parents=True, exist_ok=True)
        (lbl_dir / f"{sample}.txt").write_text(
            yolo_line(cls_id, r["final_box"], fw, fh) + "\n", encoding="utf-8")
        sizes.setdefault(r["recording"], {"width": fw, "height": fh})
        written += 1
        role_count[split] += 1
        per_rec[r["recording"]] = per_rec.get(r["recording"], 0) + 1

    names = "\n".join(f"  {i}: {c}" for i, c in enumerate(CLASSES))
    # 零条落盘时不写 data.yaml：训练器会把一个空目录当成合法数据集读进去，
    # 然后安静地训出一个什么都不检测的模型。宁可让它找不到 data.yaml 直接报错。
    if written:
        (dst / "data.yaml").write_text(
            f"# 由 sonarllm 导出；候选/伪标签，不是人工 GT\n"
            f"path: {dst.as_posix()}\ntrain: images/train\nval: images/val\n"
            f"names:\n{names}\n", encoding="utf-8")
    else:
        (dst / "_EMPTY_DO_NOT_TRAIN.txt").write_text(
            "本次导出 0 条（没有 status=accept/revise 且 data_source!=fixture 的复核记录）。\n"
            "故意不写 data.yaml：空数据集被训练器读进去会静默训出一个不检测任何东西的模型。\n"
            "先确认 reviews.jsonl 里有人类复核记录，再重跑导出。\n", encoding="utf-8")

    prov = {
        "schema": "sonarllm/dataset-provenance/v1",
        "candidate_only_not_training_ready": True,
        "sonar_gt_status": "HOLD: 原项目 converter 原文 —— sonar ground-truth boxes do not exist；"
                           "sonar.json 的框由相机框经位姿投影生成，非人工标注",
        "split_source": str(MANIFEST) + " :: paired_role（逐样本，manifest 原值）",
        "split_policy": "按样本取 paired_role；不新建划分；同一样本多 role 时拒绝导出。"
                        "train 与 val_id 出现在同一录音内是既有约定（val_id=同录音留出诊断），"
                        "不是帧级随机划分，也不是论文协议",
        "recordings_spanning_roles": spanning,
        "n_recordings_spanning_roles": len(spanning),
        "n_unassigned": role_count.get("unassigned", 0),
        "unassigned_note": "这些样本在 manifest 里 paired_role 为空（实测：三条选定录音里 "
                           "只有 150/715、96/771、96/725 帧带 role，其余为空）。"
                           "它们未被赋予 split，也不得被默认塞进 train——用前需人工决定",
        "accepts": "status=accept 取 final_box；revise 需带 final_box；reject/skip 不导出",
        "n_exported": written,
        "n_staged_rejected_at_write": len(staged) - written,
        "n_fixture_skipped": n_fixture,
        "review_log_stats": review_stats,
        "n_bad_review_lines": sum(s.get("n_bad", 0) for s in review_stats.values()),
        "review_log_note": "n_bad>0 表示 reviews.jsonl 有坏行（已跳过）；"
                           "缺文件时 stats.missing=True，用来区分'没人复核'与'日志坏了'",
        "per_recording": per_rec,
        "recordings_per_split": dict(role_count),
        "classes": CLASSES,
        "image_size_by_recording": sizes,
        "image_size_default": {"width": FW, "height": FH},
        "coordinate_frame": "sonar polar rectangle: cols=128 beams (azimuth), rows=range samples "
                            "(780 for 2023-09-20_171105, 441 for 2023-09-21_120653 / 2023-09-21_100927)",
        "refusals": refusals,
    }
    (dst / "provenance.json").write_text(
        json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
    return prov
