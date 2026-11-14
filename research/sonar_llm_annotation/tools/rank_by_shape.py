"""Re-order the census by *shape evidence* (base) instead of the composite score.

Why this exists
---------------
`tools/census.py` multiplies the shape score by three gates, so every recording
collapses into 0.004-0.058 and the order is decided by which gate fired, not by
what the return looks like.  For "which recording do I open first" that is the
wrong ranking: a recording with a strong compact return but a failed geometry fit
is *more* worth looking at than a weak one that happens to pass, because the fit
is the thing we already know we cannot trust (all three audited recordings came
back `unreliable_model`).

So this view sorts by `base` and prints the gates as warnings.  It does not
replace `CENSUS-V2.md`; the numbers are read from `census_v2.json`.

The gates still matter, but as disqualifiers for a *claim*, not for attention:
- `band_gate_frac` ~1 means the return spans the whole frame -> it is structure.
- `geo.reason` != ok means the single-point model does not hold; it says nothing
  about whether a compact return is present.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "out" / "census" / "census_v2.json"
OUT = ROOT / "out" / "census" / "RANK-BY-SHAPE.md"


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    rows = d["recordings"]
    rows = sorted(rows, key=lambda r: -float(r["base"]))
    lines = [
        "# 按形状证据（base）重排 —— 只回答\"先看哪条\"",
        "",
        "**权威表是 `out/census/CENSUS-V2.md`**（`tools/census.py` 已改成 `rank_key=base`，与本文件同序）。"
        "本文件不另立一套名次，只保留一段解释：为什么不看复合分数。",
        "",
        "理由：复合分数把三道闸乘在一起，40 条全落在 0.004–0.058，名次由\"哪道闸响了\"决定，"
        "而闸考察的几何可辨识性**我们已经知道不成立**（三条受审计录音全部 `unreliable_model`）。"
        "所以\"哪条最像目标\"要由形状证据回答，闸只当警告。",
        "",
        "> 分数高 ≠ 有目标。声呐侧没有 GT，`identity` 一律 `unresolved`。",
        "",
        "| # | recording | 类 | base | 覆盖闸 | geo | 轨迹 | 跳变 | 可导出 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        g = r.get("geo") or {}
        reason = g.get("reason", "?")
        if reason == "ok":
            reason = "ok"
        elif g.get("status") == "error":
            reason = "no_fit"
        lines.append(
            "| %d | `%s` | %s | %.3f | %.2f | %s | %d/%d | %d | %s |"
            % (i, r["recording"], r["category"], float(r["base"]),
               float(r.get("band_gate_frac") or 0.0), reason,
               int(r.get("track_len") or 0), int(r.get("n_frames_sampled") or 0),
               int(r.get("jumps") or 0),
               "是" if r.get("has_role") else "**否**")
        )
    clean = [r for r in rows if float(r.get("band_gate_frac") or 0.0) < 0.45]
    lines += [
        "",
        "## 两条硬提醒",
        "",
        "1. **覆盖闸是最硬的一条**：`band_gate_frac` 接近 1 的（`2023-09-20_175905` 1.00、"
        "`175506` 0.92、`171105` 0.90、`180722` 0.90、`174439` 0.89）在形状上就已经是贯穿亮带，"
        "不该占用人工时间；这正是当初选错录音的方式。",
        "2. **`geo` 全绿不代表对了**：`2023-09-20_182317` 的 base 0.128 与 `110229` 的 0.129 几乎相同，"
        "但它 54%% 的帧整幅覆盖（那就是结构）+ 轨迹 64 帧却只有 1 次跳变；它的几何闸\"通过\"恰好因为"
        "候选少而稳。**几何闸只能用来否决，不能用来认证。**",
        "",
        f"覆盖闸 <0.45 的录音数：{len(clean)} / {len(rows)}。",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} rows)")
    for r in rows[:8]:
        print("  %-22s base %.3f  cov %.2f  geo %-22s" % (r["recording"], float(r["base"]),
              float(r.get("band_gate_frac") or 0), (r.get("geo") or {}).get("reason", "?")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
