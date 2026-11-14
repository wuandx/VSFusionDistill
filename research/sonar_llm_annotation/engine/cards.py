#!/usr/bin/env python
"""T-CARDS: judgment-card renderer for the sonar LLM annotation line.

One call renders one 3-panel PNG -- the only thing a vision-language model gets
to see about a frame:

    A  FULL FRAME   whole raw frame (128 x 780 or 128 x 441), height-filled,
                    candidate box + crop window; optional grey-out of the
                    class-agnostic structure domain, optional bg-band bracket
    B  CROP         candidate box grown by >= 40 px of echo context, magnified
                    by an integer factor (>= 2, target height ~900 px), box drawn
    C  PRIOR+SCALE  metric row->metre ruler, the candidate's radial thickness in
                    metres, nominal-length reference bars, and 2-3 mesh_prior
                    silhouettes over the *same* crop (placeholder when absent)
    footer          sample | category | range_m | candidate.source | engine_version
                    plus provenance lines (pred, box, blobs, crop, stretch, sha)

What is deliberately NOT drawn
------------------------------
* The gantry-derived ``predicted (beam,row)`` cross.  That mapping was refuted on
  this data (circular rail, 0.32 turn per recording; at |p| >= 1.52 m the mapped
  row lands on speckle, not on the echo).  A cross is drawn only when the record
  says ``predicted.available is True`` -- i.e. when a *sonar-frame* estimate
  produced it.  Otherwise the footer states the hypothesis and its rejection.
* Any badge that would make the refuted prediction look as trustworthy as the
  candidate box: the cross is neutral grey, never the amber "valid" colour.

Design rules, and why the code looks the way it does
----------------------------------------------------
* Display only.  The frame reaches a panel as a nearest-neighbour integer zoom
  of the raw uint8 samples: no interpolation, no sharpening, no edge highlight,
  so the model never sees a boundary the sonar did not produce.
* One stretch per card.  lo/hi are measured on the whole frame and applied to
  every panel, so B and C are photometrically comparable and a bright echo in B
  cannot be an artefact of per-crop auto-levelling.
* Deterministic.  Same record -> same bytes: no clock, no dict iteration order,
  no hash(), no font autodiscovery beyond a fixed bundled font.
* numpy + PIL only.  cv2 / scipy / skimage are not installed on the Windows
  python this line runs on.

Contract (BRIEF "unified record format"): ``frame_data`` is one record, optionally
carrying ``img`` (decoded uint8 array) and ``prior_masks`` (list of bool arrays,
one per ``prior.sweep`` entry).

CLI
---
    python engine/cards.py --proposals out/<rec>/proposals.jsonl --out out/cards
    python engine/cards.py --record-json tmp/cards/record.json --out out/cards
    python engine/cards.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
ENGINE_VERSION = "v1"
CARD_VERSION = "cards/v1"

# Verdict vocabulary is owned by the judge plugin; keep these in sync with
# plugin/sonarllm/judge.py VERDICTS (docs/judgment-protocol.md, "词表 v1.1").
VERDICTS = ("object", "structure", "unsure", "empty")

# ---------------------------------------------------------------- palette ---
# Chosen to stay readable on a near-black sonar background and to avoid the
# red/green pairing that disappears for colour-blind reviewers.
C_BG = (14, 14, 18)
C_PANEL = (22, 22, 28)
C_PANEL_EDGE = (46, 46, 58)
C_TEXT = (234, 234, 240)
C_DIM = (146, 146, 158)
C_FAINT = (86, 86, 98)
C_WARN = (255, 138, 0)
C_CAND = (0, 229, 255)      # candidate box
C_PRED = (206, 206, 214)    # predicted cross -- NEUTRAL: it is a weak claim
C_ECHO = (179, 136, 255)    # echo blob boxes
C_WIN = (150, 156, 170)     # crop window shown in B (neutral: never read as echo)
C_STRUCT = (126, 126, 136)  # grey-out target of the structure-domain mask
C_SCALE = (222, 226, 234)   # metric ruler / nominal-length bars in panel C

# Nominal target sizes, read from the model-registration table (a real, cited
# source: DataSet/sonar_model_registration_consistency/mesh-registration.json,
# nominal_length_m, itself derived from the historical README).  This is a
# *nominal* size of an intact round, not the size of the observed fragment, and
# it is only a size reference -- never a classifier.
NOMINAL_LENGTH_M: dict[str, float] = {
    "100lbs_aircraft_bomb": 0.737,
    "mortar_shell": 0.580,
    "incindiary_grenade": 0.442,
}
NOMINAL_SOURCE = "mesh-registration.json nominal_length_m"
C_PRIOR = ((255, 109, 0), (245, 0, 87), (170, 0, 255))


# --------------------------------------------------------------- geometry ---
@dataclass(frozen=True)
class Style:
    """Fixed card metrics.  Dumped into the render report for reproducibility."""

    pad: int = 14               # outer margin
    gap: int = 14               # gap between panels
    header_h: int = 42          # title strip
    legend_h: int = 24          # colour legend strip
    cap_h: int = 27             # per-panel caption strip
    band_h: int = 900           # target height of the image band
    foot_pad: int = 12
    foot_line_gap: int = 6
    fs_header: int = 27
    fs_cap: int = 17
    fs_foot: int = 17
    fs_legend: int = 16
    margin: int = 40            # echo context around the candidate box, px
    min_crop_w: int = 96
    min_crop_h: int = 140
    max_zoom: int = 6
    max_panel_w: int = 660      # a panel may not get wider than this (keeps the
                                # card <= ~1520 px so a vision encoder still
                                # resolves the footer text)
    left_pad: int = 18          # horizontal breathing space beside the thin frame
    box_w: int = 2
    cross_arm: int = 11
    lo_pct: float = 0.5         # robust stretch, low quantile
    hi_pct: float = 99.5        # robust stretch, high quantile

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


DEFAULT_STYLE = Style()


# ------------------------------------------------------------- primitives ---
def _font(px: int) -> ImageFont.FreeTypeFont:
    """Bundled scalable font (Pillow >= 10.1).  Bundled => deterministic."""
    try:
        return ImageFont.load_default(size=px)
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _fmt(v: Any, nd: int = 2) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if isinstance(v, float) and not np.isfinite(v):
            return "nan"
        return f"{v:.{nd}f}"
    if v is None:
        return "unknown"
    return str(v)


def _box_or_none(box: Any) -> tuple[float, float, float, float] | None:
    if box is None:
        return None
    try:
        x0, y0, x1, y1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    if not all(np.isfinite([x0, y0, x1, y1])):
        return None
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)


# ------------------------------------------------------------------ input ---
def decode_frame(frame_data: dict) -> tuple[np.ndarray, dict]:
    """Return (uint8 HxW array, meta).  Uses ``img`` when present, else image.path."""
    src = frame_data.get("img")
    meta: dict[str, Any] = {"source": "record"}
    if src is None:
        info = frame_data.get("image") or {}
        path = info.get("path") or frame_data.get("image_path")
        if not path:
            raise ValueError(
                "frame_data has neither 'img' nor image.path; cannot render a card"
            )
        with Image.open(path) as im:
            a = np.asarray(im.convert("L"))
        meta["source"] = "file"
        meta["path"] = str(path)
    else:
        a = np.asarray(src)
        if a.ndim == 3:
            if a.shape[2] == 1:
                a = a[:, :, 0]
            else:
                a = np.asarray(Image.fromarray(a.astype(np.uint8)).convert("L"))

    if a.ndim != 2:
        raise ValueError(f"expected a 2-D frame, got shape {a.shape}")
    if a.dtype != np.uint8:
        hi = float(np.nanmax(a)) if a.size else 0.0
        if hi <= 255.0 and np.nanmin(a) >= 0.0:
            a = np.clip(np.rint(a), 0, 255).astype(np.uint8)
            meta["input_cast"] = "rounded to uint8"
        else:
            a = np.clip(a.astype(np.float32) * (255.0 / max(hi, 1e-6)), 0, 255)
            a = np.rint(a).astype(np.uint8)
            meta["input_cast"] = f"rescaled from max {hi:g}"
    return a, meta


# ------------------------------------------------------------ row -> metre ---
_META_CACHE: dict[str, dict[int, dict[str, str]]] = {}


def _recording_dir_from_image_path(path: str) -> Path | None:
    pp = Path(path)
    if pp.parent.name == "aris_raw":
        return pp.parent.parent
    return None


def read_frame_meta(image_path: str | None, aris_frame: Any) -> dict[str, str] | None:
    """One row of ``aris_frame_meta.csv`` (keyed by FrameIndex), or None."""
    if not image_path or aris_frame is None:
        return None
    rec = _recording_dir_from_image_path(str(image_path))
    if rec is None:
        return None
    csv_path = rec / "aris_frame_meta.csv"
    key = str(csv_path)
    if key not in _META_CACHE:
        table: dict[int, dict[str, str]] = {}
        if csv_path.exists():
            import csv

            with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
                for row in csv.DictReader(fh):
                    try:
                        table[int(row["FrameIndex"])] = row
                    except (KeyError, TypeError, ValueError):
                        continue
        _META_CACHE[key] = table
    try:
        return _META_CACHE[key].get(int(aris_frame))
    except (TypeError, ValueError):
        return None


def row_scale(frame_data: dict) -> dict | None:
    """Metres per row and the window's near edge, for the panel-C ruler.

    Preference order: an explicit ``row_scale`` on the record, then the
    recording's ``aris_frame_meta.csv``.  Returns None when neither is available
    (the card then says so instead of inventing a scale).
    """
    prov = frame_data.get("provenance") or {}
    declared = (prov.get("params") or {}).get("row_scale")
    if not isinstance(declared, dict):
        declared = (frame_data.get("image") or {}).get("row_scale")
    if isinstance(declared, dict):
        try:
            ws = float(declared["window_start_m"])
            res = float(declared["res_m_per_row"])
        except (KeyError, TypeError, ValueError):
            ws = res = None  # type: ignore[assignment]
        if ws is not None and res is not None and res > 0:
            return {
                "window_start_m": ws,
                "res_m_per_row": res,
                "source": "record",
                "file_meta": None,
            }

    info = frame_data.get("image") or {}
    row = read_frame_meta(info.get("path"), frame_data.get("aris_frame"))
    if not row:
        return None
    try:
        ws = float(row["WindowStart"])
        wl = float(row["WindowLength"])
        n = float(row["SamplesPerBeam"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (n > 0 and wl > 0):
        return None
    res = wl / n
    out = {
        "window_start_m": ws,
        "window_end_m": ws + wl,
        "res_m_per_row": res,
        "n_rows": int(round(n)),
        "source": "aris_frame_meta.csv",
        "file_meta": {
            "FrameIndex": row.get("FrameIndex"),
            "WindowStart": row.get("WindowStart"),
            "WindowLength": row.get("WindowLength"),
            "SamplesPerBeam": row.get("SamplesPerBeam"),
            "SoundSpeed": row.get("SoundSpeed"),
            "SamplePeriod": row.get("SamplePeriod"),
        },
    }
    try:  # independent check: res = c * (sample period) / 2
        c = float(row["SoundSpeed"])
        sp = float(row["SamplePeriod"]) * 1e-6
        if c > 0 and sp > 0:
            out["res_check_m"] = round(c * sp / 2.0, 9)
    except (KeyError, TypeError, ValueError):
        pass
    return out


def nominal_length_m(frame_data: dict) -> tuple[float | None, str]:
    """(nominal target length in metres, provenance of that number)."""
    prior = frame_data.get("prior") or {}
    try:
        v = float(prior.get("length_m"))
        if v > 0:
            return v, "prior.length_m"
    except (TypeError, ValueError):
        pass
    cat = str(frame_data.get("category") or "")
    if cat in NOMINAL_LENGTH_M:
        return NOMINAL_LENGTH_M[cat], "nominal"
    return None, "none"


def _neighbor_frame(frame_data: dict, frame: int) -> np.ndarray | None:
    """Read a sibling frame of the same recording, or None when it is absent.

    The temporal strip must be able to show "no frame" honestly: a missing
    neighbour is a gap in the evidence, not a reason to reuse the current frame.
    """
    img = frame_data.get("image") or {}
    path = img.get("path")
    if not path:
        return None
    p = Path(str(path))
    suffix = p.suffix or ".pgm"
    cand = p.with_name(f"{int(frame):04d}{suffix}")
    if not cand.is_file():
        return None
    try:
        with Image.open(cand) as im:
            return np.asarray(im.convert("L"), dtype=np.uint8)
    except (OSError, ValueError):
        return None


def robust_stretch(
    arr: np.ndarray,
    lo_pct: float = 0.5,
    hi_pct: float = 99.5,
    gain: float = 1.0,
    shoulder: bool = True,
    shoulder_out: int = 200,
    shoulder_k: float = 3.0,
    lo: float | None = None,
    hi: float | None = None,
) -> tuple[np.ndarray, dict]:
    """Perceptual stretch: map [p_lo, p_hi] -> [0, shoulder_out], then a soft
    shoulder for everything above p_hi, then multiply by gain.

    Quantiles are measured on the whole frame once, so every panel of a card
    shares the same mapping.  gain > 1 lifts weak echoes out of the speckle
    floor; it is a linear scale, not a tone curve, and it clips at 255.

    The shoulder matters on this data: p99.5 lands at 54 while the echo core
    runs to 86, so a hard clip turns the target's bright head into a flat white
    patch with no internal structure -- exactly the part the annotator has to
    judge ("box the end cap").  Values above p_hi are therefore compressed into
    [shoulder_out, 255] with a fixed monotone exponential instead of being
    clipped.  It is still one global mapping per frame; ``shoulder=False`` gives
    the strict hard-clipped p0.5-p99.5 stretch.
    """
    a = arr.astype(np.float32)
    lo_auto = float(np.percentile(a, lo_pct)) if a.size else 0.0
    hi_auto = float(np.percentile(a, hi_pct)) if a.size else 255.0
    # explicit anchors let the temporal strip share one mapping with the card
    lo = float(lo) if lo is not None else lo_auto
    hi = float(hi) if hi is not None else hi_auto
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(a.min()) if a.size else 0.0, float(a.max()) if a.size else 255.0
    if hi <= lo:
        hi = lo + 1.0
    b = (a - lo) / (hi - lo)
    if gain != 1.0:
        b = b * float(gain)
    use_shoulder = bool(shoulder) and float(a.max()) > hi
    if use_shoulder:
        s = float(shoulder_out) / 255.0
        over = np.maximum(b - 1.0, 0.0)
        y = np.where(b <= 1.0, b * s, s + (1.0 - s) * (1.0 - np.exp(-shoulder_k * over)))
        b = y
    b = np.clip(b, 0.0, 1.0)
    out = np.rint(b * 255.0).astype(np.uint8)
    return out, {
        "lo": round(lo, 3),
        "hi": round(hi, 3),
        "lo_pct": lo_pct,
        "hi_pct": hi_pct,
        "gain": gain,
        "shoulder": use_shoulder,
        "shoulder_out": int(shoulder_out) if use_shoulder else 255,
        "p_lo": float(np.percentile(a, lo_pct)) if a.size else 0.0,
        "p_hi": float(np.percentile(a, hi_pct)) if a.size else 255.0,
        "clipped_px": int((a >= hi).sum()),
        "clipped_frac": round(float((a >= hi).mean()) if a.size else 0.0, 6),
        "sat_frac": round(float((out >= 255).mean()) if a.size else 0.0, 6),
    }


def plan_crop(
    box: tuple[float, float, float, float],
    width: int,
    height: int,
    margin: int = 40,
    min_w: int = 96,
    min_h: int = 140,
    max_w: int | None = None,
    max_h: int | None = None,
) -> dict:
    """Grow ``box`` by ``margin`` px of context, keep it at least min_w x min_h,
    then clip to the frame.  Returns integer pixel edges plus the margins that
    actually survived clipping (a box near the frame edge cannot honour them).

    ``max_w`` / ``max_h`` cap the window around the box centre: a caller that
    wants a fixed magnification passes the largest crop that still fits, and the
    window shrinks instead of the zoom."""
    x0, y0, x1, y1 = box
    cx0, cy0, cx1, cy1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin

    # enforce a minimum viewing window, centred on the box
    if cx1 - cx0 < min_w:
        c = 0.5 * (cx0 + cx1)
        cx0, cx1 = c - min_w / 2.0, c + min_w / 2.0
    if cy1 - cy0 < min_h:
        c = 0.5 * (cy0 + cy1)
        cy0, cy1 = c - min_h / 2.0, c + min_h / 2.0

    # cap the window (a zoom target beats the minimum window: the caller asked)
    if max_w and cx1 - cx0 > max_w:
        c = 0.5 * (cx0 + cx1)
        cx0, cx1 = c - max_w / 2.0, c + max_w / 2.0
    if max_h and cy1 - cy0 > max_h:
        c = 0.5 * (cy0 + cy1)
        cy0, cy1 = c - max_h / 2.0, c + max_h / 2.0

    ix0 = int(np.floor(cx0))
    iy0 = int(np.floor(cy0))
    ix1 = int(np.ceil(cx1))
    iy1 = int(np.ceil(cy1))

    kx0, ky0 = max(0, ix0), max(0, iy0)
    kx1, ky1 = min(width, ix1), min(height, iy1)
    if kx1 <= kx0 or ky1 <= ky0:  # degenerate: fall back to the whole frame
        kx0, ky0, kx1, ky1 = 0, 0, width, height
        ix0, iy0, ix1, iy1 = 0, 0, width, height

    return {
        "crop_xyxy": [kx0, ky0, kx1, ky1],
        "crop_w": int(kx1 - kx0),
        "crop_h": int(ky1 - ky0),
        "requested_xyxy": [ix0, iy0, ix1, iy1],
        "margins_px": {
            "left": int(x0 - kx0),
            "top": int(y0 - ky0),
            "right": int(kx1 - x1),
            "bottom": int(ky1 - y1),
        },
        "clipped": [kx0 != ix0, ky0 != iy0, kx1 != ix1, ky1 != iy1],
    }


def choose_zoom(
    crop_w: int,
    crop_h: int,
    scale: int = 2,
    target_h: int = 900,
    max_zoom: int = 8,
    max_panel_w: int = 980,
) -> int:
    """Integer magnification: >= ``scale`` (>= 2 by contract), aimed at
    ``target_h``, never wider than ``max_panel_w``."""
    want = int(round(target_h / max(crop_h, 1)))
    k = max(int(scale), want)
    k = max(2, k)
    if crop_w > 0:
        k = min(k, max(2, max_panel_w // crop_w))
    k = min(k, max_zoom)
    return max(2, int(k))


def zoom_nearest(arr: np.ndarray, k: int) -> np.ndarray:
    """Exact integer replication -- every output pixel is a source pixel."""
    if k == 1:
        return arr
    return np.repeat(np.repeat(arr, k, axis=0), k, axis=1)


def mask_edges(mask: np.ndarray) -> np.ndarray:
    """1-px inner boundary of a boolean mask, 4-connected, pure numpy."""
    if mask.size == 0:
        return mask
    m = np.pad(mask, 1, constant_values=False)
    inner = (
        m[1:-1, 1:-1]
        & m[:-2, 1:-1]
        & m[2:, 1:-1]
        & m[1:-1, :-2]
        & m[1:-1, 2:]
        & m[:-2, :-2]
        & m[:-2, 2:]
        & m[2:, :-2]
        & m[2:, 2:]
    )
    return mask & ~inner


# ---------------------------------------------------------------- drawing ---
def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill=C_PANEL) -> None:
    draw.rectangle(box, fill=fill, outline=C_PANEL_EDGE, width=1)


def _caption(draw, x: int, y: int, text: str, font, color=C_DIM, max_w: int = 0) -> None:
    if max_w > 0:
        text = _ellipsize(draw, text, font, max_w)
    draw.text((x, y), text, font=font, fill=color)


def _ellipsize(draw, text: str, font, max_w: int) -> str:
    if max_w <= 0 or draw.textlength(text, font=font) <= max_w:
        return text
    ell = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if draw.textlength(text[:mid] + ell, font=font) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ell


def _fit_legend(draw, font, avail: int, required: list[str],
                optional: list[tuple[str, str | None]]) -> str:
    """Fit the legend into ``avail`` px without ever cutting a required claim.

    ``required`` segments (the range-band claim above all) are kept verbatim: an
    ellipsis there would leave "range band (observed, ..." on the card, which
    reads as a prediction with a qualifier we merely ran out of room to print.
    Space is made by shortening optional segments to their short form, then by
    dropping them, least important first.
    """
    sep = "   |   "

    def join(req: list[str], opt: list[tuple[str, str | None]]) -> str:
        return "legend   " + sep.join(list(req) + [o[0] for o in opt])

    opt = list(optional)
    while opt:
        text = join(required, opt)
        if draw.textlength(text, font=font) <= avail:
            return text
        for i, (full, short) in enumerate(opt):
            if short and full != short:
                opt[i] = (short, None)      # shorten, then reconsider
                break
        else:
            opt.pop(0)                       # nothing left to shorten: drop the least important
    return join(required, opt)


def _draw_candidate(draw, x0: float, y0: float, x1: float, y1: float,
                    degenerate: bool = False, width: int = 2) -> None:
    """Candidate marker.

    A 1-3 px wide candidate cannot be drawn as a readable rectangle, and
    inflating it into a plausible-looking box would invent extent.  So a
    degenerate candidate is marked with a ring at its centre: a locator, not a
    claim about the target's outline.
    """
    if not degenerate:
        _draw_box(draw, (x0, y0, x1, y1), C_CAND, width)
        return
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    r = 11
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=C_CAND, width=2)


def _draw_box(draw, box, color, width: int = 2, dash: bool = False) -> None:
    x0, y0, x1, y1 = box
    if dash:
        _draw_dashed_rect(draw, (x0, y0, x1, y1), color, width)
        return
    draw.rectangle((x0, y0, x1, y1), outline=color, width=width)


def _draw_dashed_rect(draw, box, color, width=1, dash=4, space=4) -> None:
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                               ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        length = max(abs(bx - ax), abs(by - ay))
        if length == 0:
            continue
        ux = (bx - ax) / length
        uy = (by - ay) / length
        t = 0
        while t < length:
            t2 = min(t + dash, length)
            draw.line([(ax + ux * t, ay + uy * t), (ax + ux * t2, ay + uy * t2)],
                      fill=color, width=width)
            t = t2 + space


C_BAND = (236, 176, 84)     # range band, amber -- never cyan, never a prior hue


def _dash_hline(draw, x0: float, x1: float, y: float, color, dash: int = 6,
                gap: int = 5, width: int = 1) -> None:
    """A dashed horizontal rule, drawn *over* the pixels.

    The band is blended into the crop pixels nowhere: on a 6x panel a 1-px rule
    is thin against a 60-px echo, and drawing it on top keeps it visible even
    where a candidate box or the echo itself sits on the same row.
    """
    x = float(x0)
    while x < x1:
        draw.line((x, y, min(x + dash, x1), y), fill=color, width=width)
        x += dash + gap


def _blend_band_rows(
    arr: np.ndarray,
    ys: Sequence[float],
    color: tuple[int, int, int],
    alpha: float = 0.6,
    dash: int = 6,
    gap: int = 5,
) -> np.ndarray:
    """Two dashed, semi-transparent horizontal lines, blended into the pixels.

    A band is a *row* interval.  The azimuth is not solvable on this data, so the
    band is drawn as two lines and never as a rectangle: a rectangle around the
    echo would be read as a box around a target.
    """
    out = arr.astype(np.float32)
    h, w = out.shape[:2]
    xs = np.arange(w)
    mask_x = (xs % (dash + gap)) < dash
    col = np.array(color, dtype=np.float32)
    for y in ys:
        iy = int(round(y))
        if 0 <= iy < h:
            out[iy, mask_x] = out[iy, mask_x] * (1.0 - alpha) + col * alpha
    return np.rint(np.clip(out, 0, 255)).astype(np.uint8)


def _draw_cross(draw, x: float, y: float, arm: int, color, width: int = 2,
                dash: bool = False) -> None:
    if not dash:
        draw.line([(x - arm, y), (x + arm, y)], fill=color, width=width)
        draw.line([(x, y - arm), (x, y + arm)], fill=color, width=width)
        return
    # dashed arms: a claim too weak to be a solid mark
    for vx, vy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        for t in range(0, arm, 7):
            t2 = min(t + 4, arm)
            draw.line([(x + vx * t, y + vy * t), (x + vx * t2, y + vy * t2)],
                      fill=color, width=width)


def _composite(mask_zoom: np.ndarray, color, base: Image.Image,
               fill_alpha: int = 58, edge_alpha: int = 235) -> Image.Image:
    h, w = mask_zoom.shape
    px = np.zeros((h, w, 4), np.uint8)
    px[mask_zoom] = (color[0], color[1], color[2], fill_alpha)
    px[mask_edges(mask_zoom)] = (color[0], color[1], color[2], edge_alpha)
    return Image.alpha_composite(base, Image.fromarray(px, "RGBA"))


# ------------------------------------------------------------------ prior ---
def collect_priors(frame_data: dict, limit: int = 3) -> list[dict]:
    """Normalise the prior panel inputs.

    Accepted shapes, in order of preference:
      * frame_data["prior_masks"]: list of bool (H,W) arrays -- pairs with
        prior.sweep entries by index
      * prior.sweep / prior["renders"] entries carrying a "mask" array
      * prior.sweep entries with only box_xyxy -> drawn as wireframe boxes
    """
    prior = frame_data.get("prior") or {}
    sweep = prior.get("sweep") or prior.get("renders") or []
    if not isinstance(sweep, (list, tuple)):
        sweep = []
    sweep = [s if isinstance(s, dict) else {} for s in sweep]

    masks = frame_data.get("prior_masks")
    out: list[dict] = []
    if masks is not None:
        for i, m in enumerate(list(masks)[:limit]):
            s = sweep[i] if i < len(sweep) else {}
            out.append({"mask": m, "src": s})
    else:
        for s in sweep:
            m = s.get("mask")
            if isinstance(m, np.ndarray):
                out.append({"mask": m, "src": s})
    if out:
        return out

    boxes: list[dict] = []
    for s in sweep[:limit]:
        b = _box_or_none(s.get("box_xyxy"))
        if b is not None:
            boxes.append({"box": b, "src": s})
    return boxes


def _pose_label(src: dict, idx: int) -> str:
    bits = []
    for key, short in (("yaw_deg", "yaw"), ("pitch_deg", "pitch"), ("roll_deg", "roll")):
        v = src.get(key)
        if isinstance(v, (int, float)):
            bits.append(f"{short} {v:+.0f}")
    if not bits:
        return f"P{idx + 1}"
    return f"P{idx + 1} " + " ".join(bits)


# ----------------------------------------------------------------- render ---
def _pred_token(pred: dict, available: bool) -> str:
    """Footer wording for the prediction: drawn image / rejected hypothesis."""
    if available:
        return (
            f"pred sonar-frame beam {_fmt(pred.get('beam'), 2)} "
            f"row {_fmt(pred.get('row'), 2)} az {_fmt(pred.get('az_deg'), 2)} "
            f"({pred.get('convention') or 'n/a'})"
        )
    reason = pred.get("reason") or pred.get("convention") or "not available"
    if pred.get("beam") is not None or pred.get("row") is not None:
        return f"pred NOT DRAWN ({reason}) -- gantry hypothesis, refuted on this data"
    return f"pred NOT DRAWN ({reason})"


def _footer_fields(sample: str, frame_data: dict) -> list[str]:
    pred = frame_data.get("predicted") or {}
    cand = frame_data.get("candidate") or {}
    prov = frame_data.get("provenance") or {}
    # A refuted mapping must not be printed as if it were a measurement: a bare
    # number in this slot anchors the reader no matter what the qualifier says.
    given = frame_data.get("band") or {}
    if pred.get("available") is True:
        rng_txt = f"{_fmt(pred.get('range_m'), 4)} m (sonar-frame)"
    elif given.get("row_lo") is not None:
        rs = row_scale(frame_data)
        if rs:
            lo = rs["window_start_m"] + float(given["row_lo"]) * rs["res_m_per_row"]
            hi = rs["window_start_m"] + float(given["row_hi"]) * rs["res_m_per_row"]
            span = f"{_fmt(min(lo, hi), 3)}-{_fmt(max(lo, hi), 3)} m"
        else:
            span = f"rows {int(given['row_lo'])}-{int(given['row_hi'])}"
        kind = ("band, predicted" if given.get("status") == "model_ok"
                else "band, observed; model rejected")
        rng_txt = f"{span} ({kind})"
    else:
        rng_txt = f"UNRESOLVED ({pred.get('reason') or 'no sonar-frame estimate'})"
    cand_src = cand.get("source")
    if not cand_src:
        # an empty proposal is a legitimate answer: say so instead of "unknown"
        cand_src = "NONE (empty proposal; B frames a structure ROI)"
    return [
        f"sample {sample}",
        f"category {frame_data.get('category') or 'unknown'}",
        f"range_m {rng_txt}",
        f"candidate.source {cand_src}",
        f"engine_version {prov.get('engine_version') or ENGINE_VERSION}",
    ]


def _pack(draw, tokens: Sequence[str], font, max_w: int, sep: str = "  |  ") -> list[str]:
    lines: list[str] = []
    cur = ""
    for tok in tokens:
        cand = tok if not cur else cur + sep + tok
        if cur and draw.textlength(cand, font=font) > max_w:
            lines.append(cur)
            cur = tok
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines or [""]


def _label(draw, xy, text, font, fill, pad: int = 2) -> None:
    """Small text with a black backing plate, so it survives over sonar speckle."""
    x, y = xy
    tw = draw.textlength(text, font=font)
    th = int(getattr(font, "size", 12))
    draw.rectangle((x - pad, y - pad, x + tw + pad, y + th + pad), fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)


def _nice_step(span_m: float, max_ticks: int = 7) -> float:
    for step in (0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1.0, 2.0):
        if span_m / step <= max_ticks:
            return step
    return 5.0


def _draw_metric_panel(
    cd,
    rx: int,
    by: int,
    mw: int,
    mh: int,
    k: int,
    crop: dict,
    cand_box: tuple[float, float, float, float],
    rscale: dict,
    l_nom: float | None,
    l_src: str,
    style: Style,
    f_leg,
) -> dict:
    """Metre ruler on the row axis, the candidate's radial thickness, and the
    nominal-length reference bars.  Returns a small JSON-safe summary."""
    cx0, cy0, cx1, cy1 = crop["crop_xyxy"]
    res = float(rscale["res_m_per_row"])
    ws = float(rscale["window_start_m"])

    def row_to_m(r: float) -> float:
        return ws + r * res

    info: dict[str, Any] = {"res_m_per_row": res}

    span_m = (cy1 - cy0) * res
    step = _nice_step(span_m)
    info["ruler_step_m"] = step
    t = int(np.floor(row_to_m(cy0) / step)) * step
    ticks: list[tuple[float, float]] = []
    while t <= row_to_m(cy1) + 1e-9:
        r = (t - ws) / res
        if cy0 <= r < cy1:
            ticks.append((r, float(t)))
        t = round(t + step, 6)
    for r, m in ticks:
        y = by + (r - cy0) * k
        if y > by + mh - 86:      # bottom strip is the scale block, keep it clear
            continue
        cd.line((rx + 2, y, rx + 9, y), fill=C_SCALE, width=1)
        _label(cd, (rx + 11, int(y) - 8), f"{m:.2f}", f_leg, C_SCALE)

    # candidate radial thickness (a measurement, not an assumption).  When the
    # candidate lies outside this crop the bracket would be drawn at the panel
    # edge and read as a measurement of whatever happens to be there -- so it is
    # omitted and the B panel says where the candidate actually is.
    dr = (cand_box[3] - cand_box[1]) * res
    info["cand_dR_m"] = round(float(dr), 4)
    if not (cand_box[3] <= cy0 or cand_box[1] >= cy1):
        xb = rx + (cand_box[2] - cx0) * k + 6
        xb = int(min(max(xb, rx + 12), rx + mw - 6))
        y0 = by + (cand_box[1] - cy0) * k
        y1 = by + (cand_box[3] - cy0) * k
        if y1 - y0 < 6:
            mid = 0.5 * (y0 + y1)
            y0, y1 = mid - 3, mid + 3
        cd.line((xb, y0, xb, y1), fill=C_SCALE, width=1)
        cd.line((xb - 3, y0, xb + 3, y0), fill=C_SCALE, width=1)
        cd.line((xb - 3, y1, xb + 3, y1), fill=C_SCALE, width=1)
        dtext = f"dR {dr:.2f} m"
        tw = cd.textlength(dtext, font=f_leg)
        lx = xb + 5
        if lx + tw + 4 > rx + mw:
            lx = xb - tw - 8
        _label(cd, (lx, int(max(by + 2, y0 - style.fs_legend - 2))), dtext, f_leg, C_SCALE)
    else:
        info["cand_bracket"] = "outside crop"

    # scale bar: one ruler step of *range*, drawn horizontally like a map bar.
    # (A vertical bar of a full nominal length would be 2-3x the crop height and
    # would just read as another panel border.)
    bar_len = int(round(step / res * k))
    x0 = rx + 96
    bar_len = max(12, min(bar_len, rx + mw - x0 - 16))
    y_bar = by + mh - 34
    cd.line((x0, y_bar, x0 + bar_len, y_bar), fill=C_SCALE, width=3)
    for xx in (x0, x0 + bar_len):
        cd.line((xx, y_bar - 6, xx, y_bar + 6), fill=C_SCALE, width=1)
    _label(cd, (x0, y_bar - 26), f"{step:.2f} m of range", f_leg, C_SCALE)

    if l_nom:
        rows_nom = float(l_nom) / res
        crop_rows = float(cy1 - cy0)
        # "Nx crop" only when it adds information and fits; the row count and the
        # source are the load-bearing parts of this line
        txt = f"L {l_nom:.3f} m = {rows_nom:.0f} rows"
        tail = (f" = {rows_nom / crop_rows:.1f}x crop" if rows_nom / crop_rows >= 0.35 else "")
        tail += " (nominal, intact round)" if l_src == "nominal" else ""
        room = rx + mw - x0 - 12
        if cd.textlength(txt + tail, font=f_leg) <= room:
            txt += tail
        elif l_src == "nominal" and cd.textlength(txt + " (nominal)", font=f_leg) <= room:
            txt += " (nominal)"
        _label(cd, (x0, y_bar + 12), _ellipsize(cd, txt, f_leg, room),
               f_leg, C_SCALE)
        info["nominal_length_m"] = float(l_nom)
        info["nominal_source"] = l_src
        info["nominal_rows"] = round(rows_nom, 1)
    return info


def render_with_meta(
    sample: str,
    frame_data: dict,
    out_path: Path | str,
    scale: int = 2,
    *,
    gain: float = 1.0,
    style: Style = DEFAULT_STYLE,
    write: bool = True,
    shoulder: bool = True,
    structures_mask: Any = None,
    bg_band: Any = None,
    draw_predicted: bool | None = None,
    neighbors: int = 2,
    crop_max: tuple[int, int] | None = None,
    force_zoom: int | None = None,
    crop_mode: str = "candidate",
) -> tuple[Path, dict]:
    """Render one card.  Returns (path, meta).  ``meta`` is JSON-safe.

    Optional views (all off by default, so a plain record renders as before):
    ``structures_mask``  bool HxW -- the class-agnostic structure domain; panel A
                         greys it down so the candidate has to stand out from a
                         neutral background instead of from the bright arc.
    ``bg_band``          (row0, row1) or a list of them -- rows dominated by
                         background/reverb; bracketed and hatched, never erased.
    ``draw_predicted``   override the ``predicted.available`` gate.
    ``neighbors``        how many frames either side to show in the temporal
                         strip (0 disables it).  The strip is what makes rule a2
                         -- "the bright head keeps the same range over time" --
                         judgeable from a single card.
    ``crop_mode``        what the B/C crop window follows:

                         ``candidate`` (default) -- the window is centred on the
                         candidate box and the usual margin / integer-zoom rules
                         apply.  A supplementary crop_box is ignored: what the
                         engine pointed at is what gets magnified.

                         ``band`` -- the window follows ``frame_data["crop_box"]``
                         (the band-anchored framing used by the first 110229
                         batch), falling back to the candidate.

                         ``auto`` -- candidate first; if the range band lies
                         entirely outside that window, the window is grown just
                         far enough toward the nearest band edge that one side of
                         the band is visible.  The candidate always stays inside.
                         The band never pulls the window off the candidate; it may
                         at most widen it.
    """
    crop_mode = str(crop_mode or "candidate").strip().lower()
    if crop_mode not in ("candidate", "band", "auto"):
        raise ValueError(f"crop_mode must be candidate|band|auto, got {crop_mode!r}")
    out_path = Path(out_path)
    arr, src_meta = decode_frame(frame_data)
    H, W = arr.shape[:2]

    stretched, stretch_meta = robust_stretch(
        arr, style.lo_pct, style.hi_pct, gain, shoulder=shoulder
    )
    frame_rgb = np.repeat(stretched[:, :, None], 3, axis=2)

    # --- candidate box (fallback chain: candidate -> echo rank0 -> frame) -----
    # The gantry-derived prediction is *not* a fallback box: it was refuted on
    # this data, so letting it stand in for a candidate would launder a rejected
    # hypothesis into an annotation proposal.
    pred = frame_data.get("predicted") or {}
    pred_available = pred.get("available") is True
    if draw_predicted is not None:
        pred_available = bool(draw_predicted) and pred_available
    echo = frame_data.get("echo") or {}
    blobs = echo.get("blobs") or []
    other_blobs = [b for b in blobs
                   if isinstance(b, dict) and b.get("rank", 0) != 0
                   and _box_or_none(b.get("box_xyxy")) is not None]
    cand = frame_data.get("candidate") or {}
    cand_box = _box_or_none(cand.get("box_xyxy"))
    box_src = "candidate"
    if cand_box is None:
        ranked = sorted(
            [b for b in blobs if isinstance(b, dict)], key=lambda b: b.get("rank", 99)
        )
        for b in ranked:
            cand_box = _box_or_none(b.get("box_xyxy"))
            if cand_box is not None:
                box_src = f"echo.rank{b.get('rank', '?')}"
                break
    # An empty proposal still has to be judged, and "is there a target here?" is
    # only answerable at magnification.  A `roi` (a class-agnostic structure
    # region) may therefore *frame the crop*; it is never drawn as a candidate,
    # because a cyan box would claim a detection the engine did not make.
    box_is_candidate = cand_box is not None
    roi = frame_data.get("roi") or {}
    if cand_box is None:
        cand_box = _box_or_none(roi.get("box_xyxy"))
        if cand_box is not None:
            box_src = f"roi:{roi.get('why') or 'structure'}"
    if cand_box is None:
        cand_box = (W * 0.25, H * 0.25, W * 0.75, H * 0.75)
        box_src = "frame-default (no candidate in record)"
    cand_box = (
        float(np.clip(cand_box[0], 0, W)),
        float(np.clip(cand_box[1], 0, H)),
        float(np.clip(cand_box[2], 0, W)),
        float(np.clip(cand_box[3], 0, H)),
    )

    cand_w = cand_box[2] - cand_box[0]
    cand_h = cand_box[3] - cand_box[1]
    # a candidate smaller than 3 px on either axis has no drawable extent
    cand_degenerate = bool(min(cand_w, cand_h) < 3.0)

    # The crop window follows one of two anchors.  ``band`` keeps the framing of
    # the first 110229 batch (a crop_box centred on the range band); ``candidate``
    # (the default) magnifies what the engine actually proposed, because a window
    # that excludes the candidate leaves a judge no choice but ``unsure``.
    band_r = None
    _bd = frame_data.get("band") or {}
    if _bd.get("row_lo") is not None and _bd.get("row_hi") is not None:
        band_r = (min(float(_bd["row_lo"]), float(_bd["row_hi"])),
                  max(float(_bd["row_lo"]), float(_bd["row_hi"])))
    if crop_mode == "band":
        anchor = _box_or_none(frame_data.get("crop_box")) or cand_box
    else:
        anchor = cand_box
    crop = plan_crop(anchor, W, H, style.margin, style.min_crop_w, style.min_crop_h,
                     max_w=(crop_max[0] if crop_max else None),
                     max_h=(crop_max[1] if crop_max else None))
    if crop_mode == "auto" and band_r:
        cy0a, _, _, cy1a = crop["crop_xyxy"]
        if cy1a <= band_r[0] or cy0a >= band_r[1]:   # band entirely outside
            edge = band_r[0] if band_r[0] >= cy1a else band_r[1]
            anchor2 = (min(cand_box[0], cand_box[2]), min(cand_box[1], edge),
                       max(cand_box[0], cand_box[2]), max(cand_box[3], edge))
            crop2 = plan_crop(anchor2, W, H, style.margin, style.min_crop_w,
                              style.min_crop_h,
                              max_w=(crop_max[0] if crop_max else None),
                              max_h=(crop_max[1] if crop_max else None))
            # candidate first: a window that reaches the band but drops the
            # candidate would trade one blind card for another
            if crop2["crop_xyxy"][1] <= cand_box[1] and crop2["crop_xyxy"][3] >= cand_box[3]:
                crop = crop2
    k = choose_zoom(crop["crop_w"], crop["crop_h"], scale,
                    style.band_h, style.max_zoom, style.max_panel_w)
    if force_zoom:
        k = max(1, int(force_zoom))

    cx0, cy0, cx1, cy1 = crop["crop_xyxy"]
    crop["crop_mode"] = crop_mode
    crop["crop_rows"] = [int(cy0), int(cy1)]
    crop["crop_center_row"] = round(0.5 * (cy0 + cy1), 2)
    crop_rgb = frame_rgb[cy0:cy1, cx0:cx1]
    crop_zoom = zoom_nearest(crop_rgb, k)

    # --- optional range band (row interval, drawn as two dashed lines) --------
    rscale = row_scale(frame_data)
    band = frame_data.get("band") or {}
    band_meta: dict | None = None
    if band.get("row_lo") is not None and band.get("row_hi") is not None:
        b_lo = float(band["row_lo"])
        b_hi = float(band["row_hi"])
        b_lo, b_hi = min(b_lo, b_hi), max(b_lo, b_hi)
        b_status = str(band.get("status") or "")
        b_rows_pm = band.get("rows_pm") or band.get("band_rows")
        pm = f" +-{int(b_rows_pm)} rows" if b_rows_pm else ""
        if rscale:
            m_lo = rscale["window_start_m"] + b_lo * rscale["res_m_per_row"]
            m_hi = rscale["window_start_m"] + b_hi * rscale["res_m_per_row"]
            span = f"{_fmt(min(m_lo, m_hi), 3)}-{_fmt(max(m_lo, m_hi), 3)} m"
        elif band.get("range_m") is not None:
            span = f"{_fmt(band['range_m'], 3)} m"
        else:
            span = f"rows {b_lo:.0f}-{b_hi:.0f}"
        label = band.get("label")
        if not label:
            if b_status == "model_ok":
                label = f"range band {span} (predicted{pm})"
            else:
                # never let an observed spread read as a prediction
                label = (f"range band {span} (observed{pm}; model rejected; "
                         f"NOT a prediction)")
        band_meta = {"row_lo": b_lo, "row_hi": b_hi, "status": b_status,
                     "source": band.get("source"), "label": label,
                     "short": f"band {span} "
                              f"({'predicted' if b_status == 'model_ok' else 'observed'}{pm})",
                     "outside_crop": bool(b_hi <= cy0 or b_lo >= cy1)}
        band_ys = [(b_lo - cy0) * k, (b_hi - cy0) * k]
    mh, mw = crop_zoom.shape[:2]

    band_h = max(style.band_h, mh)
    left_w_img = int(round(W * band_h / H))
    left_panel_w = left_w_img + 2 * style.left_pad

    card_w = (
        style.pad * 2 + left_panel_w + style.gap + mw + style.gap + mw
    )

    # --- temporal strip geometry (row of +-N neighbour frames) ----------------
    # Single cards cannot show "does the bright head stay at the same range over
    # time", which judgment rule a2 needs.  The strip shares this frame's crop
    # window AND its stretch anchors, so brightness is comparable across cells.
    n_cells = 2 * int(neighbors) + 1 if (neighbors and int(neighbors) > 0) else 0
    cell_gap = 6
    strip_w = mw * 2 + style.gap
    cell_w = ((strip_w - cell_gap * (n_cells - 1)) // n_cells) if n_cells else 0
    cell_h = (int(round(cell_w * (cy1 - cy0) / max(1, cx1 - cx0)))
              if n_cells else 0)
    strip_block = (style.cap_h + cell_h) if n_cells else 0

    # --- fonts & footer height ------------------------------------------------
    f_head, f_cap, f_foot = _font(style.fs_header), _font(style.fs_cap), _font(style.fs_foot)
    f_leg = _font(style.fs_legend)

    foot_inner_w = card_w - 2 * style.pad - 2 * style.foot_pad
    prov = frame_data.get("provenance") or {}
    img_sha = (frame_data.get("image") or {}).get("sha256") or _sha256_bytes(arr.tobytes())
    l_nom, l_src = nominal_length_m(frame_data)
    prov_tokens = [
        f"frame {frame_data.get('aris_frame', 'unknown')}",
        _pred_token(pred, pred_available),
        f"box {_fmt(cand_box[0], 1)},{_fmt(cand_box[1], 1)},{_fmt(cand_box[2], 1)},"
        f"{_fmt(cand_box[3], 1)} ({box_src})",
        f"echo blobs {len(blobs)}",
        f"crop win {crop['crop_xyxy'][0]},{crop['crop_xyxy'][1]},"
        f"{crop['crop_xyxy'][2]},{crop['crop_xyxy'][3]} x{k}",
        f"margins L{crop['margins_px']['left']} T{crop['margins_px']['top']} "
        f"R{crop['margins_px']['right']} B{crop['margins_px']['bottom']} "
        f"(asked {style.margin})",
        (f"row scale {_fmt(rscale['window_start_m'], 4)} + row*"
         f"{_fmt(rscale['res_m_per_row'], 6)} m  ({rscale['source']})")
        if rscale else "row scale unavailable (no window meta)",
        (f"nominal L {_fmt(l_nom, 3)} m ({NOMINAL_SOURCE})" if l_src == "nominal"
         else (f"nominal L {_fmt(l_nom, 3)} m ({l_src})" if l_nom else "nominal L unavailable")),
        f"stretch p{stretch_meta['lo_pct']}-p{stretch_meta['hi_pct']} "
        f"lo{_fmt(stretch_meta['lo'], 1)} hi{_fmt(stretch_meta['hi'], 1)}"
        + (" +shoulder" if stretch_meta.get("shoulder") else ""),
        f"gain {_fmt(gain, 1)}x",
        f"img sha256 {img_sha[:16]}",
        f"card {CARD_VERSION}",
    ]
    if cand_degenerate:
        prov_tokens.insert(3, f"cand degenerate {_fmt(cand_w, 0)}x{_fmt(cand_h, 0)} px "
                              f"-> ring marked, no extent claimed")
    if band_meta:
        prov_tokens.insert(4, f"band rows {band_meta['row_lo']:.0f}..{band_meta['row_hi']:.0f}"
                              f" ({band_meta['source'] or 'unknown'}; "
                              f"status {band_meta['status'] or 'unknown'})")
    tmp_canvas = Image.new("RGB", (10, 10))
    tmp_draw = ImageDraw.Draw(tmp_canvas)
    foot_lines = _pack(tmp_draw, _footer_fields(sample, frame_data), f_foot, foot_inner_w)
    prov_lines = _pack(tmp_draw, prov_tokens, f_foot, foot_inner_w)
    foot_h = (
        style.foot_pad * 2
        + len(foot_lines) * (style.fs_foot + style.foot_line_gap)
        + 4
        + len(prov_lines) * (style.fs_foot + style.foot_line_gap)
    )

    card_h = (style.pad + style.header_h + style.legend_h + style.cap_h + band_h
              + (style.gap + strip_block if n_cells else 0)
              + style.gap + foot_h + style.pad)
    canvas = Image.new("RGB", (card_w, card_h), C_BG)
    draw = ImageDraw.Draw(canvas)

    # --- header ---------------------------------------------------------------
    head_right = (
        f"gain {_fmt(gain, 1)}x  |  stretch p{stretch_meta['lo_pct']}-p{stretch_meta['hi_pct']}"
        f" ({_fmt(stretch_meta['lo'], 0)}..{_fmt(stretch_meta['hi'], 0)})  |  {CARD_VERSION}"
    )
    sat_frac = float(stretch_meta.get("sat_frac") or 0.0)
    if sat_frac > 0.35:
        # gain 3-5x is meant for dim frames; on a bright one it destroys the echo
        head_right += f"  |  SATURATED {sat_frac * 100:.0f}% (lower the gain)"
    hrw = draw.textlength(head_right, font=f_cap)
    draw.text((card_w - style.pad - hrw, style.pad + 12), head_right, font=f_cap, fill=C_DIM)
    # the sample id is the one token that must never be cut: drop the banner text
    # before allowing a truncated sample
    title_room = int(card_w - 2 * style.pad - hrw - 20)
    title = f"SONAR JUDGMENT CARD  {sample}"
    if draw.textlength(title, font=f_head) > title_room:
        title = sample
    draw.text((style.pad, style.pad + 6),
              _ellipsize(draw, title, f_head, title_room),
              font=f_head, fill=C_TEXT)

    leg_y = style.pad + style.header_h + 2
    # The legend is fitted by dropping *optional* segments, never by cutting the
    # band claim: a line that stops at "range band (observed, ..." is worse than
    # a shorter legend, because the one thing it must never lose is the refusal.
    leg_req = ["cyan = candidate"]
    if band_meta:
        n_rows = max(1, int(round(float(band_meta["row_hi"]) - float(band_meta["row_lo"]))))
        if str(band_meta.get("status")) == "model_ok":
            pm = band_meta.get("p90_rows") or n_rows
            leg_req.append(f"amber dash = range band (predicted +-{int(round(float(pm)))} rows)")
        else:
            leg_req.append(f"amber dash = range band (NOT a prediction; "
                           f"observed +-{n_rows} rows)")
    leg_opt: list[tuple[str, str | None]] = [
        ("grey dash = crop window of B", "grey dash = B crop"),
    ]
    if other_blobs:  # only promise a colour that is actually on this card
        leg_opt.append(("violet dash = other echo blobs", "violet dash = other blobs"))
    if pred_available:
        leg_opt.append(("grey cross = sonar-frame prediction", None))
    leg_opt.append(("white = metric scale, not evidence", "white = scale (not evidence)"))
    legend = _fit_legend(draw, f_cap, card_w - 2 * style.pad, leg_req, leg_opt)
    draw.text((style.pad, leg_y), legend, font=f_cap, fill=C_FAINT)

    band_y = style.pad + style.header_h + style.legend_h + style.cap_h
    cap_y = band_y - style.cap_h + 4

    # --- panel A: full frame --------------------------------------------------
    ax = style.pad
    a_arr = frame_rgb
    struct_used = False
    if structures_mask is not None:
        sm = np.asarray(structures_mask)
        if sm.shape == (H, W):
            sm = sm.astype(bool)
            alpha = 0.72
            grey = np.array(C_STRUCT, dtype=np.float32)
            a_arr = a_arr.astype(np.float32)
            a_arr[sm] = a_arr[sm] * (1.0 - alpha) + grey * alpha
            a_arr = np.rint(np.clip(a_arr, 0, 255)).astype(np.uint8)
            struct_used = True
        else:
            raise ValueError(
                f"structures_mask shape {sm.shape} != frame {(H, W)}"
            )
    a_img = Image.fromarray(a_arr).resize((left_w_img, band_h), Image.NEAREST)
    canvas.paste(a_img, (ax + style.left_pad, band_y))
    if band_meta:  # the same two lines at full-frame scale
        for br in (band_meta["row_lo"], band_meta["row_hi"]):
            yy = band_y + br * band_h / H
            _dash_hline(draw, ax + style.left_pad, ax + style.left_pad + left_w_img,
                        yy, C_BAND, dash=5, gap=4)
    if struct_used:
        prov_tokens.insert(4, "struct domain greyed (it is not the target)")
    _caption(draw, ax, cap_y, f"A  FRAME {W}x{H}", f_cap, C_DIM, left_panel_w)
    draw.rectangle(
        (ax + style.left_pad - 1, band_y - 1,
         ax + style.left_pad + left_w_img, band_y + band_h),
        outline=C_PANEL_EDGE, width=1,
    )

    s = band_h / H  # frame -> panel A scale
    ad = ImageDraw.Draw(canvas)
    if struct_used:
        # knows-what: say on the image that the grey field is not evidence of a target
        ad.text((ax + style.left_pad + 3, band_y + band_h - style.fs_legend - 6),
                "struct greyed", font=f_leg, fill=C_STRUCT)
    # crop window, so the reader can see which slice panel B is
    win = (ax + style.left_pad + cx0 * s, band_y + cy0 * s,
           ax + style.left_pad + cx1 * s, band_y + cy1 * s)
    _draw_box(ad, win, C_WIN, 1, dash=True)
    for (tx, ty, dx, dy) in (
        (win[0], win[1], 1, 1), (win[2], win[1], -1, 1),
        (win[0], win[3], 1, -1), (win[2], win[3], -1, -1),
    ):
        ad.line((tx, ty, tx + 7 * dx, ty), fill=C_WIN, width=2)
        ad.line((tx, ty, tx, ty + 7 * dy), fill=C_WIN, width=2)

    # bg band(s): rows dominated by background/reverb -- bracketed, not erased
    bands: list[tuple[float, float]] = []
    if bg_band is not None:
        raw = bg_band
        if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], (list, tuple)):
            items = list(raw)
        else:
            items = [raw]
        for bb in items:
            try:
                r0, r1 = float(bb[0]), float(bb[1])
            except (TypeError, ValueError, IndexError):
                continue
            r0, r1 = max(0.0, min(r0, r1)), min(float(H), max(r0, r1))
            if r1 > r0:
                bands.append((r0, r1))
    for r0, r1 in bands:
        y0 = band_y + r0 * s
        y1 = band_y + r1 * s
        for yy in (y0, y1):
            x = int(ax + style.left_pad)
            while x < int(ax + style.left_pad + left_w_img):
                ad.line((x, yy, min(x + 4, ax + style.left_pad + left_w_img), yy),
                        fill=C_DIM, width=1)
                x += 8
        ad.text((ax + style.left_pad + 3, y0 + 2), "bg band", font=f_leg, fill=C_DIM)

    # candidate box (only while it really is a candidate; an ROI frames the crop
    # and is shown by the crop window, never by a cyan detection box)
    if box_is_candidate:
        _draw_candidate(
            ad,
            ax + style.left_pad + cand_box[0] * s, band_y + cand_box[1] * s,
            ax + style.left_pad + cand_box[2] * s, band_y + cand_box[3] * s,
            degenerate=cand_degenerate, width=style.box_w,
        )
    # echo blobs (rank 0..2)
    for b in sorted([b for b in blobs if isinstance(b, dict)],
                    key=lambda b: b.get("rank", 99))[:3]:
        bb = _box_or_none(b.get("box_xyxy"))
        if bb is None or b.get("rank", 0) == 0:
            continue
        _draw_box(ad, (ax + style.left_pad + bb[0] * s, band_y + bb[1] * s,
                       ax + style.left_pad + bb[2] * s, band_y + bb[3] * s),
                  C_ECHO, 1, dash=True)
    # predicted cross -- only when a sonar-frame estimate produced it.  The
    # gantry mapping is drawn (if forced) in neutral grey with its verdict
    # spelled out next to it, never in an "evidence" colour.
    pred_has_xy = (isinstance(pred.get("beam"), (int, float))
                   and isinstance(pred.get("row"), (int, float)))
    pred_drawn = False
    pred_forced = False
    if pred_available and pred_has_xy:
        px = ax + style.left_pad + float(pred["beam"]) * s
        py = band_y + float(pred["row"]) * s
        if 0 <= float(pred["beam"]) < W and 0 <= float(pred["row"]) < H:
            _draw_cross(ad, px, py, style.cross_arm, C_PRED, 1)
            pred_drawn = True
        if not bool(pred.get("in_window", False)):
            ad.text((ax + style.left_pad + 3, band_y + band_h - style.fs_legend - 6),
                    "pred: OUT OF WINDOW", font=f_leg, fill=C_WARN)
    elif draw_predicted and pred_has_xy:
        px = ax + style.left_pad + float(pred["beam"]) * s
        py = band_y + float(pred["row"]) * s
        _draw_cross(ad, px, py, style.cross_arm, C_PRED, 1, dash=True)
        ad.text((px + style.cross_arm + 4, py - 6),
                "gantry hypothesis (refuted)", font=f_leg, fill=C_DIM)
        pred_drawn = True
        pred_forced = True

    # --- panel B: crop --------------------------------------------------------
    bx = ax + left_panel_w + style.gap
    by = band_y + (band_h - mh) // 2
    canvas.paste(Image.fromarray(crop_zoom), (bx, by))
    draw.rectangle((bx - 1, by - 1, bx + mw, by + mh), outline=C_PANEL_EDGE, width=1)
    full_frame_crop = (crop["crop_w"] >= W and crop["crop_h"] >= H)
    bcap = f"B  CROP x{k}  m{style.margin}"
    if full_frame_crop:
        bcap += "  (full frame)"
    elif any(crop["clipped"]):
        bcap += "  clipped " + "".join(
            s for s, c in zip(("L", "T", "R", "B"), crop["clipped"]) if c
        )
    if cand_degenerate:
        bcap += "  ring = no extent"
    if not box_is_candidate:
        bcap += "  ROI only (no candidate)"
    _caption(draw, bx, cap_y, bcap, f_cap, C_DIM, mw)
    bd = ImageDraw.Draw(canvas)
    if box_is_candidate:
        _draw_candidate(bd,
                        bx + (cand_box[0] - cx0) * k, by + (cand_box[1] - cy0) * k,
                        bx + (cand_box[2] - cx0) * k, by + (cand_box[3] - cy0) * k,
                        degenerate=cand_degenerate, width=style.box_w)
    if box_is_candidate:
        if cand_box[3] <= cy0 or cand_box[1] >= cy1:
            where = "above" if cand_box[3] <= cy0 else "below"
            bd.text((bx + 4, by + 3),
                    f"candidate rows {cand_box[1]:.0f}-{cand_box[3]:.0f} ({where} this crop)",
                    font=f_leg, fill=C_CAND)
        else:
            bd.text((bx + 4, by + 3), "candidate", font=f_leg, fill=C_CAND)
    if band_meta:
        # drawn over everything: the band must stay visible even where the echo
        # and the candidate box sit on the same rows
        for br in (band_meta["row_lo"], band_meta["row_hi"]):
            yy = by + (br - cy0) * k
            if by - 1 <= yy <= by + mh:
                _dash_hline(bd, bx, bx + mw, yy, C_BAND)
        # label sits at the bottom of the panel: anywhere near the band itself it
        # would cover the echo it is describing
        _blabel = band_meta["label"]
        if band_meta["outside_crop"]:
            _blabel += "  [outside this crop]"
        if bd.textlength(_blabel, font=f_leg) > mw - 8:
            # the long form does not fit beside a narrow crop; keep the claim,
            # drop the wording, and point at panel A for the band itself
            _blabel = (f"{band_meta['short']}; NOT a prediction"
                       + ("  see A" if band_meta["outside_crop"] else ""))
        _label(bd, (bx + 4, by + mh - style.fs_legend - 6), _blabel, f_leg, C_BAND)

    # --- panel C: prior -------------------------------------------------------
    rx = bx + mw + style.gap
    priors = collect_priors(frame_data)
    panel_c = Image.fromarray(crop_zoom).convert("RGBA")
    legend: list[tuple[str, tuple[int, int, int]]] = []
    prior_status = "unavailable"
    if priors:
        if "mask" in priors[0]:
            usable = []
            for i, p in enumerate(priors[:3]):
                m = np.asarray(p["mask"])
                if m.shape != (H, W) or m.dtype != np.bool_:
                    if m.shape == (H, W):
                        m = m.astype(bool)
                    else:
                        continue
                usable.append((i, p, m))
            if usable:
                for i, p, m in usable:
                    mz = zoom_nearest(m[cy0:cy1, cx0:cx1], k)
                    color = C_PRIOR[i % len(C_PRIOR)]
                    panel_c = _composite(mz, color, panel_c)
                    legend.append((_pose_label(p["src"], i), color))
                prior_status = "mask"
        if prior_status == "unavailable":
            boxes = [p for p in priors if "box" in p]
            for i, p in enumerate(boxes[:3]):
                color = C_PRIOR[i % len(C_PRIOR)]
                bb = p["box"]
                _draw_box(bd, (rx + (bb[0] - cx0) * k, by + (bb[1] - cy0) * k,
                               rx + (bb[2] - cx0) * k, by + (bb[3] - cy0) * k),
                          color, style.box_w, dash=True)
                legend.append((_pose_label(p["src"], i) + " bbox", color))
            if legend:
                prior_status = "bbox"
    canvas.paste(panel_c.convert("RGB"), (rx, by))
    draw.rectangle((rx - 1, by - 1, rx + mw, by + mh), outline=C_PANEL_EDGE, width=1)
    cd = ImageDraw.Draw(canvas)
    # the same candidate box on panel C, so silhouette vs echo is a direct read
    if box_is_candidate:
        _draw_candidate(cd, rx + (cand_box[0] - cx0) * k, by + (cand_box[1] - cy0) * k,
                        rx + (cand_box[2] - cx0) * k, by + (cand_box[3] - cy0) * k,
                        degenerate=cand_degenerate, width=1)
    metric: dict | None = None
    if rscale:
        metric = _draw_metric_panel(cd, rx, by, mw, mh, k, crop, cand_box,
                                    rscale, l_nom, l_src, style, f_leg)
    if band_meta:
        for br in (band_meta["row_lo"], band_meta["row_hi"]):
            yy = by + (br - cy0) * k
            if by - 1 <= yy <= by + mh:
                _dash_hline(cd, rx, rx + mw, yy, C_BAND)
        # the same band, stated in text on the panel that carries the ruler
        ty = by + 6
        _label(cd, (rx + 4, ty), band_meta["short"], f_leg, C_BAND)
        ty += style.fs_legend + 10
        if band_meta["outside_crop"]:
            cd.text((rx + 4, ty), "band outside this crop (see A)", font=f_leg,
                    fill=C_BAND)
            ty += style.fs_legend + 8
        if box_is_candidate and (cand_box[3] <= cy0 or cand_box[1] >= cy1):
            cd.text((rx + 4, ty), f"candidate rows {cand_box[1]:.0f}-{cand_box[3]:.0f} outside crop",
                    font=f_leg, fill=C_CAND)
    if prior_status == "unavailable":
        ccap = "C  SCALE (no prior)"
        if metric:
            ccap += f"  {metric['ruler_step_m']:.2f} m/div"
        _caption(draw, rx, cap_y, ccap, f_cap, C_WARN, mw)
        msg = "prior: unavailable"
        tw = cd.textlength(msg, font=f_cap)
        th = style.fs_cap
        # top-right, out of the echo's way and off the scale block at the bottom
        bx0 = rx + mw - tw - 18
        by0 = by + 6
        cd.rectangle((bx0, by0, bx0 + tw + 14, by0 + th + 8),
                     fill=(0, 0, 0), outline=C_WARN, width=1)
        cd.text((bx0 + 7, by0 + 4), msg, font=f_cap, fill=C_WARN)
    else:
        _caption(draw, rx, cap_y,
                 f"C  PRIOR  {len(legend)} pose(s)  x{k}",
                 f_cap, C_DIM, mw)
        ly = by + 2
        for text, color in legend:
            tw = cd.textlength(text, font=f_leg)
            cd.rectangle((rx + 4, ly, rx + 4 + tw + 22, ly + style.fs_legend + 4),
                         fill=(0, 0, 0))
            cd.rectangle((rx + 8, ly + 4, rx + 8 + 9, ly + 4 + 9), fill=color)
            cd.text((rx + 22, ly + 2), text, font=f_leg, fill=color)
            ly += style.fs_legend + 8

    # --- temporal strip: same window, +-N frames ------------------------------
    temporal: dict = {}
    if n_cells:
        try:
            cur_f: int | None = int(frame_data.get("aris_frame"))
        except (TypeError, ValueError):
            cur_f = None
        sy_cap = band_y + band_h + style.gap
        sy = sy_cap + style.cap_h
        sx0 = bx
        lo_a = float(stretch_meta["lo"])
        hi_a = float(stretch_meta["hi"])
        frames_drawn: list[int] = []
        missing: list[int] = []
        for i in range(n_cells):
            f = (cur_f - int(neighbors) + i) if cur_f is not None else None
            cx_cell = sx0 + i * (cell_w + cell_gap)
            is_cur = (f is not None and cur_f is not None and f == cur_f)
            if is_cur:
                arr_n = arr
            else:
                arr_n = _neighbor_frame(frame_data, f) if f is not None else None
            if arr_n is None:
                draw.rectangle((cx_cell, sy, cx_cell + cell_w, sy + cell_h),
                               fill=(20, 20, 24), outline=C_PANEL_EDGE)
                draw.text((cx_cell + 5, sy + max(6, cell_h // 2 - 8)),
                          "no frame", font=f_leg, fill=C_DIM)
                if f is not None:
                    missing.append(f)
            else:
                st_n, _sm = robust_stretch(
                    arr_n, lo_pct=style.lo_pct, hi_pct=style.hi_pct, gain=gain,
                    shoulder=shoulder, lo=lo_a, hi=hi_a,
                )
                cd_n = st_n[cy0:cy1, cx0:cx1]
                im_n = Image.fromarray(np.repeat(cd_n[:, :, None], 3, axis=2))
                im_n = im_n.resize((cell_w, cell_h), Image.NEAREST)
                canvas.paste(im_n, (cx_cell, sy))
                if f is not None:
                    frames_drawn.append(f)
            lab = f"{f}" if f is not None else "?"
            tw = draw.textlength(lab, font=f_leg)
            draw.rectangle((cx_cell + 3, sy + 2,
                            cx_cell + 5 + tw + 6, sy + 6 + style.fs_legend),
                           fill=(0, 0, 0))
            draw.text((cx_cell + 6, sy + 3), lab, font=f_leg,
                      fill=C_WARN if is_cur else C_TEXT)
            draw.rectangle((cx_cell, sy, cx_cell + cell_w, sy + cell_h),
                           outline=C_WARN if is_cur else C_PANEL_EDGE,
                           width=2 if is_cur else 1)
        tcap = "D  TIME  same window"
        if cur_f is not None:
            tcap += (f", frames {cur_f - int(neighbors)}..{cur_f + int(neighbors)}"
                     f"  (current {cur_f})")
        if missing:
            tcap += "  missing " + ",".join(str(m) for m in missing)
        _caption(draw, sx0, sy_cap + 4, tcap, f_cap, C_DIM, strip_w)
        temporal = {"current": cur_f, "neighbors": int(neighbors),
                    "frames": frames_drawn, "missing": missing,
                    "cell_px": [cell_w, cell_h]}

    # --- footer ---------------------------------------------------------------
    fy = (band_y + band_h + (style.gap + strip_block if n_cells else 0)
          + style.gap + style.foot_pad)
    for line in foot_lines:
        draw.text((style.pad + style.foot_pad, fy), line, font=f_foot, fill=C_TEXT)
        fy += style.fs_foot + style.foot_line_gap
    fy += 4
    for line in prov_lines:
        draw.text((style.pad + style.foot_pad, fy), line, font=f_foot, fill=C_DIM)
        fy += style.fs_foot + style.foot_line_gap

    meta = {
        "sample": sample,
        "card": CARD_VERSION,
        "size_px": [card_w, card_h],
        "zoom": k,
        "panels": {
            "A": [left_w_img, band_h],
            "B": [mw, mh],
            "C": [mw, mh],
        },
        "crop": crop,
        "stretch": stretch_meta,
        "gain": gain,
        "predicted_drawn": bool(pred_drawn),
        "predicted_forced": bool(pred_forced),
        "predicted_reason": None if pred_available else (pred.get("reason") or "unavailable"),
        "structures_greyed": bool(struct_used),
        "bg_bands": [list(b) for b in bands],
        "row_scale": rscale,
        "metric_panel": metric,
        "temporal": temporal,
        "band": band_meta,
        "image_sha256": img_sha,
        "input": src_meta,
        "candidate_box": list(cand_box),
        "box_source": box_src,
        "box_is_candidate": bool(box_is_candidate),
        "candidate_degenerate": bool(cand_degenerate),
        "box_source": box_src,
        "predicted_in_window": bool(pred.get("in_window", False)) if pred_available else None,
        "prior_status": prior_status,
        "prior_count": len(legend),
        "style": style.as_dict(),
    }
    if write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path, format="PNG", optimize=False)
        meta["out"] = str(out_path)
        meta["out_sha256"] = _sha256_bytes(out_path.read_bytes())
    return out_path, meta


def render(sample: str, frame_data: dict, out_path: Path | str, scale: int = 2,
           **kwargs: Any) -> Path:
    """BRIEF entry point: one record -> one PNG.

    Extra keyword arguments (``structures_mask``, ``bg_band``, ``gain``,
    ``shoulder``, ``draw_predicted``) pass through to :func:`render_with_meta`.
    """
    path, _meta = render_with_meta(sample, frame_data, out_path, scale=scale, **kwargs)
    return path


# ------------------------------------------------------------------- CLI ----
def _geom_module():
    """geometry.py is a sibling module; import it leniently so cards still run alone."""
    try:
        from engine import geometry as g  # run as a package / from repo root
    except ImportError:
        try:
            import geometry as g  # run as a script from engine/
        except ImportError:  # pragma: no cover - cards must work without it
            return None
    return g


def proposal_to_record(row: dict, *, recording: str | None = None) -> dict:
    """Adapt one ``engine/echo.py`` proposals.jsonl row to the BRIEF record shape.

    The proposals schema is the engine's working format (``frame``/``blobs``/
    ``mode``/``bg``/``range_window_m``/``structures``); cards want the unified
    record.  Everything here is a rename or a re-derivation of one number --
    no detection happens in this module.
    """
    g = _geom_module()
    if g is None:
        raise SystemExit("[cards] engine/geometry.py is required to read proposals")
    frame = int(row["frame"])
    rec_name = recording or row.get("recording")
    if not rec_name:
        raise SystemExit(f"[cards] proposals row for frame {frame} has no recording; "
                         f"pass --recording")
    rec = g.load_recording(rec_name, with_meta=False)
    img_path = rec.pgm_path(frame)
    hdr = rec.header
    rw = row.get("range_window_m") or list(rec.range_window)
    n_rows = int(row.get("n_rows") or rec.n_rows)
    res = (float(rw[1]) - float(rw[0])) / max(n_rows - 1, 1)

    blobs = list(row.get("blobs") or [])
    prov = row.get("provenance") or {}
    engine_tag = str(prov.get("engine_version") or "")
    compact = engine_tag.startswith("compact")
    cand = None
    if blobs:
        b0 = row.get("top") or blobs[0]
        if compact:
            # the compact detector is its own engine: the footer must name it,
            # not an echo.detect() call it never made
            cand = {
                "box_xyxy": [float(v) for v in b0["box_xyxy"]],
                "source": engine_tag,
                "score": b0.get("score"),
                "notes": (f"snr {b0.get('snr')}  peak {b0.get('peak')}  "
                          f"area {b0.get('area')}  fill {b0.get('fill')}  "
                          f"struct_overlap {b0.get('structure_overlap')}"),
            }
        else:
            cand = {
                "box_xyxy": [float(v) for v in b0["box_xyxy"]],
                "source": f"echo.detect(mode={row.get('mode')},bg.half={((row.get('bg') or {}).get('half'))})",
                "score": b0.get("score"),
                "notes": (f"snr {b0.get('snr')}  peak {b0.get('peak')}  area {b0.get('area')}  "
                          f"struct_overlap {b0.get('structure_overlap')}"),
            }
    return {
        "sample": f"{rec_name}_{frame:04d}",
        "recording": rec_name,
        "category": rec.category,
        "aris_frame": frame,
        "image": {"path": str(img_path), "width": int(rec.n_beams),
                  "height": int(hdr.get("SamplesPerBeam") or n_rows), "sha256": None},
        # No sonar-frame localisation exists (geometry is degraded, BRIEF 2.2):
        # the gantry mapping is refuted, so the record says so and carries no number.
        "predicted": {"available": False, "reason": "gantry_not_sonar_frame"},
        "echo": {"blobs": blobs,
                 "params": {"mode": row.get("mode"), "bg": row.get("bg"),
                            "energy": row.get("energy"),
                            "structures": row.get("structures")}},
        "prior": {"model": None, "length_m": None, "sweep": []},
        "candidate": cand,
        "provenance": {
            "engine_version": (engine_tag if compact else
                               f"echo.detect/{row.get('mode')} "
                               f"bg={((row.get('bg') or {}).get('mode'))}"
                               f".half{((row.get('bg') or {}).get('half'))}"),
            "inputs_sha256": {},
            "params": {
                "mode": row.get("mode"),
                "bg": row.get("bg"),
                "row_scale": {"window_start_m": float(rw[0]),
                              "res_m_per_row": res,
                              "n_rows": n_rows,
                              "source": "proposals.range_window_m"},
                "n_candidates": row.get("n_candidates"),
            },
        },
    }


def _iter_records(args) -> list[dict]:
    recs: list[dict] = []
    if args.record_json:
        recs.append(json.loads(Path(args.record_json).read_text(encoding="utf-8")))
    if args.proposals:
        p = Path(args.proposals)
        if not p.exists():
            raise SystemExit(f"[cards] proposals not found: {p}")
        rec_name = args.recording or p.parent.name
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "blobs" in row and "echo" not in row:  # engine/echo.py working format
                row = proposal_to_record(row, recording=rec_name)
            recs.append(row)
    if args.samples:
        want = {s.strip() for s in args.samples.split(",") if s.strip()}
        recs = [r for r in recs if str(r.get("sample")) in want]
    if args.frames:
        want = {int(v) for v in args.frames.split(",") if v.strip()}
        recs = [r for r in recs if int(r.get("aris_frame", -1)) in want]
    if args.limit:
        recs = recs[: args.limit]
    return recs


def _selftest(out_dir: Path) -> int:
    """Synthetic fixture: bright arc + candidate + two silhouettes.

    Proves (a) the renderer runs without geometry/echo/mesh_prior,
    (b) the same record renders byte-identically twice,
    (c) the prior-unavailable and out-of-window paths still produce a readable card.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    H, W = 780, 128
    yy, xx = np.mgrid[0:H, 0:W]
    rng = np.random.default_rng(7)
    img = rng.normal(13, 3.0, size=(H, W))
    # a specular arc, roughly where a real 100 lbs bomb echoes
    r = np.hypot((yy - 200.0) / 1.0, (xx - 66.0) * 1.6)
    arc = np.exp(-((r - 32.0) ** 2) / (2 * 9.0 ** 2))
    img += 60.0 * arc * (yy < 280)
    img = np.clip(img, 0, 255).astype(np.uint8)

    box = [16.0, 142.0, 112.0, 264.0]
    rec = {
        "sample": "FIXTURE_0000",
        "recording": "FIXTURE",
        "category": "100lbs_aircraft_bomb",
        "aris_frame": 0,
        "img": img,
        "image": {"path": None, "width": W, "height": H, "sha256": _sha256_bytes(img.tobytes())},
        "predicted": {"beam": 66.0, "row": 189.6, "range_m": 1.2604, "az_deg": 10.22,
                      "in_window": True, "convention": "selftest"},
        "echo": {"blobs": [
            {"box_xyxy": box, "area": 4200, "peak": 86, "mean": 41.0, "snr": 9.4,
             "centroid": [66.0, 177.6], "n_components_merged": 1, "rank": 0},
            {"box_xyxy": [20.0, 300.0, 44.0, 330.0], "area": 190, "peak": 38, "mean": 24.0,
             "snr": 3.1, "centroid": [30.0, 315.0], "n_components_merged": 1, "rank": 1},
        ], "params": {"k": 31, "thr": "p99"}},
        "prior": {"model": "100lbs", "length_m": 0.737, "diameter_m": 0.208,
                  "sweep": [{"yaw_deg": 0, "pitch_deg": 0, "roll_deg": 0,
                             "beam_span_px": 33.0, "row_span_px": 68.0},
                            {"yaw_deg": 45, "pitch_deg": 15, "roll_deg": 0,
                             "beam_span_px": 29.0, "row_span_px": 55.0}]},
        "candidate": {"box_xyxy": box, "source": "echo_primary+prior", "score": 0.71,
                      "notes": "selftest"},
        "provenance": {"engine_version": "v0-selftest", "inputs_sha256": {}, "params": {}},
    }
    # two elliptical silhouettes, rotated differently
    masks = []
    for ang in (0.0, np.deg2rad(38.0)):
        a, b = 34.0, 13.0
        u = (xx - 66.0) * np.cos(ang) + (yy - 190.0) * np.sin(ang)
        v = -(xx - 66.0) * np.sin(ang) + (yy - 190.0) * np.cos(ang)
        masks.append((u / a) ** 2 + (v / b) ** 2 <= 1.0)
    rec["prior_masks"] = [m.astype(np.bool_) for m in masks]

    p1, m1 = render_with_meta("FIXTURE_0000", rec, out_dir / "fixture__g1x.png")
    p2, m2 = render_with_meta("FIXTURE_0000", rec, out_dir / "fixture__g1x_again.png")
    p3, _ = render_with_meta("FIXTURE_0000", rec, out_dir / "fixture__g5x.png", gain=5)

    rec_noprior = {k: v for k, v in rec.items() if k != "prior_masks"}
    rec_noprior["prior"] = {"model": None, "sweep": [], "status": "unavailable"}
    p4, m4 = render_with_meta("FIXTURE_0000", rec_noprior, out_dir / "fixture__noprior.png")

    rec_oow = dict(rec)
    rec_oow["predicted"] = dict(rec["predicted"], in_window=False)
    p5, _ = render_with_meta("FIXTURE_0000", rec_oow, out_dir / "fixture__oow.png", gain=3)

    # a sonar-frame prediction is the only kind allowed to draw a cross
    rec_avail = dict(rec)
    rec_avail["predicted"] = dict(rec["predicted"], available=True,
                                  convention="selftest-sonar-frame")
    p6, m6 = render_with_meta("FIXTURE_0000", rec_avail, out_dir / "fixture__pred.png")

    # forcing the refuted gantry mapping must come back dashed + labelled
    p7, m7 = render_with_meta("FIXTURE_0000", rec, out_dir / "fixture__forced.png",
                              draw_predicted=True)

    # class-agnostic structure domain greyed out in panel A
    smask = np.zeros((H, W), bool)
    smask[120:300, :] = True
    p8, m8 = render_with_meta("FIXTURE_0000", rec, out_dir / "fixture__struct.png",
                              structures_mask=smask)

    h1 = _sha256_bytes(p1.read_bytes())
    h2 = _sha256_bytes(p2.read_bytes())

    # a candidate with no drawable extent must be marked, never inflated
    rec_degen = dict(rec)
    rec_degen["candidate"] = dict(rec["candidate"], box_xyxy=[60.0, 150.0, 61.0, 154.0])
    p9, m9 = render_with_meta("FIXTURE_0000", rec_degen, out_dir / "fixture__ring.png")
    p10, m10 = render_with_meta("FIXTURE_0000", rec, out_dir / "fixture__notime.png",
                                neighbors=0)

    # --- crop mode: the window must follow what the engine pointed at ---------
    rec_band = dict(rec)
    rec_band["band"] = {"row_lo": 500.0, "row_hi": 512.0, "rows_pm": 6,
                        "status": "unreliable_model", "source": "fit_point"}
    rec_band["crop_box"] = [66.0, 500.0, 92.0, 512.0]     # band-anchored framing
    p11, m11 = render_with_meta("FIXTURE_0000", rec_band, out_dir / "fixture__cropcand.png",
                                crop_mode="candidate", crop_max=(108, 146), force_zoom=6)
    p12, m12 = render_with_meta("FIXTURE_0000", rec_band, out_dir / "fixture__cropband.png",
                                crop_mode="band", crop_max=(108, 146), force_zoom=6)
    p13, m13 = render_with_meta("FIXTURE_0000", rec_band, out_dir / "fixture__cropauto.png",
                                crop_mode="auto", crop_max=(108, 146), force_zoom=6)

    checks = [
        ("deterministic", h1 == h2),
        ("no-cross-by-default", m1["predicted_drawn"] is False),
        ("cross-when-available", m6["predicted_drawn"] is True
         and m6["predicted_forced"] is False),
        ("forced-is-flagged", m7["predicted_forced"] is True),
        ("structures-greyed", m8["structures_greyed"] is True
         and m8["out_sha256"] != h1),
        ("prior-counts", m1["prior_count"] == 2 and m4["prior_count"] == 0),
        ("temporal-strip", m1["temporal"]["neighbors"] == 2
         and len(m1["temporal"]["frames"]) + len(m1["temporal"]["missing"]) == 5),
        ("temporal-off", m10["temporal"] == {}),
        ("degenerate-ring", m9["candidate_degenerate"] is True
         and m9["crop"]["crop_w"] >= DEFAULT_STYLE.min_crop_w),
        # crop mode: candidate -- the window holds the candidate and says the
        # band is outside, even though crop_box points at the band
        ("crop-mode-candidate", m11["crop"]["crop_xyxy"][1] <= box[1]
         and m11["crop"]["crop_xyxy"][3] >= box[3]
         and m11["band"]["outside_crop"] is True
         and m11["crop"]["crop_mode"] == "candidate"),
        # crop mode: band -- the old behaviour, window follows crop_box
        ("crop-mode-band", m12["crop"]["crop_xyxy"][1] <= 500.0
         and m12["crop"]["crop_xyxy"][3] >= 512.0
         and m12["crop"]["crop_xyxy"][1] >= box[3]      # candidate is now the miss
         and m12["band"]["outside_crop"] is False),
        # crop mode: auto -- candidate wins when the cap cannot hold both
        ("crop-mode-auto", m13["crop"]["crop_xyxy"][1] <= box[1]
         and m13["crop"]["crop_xyxy"][3] >= box[3]
         and m13["crop"]["crop_mode"] == "auto"
         and m13["crop"]["crop_xyxy"] != m12["crop"]["crop_xyxy"]),
    ]
    print(f"[selftest] card1      {m1['size_px']} zoom={m1['zoom']} sha={h1[:16]}")
    for name, ok_i in checks:
        print(f"[selftest] {name:<20} {'PASS' if ok_i else 'FAIL'}")
    print(f"[selftest] prior      g1={m1['prior_status']} noprior={m4['prior_status']}")
    print(f"[selftest] files      {p1.name} {p6.name} {p7.name} {p8.name}")
    print(f"[selftest] dir        {out_dir}")
    ok = all(v for _n, v in checks)
    if not ok:
        print("[selftest] FAIL", file=sys.stderr)
        return 1
    print("[selftest] PASS")
    return 0


