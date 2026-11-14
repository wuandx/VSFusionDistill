"""Geometry of the ARIS fan image: what is exact, what is not.

Status: DEGRADED (see ``docs/geometry-echo.md`` and ``BRIEF.md`` §2.2).

Exact and usable
----------------
* ``row -> range``:  ``range_m = WindowStart + j * RES`` with
  ``RES = WindowLength / SamplesPerBeam`` (per recording, from ``aris_file_meta.yaml``).
* the set of frame numbers actually present in a recording (``Recording.frames``).
* the fan geometry in *beams*: 128 beams, `beam i` = pixel column i.

Not usable (and deliberately not implemented)
---------------------------------------------
* absolute range / azimuth / FOV / target pose: a single view gives one equation and
  two unknowns.  Radial thickness fixes only ``D / RES``; azimuth width fixes only
  ``2*atan(L/2r)/theta``, i.e. the degenerate product ``r * theta`` (see ``scale_relation``).
* **``gantry.csv`` is not a sonar-frame target position.**  Its (x,y) describe a circle
  (radius 1.21 m, z = -0.75 m) traversed ~1/3 turn, while the bright echo structure stays
  within a few tens of rows for 100 % of frames.  Using it as a range/bearing prediction
  predicts a 531-row sweep that is not observed.  ``FrameGeom.predict()`` therefore
  returns ``{"available": False, ...}`` on purpose; do not resurrect it.

``fov_deg`` has no measured value.  ``beam_angle_deg`` refuses to guess one; the only
defensible statement is the bound ``fov_bound()`` returns from observed beam widths.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import yaml

REPO = Path(__file__).resolve().parents[1]
RAW_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")

# --------------------------------------------------------------------------
# recording registry (BRIEF §1; only the three development recordings)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordingSpec:
    recording: str
    class_dir: str
    category: str                 # manifest value
    nominal_length_m: float
    nominal_diameter_m: float
    notes: str = ""


RECORDINGS: Dict[str, RecordingSpec] = {
    "2023-09-20_171105": RecordingSpec(
        "2023-09-20_171105", "100lbs_bomb", "100lbs_aircraft_bomb", 0.737, 0.208,
        "Trajectory: L to R (z: 750), Tilt -22 deg, roll 0, Min Transmit, 10dB"),
    "2023-09-21_120653": RecordingSpec(
        "2023-09-21_120653", "20lbs_incendiary", "incindiary_grenade", 0.442, 0.127,
        "Trajectory: L to R (z: 750), Tilt -22 deg, roll 0, Min Transmit, 15dB"),
    "2023-09-21_100927": RecordingSpec(
        "2023-09-21_100927", "15cm_mortar", "mortar_shell", 0.58, 0.12,
        "Trajectory: L to R (z: 750), Tilt -22 deg, roll 0, Min Transmit, 15dB"),
}

# audited header constants (verified against aris_file_meta.yaml, re-read at load time)
AUDITED_HEADERS = {
    "2023-09-20_171105": dict(NumRawBeams=128, SamplesPerBeam=780,
                              WindowStart=0.6949365, WindowLength=2.3263969),
    "2023-09-21_120653": dict(NumRawBeams=128, SamplesPerBeam=441,
                              WindowStart=0.6951, WindowLength=1.3156),
    "2023-09-21_100927": dict(NumRawBeams=128, SamplesPerBeam=441,
                              WindowStart=0.6949, WindowLength=1.3153),
}
DEFAULT_RECORDING = "2023-09-20_171105"


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def _rec_dir(recording: str) -> Path:
    spec = _spec(recording)
    return RAW_ROOT / spec.class_dir / spec.recording


# --------------------------------------------------------------------------
# discovery for recordings outside the audited three
# --------------------------------------------------------------------------
# BRIEF §1 pins three development recordings, and everything that depends on the
# audited header table stays limited to them.  But the folder tree holds 40 approved
# recordings, and a survey showed several where the target shows up as a compact echo
# that the wrong three never showed.  Those need to be loadable without editing a
# hard-coded registry, so this reads the class directory straight off disk.
# A discovered spec is marked in ``notes`` and its header comes from the yaml/CSV only,
# never from AUDITED_HEADERS.
CLASS_CATEGORY = {
    "100lbs_bomb": "100lbs_aircraft_bomb",
    "100lbs_bomb_(floor)": "100lbs_aircraft_bomb",
    "20lbs_incendiary": "incindiary_grenade",
    "15cm_mortar": "mortar_shell",
}
CLASS_NOMINAL = {
    "100lbs_bomb": (0.737, 0.208),
    "100lbs_bomb_(floor)": (0.737, 0.208),
    "20lbs_incendiary": (0.442, 0.127),
    "15cm_mortar": (0.58, 0.12),
}
DISCOVERED: Dict[str, RecordingSpec] = {}


def discover(recording: str) -> Optional[RecordingSpec]:
    """Find ``<class_dir>/<recording>/aris_raw`` on disk and build a spec for it."""
    if recording in DISCOVERED:
        return DISCOVERED[recording]
    if not RAW_ROOT.is_dir():
        return None
    for cls in sorted(RAW_ROOT.iterdir()):
        if not cls.is_dir():
            continue
        cand = cls / recording
        if (cand / "aris_raw").is_dir():
            length, dia = CLASS_NOMINAL.get(cls.name, (None, None))
            spec = RecordingSpec(
                recording=recording, class_dir=cls.name,
                category=CLASS_CATEGORY.get(cls.name, "unknown"),
                nominal_length_m=length, nominal_diameter_m=dia,
                notes="discovered from disk; not one of the three audited development "
                      "recordings (BRIEF §1), header read from yaml/CSV only",
            )
            DISCOVERED[recording] = spec
            return spec
    return None


def _spec(recording: str) -> RecordingSpec:
    spec = RECORDINGS.get(recording) or DISCOVERED.get(recording) or discover(recording)
    if spec is None:
        known = sorted(set(RECORDINGS) | set(DISCOVERED))
        raise KeyError(f"unknown recording {recording!r}; known: {known}")
    return spec


def _read_yaml(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}


def _grab(d: dict, keys: Sequence[str]):
    """first present key (case-insensitive) from a yaml dict."""
    low = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        if k.lower() in low:
            return low[k.lower()]
    return None


def res_m(rec) -> float:
    """metres per row sample for a recording (or Recording/Header)."""
    h = header(rec)
    return float(h["WindowLength"]) / float(h["SamplesPerBeam"])


def header(rec) -> dict:
    """header constants for a recording name / Recording / FrameGeom / header dict."""
    if isinstance(rec, dict):
        return rec
    h = getattr(rec, "header", None)
    if isinstance(h, dict):
        return h
    return header_of(str(rec))


def header_of(recording: str) -> dict:
    d = _rec_dir(recording)
    y = _read_yaml(d / "aris_file_meta.yaml")
    hdr = dict(AUDITED_HEADERS.get(recording, {}))
    got = {
        "NumRawBeams": _grab(y, ["NumRawBeams", "num_raw_beams"]),
        "SamplesPerBeam": _grab(y, ["SamplesPerBeam", "SamplesPerChannel", "samples_per_beam"]),
        "WindowStart": _grab(y, ["WindowStart", "window_start"]),
        "WindowLength": _grab(y, ["WindowLength", "window_length"]),
        "SampleRate": _grab(y, ["SampleRate", "sample_rate"]),
        "SoundSpeed": _grab(y, ["SoundSpeed", "sound_speed"]),
        "FrameRate": _grab(y, ["FrameRate", "frame_rate"]),
    }
    for k, v in got.items():
        if v is None:
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            continue
        if num == 0.0 and k in ("WindowStart", "WindowLength", "SampleRate", "FrameRate"):
            # the on-disk yaml leaves these zeroed; real values live in aris_frame_meta.csv
            continue
        hdr[k] = int(num) if k in ("NumRawBeams", "SamplesPerBeam") else num
    # The yaml in the recording tree leaves WindowStart/WindowLength at 0.0, and for a
    # recording outside AUDITED_HEADERS there is no audited value either.  The truth is
    # in the first data row of aris_frame_meta.csv; SamplesPerBeam is the PGM height.
    if "WindowStart" not in hdr or "WindowLength" not in hdr:
        mp = d / "aris_frame_meta.csv"
        if mp.exists():
            with open(mp, "r", encoding="utf-8", errors="replace", newline="") as fh:
                first = next(csv.DictReader(fh), None) or {}
            for k in ("WindowStart", "WindowLength"):
                if k in hdr:
                    continue
                try:
                    num = float(first.get(k) or 0.0)
                except (TypeError, ValueError):
                    num = 0.0
                if num > 0.0:
                    hdr[k] = num
    if "SamplesPerBeam" not in hdr or "NumRawBeams" not in hdr:
        pgms = sorted((d / "aris_raw").glob("*.pgm"))
        if pgms:
            w, h = _pgm_shape(pgms[0])
            hdr.setdefault("NumRawBeams", w)
            hdr.setdefault("SamplesPerBeam", h)
    if "SampleRate" not in hdr:
        hdr["SampleRate"] = 250000
    if "SoundSpeed" not in hdr:
        hdr["SoundSpeed"] = 1491.28
    if "FrameRate" not in hdr:
        hdr["FrameRate"] = 15
    missing = [k for k in ("WindowStart", "WindowLength") if k not in hdr]
    if missing:
        raise KeyError(f"{recording}: header lacks {missing}; the range axis would be "
                       f"invented, so refuse instead")
    return hdr


def _pgm_shape(path: Path) -> tuple:
    """Read width/height out of a P5 header without loading the pixels."""
    with open(path, "rb") as fh:
        blob = fh.read(256)
    i, fields = 2, []
    while len(fields) < 3 and i < len(blob):
        while i < len(blob) and blob[i:i + 1].isspace():
            i += 1
        if blob[i:i + 1] == b"#":
            while i < len(blob) and blob[i:i + 1] not in (b"\n", b"\r"):
                i += 1
            continue
        j = i
        while j < len(blob) and not blob[j:j + 1].isspace():
            j += 1
        fields.append(int(blob[i:j]))
        i = j
    if len(fields) < 3:
        raise ValueError(f"truncated PGM header: {path}")
    return fields[0], fields[1]


# --------------------------------------------------------------------------
# exact conversions
# --------------------------------------------------------------------------


def row_range_m(j, rec=None) -> float:
    """Row index -> range in metres:  WindowStart + j * RES.

    ``rec`` is a recording name, a Recording, or a header dict.  Defaults to the
    bomb recording's header (kept only for the API shape; prefer passing ``rec``).
    """
    h = header(rec if rec is not None else DEFAULT_RECORDING)
    return float(h["WindowStart"]) + float(j) * (float(h["WindowLength"]) / float(h["SamplesPerBeam"]))


def range_row_m(r_m, rec=None) -> float:
    """Inverse of ``row_range_m`` (may be fractional / out of range)."""
    h = header(rec if rec is not None else DEFAULT_RECORDING)
    return (float(r_m) - float(h["WindowStart"])) / (float(h["WindowLength"]) / float(h["SamplesPerBeam"]))


def range_window(rec=None):
    h = header(rec if rec is not None else DEFAULT_RECORDING)
    n = int(h["SamplesPerBeam"])
    return (row_range_m(0, h), row_range_m(n - 1, h))


def beam_angle_deg(i, fov_deg: Optional[float] = None, flip: bool = False,
                   n_beams: int = 128) -> float:
    """Beam index -> angle in degrees relative to the fan centre.

    ``fov_deg`` is **not measured** for this dataset.  It is a free parameter bounded by
    ``fov_bound()``; calling this function without it raises instead of silently using
    the old 130 deg assumption (which the observed beam widths exclude, see BRIEF §2.2).
    """
    if fov_deg is None:
        raise ValueError(
            "fov_deg is unvalidated for this dataset (assumed value would be a guess). "
            "Use fov_bound(beams_observed, L_m) for the defensible interval, or pass "
            "fov_deg explicitly to get a nominal angle."
        )
    idx = (n_beams - 1) - float(i) if flip else float(i)
    return (idx / (n_beams - 1) - 0.5) * float(fov_deg)


def fov_bound(beams_observed: float, L_m: float, window: Optional[Sequence[float]] = None,
              n_beams: int = 128, recording: Optional[str] = None) -> dict:
    """Interval of FOV values consistent with an observed azimuth width.

    Model: a broadside object of projected width ``L_m`` at range r subtends
    ``beams = 2*atan(L/2r)/theta_rad*n_beams``; in the small-angle limit this fixes the
    degenerate product ``r*theta_rad = L*n_beams/beams_observed``.  Requiring the target to
    lie inside the sampling window turns that into a bound on theta.

    The window matters: bomb samples to 3.018 m, the two 441-row recordings only to
    2.008 m, so a bound computed with the wrong window is 4-6 deg too wide.  Pass either
    ``window=range_window(recording)`` or ``recording=...``; omitting both raises instead of
    silently borrowing the default recording's window.

    Preconditions (the bound is void if any fails): the observed width belongs to the
    target body itself, seen broadside, with no multipath / sidelobe / support structure.
    """
    if not (beams_observed and beams_observed > 0):
        raise ValueError("beams_observed must be positive")
    if window is None:
        if recording is None:
            raise ValueError(
                "fov_bound needs the sampling window of the recording it describes: pass "
                "window=range_window(recording) or recording=<name>; using another "
                "recording's window widens the interval by 4-6 deg"
            )
        window = range_window(recording)
    r_min, r_max = float(window[0]), float(window[1])
    inv = L_m * n_beams / float(beams_observed)          # r * theta_rad  [m*rad]
    t_max = math.degrees(inv / r_min)                    # theta bound from r >= r_min
    t_min = math.degrees(inv / r_max)                    # theta bound from r <= r_max
    return {
        "beams_observed": float(beams_observed),
        "L_m": float(L_m),
        "invariant_r_times_theta_rad": inv,
        "window_m": [r_min, r_max],
        "fov_deg_min": t_min,
        "fov_deg_max": t_max,
        "fov_deg_interval": [t_min, t_max],
        "preconditions": "echo is the target body itself, broadside, no multipath/structure",
        "status": "conditional_bound_not_a_measurement",
    }


def intersect_bounds(bounds: Sequence[dict]) -> dict:
    """Intersection of several ``fov_bound`` results (verification test, BRIEF §2.2)."""
    lo = max(b["fov_deg_min"] for b in bounds)
    hi = min(b["fov_deg_max"] for b in bounds)
    return {
        "n": len(bounds),
        "fov_deg_interval": [lo, hi],
        "non_empty": bool(lo <= hi),
        "members": [{"beams": b["beams_observed"], "L_m": b["L_m"],
                     "interval": b["fov_deg_interval"]} for b in bounds],
        "interpretation": (
            "non-empty intersection = a single FOV can explain every recording under the "
            "broadside-body hypothesis; it does NOT prove the hypothesis, because each "
            "per-recording interval is wide (see docs)"),
    }


def scale_relation(az_width_beams: float, radial_rows: float, L_m: float,
                   D_m: Optional[float] = None, rec=None) -> dict:
    """Degenerate size relations of one view: what a single frame can and cannot fix.

    Returns the observable products only; absolute range stays unresolvable.
    """
    h = header(rec if rec is not None else DEFAULT_RECORDING)
    res = float(h["WindowLength"]) / float(h["SamplesPerBeam"])
    rows_from_diameter = (D_m / res) if D_m else None
    inv = L_m * int(h["NumRawBeams"]) / float(az_width_beams)
    return {
        "radial_rows_observed": float(radial_rows),
        "radial_m_observed": float(radial_rows) * res,
        "rows_expected_from_diameter": rows_from_diameter,
        "diameter_implied_m": float(radial_rows) * res,
        "invariant_r_times_theta_rad": inv,
        "fov_deg_if_range": {r: math.degrees(inv / r) for r in (0.7, 1.0, 1.5, 2.0, 3.0)},
        "abs_range": "unresolvable_from_single_view",
        "note": "rows fix only size/RES; beams fix only L*n/RES_angle, i.e. r*theta",
    }


# --------------------------------------------------------------------------
# recordings / frames
# --------------------------------------------------------------------------


@dataclass
class Recording:
    spec: RecordingSpec
    header: dict
    frames: List[int]
    meta: Dict[int, dict] = field(default_factory=dict)

    # ---- convenience
    @property
    def recording(self) -> str:
        return self.spec.recording

    @property
    def category(self) -> str:
        return self.spec.category

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    @property
    def frame_start(self) -> int:
        return self.frames[0]

    @property
    def frame_end(self) -> int:
        return self.frames[-1]

    @property
    def res_m(self) -> float:
        return float(self.header["WindowLength"]) / float(self.header["SamplesPerBeam"])

    @property
    def n_rows(self) -> int:
        return int(self.header["SamplesPerBeam"])

    @property
    def n_beams(self) -> int:
        return int(self.header["NumRawBeams"])

    @property
    def range_window(self):
        return (row_range_m(0, self.header), row_range_m(self.n_rows - 1, self.header))

    def row_range_m(self, j) -> float:
        return row_range_m(j, self.header)

    def has_frame(self, f: int) -> bool:
        return int(f) in set(self.frames)

    def pgm_path(self, f: int) -> Path:
        f = int(f)
        if not self.has_frame(f):
            raise KeyError(f"frame {f} not present in {self.recording} "
                           f"(range {self.frame_start}..{self.frame_end}, n={self.n_frames})")
        return _rec_dir(self.recording) / "aris_raw" / f"{f:04d}.pgm"

    def frame(self, f: int) -> "FrameGeom":
        return FrameGeom(self, int(f))

    def __repr__(self) -> str:  # pragma: no cover
        return (f"Recording({self.recording}, frames {self.frame_start}..{self.frame_end}, "
                f"n={self.n_frames}, rows={self.n_rows})")


class FrameGeom:
    def __init__(self, recording: Recording, frame: int):
        self.recording_obj = recording
        self.recording = recording.recording
        self.frame = int(frame)
        self.category = recording.category

    # ---- geometry that is exact
    @property
    def path(self) -> Path:
        return self.recording_obj.pgm_path(self.frame)

    @property
    def header(self) -> dict:
        """recording header, with this frame's WindowStart/WindowLength if present."""
        h = dict(self.recording_obj.header)
        m = self.meta()
        for key in ("WindowStart", "WindowLength"):
            try:
                v = float(m.get(key))
            except (TypeError, ValueError):
                continue
            if v > 0:
                h[key] = v
        return h

    def range_at_row(self, j) -> float:
        return row_range_m(j, self.header)

    def range_window(self):
        h = self.header
        return (row_range_m(0, h), row_range_m(int(h["SamplesPerBeam"]) - 1, h))

    def meta(self) -> dict:
        return self.recording_obj.meta.get(self.frame, {})

    # ---- geometry that is NOT available
    def predict(self) -> dict:
        """Explicitly unavailable (BRIEF §2.2).

        A sonar-frame pose is not recoverable here: ``gantry.csv`` is not in the sonar
        frame (its motion contradicts the observed image motion by ~50x in rows), and a
        single view cannot fix (range, FOV) - see ``scale_relation``.
        """
        return {
            "available": False,
            "reason": "gantry_not_sonar_frame",
            "detail": ("gantry.csv (x,y,z) is a ~1.21 m circle with 11-17 mm residual "
                       "traversed ~1/3 turn; using it as a range/bearing prediction "
                       "implies a ~531-row sweep that is not observed in any recording"),
            "beam": None, "row": None, "range_m": None, "az_deg": None,
            "target_xyz_m": None, "in_window": None,
            "convention": "none: geometry degraded, see BRIEF 2.2",
        }


