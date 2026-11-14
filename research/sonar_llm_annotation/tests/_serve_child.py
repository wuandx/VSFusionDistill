"""Child process: run the real review service (Handler + serve_forever) on a given port.

argv: port, root (proposals/cards/judgments/reviews + tmp all live under root)
The module-level TMP_DIR is redirected into `root` first, so starting this service never
overwrites tmp/review/server*.json belonging to the review line on 8771.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
port = int(sys.argv[1])
root = Path(sys.argv[2])

spec = importlib.util.spec_from_file_location("qa_serve_server", REPO / "review" / "server.py")
srv = importlib.util.module_from_spec(spec)
sys.modules["qa_serve_server"] = srv
spec.loader.exec_module(srv)

srv.TMP_DIR = root / "tmp"
srv.OUT_DIR = root
srv.CFG.cards_dir = root / "cards"
srv.CFG.judgments_root = root
srv.CFG.operator = "qa-server"
raise SystemExit(srv.main(["--port", str(port), "--host", "127.0.0.1",
                           "--proposals", str(root / "proposals")]))
