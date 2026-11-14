"""Check current audit documents, non-test input hashes, and read-only git state."""
from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    "README.md", "AGENTS.md", "handoff.md", "dataset.md", "brainstorm.md",
    "experiment/results.md", "experiment/evaluation.md", "experiment/plan-camera-teacher.md",
    "复现/camera-baseline/README.md",
    "复现/camera-baseline/implementation-evidence-review.md",
    "复现/camera-baseline/data-protocol-evidence-review.md",
    "related_work/paper-evidence-review.md",
]


def main():
    broken = []
    checked_links = 0
    placeholders = []
    for name in DOCS:
        path = ROOT / name
        content = path.read_text(encoding="utf-8")
        if "{{" in content:
            placeholders.append(name)
        for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", content):
            target = match.group(1).strip("<>")
            if target.startswith(("https://", "http://", "#")):
                continue
            target = re.sub(r":\d+$", "", target.split("#", 1)[0])
            destination = Path(target)
            if not destination.is_absolute():
                destination = path.parent / target
            checked_links += 1
            if not destination.exists():
                broken.append({"document": name, "target": target})
    syntax_errors = []
    for path in (ROOT / "tools").glob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except SyntaxError as exc:
            syntax_errors.append(str(exc))
    snapshot = json.loads((ROOT / "复现/camera-baseline/evidence-snapshot-2026-11-10.json").read_text(encoding="utf-8"))
    changed_inputs = []
    for row in snapshot["files"]:
        if row["exists"]:
            path = Path(row["path"])
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                changed_inputs.append(str(path))
    repo = snapshot["repo"]

    def git(*args):
        return subprocess.check_output(["git", "--no-optional-locks", "-C", repo, *args], text=True).strip()

    head, status = git("rev-parse", "HEAD"), git("status", "--porcelain=v1")
    result = {
        "scope": "document links, syntax only, explicit non-test input hashes, read-only git",
        "documents": len(DOCS), "local_links_checked": checked_links,
        "broken_links": broken, "unfilled_placeholders_in_current_docs": placeholders,
        "syntax_errors": syntax_errors, "changed_allowlisted_inputs": changed_inputs,
        "head_before": snapshot["head"], "head_after": head,
        "status_before": snapshot["status_porcelain"], "status_after": status,
        "repo_state_matches": head == snapshot["head"] and status == snapshot["status_porcelain"],
        "no_training_or_inference": True,
        "limitations": "No remote link availability test, no model/COCOeval rerun, no test data access; matching HEAD/status and allowlist hashes are not a hash of the entire research tree.",
    }
    result["passed"] = not (broken or placeholders or syntax_errors or changed_inputs) and result["repo_state_matches"]
    output = ROOT / "复现/camera-baseline/workflow-verification.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