def load_recording(recording: str, with_meta: bool = True) -> Recording:
    spec = _spec(recording)
    d = _rec_dir(recording)
    raw = d / "aris_raw"
    if not raw.is_dir():
        raise FileNotFoundError(f"missing {raw}")
    frames = sorted(int(p.stem) for p in raw.glob("*.pgm") if p.stem.isdigit())
    hdr = header_of(recording)
    meta: Dict[int, dict] = {}
    if with_meta:
        mp = d / "aris_frame_meta.csv"
        if mp.exists():
            with open(mp, "r", encoding="utf-8", errors="replace", newline="") as fh:
                for row in csv.DictReader(fh):
                    key = row.get("FrameIndex") or row.get("frame") or row.get("frame_idx")
                    try:
                        meta[int(float(key))] = row
                    except (TypeError, ValueError):
                        continue
    rec = Recording(spec=spec, header=hdr, frames=frames, meta=meta)
    # audit: header must agree with the audited table
    aud = AUDITED_HEADERS.get(recording, {})
    for k, v in aud.items():
        got = hdr.get(k)
        if got is None or abs(float(got) - float(v)) > 1e-6 * max(1.0, abs(float(v))):
            rec.header[k] = v
    return rec


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="geometry facts for one recording (read-only)")
    ap.add_argument("--recording", required=True)
    ap.add_argument("--frames", default="")
    ap.add_argument("--list-frames", action="store_true", help="print every frame number")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rec = load_recording(args.recording)
    h = rec.header
    info = {
        "recording": rec.recording,
        "class_dir": rec.spec.class_dir,
        "category": rec.category,
        "frames": {"n": rec.n_frames, "first": rec.frame_start, "last": rec.frame_end,
                   "present": rec.frames if args.list_frames else "..."},
        "header": {k: h.get(k) for k in ("NumRawBeams", "SamplesPerBeam", "WindowStart",
                                        "WindowLength", "SampleRate", "SoundSpeed", "FrameRate")},
        "res_m_per_row": rec.res_m,
        "range_window_m": list(rec.range_window),
        "predict": rec.frame(rec.frame_start).predict(),
        "nominal": {"length_m": rec.spec.nominal_length_m,
                    "diameter_m": rec.spec.nominal_diameter_m},
    }
    wanted = [int(s) for s in args.frames.replace(" ", "").split(",") if s]
    rows = []
    for f in wanted or [rec.frame_start]:
        if not rec.has_frame(f):
            rows.append({"frame": f, "error": "not present", "range": [rec.frame_start, rec.frame_end]})
            continue
        fg = rec.frame(f)
        m = fg.meta()
        rows.append({
            "frame": f,
            "SonarPan": m.get("SonarPan"), "SonarTilt": m.get("SonarTilt"),
            "SonarRoll": m.get("SonarRoll"),
            "range_m": [fg.range_at_row(0), fg.range_at_row(rec.n_rows - 1)],
        })
    info["requested_frames"] = rows
    if args.json:
        import json
        print(json.dumps(info, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"{rec.recording}  [{rec.spec.class_dir} / {rec.category}]")
        print(f"  frames {rec.frame_start}..{rec.frame_end}  n={rec.n_frames}")
        print(f"  rows={rec.n_rows} beams={rec.n_beams}  RES={rec.res_m:.8f} m/row")
        print(f"  WindowStart={h.get('WindowStart')}  WindowLength={h.get('WindowLength')}")
        print(f"  range window {rec.range_window[0]:.4f} .. {rec.range_window[1]:.4f} m")
        print(f"  predict(): {rec.frame(rec.frame_start).predict()['reason']} "
              f"(available={rec.frame(rec.frame_start).predict()['available']})")
        for r in rows:
            if "error" in r:
                print(f"  frame {r['frame']}: NOT PRESENT ({r['range'][0]}..{r['range'][1]})")
            else:
                print(f"  frame {r['frame']}: pan={_fmt(r['SonarPan'])} tilt={_fmt(r['SonarTilt'])} "
                      f"roll={_fmt(r['SonarRoll'])} range={r['range_m'][0]:.3f}..{r['range_m'][1]:.3f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
