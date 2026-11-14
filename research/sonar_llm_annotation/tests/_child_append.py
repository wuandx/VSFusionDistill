"""Child process: append N review rows to out/_qa/.../reviews.jsonl through the real writer.

argv: root, recording, n, prefix
Used by test_12 to prove two concurrent processes never interleave a line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("qa_child_server", REPO / "review" / "server.py")
srv = importlib.util.module_from_spec(spec)
sys.modules["qa_child_server"] = srv
spec.loader.exec_module(srv)

root = Path(sys.argv[1])
recording = sys.argv[2]
n = int(sys.argv[3])
prefix = sys.argv[4]
srv.OUT_DIR = root
for i in range(n):
    row = {"sample": "%s_%04d" % (prefix, i), "recording": recording,
           "status": "uncertain", "operator": "qa-conc",
           "payload": "x" * 200, "i": i}
    srv.append_review(recording, row)
print(json.dumps({"ok": True, "n": n, "pid": __import__("os").getpid()}))
