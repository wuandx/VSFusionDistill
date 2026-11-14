"""Shared helpers for the sonar_llm_annotation QA suite.

Deliberately dependency-free: this box has numpy / Pillow / pyyaml only, no pytest.
Every helper here is read-only except inside ``out/_qa/`` (the QA write scope).
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"
OUT_QA = REPO / "out" / "_qa"
RAW_ROOT = Path(r"D:\pby\uxo-full\extracted\recordings")

REC_BOMB = "2023-09-20_171105"        # 128 x 780
REC_GRENADE = "2023-09-21_120653"     # 128 x 441
REC_MORTAR = "2023-09-21_100927"      # 128 x 441
RECORDINGS = (REC_BOMB, REC_GRENADE, REC_MORTAR)
CLASS_DIR = {
    REC_BOMB: "100lbs_bomb",
    REC_GRENADE: "20lbs_incendiary",
    REC_MORTAR: "15cm_mortar",
}
CATEGORY = {
    REC_BOMB: "100lbs_aircraft_bomb",
    REC_GRENADE: "incindiary_grenade",
    REC_MORTAR: "mortar_shell",
}
FRAME_HEIGHT = {REC_BOMB: 780, REC_GRENADE: 441, REC_MORTAR: 441}
FRAME_WIDTH = {rec: 128 for rec in RECORDINGS}

PY = sys.executable


# ------------------------------------------------------------------ paths ---
def qa_dir(*parts: str) -> Path:
    """Create (if needed) and return a directory inside out/_qa."""
    p = OUT_QA.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def fresh_dir(*parts: str) -> Path:
    """Empty a directory inside out/_qa (removing stale artefacts from earlier runs)."""
    p = OUT_QA.joinpath(*parts)
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def rel(p: Path | str) -> str:
    """Repo-relative posix path, for messages that must be copy-pasteable."""
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except Exception:
        return str(p)


# ------------------------------------------------------------------ hashes ---
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_hashes() -> dict:
    """sha256 of every source file under test, so a report states *what* was tested."""
    files = []
    files += sorted((REPO / "engine").glob("*.py"))
    files += sorted((REPO / "plugin" / "sonarllm").glob("*.py"))
    files += sorted((REPO / "tools").glob("*.py"))
    files += [REPO / "review" / "server.py"]
    return {rel(p): sha256_file(p) for p in files if p.is_file()}


class SkipTest(Exception):
    """Raise when a case cannot run because its feature is not delivered yet.

    A skip is recorded as SKIP and is *not* a failure: it must state why, so a reader can
    tell "not built yet" from "built and passing".
    """


# ------------------------------------------------------------------ imports ---
_ENGINE: dict = {}


def eng(name: str):
    """Import engine/<name>.py (package import so the relative imports work)."""
    if name in _ENGINE:
        return _ENGINE[name]
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    mod = importlib.import_module("engine." + name)
    _ENGINE[name] = mod
    return mod


_PLUGIN = {}


def plugin():
    """Import the plugin package ``sonarllm`` from plugin/, with its submodules bound."""
    if "sonarllm" in _PLUGIN:
        return _PLUGIN["sonarllm"]
    sp = str(REPO / "plugin")
    if sp not in sys.path:
        sys.path.insert(0, sp)
    import sonarllm  # noqa: PLC0415
    import importlib  # noqa: PLC0415

    for sub in ("__main__", "cli", "dataset", "judge"):
        try:
            importlib.import_module("sonarllm." + sub)
        except Exception:  # noqa: BLE001 - a missing submodule is reported by the test itself
            pass
    _PLUGIN["sonarllm"] = sonarllm
    return sonarllm


_SERVER = {}


def server_mod():
    """Load review/server.py as its own module (it is a script, not a package)."""
    if "srv" in _SERVER:
        return _SERVER["srv"]
    path = REPO / "review" / "server.py"
    spec = importlib.util.spec_from_file_location("qa_review_server", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["qa_review_server"] = mod
    spec.loader.exec_module(mod)
    _SERVER["srv"] = mod
    return mod


# ------------------------------------------------------------------ raw data ---
def rec_dir(rec: str) -> Path:
    return RAW_ROOT / CLASS_DIR[rec] / rec


def pgm_path(rec: str, frame: int) -> Path:
    return rec_dir(rec) / "aris_raw" / ("%04d.pgm" % int(frame))


def read_pgm(path: Path | str):
    """Read a binary PGM through the engine's own reader (numpy array, uint8)."""
    echo = eng("echo")
    return echo.read_pgm(Path(path))


def read_pgm_header(path: Path | str) -> tuple:
    """(width, height) from the PGM header without decoding the payload."""
    data = Path(path).read_bytes()[:64]
    parts = data.split(b"\n")
    if not parts or parts[0].strip() != b"P5":
        raise ValueError("not a P5 pgm: %s" % path)
    w, h = (int(v) for v in parts[1].split())
    return w, h


def write_pgm(path: Path | str, arr) -> Path:
    """Write a uint8 HxW array as a binary PGM (P5, maxval 255)."""
    import numpy as np

    a = np.asarray(arr)
    if a.dtype != np.uint8:
        a = np.clip(np.rint(a), 0, 255).astype(np.uint8)
    h, w = a.shape
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"P5\n%d %d\n255\n" % (w, h) + a.tobytes())
    return path


