#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mesh_prior.py — T-MESH: 3D UXO mesh silhouette prior on the ARIS (beam,row) grid.

What this module answers
------------------------
"At range R, azimuth AZ, with this pose hypothesis, how many (beam,row) pixels
could this object occupy?"  It returns a silhouette mask on the sonar pixel
grid, its bounding box, its beam/row spans and the in-frame fraction.

What it deliberately does NOT do
--------------------------------
* No acoustic model.  No shadowing, no multipath, no multi-bounce, no
  refraction, no beam pattern, no TVG.  Geometry only.
* No pose estimate.  yaw/pitch/roll are *hypotheses* that get swept; every
  returned record carries ``uniqueness: false`` and an ``assumption`` string.
* No GT claim.  Output is a "possible extent" constraint, nothing else.

Data path
---------
OBJ (Agisoft Metashape, 95k verts, ~15 MB)
  -> parse v / f (triangulate polygons by fan)
  -> canonical frame from PCA of the raw vertices (long axis -> +x)
  -> uniform scale so that the long-axis extent == nominal_length_m
  -> voxel-cluster face centroids down to <= 3000 surface points
     (raw per-axis extremes are force-injected, so extent is preserved exactly)
  -> pose rotation (yaw,pitch,roll) about the line of sight
  -> perspective projection of every point: (az, range) -> (beam, row)
  -> rasterize (point splat or triangle fill, both pure numpy) -> close/fill
  -> mask + box + spans

Pixel grid (from rec_meta, NOT hardcoded -- see note)
-----------------------------------------------------
    deg_per_beam = FOV_DEG / n_beams                  (130/128 = 1.015625)
    beam         = (n_beams - 1)/2 + az_deg / deg_per_beam
    row          = (range_m - window_start_m) / (window_length_m / n_samples)

NOTE (measured, 2026-11-12): ``n_samples`` differs per recording.
``2023-09-20_171105`` (100lbs) is 128x780; ``2023-09-21_120653`` (incindiary)
and ``2023-09-21_100927`` (15cm mortar) are 128x441.  BRIEF section 1 states
780; that holds for the 100lbs recording only.  ``rec_meta`` decides the mask
shape, so this module follows the recording.

Hashes
------
``sha256`` of the raw OBJ, of the downsampled point array (little-endian
float64, C order) and of the decimated face array (little-endian int64) are
written to every output, so "which mesh produced this" is checkable.

CLI
---
    python engine/mesh_prior.py --category mortar_shell --range 1.26 --az 10 \
        --out out/prior_demo.json
    python engine/mesh_prior.py --all --check
    python engine/mesh_prior.py --all --check --images tmp/mesh

Only numpy (+ PIL for the optional debug overlays) is used.  No cv2 / scipy /
skimage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------
# constants / paths (resolved from __file__, never from argv)
# --------------------------------------------------------------------------

ENGINE_VERSION = "mesh-prior-v0"
SCHEMA = "sonar_llm_annotation/mesh_prior/v0"

REPO = Path(__file__).resolve().parents[1]          # .../sonar_llm_annotation
WORKSPACE = REPO.parent                             # .../声呐目标检测_workflow
MODEL_DIR = (WORKSPACE / "related_work" / "sonar-projection-audit-assets"
             / "data_export_3dmodels" / "3d_models")
REGISTRATION_JSON = (WORKSPACE / "DataSet" / "sonar_model_registration_consistency"
                     / "mesh-registration.json")
OUT_DIR = REPO / "out"
TMP_DIR = REPO / "tmp" / "mesh"
RAW_ROOT = Path("D:/pby/uxo-full/extracted/recordings")   # read-only

FOV_DEG = 130.0            # BRIEF section 1 / section 2
MAX_POINTS = 3000          # hard cap on the downsampled surface point set

# manifest category  ->  OBJ model name
CATEGORY_TO_MODEL = {
    "100lbs_aircraft_bomb": "100lbs",
    "incindiary_grenade": "incindiary",
    "mortar_shell": "mortar_shell",
}
MODEL_TO_CATEGORY = {v: k for k, v in CATEGORY_TO_MODEL.items()}

# recording -> class_dir under RAW_ROOT (BRIEF section 1)
RECORDING_TO_CLASS_DIR = {
    "2023-09-20_171105": "100lbs_bomb",
    "2023-09-21_120653": "20lbs_incendiary",
    "2023-09-21_100927": "15cm_mortar",
}

# which recording a single-category run should be rendered on by default
# (each recording has its own SamplesPerBeam, so this is not cosmetic)
CATEGORY_DEFAULT_RECORDING = {
    "100lbs_aircraft_bomb": "2023-09-20_171105",
    "incindiary_grenade": "2023-09-21_120653",
    "mortar_shell": "2023-09-21_100927",
}

# BRIEF section 1 constants, used only when nothing better is readable.
FALLBACK_REC_META = {    "recording": "2023-09-20_171105",   # 100lbs, BRIEF section 2 worked example
    "frame": 622,
    "n_beams": 128,
    "n_samples": 780,
    "window_start_m": 0.6949365139007568,
    "window_length_m": 2.326396942138672,
}

ASSUMPTION = (
    "geometry-only footprint: rigid photogrammetry mesh, uniform scale from the "
    "nominal length, nominal centre placed on the given (range, az) line of sight; "
    "NO acoustic shadowing / multipath / multi-bounce / refraction / beam-pattern "
    "or TVG modelling. The mask is a conservative 'possible extent', not a "
    "prediction of echo brightness."
)
POSE_CONVENTION = (
    "sonar frame: +x starboard(right), +y down, +z boresight. az_deg>0 toward +x; "
    "range = euclidean |p| from the sonar origin. Pose = R_right(pitch) * R_down(yaw) "
    "* B * R_xmodel(roll), B maps model (+x,+y,+z) -> (boresight, down, -starboard). "
    "yaw=0 -> long axis along the line of sight (end-on, minimum silhouette); "
    "|yaw|=90 -> broadside (maximum silhouette); pitch>0 = nose up; roll spins the "
    "mesh about its own long axis. Model canonical frame: +x = PCA major axis, "
    "origin = raw AABB centre."
)


# --------------------------------------------------------------------------
# small numeric helpers (pure numpy)
# --------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_array(arr: np.ndarray, dtype: str) -> str:
    a = np.ascontiguousarray(arr.astype(np.dtype(dtype), copy=False))
    return hashlib.sha256(a.tobytes()).hexdigest()


def _r(x, nd: int = 6) -> float:
    """Round for JSON output; reject non-finite numbers."""
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"non-finite number in output: {v!r}")
    return round(v, nd)


