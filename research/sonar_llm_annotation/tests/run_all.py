#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal test runner for the sonar_llm_annotation QA suite.

No pytest on this machine, so this is a plain collector: import each ``test_*.py``,
run every module-level ``test_*`` function in definition order, record PASS / FAIL /
ERROR with the assertion message, and write ``out/_qa/qa-results.json``.

    python tests/run_all.py                 # everything
    python tests/run_all.py --only 02 echo  # modules whose filename contains any token
    python tests/run_all.py --list
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _util  # noqa: E402


def discover(only=None):
    mods = sorted(HERE.glob("test_*.py"))
    if only:
        mods = [p for p in mods if any(tok.lower() in p.stem.lower() for tok in only)]
    return mods


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="QA suite runner (no pytest)")
    ap.add_argument("--only", nargs="*", default=None, help="filename substrings")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    mods = discover(args.only)
    if not mods:
        print("no test modules matched", file=sys.stderr)
        return 2
    if args.list:
        for p in mods:
            print(p.stem)
        return 0

    _util.OUT_QA.mkdir(parents=True, exist_ok=True)
    src_before = _util.source_hashes()

    results = []
    t_start = time.time()
    for path in mods:
        try:
            mod = importlib.import_module(path.stem)
        except Exception:
            results.append({"module": path.stem, "test": "<import>", "status": "ERROR",
                            "seconds": 0.0, "message": traceback.format_exc()})
            print("ERROR %-28s <import>\n%s" % (path.stem, traceback.format_exc()))
            continue
        fns = [(n, f) for n, f in vars(mod).items()
               if n.startswith("test_") and callable(f)]
        print("\n== %s (%d tests)" % (path.stem, len(fns)))
        for name, fn in fns:
            t0 = time.time()
            status, message = "PASS", ""
            try:
                fn()
            except _util.SkipTest as exc:
                status, message = "SKIP", str(exc)
            except AssertionError as exc:
                frame = traceback.extract_tb(sys.exc_info()[2])[-1]
                where = "%s:%d" % (os.path.basename(frame.filename), frame.lineno)
                status = "FAIL"
                message = "%s (%s)" % (str(exc) or "assertion failed", where)
            except Exception as exc:  # noqa: BLE001
                status = "ERROR"
                message = "".join(traceback.format_exception_only(type(exc), exc)).strip() \
                    + "\n" + traceback.format_exc(limit=6)
            dt = time.time() - t0
            results.append({"module": path.stem, "test": name, "status": status,
                            "seconds": round(dt, 3), "message": message})
            head = "%-5s %-30s %6.2fs" % (status, name, dt)
            print(head if status == "PASS" else head + "\n      " + message.replace("\n", "\n      "))

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_err = sum(1 for r in results if r["status"] == "ERROR")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")
    src_after = _util.source_hashes()
    changed = sorted(k for k in set(src_before) | set(src_after)
                     if src_before.get(k) != src_after.get(k))

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "python": sys.version.split()[0],
        "seconds": round(time.time() - t_start, 2),
        "counts": {"pass": n_pass, "fail": n_fail, "error": n_err, "skip": n_skip,
                   "total": len(results)},
        "sources_tested": src_before,
        "sources_changed_during_run": changed,
        "results": results,
    }
    out = _util.OUT_QA / "qa-results.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n%s" % ("-" * 72))
    print("PASS %d   FAIL %d   ERROR %d   SKIP %d   (%.1fs)"
          % (n_pass, n_fail, n_err, n_skip, time.time() - t_start))
    if changed:
        print("WARNING: sources changed during the run: %s" % ", ".join(changed))
    print("written: %s" % _util.rel(out))
    return 0 if (n_fail == 0 and n_err == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