def frame_pgm_bytes(rec: str, frame: int) -> bytes:
    return pgm_path(rec, frame).read_bytes()


# ------------------------------------------------------------------ synthetic ---
def synth_sonar(h: int = 780, w: int = 128, seed: int = 11):
    """A synthetic ARIS-like frame with a persistent bright band.

    The band is deliberately *column complete* (every beam sees it), which is what makes
    the masked row profile an exact shifted copy of itself: ``profile[b][r] ==
    profile[a][r + drow]`` with no column-subset noise.  Three row-dependent ridges give
    the row profile structure -- exactly the thing the old median projection destroyed --
    and a smooth beam-gain ripple keeps the beam profile non-degenerate so ``dbeam`` is
    measurable instead of being forced to 0.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    yy = np.arange(h, dtype=np.float64)[:, None]
    xx = np.arange(w, dtype=np.float64)[None, :]
    img = rng.normal(10.0, 2.0, size=(h, w))
    # beam gain ripple (vertical stripes), ~10 gray levels peak to peak
    img = img + 5.0 * np.sin(2.0 * np.pi * xx / 17.0)
    # persistent bottom-reverberation band, brightness varying with range
    prof = (46.0 * np.exp(-((yy - 0.24 * h) ** 2) / (2.0 * (0.055 * h) ** 2))
            + 30.0 * np.exp(-((yy - 0.58 * h) ** 2) / (2.0 * (0.020 * h) ** 2))
            + 22.0 * np.exp(-((yy - 0.85 * h) ** 2) / (2.0 * (0.040 * h) ** 2)))
    img = img + prof * (0.92 + 0.08 * np.sin(2.0 * np.pi * xx / 23.0))
    # a faint specular arc (target-like), well below the band so it cannot dominate it
    r = np.hypot((yy - 0.42 * h), (xx - 0.50 * w) * 1.7)
    img = img + 30.0 * np.exp(-((r - 0.030 * h) ** 2) / (2.0 * (0.006 * h) ** 2))
    return np.clip(img, 0, 255).astype(np.uint8)


def synth_sphere_mesh(diameter_m: float = 0.2, n: int = 4000, model: str = "qa_sphere"):
    """A Mesh wrapping a Fibonacci sphere; the analytic projection unit test's fixture."""
    import numpy as np

    mp = eng("mesh_prior")
    pts = mp.sphere_cloud(float(diameter_m), n=n)
    return mp.Mesh(
        category="qa_sphere",
        model=model,
        obj_path="<synthetic>",
        sha256_obj="",
        nominal_length_m=float(diameter_m),
        nominal_diameter_m=float(diameter_m),
        vertices=pts,
        faces=np.zeros((0, 3), dtype=np.int64),
        points=pts,
        extent_m=np.array([diameter_m, diameter_m, diameter_m], dtype=np.float64),
    )


# ------------------------------------------------------------------ process ---
def run_py(args, cwd: Path | str | None = None, timeout: float = 600.0,
           env_extra: dict | None = None, check: bool = False):
    """Run the current interpreter with *args* (list).  Returns CompletedProcess."""
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})
    cp = subprocess.run([PY, *[str(a) for a in args]],
                        cwd=str(cwd or REPO), capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=timeout, env=env)
    if check and cp.returncode != 0:
        raise AssertionError("command failed (%d): %s\nstdout:\n%s\nstderr:\n%s"
                             % (cp.returncode, " ".join(map(str, args)),
                                cp.stdout[-4000:], cp.stderr[-4000:]))
    return cp


# ------------------------------------------------------------------ network ---
def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, int(port)))
        except OSError:
            return False
    return True


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        try:
            s.connect((host, int(port)))
        except OSError:
            return False
    return True


def wait_port_free(port: int, timeout: float = 15.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if port_is_free(port):
            return True
        time.sleep(0.1)
    return port_is_free(port)


def wait_port_open(port: int, timeout: float = 20.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if port_open(port):
            return True
        time.sleep(0.05)
    return port_open(port)


# ------------------------------------------------------------------ asserts ---
def assert_raises(exc_types, fn, *args, contains: str | None = None, **kwargs):
    """Assert that fn raises; return the exception so the message can be inspected."""
    try:
        fn(*args, **kwargs)
    except exc_types as exc:  # noqa: PERF203
        if contains is not None and contains not in str(exc):
            raise AssertionError(
                "raised %s but message did not contain %r: %s"
                % (type(exc).__name__, contains, exc)) from None
        return exc
    except BaseException as exc:  # noqa: BLE001
        raise AssertionError("expected %s, got %s: %s"
                             % (exc_types, type(exc).__name__, exc)) from None
    raise AssertionError("expected %s, nothing was raised" % (exc_types,))


def assert_close(got, want, tol, what: str = ""):
    if abs(float(got) - float(want)) > float(tol):
        raise AssertionError("%s: got %.6f, want %.6f (tol %g)"
                             % (what or "value", float(got), float(want), float(tol)))


def jdump(obj, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
