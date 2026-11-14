"""Agreement for the *supplementary* card batch (4 frames re-cropped on the candidate).

Why not `tools/merge_judgments.py`
----------------------------------
That tool publishes into `out/<rec>/judgments/`, which is the directory the plugin
validates and binds to the *canonical* frozen card set.  The supplementary batch was
rendered from a different crop window (`--crop-mode candidate`), so its cards have a
different `card_sha256`.  Publishing them into `judgments/` would either overwrite the
main batch's 12 verdicts or leave 4 entries whose hash does not match the card the
plugin looks up -- both are worse than keeping the batch separate and saying so.

So this writes `judge_agreement_supp.json` next to the main agreement file and leaves
`judgments/` alone.  The review log is keyed by sample id, so a human review of these
4 samples still lands in `reviews.jsonl` and still exports.

It also refuses to invent a third opinion: on a split it keeps A's verdict and records
both verbatim, exactly like the main merge.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = "2023-09-21_110229"
BASE = ROOT / "out" / REC


def load(d: Path) -> dict:
    out = {}
    for p in sorted(d.glob("*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        out[j["sample"]] = j
    return out


def kappa(pairs) -> tuple:
    """po/pe/kappa. kappa is None when pe == 1: both judges used one label only.

    That case is not kappa=0.  With no variation, chance agreement is 1.0 and the
    formula divides by zero; reporting 0 would read as "no better than chance" when
    the truth is "chance agreement is already perfect, so kappa carries no
    information".  4/4 `object` is exactly that case, so it must be reported as
    undefined rather than as a number.
    """
    n = len(pairs)
    if not n:
        return 0, 0.0, None
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    k = None if pe >= 1.0 else round((po - pe) / (1.0 - pe), 4)
    return n, round(po, 4), k


def main() -> int:
    a = load(BASE / "judge_a_supp")
    b = load(BASE / "judge_b_supp")
    samples = sorted(set(a) & set(b))
    pairs = [(a[s]["verdict"], b[s]["verdict"]) for s in samples]
    n, po, k = kappa(pairs)
    rec = {
        "schema": "sonar_llm_annotation/judge_agreement/v0",
        "recording": REC,
        "batch": "supp",
        "why_this_batch": (
            "the 12 canonical cards crop rows 317-441 (the 1.85 m band); 4 of the 12 "
            "candidates sit at rows 109-140, outside that crop, so both judges could only "
            "say 'candidate outside crop'. Re-rendered with --crop-mode candidate into "
            "cards_supp/ and judged blind again, each judge into its own directory."
        ),
        "card_dir": str((BASE / "cards_supp").relative_to(ROOT)).replace("\\", "/"),
        "n_a": len(a), "n_b": len(b), "n_both": n,
        "agreement": {
            "n": n, "po": po, "kappa": k,
            "kappa_note": (
                "undefined, not zero" if k is None else
                "computed over the four-way verdict labels observed"
            ),
        },
        "samples": {
            s: {
                "a": {kk: a[s].get(kk) for kk in ("verdict", "shape", "box", "confidence")},
                "b": {kk: b[s].get(kk) for kk in ("verdict", "shape", "box", "confidence")},
                "agree": a[s]["verdict"] == b[s]["verdict"],
            }
            for s in samples
        },
        "published_to_judgments": False,
        "note": (
            "kept out of out/<rec>/judgments/ on purpose: those 4 entries would carry "
            "cards_supp card_sha256 while the plugin's canonical card for the sample is the "
            "frozen main-batch card, so the hash guard would reject them. A human review of "
            "these samples still lands in reviews.jsonl and still exports."
        ),
    }
    dst = BASE / "judge_agreement_supp.json"
    dst.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[supp] n={n} po={po} kappa={k if k is not None else 'undefined (pe=1, both judges used one label)'}")
    for s in samples:
        print("  %-22s A=%-9s B=%-9s %s" % (s, a[s]["verdict"], b[s]["verdict"],
                                            "" if a[s]["verdict"] == b[s]["verdict"] else "SPLIT"))
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
