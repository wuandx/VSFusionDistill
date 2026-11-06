#!/usr/bin/env python
"""Pre-launch config gate: diff a candidate config against a reference config.

Every training arm derived from an existing config MUST pass this gate before
launch. The point is that a human (or an assistant) transcription of a config is
unreliable: a single omitted transform key silently changes what the arm means,
and the loss curve will not tell you.

Usage
-----
    PYTHONPATH=. python tools/config_gate.py \
        --candidate configs/f2/s0_c0_camera_only_yoloxs.py \
        --reference configs/f2/e11_bcam_camera_only_yoloxs.py \
        --expect "model.uncoupled_sonar_head=None" \
        --expect "model.fused_sonar_head=None" \
        --expect "model.fusion.type=NoneFusion"

Rules
-----
* Every difference outside the allowed volatile keys below must be declared with
  --expect, using a dotted path prefix (a prefix match is enough, so
  `model.loss_weights` covers all its children).
* Undeclared differences -> exit 1. The gate is fail-closed on purpose.
* Declared-but-absent differences are also reported (a stale --expect usually
  means the config drifted from what you thought you were doing).
"""
from __future__ import annotations

import argparse
import json
import sys

# Volatile / bookkeeping keys that never change the meaning of an arm.
VOLATILE = (
    "_scope_", "custom_imports", "default_hooks", "log_processor", "visualizer",
    "vis_backends", "resume", "load_from", "work_dir", "randomness",
    "auto_scale_lr", "env_cfg", "default_scope", "experiment_name", "launcher",
    "log_level", "cfg_name", "file_name",
)


def load(path: str) -> dict:
    from mmengine.config import Config
    from mmengine.registry import init_default_scope

    import aodet.datasets  # noqa: F401
    import aodet.models  # noqa: F401

    init_default_scope("mmdet")
    return Config.fromfile(path).to_dict()


def walk(x, y, prefix="", out=None):
    if out is None:
        out = []
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if k not in x:
                out.append((f"{prefix}{k}", "<absent>", dump(y[k])))
            elif k not in y:
                out.append((f"{prefix}{k}", dump(x[k]), "<absent>"))
            else:
                walk(x[k], y[k], f"{prefix}{k}.", out)
    else:
        a, b = dump(x), dump(y)
        if a != b:
            out.append((prefix[:-1], a, b))
    return out


def dump(v) -> str:
    return json.dumps(v, default=str, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--expect", action="append", default=[],
                    help="dotted path prefix of an intended difference; repeatable")
    ap.add_argument("--max-show", type=int, default=80)
    args = ap.parse_args()

    cand, ref = load(args.candidate), load(args.reference)
    diffs = walk(cand, ref)

    unexpected, expected_hit = [], []
    for path, a, b in diffs:
        if any(v in path for v in VOLATILE):
            continue
        hit = next((e for e in args.expect if path == e or path.startswith(e + ".") or path.startswith(e)), None)
        (expected_hit if hit else unexpected).append((path, a, b, hit))

    print(f"candidate : {args.candidate}")
    print(f"reference : {args.reference}")
    print(f"differences: {len(expected_hit) + len(unexpected)}  "
          f"(declared {len(expected_hit)}, undeclared {len(unexpected)})")
    print()

    if expected_hit:
        print("== declared (intended) ==")
        for path, a, b, _ in expected_hit:
            print(f"  {path}\n      candidate={a}\n      reference={b}")
        print()

    if unexpected:
        print("== UNDECLARED (blocks launch) ==")
        for path, a, b, _ in unexpected[: args.max_show]:
            print(f"  {path}\n      candidate={a}\n      reference={b}")
        if len(unexpected) > args.max_show:
            print(f"  ... {len(unexpected) - args.max_show} more")
        print()

    # stale declarations
    used = {h for _, _, _, h in expected_hit}
    stale = [e for e in args.expect if e not in used]
    if stale:
        print("== declared but ABSENT (config does not differ there) ==")
        for e in stale:
            print(f"  {e}")
        print()

    if unexpected:
        print("GATE: FAIL - undeclare/justify the differences above, or fix the config.")
        return 1
    print("GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
