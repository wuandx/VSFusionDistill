"""sonarllm 命令行。

    python -m sonarllm status
    python -m sonarllm manifest --recording 2023-09-20_171105
    python -m sonarllm check    --recording 2023-09-20_171105
    python -m sonarllm export   --dst out/dataset
    python -m sonarllm serve
"""

from __future__ import annotations

import argparse
import json
import sys
import re
import subprocess
import sys
from pathlib import Path

from . import OUT, ROOT, __version__
from . import dataset as ds
from . import judge

REC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")


def _recordings() -> list[str]:
    if not OUT.is_dir():
        return []
    return sorted(p.name for p in OUT.iterdir()
                  if p.is_dir() and REC_RE.match(p.name))


def _count_cards(rec: str) -> int:
    seen: set[str] = set()
    for root in judge.card_roots():
        seen.update(p.stem for p in root.glob(f"{rec}_*.png"))
    return len(seen)


def cmd_status(args: argparse.Namespace) -> int:
    print(f"sonarllm {__version__}  root={ROOT}")
    if not _recordings():
        print("out/ 下还没有按录音组织的产物")
        return 0
    print(f"{'recording':<22}{'proposals':>10}{'cards':>7}{'judged':>7}{'reviews':>8}  verdicts")
    for rec in _recordings():
        prop = OUT / rec / "proposals.jsonl"
        n_prop = sum(1 for _ in prop.open(encoding="utf-8")) if prop.is_file() else 0
        cards = _count_cards(rec)
        js = judge.load_judgments(rec)
        rev = ds.read_reviews(rec)
        s = judge.summarize(rec)
        print(f"{rec:<22}{n_prop:>10}{cards:>7}{len(js):>7}{len(rev):>8}  "
              f"{json.dumps(s['verdicts'], ensure_ascii=False)}")
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    m = judge.build_manifest(args.recording)
    print(json.dumps({k: m[k] for k in ("recording", "n_items", "missing_cards", "output_path")},
                     ensure_ascii=False, indent=2))
    if m["n_items"] == 0:
        print("没有找到卡片；先跑 engine/cards 生成 out/cards/<sample>.png", file=sys.stderr)
        return 1
    return 0


def cmd_resign(args: argparse.Namespace) -> int:
    """卡片重渲后，把已有判定的 card_sha256 重新签一次（留下可审计痕迹）。

    为什么需要：卡片是「声呐像素 + 图层」合成的。重渲通常只改图层（页脚、刻度尺、
    候选框来源），底层 PGM 像素一个都没动——判读员量出来的框仍然成立。
    但 `card_sha256` 守卫会把它判成"卡片已变，结论作废"。这个子命令不是放宽守卫，
    而是把"我知道它变了、变的是图层"这件事记进文件：旧的 sha 留在
    `card_sha256_previous`，并写 `resigned_at` / `resigned_by` / `resigned_note`。
    只有当人确认过底层像素没变时才该跑它。
    """
    import datetime as _dt

    rec = args.recording
    js = judge.load_judgments(rec)
    if not js:
        print(f"{rec}: 没有判定文件")
        return 1

    reused, missing = [], []
    for sample, obj in sorted(js.items()):
        card = judge.find_card(sample)
        if card is None:
            missing.append(sample)
            continue
        new = judge.sha256_file(card)
        old = obj.get("card_sha256")
        if old == new:
            continue
        reused.append((sample, old, new))
        obj["card_sha256_previous"] = old
        obj["card_sha256"] = new
        obj["resigned_at"] = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
        obj["resigned_by"] = args.by
        obj["resigned_note"] = ("card re-rendered; sonar pixels unchanged, "
                                "overlay/legend changed")
        path = OUT / rec / "judgments" / f"{sample}.json"
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for sample, old, new in reused:
        print(f"  resigned {sample}: {(old or '')[:12]}… -> {new[:12]}…")
    for sample in missing:
        print(f"  MISSING CARD {sample}: 找不到当前卡片，无法重签", file=sys.stderr)
    print(f"\n{rec}: 重签 {len(reused)} 条，未变 {len(js) - len(reused) - len(missing)} 条，"
          f"缺卡 {len(missing)} 条")
    return 0 if not missing else 2


def cmd_check(args: argparse.Namespace) -> int:
    rec = args.recording
    js = judge.load_judgments(rec)
    if not js:
        print(f"{rec}: 没有判定文件")
        return 1
    bad = 0
    for sample, obj in sorted(js.items()):
        norm, errs = judge.normalize(obj, recording=rec)
        if errs:
            bad += 1
            print(f"  FAIL {sample}: {'; '.join(errs)}")
    print(f"\n{rec}: {len(js)} 条判定，{bad} 条不合法")
    return 0 if bad == 0 else 2


def cmd_export(args: argparse.Namespace) -> int:
    dst = Path(args.dst)
    try:
        prov = ds.export(dst, recordings=args.recording or None,
                         allow_fixture=args.allow_fixture, force=args.force)
    except ds.ExportRefused as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps({k: prov[k] for k in ("n_exported", "per_recording",
                                           "recordings_per_split", "n_unassigned",
                                           "n_fixture_skipped",
                                           "candidate_only_not_training_ready")},
                     ensure_ascii=False, indent=2))
    if prov["n_exported"] == 0:
        print("  导出 0 条：没有 status=accept/revise 的**人类**复核记录。"
              "已故意不写 data.yaml（见 _EMPTY_DO_NOT_TRAIN.txt）。", file=sys.stderr)
    if prov["refusals"]:
        print(f"  {len(prov['refusals'])} 条拒绝/跳过，详见 provenance.json", file=sys.stderr)
    print(f"  -> {dst}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    server = ROOT / "review" / "server.py"
    if not server.is_file():
        print("review/server.py 不存在", file=sys.stderr)
        return 1
    cmd = [sys.executable, str(server),
           "--port", str(args.port),
           "--proposals", str(OUT),
           "--cards", str(OUT / "cards"),
           "--judgments", str(OUT)]
    print(" ".join(cmd))
    return subprocess.call(cmd)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(prog="sonarllm",
                                 description="LLM 辅助声呐图像标注（候选/伪标签，非 GT）")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="总览各录音的产出与判定统计")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("manifest", help="生成判读任务清单（给任何能看图的模型）")
    p.add_argument("--recording", required=True)
    p.set_defaults(fn=cmd_manifest)

    p = sub.add_parser("check", help="校验判定 JSON 的合法性与图-结论一致性")
    p.add_argument("--recording", required=True)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("resign", help="卡片重渲后重签已有判定的 card_sha256（可审计）")
    p.add_argument("--recording", required=True)
    p.add_argument("--by", default="lead")
    p.set_defaults(fn=cmd_resign)

    p = sub.add_parser("export", help="把人工复核结果导出为 YOLO 数据集目录")
    p.add_argument("--dst", default=str(OUT / "dataset"))
    p.add_argument("--recording", action="append", default=None)
    p.add_argument("--allow-fixture", action="store_true",
                   help="把 data_source=fixture 的自测记录也导出（只给自测用，别拿去训练）")
    p.add_argument("--force", action="store_true", help="目标目录非空时允许覆盖")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("serve", help="启动人工复核网页（默认 8771）")
    p.add_argument("--port", type=int, default=8771)
    p.set_defaults(fn=cmd_serve)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
