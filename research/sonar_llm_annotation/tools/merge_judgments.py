"""Merge two independent blind judging runs and report their agreement.

Why a merge step at all
-----------------------
A judgement is only evidence if it was given *independently*.  Two judges writing into the
same directory (which happened once) leave one file, and the surviving file looks just as
confident as an agreed one -- the agreement was destroyed by the storage layout, not by the
judges.  So each judge writes its own directory (`judge_a/`, `judge_b/`), and this script is
the only thing that produces `judgments/`, which is what the plugin validates and lives with.

What it refuses to do
---------------------
It never averages verdicts, and never turns a disagreement into `unsure` on its own: that
would invent a third opinion nobody gave.  On disagreement it keeps judge A's verdict, flags
`disagreement: true`, and records both verdicts verbatim so a human can see the split.

Cohen's kappa is computed over the four-way verdict label pairs actually observed.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin"))

from sonarllm import judge as J  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def _load_dir(d: Path) -> Dict[str, dict]:
    rows: Dict[str, dict] = {}
    if not d.is_dir():
        return rows
    for p in sorted(d.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get("sample"):
            rows[obj["sample"]] = obj
    return rows


def kappa(pairs: Sequence[Tuple[str, str]]) -> dict:
    """Cohen's kappa for two raters over categorical labels."""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "po": None, "pe": None, "kappa": None}
    po = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    labels = set(ca) | set(cb)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    k = None if pe >= 1.0 else (po - pe) / (1.0 - pe)
    return {"n": n, "po": round(po, 4), "pe": round(pe, 4),
            "kappa": None if k is None else round(k, 4),
            "labels_a": dict(sorted(ca.items())), "labels_b": dict(sorted(cb.items()))}


def merge(recording: str, a_dir: Optional[str] = None, b_dir: Optional[str] = None) -> dict:
    rec_out = OUT / recording
    A = _load_dir(rec_out / (a_dir or "judge_a"))
    B = _load_dir(rec_out / (b_dir or "judge_b"))
    samples = sorted(set(A) | set(B))
    merged_dir = rec_out / "judgments"
    merged_dir.mkdir(parents=True, exist_ok=True)

    both, only_a, only_b, invalid = [], [], [], []
    written = 0
    for s in samples:
        a, b = A.get(s), B.get(s)
        if a and b:
            va, ea = J.normalize(a, recording=recording)
            vb, eb = J.normalize(b, recording=recording)
            if va is None or vb is None:
                invalid.append({"sample": s, "errors_a": ea, "errors_b": eb})
                continue
            both.append((va["verdict"], vb["verdict"]))
            out = dict(va)
            out["judge_model"] = f"merge({va.get('judge_model','A')},{vb.get('judge_model','B')})"
            out["judges"] = {"a": {k: va.get(k) for k in ("verdict", "shape", "box", "confidence")},
                             "b": {k: vb.get(k) for k in ("verdict", "shape", "box", "confidence")}}
            out["disagreement"] = va["verdict"] != vb["verdict"]
            out["agreement"] = not out["disagreement"]
            if out["disagreement"]:
                out["alt_verdict"] = vb["verdict"]
                out["alt_reason"] = vb.get("reason", "")
        elif a:
            only_a.append(s)
            va, _ = J.normalize(a, recording=recording)
            if va is None:
                continue
            out = dict(va)
            out["judges"] = {"a": {k: va.get(k) for k in ("verdict", "shape", "box", "confidence")}}
            out["agreement"] = None
        else:
            only_b.append(s)
            vb, _ = J.normalize(b, recording=recording)
            if vb is None:
                continue
            out = dict(vb)
            out["judges"] = {"b": {k: vb.get(k) for k in ("verdict", "shape", "box", "confidence")}}
            out["agreement"] = None
        (merged_dir / f"{s}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
        written += 1

    k = kappa(both)
    report = {
        "recording": recording,
        "schema": "sonar_llm_annotation/judge_agreement/v0",
        "n_a": len(A), "n_b": len(B), "n_both": len(both),
        "n_only_a": only_a, "n_only_b": only_b, "n_invalid": invalid,
        "n_merged": written,
        "agreement": k,
        "disagreements": [{"sample": s, "a": A[s]["verdict"], "b": B[s]["verdict"]}
                          for s in sorted(A) if s in B and A[s].get("verdict") != B[s].get("verdict")],
        "rule": ("on disagreement the merged file keeps judge A's verdict and records "
                 "alt_verdict; no averaging, no silent conversion to unsure"),
    }
    (rec_out / "judge_agreement.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# 判读一致性（{}）".format(recording), "",
          f"- A {len(A)} 条 / B {len(B)} 条 / 两边都有 {len(both)} 条 / 合并写出 {written} 条",
          f"- 一致率 po = {k['po']}，机会一致率 pe = {k['pe']}，Cohen's κ = **{k['kappa']}**"]
    if report["disagreements"]:
        md.append("")
        md.append("| sample | A | B |")
        md.append("|---|---|---|")
        for d in report["disagreements"]:
            md.append(f"| `{d['sample']}` | {d['a']} | {d['b']} |")
    md += ["", "> 分歧不取平均、不自动改成 unsure；合并文件保留 A 的结论并记 `alt_verdict`。"]
    (merged_dir / "_AGREEMENT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="merge two blind judging runs, report kappa")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--a-dir", default=None)
    ap.add_argument("--b-dir", default=None)
    a = ap.parse_args(argv)
    r = merge(a.recording, a.a_dir, a.b_dir)
    k = r["agreement"]
    print(f"[merge] {a.recording}  A={r['n_a']} B={r['n_b']} both={r['n_both']} "
          f"merged={r['n_merged']}")
    if k["n"]:
        print(f"  po={k['po']} pe={k['pe']} kappa={k['kappa']}  disagreements={len(r['disagreements'])}")
    else:
        print("  no overlapping samples -- agreement not computable")
    for d in r["disagreements"]:
        print(f"  split: {d['sample']}  A={d['a']}  B={d['b']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