def attach_band(rec: dict, band_doc: dict) -> dict:
    """Attach a ``rangeband/v0`` band to one record (returns the same dict).

    The band is a *row interval*; the frame's azimuth is not solvable, so the
    record carries rows, not a box.  ``crop_box`` is only a framing hint for
    ``--crop-mode band`` -- it is what made the first 110229 batch crop rows
    317-441 and miss a candidate sitting at rows 109-140.
    """
    f = str(int(rec.get("aris_frame", -1)))
    info = (band_doc.get("frames") or {}).get(f) or {}
    if info.get("row_lo") is None or info.get("row_hi") is None:
        return rec
    src = str(band_doc.get("source") or "")
    rec["band"] = {
        "row_lo": float(info["row_lo"]),
        "row_hi": float(info["row_hi"]),
        "range_m": info.get("range_m"),
        "rows_pm": band_doc.get("band_rows"),
        "status": band_doc.get("status"),
        "source": src.split("(")[0].strip() or src,     # e.g. "fit_point"
    }
    cand = rec.get("candidate") or {}
    box = _box_or_none(cand.get("box_xyxy"))
    if box is not None:
        cx = 0.5 * (box[0] + box[2])
    else:
        cx = 0.5 * float((rec.get("image") or {}).get("width") or 1)
    rec["crop_box"] = [cx - 26.0, float(info["row_lo"]), cx + 26.0, float(info["row_hi"])]
    return rec


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render sonar judgment cards (T-CARDS)")
    ap.add_argument("--record-json", help="single unified record (JSON)")
    ap.add_argument("--proposals", help="proposals.jsonl, one record per line")
    ap.add_argument("--recording", help="recording id (default: the parent dir of --proposals)")
    ap.add_argument("--samples", help="comma-separated sample ids to keep")
    ap.add_argument("--frames", help="comma-separated aris_frame values to keep")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(REPO / "out" / "cards"))
    ap.add_argument("--flat", action="store_true",
                    help="write <out>/<sample>.png instead of <out>/<recording>/...")
    ap.add_argument("--neighbors", type=int, default=2,
                    help="frames either side in the temporal strip (0 = off)")
    ap.add_argument("--gain", default="1", help="comma list, e.g. 1,3,5")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--margin", type=int, default=DEFAULT_STYLE.margin)
    ap.add_argument("--band-h", type=int, default=DEFAULT_STYLE.band_h)
    ap.add_argument("--band", help="rangeband/v0 band.json to overlay (per-frame rows)")
    ap.add_argument("--crop-mode", default="candidate",
                    choices=["candidate", "band", "auto"],
                    help="what the B/C crop follows: candidate box (default), "
                         "the band-anchored crop_box, or auto")
    ap.add_argument("--crop-max", default="",
                    help="cap the crop window, e.g. 108x146 (keeps zoom high)")
    ap.add_argument("--force-zoom", type=int, default=0,
                    help="force an integer zoom instead of the computed one")
    ap.add_argument("--report", help="write a JSON report here")
    ap.add_argument("--why", help="one line recorded in the report (why this render)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    style = Style(margin=args.margin, band_h=args.band_h)

    if args.selftest:
        return _selftest(REPO / "tmp" / "cards" / "selftest")

    recs = _iter_records(args)
    if not recs:
        print("[cards] no records selected", file=sys.stderr)
        return 3

    gains = [float(g) for g in args.gain.split(",") if g.strip()]
    crop_max = None
    if args.crop_max:
        w_s, h_s = args.crop_max.lower().replace(" ", "").split("x")
        crop_max = (int(w_s), int(h_s))
    if args.band:
        band_doc = json.loads(Path(args.band).read_text(encoding="utf-8"))
        recs = [attach_band(rec, band_doc) for rec in recs]
    out_dir = Path(args.out)
    metas: list[dict] = []
    for rec in recs:
        sample = str(rec.get("sample") or "unknown")
        sub = out_dir if args.flat else out_dir / str(rec.get("recording") or "unknown")
        for g in gains:
            if args.flat and len(gains) == 1:
                suffix = ""  # out/cards/<sample>.png
            else:
                suffix = "__g1x" if g == 1 else f"__g{_fmt(g, 0)}x"
            path = sub / f"{sample}{suffix}.png"
            _p, meta = render_with_meta(sample, rec, path, scale=args.scale,
                                        gain=g, style=style,
                                        neighbors=args.neighbors,
                                        crop_max=crop_max,
                                        force_zoom=(args.force_zoom or None),
                                        crop_mode=args.crop_mode)
            meta["gain"] = g
            meta["why"] = args.why
            metas.append(meta)
            print(f"[cards] {path}  {meta['size_px'][0]}x{meta['size_px'][1]}  "
                  f"zoom={meta['zoom']}  crop={meta['crop']['crop_xyxy']}  "
                  f"mode={args.crop_mode}  prior={meta['prior_status']}")
    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        doc = {"crop_mode": args.crop_mode,
               "frozen_at": datetime.now().astimezone().isoformat(timespec="seconds"),
               "why": args.why,
               "cards": metas}
        rp.write_text(json.dumps(doc, ensure_ascii=False, indent=2,
                                 allow_nan=False), encoding="utf-8")
        print(f"[cards] report {rp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
