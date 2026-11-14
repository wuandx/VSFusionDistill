#!/usr/bin/env python3
"""Build the survey index for this literature round from the acquired meta.json files.

Source of truth for curation fields (tier / why / cmold_section) is
../selected.json; meta.json supplies verified metadata (title, authors, date,
arXiv version, hashes, whether a real LaTeX tree came down).

Writes:
  ../README.md        narrative survey + graded tables + acquisition status
  ../index.md        one flat table (machine-friendly)
  ../acquisition-status.json  machine-readable per-paper state
"""
import json
import os
import glob
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
LIT = os.path.dirname(HERE)
RW = os.path.dirname(LIT)

TIER_NOTE = {
    "A": "直接同题/同轴，必须精读并引用",
    "B": "方法或数据集可迁移，应引用",
    "C": "背景或对照，可择要引用",
}
SECTION_TITLE = {
    "II-A": "声呐图像的水下目标检测（CMOLD §II-A）",
    "II-B": "相机–声呐融合（CMOLD §II-B）",
    "II-C": "水下目标检测中的知识蒸馏（CMOLD §II-C）",
    "II-C→跨模态": "跨模态知识蒸馏用于目标检测（CMOLD §II-C 之外，属新增长轴）",
    "III/IV": "缺失模态、特权信息与无配对蒸馏（CMOLD §III/§IV 的方法学支撑）",
    "V": "讨论与未来工作（声呐图像合成/翻译）",
}


def load():
    sel = json.load(open(os.path.join(LIT, "selected.json"), encoding="utf-8"))
    by_id = {s["id"]: dict(s) for s in sel}
    # acquire.py derives its own slug; trust whatever dir actually holds the meta.json
    on_disk = {}
    for name in os.listdir(RW):
        mp = os.path.join(RW, name, "meta.json")
        if os.path.isfile(mp):
            try:
                aid = json.load(open(mp, encoding="utf-8")).get("arxiv_id", "")
            except Exception:
                continue
            if aid:
                on_disk[aid] = name
    for sid, ent in by_id.items():
        if sid in on_disk:
            ent["slug"] = on_disk[sid]
    rows = []
    for sid, ent in by_id.items():
        d = os.path.join(RW, ent["slug"])
        mp = os.path.join(d, "meta.json")
        rec = {"id": sid, **ent, "dir": ent["slug"], "have": os.path.exists(mp)}
        if rec["have"]:
            m = json.load(open(mp, encoding="utf-8"))
            rec.update({
                "title": m.get("title", ""),
                "authors": m.get("authors", []),
                "date": m.get("date", ""),
                "versions": m.get("versions", []),
                "pdf_bytes": (m.get("pdf") or {}).get("bytes", 0),
                "pdf_sha": (m.get("pdf") or {}).get("sha256", ""),
                "pdf_err": (m.get("pdf") or {}).get("error", ""),
                "eprint_kind": (m.get("eprint") or {}).get("kind", ""),
                "eprint_err": (m.get("eprint") or {}).get("error", ""),
                "tex": (m.get("eprint") or {}).get("tex_files", []) or [],
                "n_files": (m.get("eprint") or {}).get("n_files", 0),
            })
        rows.append(rec)
    return rows


def tex_state(r):
    if not r["have"]:
        return "未取得"
    if r.get("tex"):
        return f"有（{len(r['tex'])} 个 .tex）"
    if r.get("eprint_kind") == "pdf":
        return "无（作者只投 PDF）"
    return "无（源包无 .tex）"