def _rot_axis(axis: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rodrigues rotation about a unit axis, degrees."""
    a = np.asarray(axis, dtype=np.float64)
    a = a / np.linalg.norm(a)
    t = math.radians(float(angle_deg))
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    return np.array([
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ], dtype=np.float64)


def _shift2d(a: np.ndarray, dy: int, dx: int, fill: bool = False) -> np.ndarray:
    h, w = a.shape
    out = np.full((h, w), fill, dtype=a.dtype)
    sy0, sy1 = max(0, -dy), h - max(0, dy)
    sx0, sx1 = max(0, -dx), w - max(0, dx)
    if sy1 > sy0 and sx1 > sx0:
        out[sy0 + dy:sy1 + dy, sx0 + dx:sx1 + dx] = a[sy0:sy1, sx0:sx1]
    return out


def _disk_offsets(radius: int) -> list:
    r = int(radius)
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if dy * dy + dx * dx <= r * r + 1e-9]


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    """Binary dilation with a disk structuring element (no scipy)."""
    if radius <= 0 or not mask.any():
        return mask.copy()
    out = mask.copy()
    for dy, dx in _disk_offsets(radius):
        if dy == 0 and dx == 0:
            continue
        out |= _shift2d(mask, dy, dx, fill=False)
    return out


def erode(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0 or not mask.any():
        return mask.copy()
    return ~dilate(~mask, radius)


def close_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """Morphological closing; bridges the 1 px gaps of a face-sampled surface."""
    if radius <= 0 or not mask.any():
        return mask.copy()
    return erode(dilate(mask, radius), radius)


def fill_rows(mask: np.ndarray) -> np.ndarray:
    """Row-wise convex closure: between the first and last hit of each row.

    A convex UXO silhouette is a compact footprint; a point/face-sampled
    surface projects to a dotted one.  Filling each row keeps the extreme
    boundary of the sampled projection while removing interior holes.
    """
    if not mask.any():
        return mask.copy()
    h, w = mask.shape
    has = mask.any(axis=1)
    first = mask.argmax(axis=1)
    last = w - 1 - mask[:, ::-1].argmax(axis=1)
    cols = np.arange(w)[None, :]
    band = (cols >= first[:, None]) & (cols <= last[:, None])
    return band & has[:, None]


def fill_cols(mask: np.ndarray) -> np.ndarray:
    """Column-wise (per-beam) closure: between the first and last hit of each beam.

    The sonar image is (n_samples rows, n_beams cols) and range runs down a
    column, so the occupied interval of one beam is a contiguous range interval
    for any convex body.  Filling each column therefore reconstructs the
    *shadow* of the sampled surface without inventing extent along range, which
    is exactly the quantity a candidate box needs.
    """
    if not mask.any():
        return mask.copy()
    h, w = mask.shape
    has = mask.any(axis=0)
    first = mask.argmax(axis=0)
    last = h - 1 - mask[::-1, :].argmax(axis=0)
    rows = np.arange(h)[:, None]
    band = (rows >= first[None, :]) & (rows <= last[None, :])
    return band & has[None, :]


def convex_hull_2d(pts: np.ndarray) -> np.ndarray:
    """Andrew monotone chain; returns hull vertices in CCW order (no scipy)."""
    p = np.asarray(pts, dtype=np.float64)
    if p.shape[0] < 3:
        return p.copy()
    order = np.lexsort((p[:, 1], p[:, 0]))
    p = p[order]
    keep = np.ones(len(p), dtype=bool)
    keep[1:] = np.any(np.diff(p, axis=0) != 0.0, axis=1)
    p = p[keep]
    if len(p) < 3:
        return p.copy()

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for q in p:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0.0:
            lower.pop()
        lower.append(q)
    upper = []
    for q in p[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0.0:
            upper.pop()
        upper.append(q)
    return np.asarray(lower[:-1] + upper[:-1], dtype=np.float64)


def hull_area(hull: np.ndarray) -> float:
    if len(hull) < 3:
        return 0.0
    x, y = hull[:, 0], hull[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


# --------------------------------------------------------------------------
# rec_meta: the pixel grid
# --------------------------------------------------------------------------

@dataclass
class RecMeta:
    n_beams: int = 128
    n_samples: int = 780
    window_start_m: float = FALLBACK_REC_META["window_start_m"]
    window_length_m: float = FALLBACK_REC_META["window_length_m"]
    fov_deg: float = FOV_DEG
    recording: str | None = None
    frame: int | None = None
    source: str = "fallback"
    geometry_crosscheck: dict | None = None

    @property
    def deg_per_beam(self) -> float:
        return self.fov_deg / float(self.n_beams)

    @property
    def row_m(self) -> float:
        """Metres per row (0.002983 m for both 780/2.3264 and 441/1.3156)."""
        return self.window_length_m / float(self.n_samples)

    @property
    def beam_center(self) -> float:
        return (self.n_beams - 1) / 2.0

    def as_dict(self) -> dict:
        return {
            "recording": self.recording,
            "frame": self.frame,
            "n_beams": int(self.n_beams),
            "n_samples": int(self.n_samples),
            "image_shape_row_col": [int(self.n_samples), int(self.n_beams)],
            "fov_deg": _r(self.fov_deg, 6),
            "deg_per_beam": _r(self.deg_per_beam, 6),
            "beam_center_index": _r(self.beam_center, 6),
            "window_start_m": _r(self.window_start_m, 6),
            "window_length_m": _r(self.window_length_m, 6),
            "row_m": _r(self.row_m, 8),
            "source": self.source,
            "geometry_crosscheck": self.geometry_crosscheck,
        }


def _geometry_header(recording: str | None):
    """Header constants from engine/geometry.py (T-GEOM).  None when unavailable."""
    if not recording:
        return None
    try:
        import importlib
        if str(REPO / "engine") not in sys.path:
            sys.path.insert(0, str(REPO / "engine"))
        geom = importlib.import_module("geometry")
        h = geom.header_of(recording)
        return {
            "n_beams": int(h["NumRawBeams"]),
            "n_samples": int(h["SamplesPerBeam"]),
            "window_start_m": float(h["WindowStart"]),
            "window_length_m": float(h["WindowLength"]),
        }
    except Exception:
        return None


def _rec_meta_from_geometry(recording: str | None, frame: int | None):
    """Try engine/geometry.py (owned by T-GEOM).  Absent/incomplete -> None."""
    h = _geometry_header(recording)
    if not h or not (h["n_samples"] > 0 and h["window_length_m"] > 0):
        return None
    return RecMeta(n_beams=h["n_beams"], n_samples=h["n_samples"],
                   window_start_m=h["window_start_m"],
                   window_length_m=h["window_length_m"],
                   recording=recording, frame=frame, source="engine.geometry")


def _rec_meta_from_csv(recording: str, frame: int | None):
    """Read <recording>/aris_frame_meta.csv (+ aris_file_meta.yaml).  Read-only."""
    class_dir = RECORDING_TO_CLASS_DIR.get(recording)
    if class_dir is None:
        return None
    root = RAW_ROOT / class_dir / recording
    csv_path = root / "aris_frame_meta.csv"
    if not csv_path.exists():
        return None
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            return None
        row = rows[0]
        if frame is not None:
            for cand in rows:
                if int(float(cand["FrameIndex"])) == int(frame):
                    row = cand
                    break
        n_samples = int(float(row.get("SamplesPerBeam") or 0))
        ws = float(row["WindowStart"])
        wl = float(row["WindowLength"])
        n_beams = 0
        yml = root / "aris_file_meta.yaml"
        if yml.exists():
            txt = yml.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^NumRawBeams:\s*(\d+)", txt, re.M)
            if m:
                n_beams = int(m.group(1))
        if n_beams <= 0:
            n_beams = FALLBACK_REC_META["n_beams"]
        if n_samples <= 0:
            n_samples = FALLBACK_REC_META["n_samples"]
        if not (wl > 0):
            return None
        return RecMeta(n_beams=n_beams, n_samples=n_samples, window_start_m=ws,
                       window_length_m=wl, recording=recording, frame=frame,
                       source="aris_frame_meta.csv")
    except Exception:
        return None


def resolve_rec_meta(recording: str | None = None, frame: int | None = None) -> RecMeta:
    """Grid for the projection, with a cross-check against engine/geometry.py.

    Order: per-frame ``aris_frame_meta.csv`` (the only per-frame source of
    WindowStart/WindowLength) -> ``engine.geometry.header_of`` (audited header)
    -> BRIEF section 1 constants.  Whichever is used, the result is compared to
    geometry's header and the comparison is kept as ``geometry_crosscheck`` so
    the two modules cannot silently disagree about the pixel grid.
    """
    meta = None
    if recording:
        meta = _rec_meta_from_csv(recording, frame)
    if meta is None:
        meta = _rec_meta_from_geometry(recording, frame)
    if meta is None:
        fb = dict(FALLBACK_REC_META)
        meta = RecMeta(n_beams=fb["n_beams"], n_samples=fb["n_samples"],
                       window_start_m=fb["window_start_m"],
                       window_length_m=fb["window_length_m"],
                       recording=fb["recording"] if recording is None else recording,
                       frame=fb["frame"] if frame is None else frame,
                       source="BRIEF_section_1_fallback")
    gh = _geometry_header(recording or meta.recording)
    if gh is None:
        meta.geometry_crosscheck = {"status": "unavailable"}
    else:
        d_ws = abs(gh["window_start_m"] - float(meta.window_start_m))
        d_wl = abs(gh["window_length_m"] - float(meta.window_length_m))
        ok = (gh["n_beams"] == int(meta.n_beams)
              and gh["n_samples"] == int(meta.n_samples)
              and d_ws <= 1e-3 and d_wl <= 1e-3)
        meta.geometry_crosscheck = {
            "status": "agree" if ok else "differ",
            "geometry_header": gh,
            "delta_window_start_m": _r(d_ws, 6),
            "delta_window_length_m": _r(d_wl, 6),
        }
    return meta


def _coerce_meta(rec_meta) -> RecMeta:
    if isinstance(rec_meta, RecMeta):
        return rec_meta
    if isinstance(rec_meta, dict):
        d = rec_meta
        img = d.get("image_shape_row_col") or []
        return RecMeta(
            n_beams=int(d.get("n_beams") or (img[1] if len(img) > 1 else 128)),
            n_samples=int(d.get("n_samples") or (img[0] if img else 780)),
            window_start_m=float(d.get("window_start_m", FALLBACK_REC_META["window_start_m"])),
            window_length_m=float(d.get("window_length_m", FALLBACK_REC_META["window_length_m"])),
            fov_deg=float(d.get("fov_deg", FOV_DEG)),
            recording=d.get("recording"), frame=d.get("frame"),
            source=str(d.get("source", "dict")),
        )
    raise TypeError(f"rec_meta must be RecMeta or dict, got {type(rec_meta)!r}")


# --------------------------------------------------------------------------
# OBJ loading + decimation
# --------------------------------------------------------------------------

def _parse_obj(path: Path):
    """Streaming OBJ parse.  Vertices keep xyz only (Metashape appends rgb)."""
    vs: list = []
    fs: list = []
    n_v = n_f = n_poly = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                p = line.split()
                vs.append((float(p[1]), float(p[2]), float(p[3])))
                n_v += 1
            elif line.startswith("f "):
                toks = line.split()[1:]
                idx = []
                for t in toks:
                    i = int(t.split("/")[0])
                    idx.append(i - 1 if i > 0 else len(vs) + i)
                n_f += 1
                if len(idx) == 3:
                    fs.append(idx)
                elif len(idx) > 3:                      # fan triangulate
                    n_poly += 1
                    for k in range(1, len(idx) - 1):
                        fs.append((idx[0], idx[k], idx[k + 1]))
    V = np.asarray(vs, dtype=np.float64)
    F = np.asarray(fs, dtype=np.int64)
    stats = {"n_vertex_lines": n_v, "n_face_lines": n_f,
             "n_polygon_faces_fan_split": n_poly, "n_triangles": int(F.shape[0])}
    if V.ndim != 2 or V.shape[1] != 3 or F.ndim != 2 or F.shape[1] != 3:
        raise ValueError(f"malformed OBJ: {path}")
    if F.min() < 0 or F.max() >= len(V):
        raise ValueError(f"OBJ face index out of range: {path}")
    return V, F, stats


def _canonical_frame(V: np.ndarray):
    """PCA frame: origin = raw AABB centre, +x = major axis, right-handed."""
    lo, hi = V.min(axis=0), V.max(axis=0)
    center = 0.5 * (lo + hi)
    X = V - center
    cov = (X.T @ X) / max(len(X) - 1, 1)
    w, E = np.linalg.eigh(cov)
    E = E[:, np.argsort(w)[::-1]]
    for k in range(3):                                   # deterministic signs
        col = E[:, k].copy()
        j = int(np.argmax(np.abs(col)))
        if col[j] < 0:
            E[:, k] = -col
    if np.linalg.det(E) < 0:                             # keep right-handed
        E[:, 2] = -E[:, 2]
    P = X @ E
    ext = P.max(axis=0) - P.min(axis=0)
    return P, ext, E, center


def _voxel_faces(P: np.ndarray, F: np.ndarray, scale: float, max_points: int):
    """One representative triangle per occupied voxel of face centroids.

    The cell count is the largest grid that keeps occupied cells <=
    max_points - 8 (8 reserved for the injected raw extremes).  Faces are
    selected by proximity of their centroid to the cell's centroid mean, ties
    broken by face index, so the result is bit-stable.
    """
    Pq = P * scale
    C = Pq[F].mean(axis=1)
    lo = Pq.min(axis=0)
    length = float((Pq.max(axis=0) - lo).max())
    budget = max_points - 8

    def cells(n: int) -> np.ndarray:
        h = length / n
        ij = np.floor((C - lo) / h).astype(np.int64)
        np.clip(ij, 0, n - 1, out=ij)
        return (ij[:, 0] * n + ij[:, 1]) * n + ij[:, 2]

    best_n, best_cells = 4, cells(4)
    lo_n, hi_n = 4, 256
    while lo_n <= hi_n:                                  # monotone in n
        mid = (lo_n + hi_n) // 2
        c = cells(mid)
        if np.unique(c).size <= budget:
            best_n, best_cells = mid, c
            lo_n = mid + 1
        else:
            hi_n = mid - 1
    keys = best_cells
    order = np.argsort(keys, kind="stable")
    ks = keys[order]
    starts = np.flatnonzero(np.r_[True, ks[1:] != ks[:-1]])
    ends = np.r_[starts[1:], len(ks)]

    rep = np.empty(len(starts), dtype=np.int64)
    for i, (s, e) in enumerate(zip(starts, ends)):
        idxs = order[s:e]
        c = C[idxs]
        d = ((c - c.mean(axis=0)) ** 2).sum(axis=1)
        j = int(np.lexsort((idxs, d))[0])          # nearest to the cell mean,
        rep[i] = int(idxs[j])                      # ties -> lowest face index

    sel = np.sort(rep)                                   # canonical order
    return sel, C, Pq, best_n


def _extreme_points(Pq: np.ndarray) -> np.ndarray:
    """The 6 per-axis extremes of the raw cloud (extent guarantee)."""
    out = []
    for k in range(3):
        out.append(Pq[int(np.argmin(Pq[:, k]))])
        out.append(Pq[int(np.argmax(Pq[:, k]))])
    return np.asarray(out, dtype=np.float64)


@dataclass
class Mesh:
    """Downsampled UXO mesh in the canonical frame, metres."""

    category: str
    model: str
    obj_path: str
    sha256_obj: str
    nominal_length_m: float
    nominal_diameter_m: float | None
    vertices: np.ndarray            # (U,3) decimated unique vertices, metres
    faces: np.ndarray               # (F,3) indices into vertices
    points: np.ndarray              # (K,3) representative surface points, <= MAX_POINTS
    extent_m: np.ndarray            # (3,) long, mid, minor (metres)
    provenance: dict = field(default_factory=dict)

    def summary(self) -> dict:
        p = self.provenance
        return {
            "model": self.model,
            "category": self.category,
            "obj_path": self.obj_path,
            "sha256_obj": self.sha256_obj,
            "nominal_length_m": _r(self.nominal_length_m, 6),
            "nominal_diameter_m": (None if self.nominal_diameter_m is None
                                   else _r(self.nominal_diameter_m, 6)),
            "extent_m": [_r(v, 6) for v in self.extent_m],
            "extent_long_m": _r(self.extent_m[0], 6),
            "extent_transverse_m": [_r(self.extent_m[1], 6), _r(self.extent_m[2], 6)],
            "raw": {
                "n_vertices": p.get("n_raw_vertices"),
                "n_faces": p.get("n_raw_faces"),
                "n_vertex_lines": p.get("n_vertex_lines"),
                "n_face_lines": p.get("n_face_lines"),
                "extent_m": p.get("raw_extent_m"),
            },
            "decimated": {
                "n_points": int(self.points.shape[0]),
                "n_faces": int(self.faces.shape[0]),
                "n_vertices": int(self.vertices.shape[0]),
                "voxel_grid_n": p.get("voxel_grid_n"),
                "voxel_size_m": p.get("voxel_size_m"),
                "sha256_points": p.get("sha256_points"),
                "sha256_faces": p.get("sha256_faces"),
                "extent_m": p.get("decimated_extent_m"),
                "extent_preserved": p.get("extent_preserved"),
            },
            "scale_m_per_obj_unit": _r(p.get("scale_m_per_obj_unit", 0.0), 8),
            "assumption": ASSUMPTION,
            "pose_convention": POSE_CONVENTION,
            "uniqueness": False,
            "engine_version": ENGINE_VERSION,
        }


def _nominal_from_registration(model: str) -> dict:
    try:
        reg = json.loads(REGISTRATION_JSON.read_text(encoding="utf-8"))
        for m in reg.get("models", []):
            if m.get("model") == model:
                return {
                    "nominal_length_m": m.get("nominal_length_m"),
                    "nominal_diameter_m": m.get("nominal_diameter_m"),
                    "registration_vertices": m.get("vertices"),
                    "registration_pca_extent_obj_units": m.get("pca_extent_obj_units"),
                    "registration_sha256": m.get("sha256"),
                    "registration_status": reg.get("status"),
                    "mesh_to_target": m.get("mesh_to_target"),
                }
    except Exception:
        pass
    return {}


def load_mesh(category: str, *, max_points: int = MAX_POINTS) -> Mesh:
    """Load, canonicalise, scale and decimate one UXO OBJ.

    ``category`` accepts a manifest value (``100lbs_aircraft_bomb``) or a bare
    model name (``100lbs``).  Scale is uniform: long-axis extent -> nominal
    length (registration ``length_only_candidate_scale`` convention).  The
    registration's ``mesh_to_target`` is HOLD and is NOT used.
    """
    model = CATEGORY_TO_MODEL.get(category, category)
    cat = MODEL_TO_CATEGORY.get(model, category)
    if model not in MODEL_TO_CATEGORY:
        raise KeyError(f"unknown category/model {category!r}; known: {sorted(CATEGORY_TO_MODEL)}")
    path = MODEL_DIR / f"{model}.obj"
    if not path.exists():
        raise FileNotFoundError(path)

    nom = _nominal_from_registration(model)
    nominal_length = nom.get("nominal_length_m")
    if nominal_length is None:
        raise ValueError(
            f"{model}: no nominal length in mesh-registration.json; pass an explicit "
            "length (artillery_shell has no registered nominal size)")

    V, F, obj_stats = _parse_obj(path)
    P, ext_raw, E, center = _canonical_frame(V)
    scale = float(nominal_length) / float(ext_raw[0])

    sel, C, Pq, grid_n = _voxel_faces(P, F, scale, max_points)
    pts = np.vstack([C[sel], _extreme_points(Pq)])
    if pts.shape[0] > max_points:
        pts = pts[:max_points]

    faces_dec = F[sel]
    used, inv = np.unique(faces_dec.reshape(-1), return_inverse=True)
    verts = Pq[used]
    faces_remap = inv.reshape(-1, 3).astype(np.int64)

    ext_dec = pts.max(axis=0) - pts.min(axis=0)
    ext_dec_faces = verts.max(axis=0) - verts.min(axis=0)
    ext_raw_m = ext_raw * scale
    preserved = bool(np.all(np.abs(ext_dec - ext_raw_m) <= 1e-9 * np.maximum(1.0, np.abs(ext_raw_m))))
    preserved_faces = bool(np.all(np.abs(ext_dec_faces - ext_raw_m) <= 0.02 * np.maximum(1.0, np.abs(ext_raw_m))))

    prov = {
        "n_raw_vertices": int(V.shape[0]),
        "n_raw_faces": int(F.shape[0]),
        "n_vertex_lines": obj_stats["n_vertex_lines"],
        "n_face_lines": obj_stats["n_face_lines"],
        "n_polygon_faces_fan_split": obj_stats["n_polygon_faces_fan_split"],
        "raw_extent_m": [_r(v, 6) for v in ext_raw_m],
        "raw_extent_obj_units": [_r(v, 6) for v in ext_raw],
        "pca_axes_obj_frame": [[_r(v, 6) for v in E[:, k]] for k in range(3)],
        "pca_center_obj_frame": [_r(v, 6) for v in center],
        "scale_m_per_obj_unit": float(scale),
        "decimated_extent_m": [_r(v, 6) for v in ext_dec],
        "decimated_face_extent_m": [_r(v, 6) for v in ext_dec_faces],
        "extent_preserved": preserved,
        "extent_preserved_faces_2pct": preserved_faces,
        "voxel_grid_n": int(grid_n),
        "voxel_size_m": _r(float((ext_raw_m.max()) / grid_n), 6),
        "sha256_points": _sha256_array(pts, "<f8"),
        "sha256_faces": _sha256_array(faces_remap, "<i8"),
        "nominal_source": "DataSet/sonar_model_registration_consistency/mesh-registration.json",
        "registration_match": nom,
        "mesh_to_target_used": False,
        "downsample": "one triangle per occupied voxel of face centroids + 6 raw axis extremes",
        "units": "metres, canonical frame, long axis = +x",
    }
    return Mesh(category=cat, model=model, obj_path=str(path),
                sha256_obj=_sha256_file(path),
                nominal_length_m=float(nominal_length),
                nominal_diameter_m=(None if nom.get("nominal_diameter_m") is None
                                    else float(nom["nominal_diameter_m"])),
                vertices=verts, faces=faces_remap, points=pts,
                extent_m=ext_dec, provenance=prov)


# --------------------------------------------------------------------------
# projection
# --------------------------------------------------------------------------

def los_frame(az_deg: float):
    """Unit vectors of the line-of-sight frame in sonar coordinates."""
    az = math.radians(float(az_deg))
    fwd = np.array([math.sin(az), 0.0, math.cos(az)])      # sonar -> object
    right = np.array([math.cos(az), 0.0, -math.sin(az)])   # starboard, horizontal
    down = np.array([0.0, 1.0, 0.0])
    return fwd, right, down


def pose_rotation(az_deg: float, yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    """Model(canonical) -> sonar rotation.  See POSE_CONVENTION."""
    fwd, right, down = los_frame(az_deg)
    B = np.column_stack([fwd, down, -right])               # model x,y,z -> sonar
    R = (_rot_axis(right, pitch_deg) @ _rot_axis(down, yaw_deg)
         @ B @ _rot_axis(np.array([1.0, 0.0, 0.0]), roll_deg))
    return R


def project_points(points_m: np.ndarray, range_m: float, az_deg: float,
                   R: np.ndarray, meta: RecMeta) -> dict:
    """Perspective projection of canonical-frame points to (beam, row)."""
    fwd, _, _ = los_frame(az_deg)
    center = float(range_m) * fwd
    p = center[None, :] + points_m @ R.T
    z = p[:, 2]
    az_p = np.degrees(np.arctan2(p[:, 0], np.maximum(z, 1e-9)))
    rng = np.sqrt((p * p).sum(axis=1))
    beam = meta.beam_center + az_p / meta.deg_per_beam
    row = (rng - meta.window_start_m) / meta.row_m
    return {
        "beam": beam, "row": row, "az_deg": az_p, "range_m": rng,
        "behind_sonar": bool((z <= 1e-9).any()),
        "p": p,
    }


def full_cloud(category: str) -> np.ndarray:
    """Every OBJ vertex, canonicalised and scaled exactly like ``load_mesh``.

    Used only by ``--check`` to measure how much the 3000-point decimation
    moves the projected footprint.  Not part of the runtime path.
    """
    model = CATEGORY_TO_MODEL.get(category, category)
    nom = _nominal_from_registration(model)
    V, _F, _st = _parse_obj(MODEL_DIR / f"{model}.obj")
    P, ext_raw, _E, _c = _canonical_frame(V)
    return P * (float(nom["nominal_length_m"]) / float(ext_raw[0]))


def cloud_spans(points_m: np.ndarray, range_m: float, az_deg: float,
                R: np.ndarray, meta: RecMeta) -> dict:
    """Continuous (beam_min, beam_max, row_min, row_max) of a point cloud."""
    pr = project_points(points_m, range_m, az_deg, R, meta)
    b, r = pr["beam"], pr["row"]
    return {
        "beam_min": float(b.min()), "beam_max": float(b.max()),
        "row_min": float(r.min()), "row_max": float(r.max()),
    }


def sphere_cloud(diameter_m: float, n: int = 20000) -> np.ndarray:
    """Fibonacci sphere of ``diameter_m`` at the origin (a projection unit test).

    A 0.2 m-diameter body at 1.26 m must span ~0.2/row_m rows.  Comparing this
    against a real UXO is what separates "projection is wrong" from "a long rod
    genuinely spans more rows at broadside, because its ends are farther away".
    """
    i = np.arange(n, dtype=np.float64) + 0.5
    phi = np.arccos(1.0 - 2.0 * i / n)
    theta = math.pi * (1.0 + 5.0 ** 0.5) * i
    rad = 0.5 * float(diameter_m)
    return np.column_stack([rad * np.sin(phi) * np.cos(theta),
                            rad * np.sin(phi) * np.sin(theta),
                            rad * np.cos(phi)])


def _padded_canvas(beam: np.ndarray, row: np.ndarray, meta: RecMeta):
    span_c = float(np.max(np.abs(beam - meta.beam_center))) + 1.0
    span_r = float(np.max(np.abs(row - meta.n_samples / 2.0))) + 1.0
    pad_c = int(math.ceil(span_c)) + 3
    pad_r = int(math.ceil(span_r)) + 3
    return (int(meta.n_samples) + 2 * pad_r, int(meta.n_beams) + 2 * pad_c, pad_r, pad_c)


def _splat(beam: np.ndarray, row: np.ndarray, shape, off_r: int, off_c: int) -> np.ndarray:
    h, w = shape
    m = np.zeros((h, w), dtype=bool)
    cc = np.rint(beam).astype(np.int64) + off_c
    rr = np.rint(row).astype(np.int64) + off_r
    ok = (cc >= 0) & (cc < w) & (rr >= 0) & (rr < h)
    m[rr[ok], cc[ok]] = True
    return m


def rasterize_triangles(tris_2d: np.ndarray, shape, off_r: int = 0, off_c: int = 0,
                        min_half_px: float = 0.75) -> np.ndarray:
    """Fill triangles in (col=beam, row=row) pixel space.  Pure numpy.

    Each triangle is scanned over its own integer bbox with a barycentric test.
    ``min_half_px`` pads degenerate (sub-pixel) triangles, which is what a
    ~1 cm photogrammetry face is at 1.3 m with 3 mm pixels.
    """
    h, w = shape
    m = np.zeros((h, w), dtype=bool)
    for tri in tris_2d:
        x = tri[:, 0] + off_c
        y = tri[:, 1] + off_r
        xmin = int(math.floor(x.min() - min_half_px)); xmax = int(math.ceil(x.max() + min_half_px))
        ymin = int(math.floor(y.min() - min_half_px)); ymax = int(math.ceil(y.max() + min_half_px))
        xmin = max(xmin, 0); ymin = max(ymin, 0); xmax = min(xmax, w - 1); ymax = min(ymax, h - 1)
        if xmax < xmin or ymax < ymin:
            continue
        gx, gy = np.meshgrid(np.arange(xmin, xmax + 1) + 0.0,
                             np.arange(ymin, ymax + 1) + 0.0)
        d = ((x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0]))
        if abs(d) < 1e-12:
            continue
        a = ((x[1] - gx) * (y[2] - gy) - (x[2] - gx) * (y[1] - gy)) / d
        b = ((x[2] - gx) * (y[0] - gy) - (x[0] - gx) * (y[2] - gy)) / d
        c = 1.0 - a - b
        hit = (a >= -0.05) & (b >= -0.05) & (c >= -0.05)
        if hit.any():
            m[ymin:ymax + 1, xmin:xmax + 1] |= hit
    return m


def _mask_from_points(beam, row, meta: RecMeta, radius_px: int, shape=None):
    h, w, off_r, off_c = _padded_canvas(beam, row, meta) if shape is None else shape
    raw = _splat(beam, row, (h, w), off_r, off_c)
    return raw, (h, w, off_r, off_c)


def _finish_mask(padded: np.ndarray, meta: RecMeta, off: tuple) -> dict:
    """Close/fill, then crop to the real grid; report spans + in-frame fraction."""
    h, w, off_r, off_c = off
    closed = fill_rows(close_mask(padded, 1))
    core = closed[off_r:off_r + int(meta.n_samples), off_c:off_c + int(meta.n_beams)]
    total = int(closed.sum())
    inside = int(core.sum())
    rows_any = np.flatnonzero(core.any(axis=1))
    cols_any = np.flatnonzero(core.any(axis=0))
    if rows_any.size and cols_any.size:
        y0, y1 = int(rows_any[0]), int(rows_any[-1]) + 1
        x0, x1 = int(cols_any[0]), int(cols_any[-1]) + 1
        box = [x0, y0, x1, y1]
        b_span = float(x1 - x0)
        r_span = float(y1 - y0)
    else:
        box, b_span, r_span = None, 0.0, 0.0

    # unclipped box, from the padded canvas
    rows_all = np.flatnonzero(closed.any(axis=1))
    cols_all = np.flatnonzero(closed.any(axis=0))
    if rows_all.size and cols_all.size:
        box_un = [int(cols_all[0]) - off_c, int(rows_all[0]) - off_r,
                  int(cols_all[-1]) + 1 - off_c, int(rows_all[-1]) + 1 - off_r]
    else:
        box_un = None
    return {
        "mask": core,
        "box_xyxy": box,
        "beam_span_px": b_span,
        "row_span_px": r_span,
        "predicted_area_px": inside,
        "visible_frac": (float(inside) / float(total)) if total else 0.0,
        "clipped": bool(total != inside),
        "box_xyxy_unclipped": box_un,
        "area_padded_px": total,
    }


def silhouette(mesh: Mesh, range_m: float, az_deg: float, yaw_deg: float,
               pitch_deg: float, roll_deg: float, rec_meta, *,
               raster: str = "shadow", radius_px: int = 1, meta_override=None) -> dict:
    """Silhouette of ``mesh`` on the (n_samples, n_beams) grid.

    Returns (BRIEF section 4 keys first):
      mask      np.bool_ (n_samples, n_beams)
      box_xyxy  [x0,y0,x1,y1] pixel edges, None when nothing lands in frame
      beam_span_px / row_span_px   inclusive pixel extent of the mask
      predicted_area_px            in-frame mask pixel count
      visible_frac                 in-frame area / total projected area
    plus diagnostics: clipped, box_xyxy_unclipped, continuous extents,
    pose/assumption fields (uniqueness is always False).
    """
    meta = _coerce_meta(rec_meta) if meta_override is None else meta_override
    R = pose_rotation(az_deg, yaw_deg, pitch_deg, roll_deg)
    pr = project_points(mesh.points, range_m, az_deg, R, meta)
    shape = _padded_canvas(pr["beam"], pr["row"], meta)
    h, w, off_r, off_c = shape

    if raster == "points":
        padded = _splat(pr["beam"], pr["row"], (h, w), off_r, off_c)
    elif raster == "shadow":
        # point-splat the decimated surface, then close it along range per beam
        padded = close_mask(fill_cols(_splat(pr["beam"], pr["row"], (h, w), off_r, off_c)), 1)
    elif raster == "triangles":
        tri_pts = mesh.vertices[mesh.faces]                   # (F,3,3)
        tri = np.empty((tri_pts.shape[0] * 3, 3))
        fwd, _, _ = los_frame(az_deg)
        center = float(range_m) * fwd
        flat = tri_pts.reshape(-1, 3) @ R.T + center[None, :]
        az_f = np.degrees(np.arctan2(flat[:, 0], np.maximum(flat[:, 2], 1e-9)))
        rng_f = np.sqrt((flat * flat).sum(axis=1))
        tri = np.column_stack([meta.beam_center + az_f / meta.deg_per_beam,
                               (rng_f - meta.window_start_m) / meta.row_m]).reshape(-1, 3, 2)
        padded = rasterize_triangles(tri, (h, w), off_r, off_c)
    else:
        raise ValueError(f"raster must be 'points', 'shadow' or 'triangles', got {raster!r}")

    if radius_px > 1 and raster == "points":
        padded = dilate(padded, radius_px - 1)

    out = _finish_mask(padded, meta, shape)
    span_b_cont = float(pr["beam"].max() - pr["beam"].min())
    span_r_cont = float(pr["row"].max() - pr["row"].min())
    out.update({
        "range_m": _r(range_m, 6),
        "az_deg": _r(az_deg, 6),
        "pose_deg": {"yaw_deg": _r(yaw_deg, 4), "pitch_deg": _r(pitch_deg, 4),
                     "roll_deg": _r(roll_deg, 4)},
        "beam_span_cont_px": _r(span_b_cont, 4),
        "row_span_cont_px": _r(span_r_cont, 4),
        "range_min_m": _r(pr["range_m"].min(), 6),
        "range_max_m": _r(pr["range_m"].max(), 6),
        "n_points_used": int(mesh.points.shape[0]),
        "raster": raster,
        "behind_sonar": pr["behind_sonar"],
        "model": mesh.model,
        "category": mesh.category,
        "assumption": ASSUMPTION,
        "pose_convention": POSE_CONVENTION,
        "uniqueness": False,
        "engine_version": ENGINE_VERSION,
        "mask_sha256": hashlib.sha256(np.ascontiguousarray(out["mask"]).tobytes()).hexdigest(),
        "grid": meta.as_dict(),
    })
    return out


def _hull_entry(mesh: Mesh, range_m: float, az_deg: float, yaw_deg: float,
                pitch_deg: float, roll_deg: float, meta: RecMeta) -> dict:
    """Fast sweep entry: convex hull of the projected points (no raster)."""
    R = pose_rotation(az_deg, yaw_deg, pitch_deg, roll_deg)
    pr = project_points(mesh.points, range_m, az_deg, R, meta)
    hb, hr = pr["beam"], pr["row"]
    hull = convex_hull_2d(np.column_stack([hb, hr]))
    area = hull_area(hull)
    if len(hull):
        x0 = int(math.floor(hull[:, 0].min())); x1 = int(math.ceil(hull[:, 0].max())) + 1
        y0 = int(math.floor(hull[:, 1].min())); y1 = int(math.ceil(hull[:, 1].max())) + 1
        box = [x0, y0, x1, y1]
    else:
        box = None
    in_frame = (box is not None and box[2] > 0 and box[0] < meta.n_beams
                and box[3] > 0 and box[1] < meta.n_samples)
    return {
        "yaw_deg": _r(yaw_deg, 4),
        "pitch_deg": _r(pitch_deg, 4),
        "roll_deg": _r(roll_deg, 4),
        "beam_span_px": _r(hull[:, 0].max() - hull[:, 0].min() if len(hull) else 0.0, 4),
        "row_span_px": _r(hull[:, 1].max() - hull[:, 1].min() if len(hull) else 0.0, 4),
        "box_xyxy": box,
        "hull_area_px": _r(area, 2),
        "in_frame": bool(in_frame),
        "backend": "hull",
    }


def plausible_sweep(mesh: Mesh, range_m: float, az_deg: float, rec_meta,
                    n_yaw: int = 24, n_pitch: int = 6, n_roll: int = 6,
                    *, pitch_max_deg: float = 30.0, backend: str = "hull") -> list:
    """Sweep pose hypotheses and return one record per (yaw, pitch, roll).

    This is an enumeration of *possible* poses, not an estimate: the pipeline
    should take the union / envelope over the sweep, never a single entry.
    """
    meta = _coerce_meta(rec_meta)
    yaws = [360.0 * i / n_yaw for i in range(n_yaw)]
    if n_pitch <= 1:
        pitches = [0.0]
    else:
        pitches = list(np.linspace(-pitch_max_deg, pitch_max_deg, n_pitch))
    rolls = [360.0 * i / n_roll for i in range(n_roll)]

    out = []
    for y in yaws:
        for p in pitches:
            for rr in rolls:
                if backend == "hull":
                    out.append(_hull_entry(mesh, range_m, az_deg, y, p, rr, meta))
                else:
                    s = silhouette(mesh, range_m, az_deg, y, p, rr, meta, raster=backend)
                    out.append({
                        "yaw_deg": _r(y, 4), "pitch_deg": _r(p, 4), "roll_deg": _r(rr, 4),
                        "beam_span_px": _r(s["beam_span_px"], 4),
                        "row_span_px": _r(s["row_span_px"], 4),
                        "box_xyxy": s["box_xyxy"],
                        "area_px": int(s["predicted_area_px"]),
                        "in_frame": not s["clipped"],
                        "backend": backend,
                    })
    return out


def sweep_summary(sweep: list) -> dict:
    if not sweep:
        return {}
    bs = [e["beam_span_px"] for e in sweep]
    rs = [e["row_span_px"] for e in sweep]
    boxes = [e["box_xyxy"] for e in sweep if e["box_xyxy"]]
    env = None
    if boxes:
        env = [min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes)]
    big_b = max(sweep, key=lambda e: e["beam_span_px"])
    big_r = max(sweep, key=lambda e: e["row_span_px"])
    return {
        "n_poses": len(sweep),
        "beam_span_px_min": _r(min(bs), 4), "beam_span_px_max": _r(max(bs), 4),
        "row_span_px_min": _r(min(rs), 4), "row_span_px_max": _r(max(rs), 4),
        "envelope_box_xyxy": env,
        "widest_beam_pose": {k: big_b[k] for k in ("yaw_deg", "pitch_deg", "roll_deg")},
        "widest_row_pose": {k: big_r[k] for k in ("yaw_deg", "pitch_deg", "roll_deg")},
        "note": ("span range over pose hypotheses; use the envelope for candidate-box "
                 "limits, never a single pose"),
    }


# --------------------------------------------------------------------------
# JSON helpers
# --------------------------------------------------------------------------

def _public(d: dict, keys=None) -> dict:
    """Drop numpy arrays from a record so it can be serialised."""
    out = {}
    for k, v in d.items():
        if keys is not None and k not in keys:
            continue
        if isinstance(v, np.ndarray):
            continue
        if isinstance(v, (np.bool_, bool)):
            out[k] = bool(v)
        elif isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating,)):
            out[k] = _r(float(v), 6)
        else:
            out[k] = v
    return out


def write_json(path: Path, obj: dict) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# debug images (PIL, optional)
# --------------------------------------------------------------------------

def _render_overlay(mask: np.ndarray, box, path: Path, title: str):
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    h, w = mask.shape
    canvas = np.full((h, w, 3), 24, dtype=np.uint8)
    canvas[mask] = (60, 230, 120)
    if box:
        x0, y0, x1, y1 = box
        canvas[max(0, y0):max(0, y1), max(0, x0):max(0, x0 + 1)] = (255, 200, 0)
        canvas[max(0, y0):max(0, y1), max(0, x1 - 1):max(0, x1)] = (255, 200, 0)
        canvas[max(0, y0):max(0, y0 + 1), max(0, x0):max(0, x1)] = (255, 200, 0)
        canvas[max(0, y1 - 1):max(0, y1), max(0, x0):max(0, x1)] = (255, 200, 0)
    img = Image.fromarray(canvas).resize((w * 3, h * 3), Image.NEAREST)
    dr = ImageDraw.Draw(img)
    dr.text((4, 4), title, fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)

    # zoom: crop a padded window around the silhouette so the shape is readable
    if box:
        pad = 8
        x0, y0, x1, y1 = box
        cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
        cx1, cy1 = min(w, x1 + pad), min(h, y1 + pad)
        crop = canvas[cy0:cy1, cx0:cx1]
        if crop.size:
            zf = max(1, min(10, 900 // max(1, max(crop.shape[0], crop.shape[1]))))
            zi = Image.fromarray(crop).resize(
                (crop.shape[1] * zf, crop.shape[0] * zf), Image.NEAREST)
            ImageDraw.Draw(zi).text((3, 3), f"x{zf}  beam[{x0},{x1}) row[{y0},{y1})",
                                    fill=(255, 255, 255))
            zi.save(path.with_name(path.stem + "_zoom.png"))
    return path


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------

def _check_range_az() -> tuple:
    return 1.26, 10.0


def run_check(out_path: Path, image_dir: Path | None = None, n_yaw: int = 24,
              n_pitch: int = 6, n_roll: int = 6) -> dict:
    rng_m, az = _check_range_az()
    meta = resolve_rec_meta(FALLBACK_REC_META["recording"], FALLBACK_REC_META["frame"])
    models = []
    for cat in ("100lbs_aircraft_bomb", "incindiary_grenade", "mortar_shell"):
        mesh = load_mesh(cat)
        s_broad = silhouette(mesh, rng_m, az, 90.0, 0.0, 0.0, meta)
        s_end = silhouette(mesh, rng_m, az, 0.0, 0.0, 0.0, meta)
        sweep = plausible_sweep(mesh, rng_m, az, meta, n_yaw=n_yaw,
                               n_pitch=n_pitch, n_roll=n_roll)

        # how far does 95k -> 3k move the projected footprint?  (no raster:
        # pure point-cloud extremes, so this isolates the decimation error)
        got = []
        for yaw_ref in (90.0, 45.0, 0.0):
            R = pose_rotation(az, yaw_ref, 0.0, 0.0)
            full = cloud_spans(full_cloud(cat), rng_m, az, R, meta)
            dec = cloud_spans(mesh.points, rng_m, az, R, meta)
            got.append({
                "yaw_deg": yaw_ref,
                "full": {k: _r(v, 3) for k, v in full.items()},
                "decimated": {k: _r(v, 3) for k, v in dec.items()},
                "delta_px": {k: _r(dec[k] - full[k], 3) for k in full},
            })
        worst = max(abs(e["delta_px"][k]) for e in got for k in e["delta_px"])

        entry = {
            "category": cat,
            "mesh": mesh.summary(),
            "fixed_geometry": {"range_m": rng_m, "az_deg": az},
            "broadside": _public(s_broad),
            "end_on": _public(s_end),
            "sweep": {**_public(sweep_summary(sweep)), "entries": sweep},
            "decimation_footprint": {"cases": got, "max_abs_delta_px": _r(worst, 3)},
        }
        models.append(entry)
        if image_dir is not None:
            for tag, s in (("broad", s_broad), ("end", s_end)):
                _render_overlay(s["mask"], s["box_xyxy"],
                                image_dir / f"{mesh.model}_{tag}.png",
                                f"{mesh.model} r={rng_m} az={az} {tag} "
                                f"b={s['beam_span_px']:.0f} r={s['row_span_px']:.0f}")

    # ---- assertions -------------------------------------------------------
    checks = {}
    m100 = models[0]["mesh"]
    b100 = models[0]["broadside"]
    checks["extent_preserved_all"] = all(m["mesh"]["decimated"]["extent_preserved"] for m in models)
    checks["100lbs_broadside_beam_span_30_36"] = 30.0 <= b100["beam_span_px"] <= 36.0
    checks["100lbs_broadside_row_span_60_82"] = 60.0 <= b100["row_span_px"] <= 82.0
    checks["mask_nonempty_all"] = all(m["broadside"]["predicted_area_px"] > 10 for m in models)
    checks["no_uniqueness_claim"] = all(m["broadside"]["uniqueness"] is False for m in models)
    # decimation must not move the projected footprint by more than the pixel grid
    worst_dec = max(m["decimation_footprint"]["max_abs_delta_px"] for m in models)
    checks["decimation_footprint_le_1px"] = bool(worst_dec <= 1.0)

    # projection unit test on a bare 0.208 m sphere: an isotropic body at
    # r=1.26 m must span ~0.208 m along range (=~70 rows), no more.
    R_bs = pose_rotation(az, 90.0, 0.0, 0.0)
    sph = cloud_spans(sphere_cloud(0.208), rng_m, az, R_bs, meta)
    sph_rows = sph["row_max"] - sph["row_min"]
    sph_beams = sph["beam_max"] - sph["beam_min"]
    checks["sphere_0p208_row_span_64_72"] = bool(64.0 <= sph_rows <= 72.0)
    sphere_probe = {"diameter_m": 0.208, "row_span_px": _r(sph_rows, 3),
                    "beam_span_px": _r(sph_beams, 3),
                    "row_m": _r(meta.row_m, 8),
                    "expected_row_span": _r(0.208 / meta.row_m, 3),
                    "note": ("isotropic body: row span == diameter.  A 0.737 m rod at "
                             "broadside spans more (~80 rows) because its ends sit "
                             "0.37 m farther away, not because the projection is off.")}

    # determinism: recompute the 100lbs broadside mask and compare hashes
    h1 = models[0]["broadside"]["mask_sha256"]
    again = silhouette(load_mesh("100lbs_aircraft_bomb"), rng_m, az, 90.0, 0.0, 0.0, meta)
    checks["mask_reproducible"] = bool(again["mask_sha256"] == h1)

    out = {
        "schema": SCHEMA,
        "engine": "engine/mesh_prior.py",
        "engine_version": ENGINE_VERSION,
        "command": "python engine/mesh_prior.py --all --check",
        "rec_meta": meta.as_dict(),
        "pose_convention": POSE_CONVENTION,
        "assumption": ASSUMPTION,
        "uniqueness": False,
        "fov_deg": FOV_DEG,
        "downsample_cap_points": MAX_POINTS,
        "models": models,
        "checks": checks,
        "checks_all_pass": bool(all(checks.values())),
        "sphere_probe": sphere_probe,
        "notes": [
            "n_samples differs per recording: 780 for 100lbs_bomb/2023-09-20_171105, "
            "441 for 20lbs_incendiary/2023-09-21_120653 and 15cm_mortar/2023-09-21_100927",
            "beam_span_px / row_span_px are mask pixel extents (max-min+1); "
            "beam_span_cont_px / row_span_cont_px are the continuous projected extents",
            "pose is swept, never estimated; no acoustic shadow/multipath modelling",
        ],
    }
    sha = write_json(out_path, out)
    out["_json_sha256"] = sha
    return out


def _print_check(out: dict) -> None:
    rm = out["rec_meta"]
    print(f"[mesh_prior {ENGINE_VERSION}] rec_meta: {rm['recording']} frame={rm['frame']} "
          f"{rm['n_samples']}x{rm['n_beams']} row_m={rm['row_m']} src={rm['source']}")
    print(f"{'model':<14}{'ext_long':>9}{'ext_trans':>20}{'raw_v/f':>16}"
          f"{'pts/f':>12}{'b_span':>8}{'r_span':>8}{'area':>7}{'vis':>6}")
    for m in out["models"]:
        mesh = m["mesh"]
        b = m["broadside"]
        d = mesh["decimated"]
        print(f"{mesh['model']:<14}{mesh['extent_long_m']:>9.4f}"
              f"{mesh['extent_transverse_m'][0]:>10.4f}/{mesh['extent_transverse_m'][1]:<9.4f}"
              f"{mesh['raw']['n_vertices']:>7}/{mesh['raw']['n_faces']:<8}"
              f"{d['n_points']:>7}/{d['n_faces']:<5}"
              f"{b['beam_span_px']:>8.1f}{b['row_span_px']:>8.1f}"
              f"{b['predicted_area_px']:>7}{b['visible_frac']:>6.2f}")
        sw = m["sweep"]
        print(f"{'':14}sweep yaw[{sw['widest_beam_pose']['yaw_deg']:.0f}..] "
              f"beam_span {sw['beam_span_px_min']:.1f}..{sw['beam_span_px_max']:.1f} "
              f"row_span {sw['row_span_px_min']:.1f}..{sw['row_span_px_max']:.1f} "
              f"env={sw['envelope_box_xyxy']}")
    print("checks:", json.dumps(out["checks"], ensure_ascii=False))
    print("all_pass:", out["checks_all_pass"])


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _default_out(category: str | None) -> Path:
    if category is None:
        return OUT_DIR / "prior_check.json"
    model = CATEGORY_TO_MODEL.get(category, category)
    return OUT_DIR / f"prior_{model}.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="T-MESH 3D mesh silhouette prior")
    ap.add_argument("--category", help="manifest category or model name")
    ap.add_argument("--all", action="store_true", help="run all three categories")
    ap.add_argument("--range", dest="range_m", type=float, default=1.26)
    ap.add_argument("--az", dest="az_deg", type=float, default=10.0)
    ap.add_argument("--yaw", type=float, default=90.0)
    ap.add_argument("--pitch", type=float, default=0.0)
    ap.add_argument("--roll", type=float, default=0.0)
    ap.add_argument("--recording", default=None)
    ap.add_argument("--frame", type=int, default=None)
    ap.add_argument("--n-yaw", type=int, default=24)
    ap.add_argument("--n-pitch", type=int, default=6)
    ap.add_argument("--n-roll", type=int, default=6)
    ap.add_argument("--raster", default="shadow", choices=["shadow", "points", "triangles"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true", help="assert the BRIEF criteria")
    ap.add_argument("--images", default=None, help="dir for debug overlay PNGs (tmp only)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.all or args.check:
        image_dir = None
        if args.images:
            cand = Path(args.images)
            cand = (cand if cand.is_absolute() else (REPO / cand)).resolve()
            base = str(TMP_DIR).replace("\\", "/")
            inside = str(cand).replace("\\", "/") == base or \
                str(cand).replace("\\", "/").startswith(base + "/")
            if inside:
                image_dir = cand
            else:
                print(f"[mesh_prior] --images must live under tmp/mesh/; ignored", file=sys.stderr)
        out_path = Path(args.out) if args.out else _default_out(None)
        res = run_check(out_path, image_dir=image_dir, n_yaw=args.n_yaw,
                        n_pitch=args.n_pitch, n_roll=args.n_roll)
        if not args.quiet:
            _print_check(res)
            print(f"out: {out_path}  sha256={res['_json_sha256']}")
        return 0 if res["checks_all_pass"] else 1

    if not args.category:
        ap.error("--category or --all is required")
    mesh = load_mesh(args.category)
    rec_default = CATEGORY_DEFAULT_RECORDING.get(mesh.category)
    meta = resolve_rec_meta(args.recording or rec_default,
                            args.frame if args.frame is not None else None)
    s = silhouette(mesh, args.range_m, args.az_deg, args.yaw, args.pitch, args.roll,
                   meta, raster=args.raster)
    sweep = plausible_sweep(mesh, args.range_m, args.az_deg, meta,
                            n_yaw=args.n_yaw, n_pitch=args.n_pitch, n_roll=args.n_roll)
    rec = {
        "schema": SCHEMA,
        "engine": "engine/mesh_prior.py",
        "engine_version": ENGINE_VERSION,
        "command": ("python engine/mesh_prior.py --category "
                    f"{mesh.model} --range {args.range_m} --az {args.az_deg}"),
        "category": mesh.category,
        "mesh": mesh.summary(),
        "rec_meta": meta.as_dict(),
        "silhouette": _public(s),
        "sweep": {**_public(sweep_summary(sweep)),
                  "entries": sweep},
        "pose_convention": POSE_CONVENTION,
        "assumption": ASSUMPTION,
        "uniqueness": False,
    }
    out_path = Path(args.out) if args.out else _default_out(args.category)
    sha = write_json(out_path, rec)
    if not args.quiet:
        print(f"[{mesh.model}] extent_m={mesh.summary()['extent_m']} "
              f"points={mesh.points.shape[0]} faces={mesh.faces.shape[0]}")
        print(f"  range={args.range_m} az={args.az_deg} pose=({args.yaw},{args.pitch},{args.roll}) "
              f"beam_span={s['beam_span_px']} row_span={s['row_span_px']} "
              f"area={s['predicted_area_px']} visible={s['visible_frac']:.3f} "
              f"box={s['box_xyxy']}")
        print(f"  sweep: beam_span {sweep and min(e['beam_span_px'] for e in sweep):.1f}"
              f"..{max(e['beam_span_px'] for e in sweep):.1f} "
              f"row_span {min(e['row_span_px'] for e in sweep):.1f}"
              f"..{max(e['row_span_px'] for e in sweep):.1f}")
        print(f"out: {out_path}  sha256={sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
