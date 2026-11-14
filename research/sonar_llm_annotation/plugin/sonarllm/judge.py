"""VLM 判读环节：模型无关的判定协议。

与 BKRC_ChatLabel 那类工具的关键差别：它把大模型塞进网页里（网页 <-> 模型强耦合，
换模型就要改工具、要 API key）；这里反过来，判定被拆成**卡片 + 结构化 JSON**，
任何能看图的模型（DSH teammate / Claude / GPT / 本地 VLM / 人）都能当判读员：

  * 生产者（engine）只负责"把证据摆清楚"：一张卡三栏，全帧 / 高倍裁切 / 尺度参考。
  * 判读者只负责"看图说结论"：写一个 JSON。
  * 两者之间没有 API 依赖，判定可留痕、可复算、可换模型重跑。

判定口径（这是本线最重要的一条）：声呐扇面里那条贯穿左右、几乎每帧都在的大亮弧
经实测是**类无关结构**（三类目标标称尺寸差近 4 倍，该弧的角宽 104-125 beams、
径向厚度 0.32-0.33 m 几乎不变）。所以判读的关键分辨不是"亮不亮"，而是
**"离散可定位的物体" vs "贯穿扇面的结构"**。框住结构 = 错误标注。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import OUT, ROOT

VERDICTS = ("object", "structure", "unsure", "empty")
SHAPES = ("point", "short_arc", "streak", "blob", "none")

_VERDICT_HELP = {
    "object": "扇面内存在与背景结构可分离的、离散的、有边界的高亮回波",
    "structure": "只有贯穿扇面/延伸到边缘的大尺度结构，没有可定位的离散目标",
    "unsure": "有迹象但不足以判定（说出卡在哪一步）",
    "empty": "扇面内没有显著高亮回波",
}

JUDGE_SCHEMA = {
    "sample": "<str> 例如 2023-09-20_171105_0622",
    "verdict": "  |  ".join(VERDICTS),
    "shape": "  |  ".join(SHAPES),
    "box": "[x1,y1,x2,y2] 像素框，或 null（verdict!=object 时通常为 null）",
    "discrete_object_present": "<bool>",
    "structure_present": "<bool>",
    "structure_overlap": "<0..1 猜测框与贯穿结构重叠比例>",
    "reason": "<一句话，只能引用卡上看得见的形态>",
    "confidence": "<0..1>",
    "judge_model": "<模型或 agent 名>",
    "card_sha256": "<判读所依据卡片的 sha256，防止图和结论对不上>",
}


_H_CACHE: dict[str, int] = {}
def frame_h(recording: str) -> int:
    """该录音的真实网格高度（从不读缓存文件，直接读 PGM 头）。"""
    cached = _H_CACHE.get(recording)
    if cached:
        return cached
    from .dataset import REC_ROOT, pgm_size  # 延迟导入，避免循环

    h = 780
    try:
        for cls_dir in REC_ROOT.iterdir():
            raw = cls_dir / recording / "aris_raw"
            if not raw.is_dir():
                continue
            first = sorted(raw.glob("*.pgm"))
            if first:
                _w, hh = pgm_size(first[0])
                h = int(hh)
                break
    except Exception:  # noqa: BLE001 - 读不到就退回默认值，不阻断判读
        h = 780
    _H_CACHE[recording] = h
    return h


def card_roots(include_dev: bool = False) -> list[Path]:
    """卡片可能落的位置，按优先级。

    默认**只**认生产目录（`out/cards`、`out/<rec>/cards`）。`tmp/cards*` 是渲染期的
    草稿，同一 `sample` 名字下可能是一张用假检测画出来的旧卡——如果把它也当合法来源，
    判读员会对着过期卡片下判断，而 `card_sha256` 守卫只会说"和这张旧卡一致"，照样放行。
    要看草稿时显式传 `include_dev=True`。
    """
    roots = [OUT / "cards"] + sorted(OUT.glob("*/cards"))
    if include_dev:
        roots += [ROOT / "tmp" / "cards" / "dryrun", ROOT / "tmp" / "cards"]
    return [p for p in roots if p.is_dir()]


def find_card(sample: str) -> Path | None:
    for root in card_roots():
        p = root / f"{sample}.png"
        if p.is_file():
            return p
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(recording: str, samples: list[str] | None = None) -> dict:
    """产出「判读任务清单」：告诉判读员看哪些卡、按什么格式回。

    写 out/<recording>/judgments/_manifest.json
    """
    if samples is None:
        found: dict[str, Path] = {}
        for root in card_roots():
            for p in sorted(root.glob(f"{recording}_*.png")):
                found.setdefault(p.stem, p)
        samples = sorted(found)
    items = []
    missing = []
    for s in samples:
        card = find_card(s)
        if card is None:
            missing.append(s)
            continue
        items.append({"sample": s, "card": str(card), "card_sha256": sha256_file(card)})

    manifest = {
        "schema": "sonarllm/judge-manifest/v1",
        "recording": recording,
        "n_items": len(items),
        "missing_cards": missing,
        "instructions": [
            "逐张 read_image 看图，再下结论；不要凭元数据猜。",
            "卡上 C 栏若写 prior: unavailable，视为无信息，不得当证据。",
            "amber/虚线的 predicted 标记来源是已被证伪的 gantry 假设，不得当证据。",
            "判读要点：贯穿扇面、探到左右边缘、径向厚度均匀的大亮弧 = 结构；"
            "小而亮、边界清晰、局部成立的 = 可能是物体。",
            "verdict=object 时才给 box；框住结构视为错误标注。",
        ],
        "schema_fields": JUDGE_SCHEMA,
        "verdict_help": _VERDICT_HELP,
        "items": items,
        "output_path": str(OUT / recording / "judgments" / "<sample>.json"),
    }
    dst = OUT / recording / "judgments"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def normalize(obj: dict, recording: str | None = None) -> tuple[dict | None, list[str]]:
    """校验并规范化一条判定；返回 (规范结果, 错误列表)。"""
    errs: list[str] = []
    if not isinstance(obj, dict):
        return None, ["not an object"]
    out = dict(obj)
    sample = out.get("sample")
    if not isinstance(sample, str) or not sample:
        errs.append("sample missing")
    if recording and isinstance(sample, str) and not sample.startswith(recording):
        errs.append(f"sample {sample!r} 不属于录音 {recording!r}")

    verdict = out.get("verdict")
    if verdict not in VERDICTS:
        errs.append(f"verdict {verdict!r} 不在 {VERDICTS} 里")

    shape = out.get("shape", "none")
    if shape not in SHAPES:
        errs.append(f"shape {shape!r} 不在 {SHAPES} 里")

    box = out.get("box")
    if box is not None:
        if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)):
            errs.append("box 必须是 4 个数或 null")
        else:
            x1, y1, x2, y2 = [float(v) for v in box]
            if x2 <= x1 or y2 <= y1:
                errs.append("box 需满足 x2>x1 且 y2>y1")
            hh = frame_h(recording) if recording else 780
            if not (0 <= x1 and x2 <= 128 and 0 <= y1 and y2 <= hh):
                errs.append(f"box 越界（图像 128x{hh}）：{box}")
            out["box"] = [x1, y1, x2, y2]

    if verdict == "object" and out.get("box") is None:
        errs.append("verdict=object 但没有 box")

    conf = out.get("confidence")
    if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
        errs.append("confidence 需在 0..1")

    # 图和结论必须对得上：判读员声称的 card_sha256 要等于当前卡片
    if isinstance(sample, str):
        card = find_card(sample)
        claimed = out.get("card_sha256")
        if card is not None and claimed:
            real = sha256_file(card)
            if real != claimed:
                errs.append("card_sha256 与当前卡片不一致（卡片已重渲染，判定需重做）")
        out.setdefault("card_sha256", sha256_file(card) if card else None)

    out["_schema"] = "sonarllm/judgment/v1"
    return (None if errs else out), errs


def load_judgments(recording: str) -> dict[str, dict]:
    d = OUT / recording / "judgments"
    res: dict[str, dict] = {}
    if not d.is_dir():
        return res
    for p in sorted(d.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            res[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            res[p.stem] = {"_error": str(exc)}
    return res


def summarize(recording: str) -> dict:
    js = load_judgments(recording)
    tally: dict[str, int] = {}
    for j in js.values():
        v = j.get("verdict", "<invalid>")
        tally[v] = tally.get(v, 0) + 1
    with_box = sum(1 for j in js.values() if j.get("box"))
    return {"recording": recording, "n": len(js), "verdicts": tally, "with_box": with_box}