def main():
    rows = load()
    order = {"A": 0, "B": 1, "C": 2}
    rows.sort(key=lambda r: (order.get(r.get("tier", "C"), 3), r.get("date", ""), r["id"]))

    got = [r for r in rows if r["have"]]
    with_tex = [r for r in got if r.get("tex")]
    status = {
        "generated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "selected": len(rows),
        "acquired": len(got),
        "with_latex": len(with_tex),
        "rows": [{k: r.get(k) for k in ("id", "dir", "tier", "title", "date", "cmold_section",
                                        "pdf_bytes", "pdf_sha", "tex", "eprint_kind")}
                 for r in rows],
    }
    json.dump(status, open(os.path.join(LIT, "acquisition-status.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- index.md ----
    lines = ["# 文献索引（lit-2026-11-12）", "",
             f"收录 {len(rows)} 篇；已下载 {len(got)} 篇，其中可获 LaTeX 源码 {len(with_tex)} 篇。", "",
             "| # | 等级 | 标题 | arXiv | 日期 | 对应 CMOLD 章节 | LaTeX | 目录 |",
             "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {r.get('tier','?')} | {r.get('title','(未取得)')} | "
                     f"[{r['id']}](https://arxiv.org/abs/{r['id']}) | {r.get('date','')} | "
                     f"{r.get('cmold_section','')} | {tex_state(r)} | `{r['dir']}/` |")
    open(os.path.join(LIT, "index.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # ---- README.md ----
    out = []
    out.append("# 相关论文检索：为 CMOLD 一系论文补文献面\n")
    out.append(f"生成时间：{status['generated']}　检索方式：arXiv HTML 搜索（18 组 abstract 字段查询，"
               "592 条候选，去重并排除既有 63 篇后按主题打分）＋ 逐条 abs 页核验。\n")
    out.append("本文件只登记**已核验元数据**的条目：标题、作者、日期、arXiv 编号均取自 "
               "`https://arxiv.org/abs/<id>` 的 citation meta 标签，随附 SHA-256。"
               "未取得正文的不写内容判断，只写检索所见。\n")
    out.append("综述与定位判断（哪些说法立得住、撞车排查、反证）见 [SURVEY.md](SURVEY.md)；"
               "本文件只做逐篇登记。\n"   "代码可得性（91 篇逐个查过仓库）见 [CODE.md](CODE.md)。")
    out.append("## 0. 本轮口径\n")
    out.append("- 「我论文」按 CMOLD 理解：Aydogmus & Erer, *Cross-Modality Object-Level Knowledge "
               "Distillation for Enhanced Underwater UXO Detection*, IEEE Access 14, 2026, "
               "DOI 10.1109/ACCESS.2026.3666096。camera(RGB) teacher → sonar student，共享 YOLOX，object-level KD。\n")
    out.append("- 收录分三档：**A** 直接同题/同轴；**B** 方法或数据可迁移；**C** 背景与对照。"
               "分档是我方判断，不是论文自述。\n")
    out.append("- LaTeX 列只写**实际拿到的作者源包**；`e-print` 返回 PDF 的记为「作者只投 PDF」，"
               "不冒充 LaTeX。\n")
    out.append(f"- 统计：选中 {len(rows)} 篇，成功下载 {len(got)} 篇，其中 {len(with_tex)} 篇带 .tex 源文件。\n")

    for tier in ("A", "B", "C"):
        sub = [r for r in rows if r.get("tier") == tier]
        if not sub:
            continue
        out.append(f"\n## 等级 {tier}：{TIER_NOTE[tier]}（{len(sub)} 篇）\n")
        out.append("| 标题 | arXiv | 日期 | 相关性（我方判断） | 对应章节 | LaTeX |")
        out.append("|---|---|---|---|---|---|")
        for r in sub:
            t = r.get("title", "(未取得)").replace("|", "\\|")
            out.append(f"| {t} | [{r['id']}](https://arxiv.org/abs/{r['id']}) | {r.get('date','')} | "
                       f"{r.get('why','')} | {r.get('cmold_section','')} | {tex_state(r)} |")

    out.append("\n## 按 CMOLD 章节归位\n")
    buckets = {}
    for r in rows:
        buckets.setdefault(r.get("cmold_section", ""), []).append(r)
    for sec in ("II-A", "II-B", "II-C", "II-C→跨模态", "III/IV", "V"):
        sub = buckets.get(sec, [])
        if not sub:
            continue
        out.append(f"### {SECTION_TITLE.get(sec, sec)}（{len(sub)} 篇）\n")
        for r in sub:
            out.append(f"- **{r.get('title','(未取得)')}**（arXiv:{r['id']}，{r.get('date','')}）"
                       f"——{r.get('why','')}")
        out.append("")

    out.append("\n## 获取记录\n")
    out.append("| arXiv | PDF | 源包 | 说明 |")
    out.append("|---|---|---|---|")
    for r in rows:
        pdf = f'{r.get("pdf_bytes",0)//1024} KB' if r.get("pdf_bytes") else (r.get("pdf_err") or "—")
        ep = r.get("eprint_kind") or (r.get("eprint_err") or "—")
        note = "" if r.get("tex") else ("作者只投 PDF，无 LaTeX" if ep == "pdf" else "源包内无 .tex")
        out.append(f"| {r['id']} | {pdf} | {ep} | {note} |")

    open(os.path.join(LIT, "README.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"selected={len(rows)} acquired={len(got)} latex={len(with_tex)}")


if __name__ == "__main__":
    main()
