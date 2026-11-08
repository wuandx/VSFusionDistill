#!/usr/bin/env python
"""R0 prereq: paper-style frame-level 8:2 stratified split (CMOLD repro).

Protocol (frozen in doc/logs/2026-11-08-cmold-paper-repro-plan.md §2/§6):

* pool = frame_meta.csv rows with ``split`` in ("train", "val")
  -> 4,152 frames / 37 recordings on uxo-full.  The ``test`` recordings
  (10) are never opened, and ``val_id`` (594 frames, the internal
  hold-out of the same 27 train recordings) is outside the pool: the
  pool is exactly the 4,152 frames of plan §2.
* frame-level random 8:2, seed 0, stratified per class (3 classes:
  100lbs_aircraft_bomb / incindiary_grenade / mortar_shell).
  Paper rationale: the paper has no "recording" concept, only
  "training and validation" (~4,700 image pairs), so a recording-level
  hold-out would answer a different question.  Deviation 1 of the plan:
  the two protocols are not comparable (34.1 AP50 points between
  protocols, doc/logs/2026-11-05-literature-comparison-blob.md:21).
* products, all under ``<paired_root>/../repro`` (new subdirectory only;
  no existing platform file is touched):
    frame_split.json  {"seed":0,"counts":{"train":N,"val":M},
                       "train":[sonar_image_id...],"val":[...], ...}
    sonar.json        copy of sonar.json with images[].split rewritten
    camera.json       copy of camera.json with images[].split rewritten

Why the annotation-file rewrite is *inert* for the current dataset, and
what actually switches the split (read before wiring this into configs):

* ``PairedSonarCameraDataset`` filters on ``sample["split"]``
  (aodet/datasets/paired_dataset.py:105), and that value comes from the
  *frame_meta.csv* ``split`` column, not from the json:
  aodet/datasets/paired_format.py:84 ``"split": row.get("split", "")``
  with ``self.frame_meta`` read from ``<root>/frame_meta.csv``
  (aodet/datasets/paired_format.py:152-156).
* The ann files carry no split at all: every entry of
  ``sonar.json/camera.json["images"]`` has keys
  file_name/height/id/width only (verified on the platform), and no
  reader in aodet/ ever looks at ``images[].split``.
* ``read_paired`` also loads camera.json, sonar.json, pairs.csv and
  frame_meta.csv from one single root
  (aodet/datasets/paired_format.py:144-170), and image paths are joined
  onto that root (aodet/datasets/paired_dataset.py:119-122), so a
  ``repro/`` directory holding only the two json files cannot serve as
  a data_root.

So the wiring that works is a new reader that filters by the ids in
``frame_split.json`` (a subclass in a NEW file, leaving
PairedSonarCameraDataset untouched), or a ``repro/frame_meta.csv`` copy
whose ``split`` column is rewritten.  The two rewritten ann files are
produced anyway because plan §6 freezes them as the split's data-side
artifact (useful for any reader that filters on ``images[].split``, and
they keep the full 6,246 images so annotation/image ids stay consistent).

Determinism: the per-stratum ranking is a sha256 of ``"<seed>:<id>"``,
not ``random.Random``.  The split is then reproducible bit-for-bit on
any Python version, from (seed, frame ids) alone, and can be re-derived
by a reader that distrusts this tool.

Usage:

    python tools/make_frame_split.py            # write products + verify
    python tools/make_frame_split.py --check    # verify only, no writes
"""

import argparse
import collections
import csv
import hashlib
import json
import os
import sys

SEED = 0
VAL_FRAC = 0.2
POOL_SPLITS = ("train", "val")
SPLIT_JSON = "frame_split.json"
# Windows path first (the plan's spelling), WSL mirror second: the tool
# must run under both (tests run in WSL ~/mycode/VSFusionDistill/.venv).
PAIRED_ROOT_CANDIDATES = ("D:/pby/uxo-full/paired",
                          "/mnt/d/pby/uxo-full/paired")
REPRO_DIRNAME = "repro"
# frames outside the pool keep their frame_meta split value in the
# rewritten ann files, so "test" stays recognisable (and unopened).
POSITIONAL_COLUMNS = ("sample_id", "camera_image_id", "sonar_image_id",
                      "recording", "split")


def first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def default_paired_root():
    root = os.environ.get("UXO_PAIRED_ROOT")
    if root:
        return root
    root = first_existing(PAIRED_ROOT_CANDIDATES)
    if root is None:
        raise SystemExit(
            "paired root not found; pass --paired-root (tried: %s)"
            % ", ".join(PAIRED_ROOT_CANDIDATES))
    return root


def default_out_dir(paired_root):
    """<platform>/repro: a sibling of the paired root, never inside it.

    paired_root is .../uxo-full/paired, so the sibling ../repro is
    D:/pby/uxo-full/repro in Windows form and /mnt/d/... in WSL form.
    """
    return os.path.join(os.path.dirname(os.path.normpath(paired_root)),
                        REPRO_DIRNAME)


def load_frame_meta(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for col in POSITIONAL_COLUMNS:
        if rows and col not in rows[0]:
            raise SystemExit("frame_meta.csv missing column %r" % col)
    for r in rows:
        r["sonar_image_id"] = int(r["sonar_image_id"])
        r["camera_image_id"] = int(r["camera_image_id"])
    return rows


def pool_rows(rows):
    """The frozen pool: split in (train, val) only."""
    return [r for r in rows if r["split"] in POOL_SPLITS]


def load_frame_classes(paired_root, image_ids=None):
    """sonar_image_id -> tuple of sonar category ids present in that frame.

    Empty tuple = frame without sonar annotation (negative sample); kept
    as its own stratum so the split does not depend on a frame having a
    box.
    """
    with open(os.path.join(paired_root, "sonar.json"), encoding="utf-8") as f:
        sonar = json.load(f)
    by_img = collections.defaultdict(set)
    for a in sonar.get("annotations", []):
        by_img[int(a["image_id"])].add(int(a["category_id"]))
    names = {int(c["id"]): c["name"] for c in sonar.get("categories", [])}
    if image_ids is not None:
        keep = set(image_ids)
        by_img = {k: v for k, v in by_img.items() if k in keep}
    classes = {k: tuple(sorted(v)) for k, v in by_img.items()}
    if image_ids is not None:
        for i in image_ids:
            classes.setdefault(int(i), ())
    return classes, names


def _rank(image_id, seed):
    """Deterministic per-frame rank: sha256 of "<seed>:<id>" (hex)."""
    return hashlib.sha256(("%d:%d" % (seed, int(image_id))).encode("ascii")
                          ).hexdigest()


def _n_val(n, val_frac):
    """Round half up, so 20% of n never loses a frame to banker's rounding."""
    return int(val_frac * n + 0.5)


def assign(rows, classes, category_names=None, seed=SEED, val_frac=VAL_FRAC):
    """Stratified frame-level split over ``rows`` (already the pool).

    Returns a dict with train/val id lists (sorted), per-class counts and
    the recording provenance needed by the self-check.
    """
    category_names = category_names or {}
    strata = collections.defaultdict(list)
    for r in rows:
        sid = r["sonar_image_id"]
        strata[classes.get(sid, ())].append(sid)

    train, val = [], []
    per_class = collections.defaultdict(lambda: {"train": 0, "val": 0})
    for stratum in sorted(strata, key=lambda s: (len(s), s)):
        ids = sorted(set(strata[stratum]))
        order = sorted(ids, key=lambda i: (_rank(i, seed), i))
        n_val = _n_val(len(order), val_frac)
        val.extend(order[:n_val])
        train.extend(order[n_val:])
        for sid in order[:n_val]:
            for cid in stratum:
                per_class[category_names.get(cid, str(cid))]["val"] += 1
        for sid in order[n_val:]:
            for cid in stratum:
                per_class[category_names.get(cid, str(cid))]["train"] += 1

    per_class_out = {}
    for name in sorted(per_class):
        v, t = per_class[name]["val"], per_class[name]["train"]
        per_class_out[name] = {
            "train": t, "val": v, "total": t + v,
            "val_frac": round(v / float(t + v), 6) if t + v else 0.0,
        }

    rec_of = {r["sonar_image_id"]: r["recording"] for r in rows}
    rec_train = sorted({rec_of[i] for i in train})
    rec_val = sorted({rec_of[i] for i in val})
    pool_recs = sorted({r["recording"] for r in rows})
    return {
        "seed": seed,
        "val_frac": val_frac,
        "counts": {"train": len(train), "val": len(val)},
        "train": sorted(train),
        "val": sorted(val),
        "per_class": per_class_out,
        "recordings": {
            "pool": pool_recs,
            "train": rec_train,
            "val": rec_val,
            "shared": sorted(set(rec_train) & set(rec_val)),
        },
        "n_strata": len(strata),
    }


def build(paired_root, seed=SEED, val_frac=VAL_FRAC):
    """Assemble the frame_split.json payload for one paired root."""
    meta_path = os.path.join(paired_root, "frame_meta.csv")
    rows = load_frame_meta(meta_path)
    pool = pool_rows(rows)
    classes, names = load_frame_classes(
        paired_root, [r["sonar_image_id"] for r in pool])
    payload = assign(pool, classes, names, seed=seed, val_frac=val_frac)
    assert len(payload["train"]) + len(payload["val"]) == len(pool)
    # frames outside the pool are recorded (counts only) so the check can
    # prove nothing from test leaked in
    payload["pool"] = {
        "split_values": list(POOL_SPLITS),
        "frames": len(pool),
        "recordings": len({r["recording"] for r in pool}),
        "excluded_splits": dict(sorted(
            collections.Counter(
                r["split"] for r in rows if r["split"] not in POOL_SPLITS
            ).items())),
        "categories": [[int(c), n] for c, n in sorted(names.items())],
    }
    payload["source"] = {
        "paired_root": portable_path(paired_root),
        "frame_meta_csv": "frame_meta.csv",
        "frame_meta_sha256": sha256_file(meta_path),
    }
    return payload


def portable_path(path):
    """/mnt/d/pby/... -> D:/pby/..., so the artifact reads the same from
    Windows and from WSL."""
    p = os.path.normpath(path).replace("\\", "/")
    if p.startswith("/mnt/") and len(p) > 6:
        drive = p[5]
        return drive.upper() + ":" + p[6:]
    return p


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def role_by_id(payload, rows):
    """image_id -> split value for the rewritten ann files.

    Pool frames get the repro role (train/val); everything else keeps its
    frame_meta split ("test", "val_id"), so a reader filtering on
    train/val cannot pick up an out-of-pool frame.
    """
    role_son, role_cam = {}, {}
    for r in rows:
        sid = int(r["sonar_image_id"])
        cid = int(r["camera_image_id"])
        role_son[sid] = r["split"]
        role_cam[cid] = r["split"]
    for sid in payload["train"]:
        role_son[sid] = "train"
    for sid in payload["val"]:
        role_son[sid] = "val"
    # camera ids map through frame_meta; pool membership is defined on the
    # sonar id, so mirror it with the same frame row
    sonar_role = dict(role_son)
    for r in rows:
        cid = int(r["camera_image_id"])
        role_cam[cid] = sonar_role[int(r["sonar_image_id"])]
    return role_son, role_cam


def write_ann_split(src, dst, role_by_image_id):
    with open(src, encoding="utf-8") as f:
        coco = json.load(f)
    missing = 0
    for im in coco.get("images", []):
        role = role_by_image_id.get(int(im["id"]))
        if role is None:
            missing += 1
            continue
        im["split"] = role
    if missing:
        raise SystemExit("%s: %d images without a split role" % (src, missing))
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(coco, f, ensure_ascii=False)
    counts = collections.Counter(im["split"] for im in coco["images"])
    return dict(sorted(counts.items()))


def write_products(payload, paired_root, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    split_path = os.path.join(out_dir, SPLIT_JSON)
    slim = {k: payload[k] for k in ("seed", "val_frac", "counts", "train",
                                    "val", "per_class", "pool", "source")}
    slim["recordings"] = {k: payload["recordings"][k]
                          for k in ("pool", "train", "val", "shared")}
    with open(split_path, "w", encoding="utf-8") as f:
        json.dump(slim, f, indent=2, ensure_ascii=False)
    rows = load_frame_meta(os.path.join(paired_root, "frame_meta.csv"))
    role_son, role_cam = role_by_id(payload, rows)
    out = {"frame_split_json": split_path,
           "frame_split_sha256": sha256_file(split_path)}
    for name, roles in (("sonar.json", role_son), ("camera.json", role_cam)):
        dst = os.path.join(out_dir, name)
        out[name] = write_ann_split(os.path.join(paired_root, name), dst,
                                    roles)
    return out


def check(payload, rows, classes, category_names=None, tol=0.01):
    """Self-check of one payload against the frame_meta it was built from.

    Returns (ok, lines).  Every assertion is a hard requirement of plan
    §2/§6: disjoint sets, full pool coverage, no test recording, per-class
    stratification, and seed reproducibility.
    """
    lines, ok = [], True

    def req(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        lines.append("  [%s] %s%s" % ("pass" if cond else "FAIL", name,
                                      (" -- " + detail) if detail else ""))

    train, val = list(payload["train"]), list(payload["val"])
    pool = pool_rows(rows)
    pool_ids = {r["sonar_image_id"] for r in pool}
    test_recs = {r["recording"] for r in rows if r["split"] == "test"}

    lines.append("pool: %d frames / %d recordings, split in %s"
                 % (len(pool), len({r["recording"] for r in pool}),
                    "/".join(POOL_SPLITS)))
    lines.append("excluded from pool: %s"
                 % json.dumps(payload["pool"]["excluded_splits"],
                              ensure_ascii=False, sort_keys=True))

    req("counts match the id lists",
        payload["counts"]["train"] == len(train)
        and payload["counts"]["val"] == len(val),
        "counts=%s" % payload["counts"])
    req("union covers the pool exactly", set(train) | set(val) == pool_ids,
        "%d ids" % len(pool_ids))
    req("train/val disjoint", not (set(train) & set(val)),
        "intersection=%d" % len(set(train) & set(val)))
    req("no duplicate ids", len(set(train)) == len(train)
        and len(set(val)) == len(val))
    req("no id outside the pool",
        (set(train) | set(val)) <= pool_ids)
    used_recs = {r["recording"] for r in rows
                 if r["sonar_image_id"] in set(train) | set(val)}
    req("no test recording in the split", not (used_recs & test_recs),
        "test recordings=%d" % len(test_recs))
    req("only recordings of the pool are used",
        used_recs <= {r["recording"] for r in pool},
        "%d recordings" % len(used_recs))

    lines.append("per class (train / val / total, val_frac):")
    for name, c in sorted(payload["per_class"].items()):
        frac = c["val"] / float(c["total"]) if c["total"] else 0.0
        lines.append("  %-22s %5d %5d %5d  %.4f"
                     % (name, c["train"], c["val"], c["total"], frac))
        # small classes get one frame of rounding slack, never more
        eff_tol = max(tol, 1.5 / c["total"]) if c["total"] else tol
        req("per-class val fraction within %.4f (%s)" % (eff_tol, name),
            abs(frac - payload["val_frac"]) <= eff_tol,
            "%.4f vs %.4f" % (frac, payload["val_frac"]))
    if not payload["per_class"]:
        req("pool has classes", False)

    shared = payload["recordings"]["shared"]
    lines.append("recordings: %d in the pool, %d in train, %d in val, %d in "
                 "both (frame-level random => near-neighbour leakage is "
                 "expected, plan §9)"
                 % (len(payload["recordings"]["pool"]),
                    len(payload["recordings"]["train"]),
                    len(payload["recordings"]["val"]), len(shared)))
    req("every pool recording is used",
        set(payload["recordings"]["pool"]) == used_recs)

    again = assign(pool, classes, category_names, seed=payload["seed"],
                   val_frac=payload["val_frac"])
    req("seed %d reproduces the same split" % payload["seed"],
        again["train"] == payload["train"] and again["val"] == payload["val"])
    other = assign(pool, classes, category_names, seed=payload["seed"] + 1,
                   val_frac=payload["val_frac"])
    req("a different seed changes the split",
        other["train"] != payload["train"])
    return ok, lines


def compare_with_disk(payload, out_dir):
    """--check against an existing artifact: (ok, lines)."""
    path = os.path.join(out_dir, SPLIT_JSON)
    if not os.path.exists(path):
        return True, ["  [skip] %s not present yet" % path]
    with open(path, encoding="utf-8") as f:
        disk = json.load(f)
    diffs = []
    for key in ("seed", "counts", "train", "val"):
        if disk.get(key) != payload[key]:
            diffs.append(key)
    ok = not diffs
    lines = ["  [%s] %s matches a fresh build of seed %d"
             % ("pass" if ok else "FAIL", path, payload["seed"])]
    if diffs:
        lines.append("        fields that differ: %s" % ", ".join(diffs))
        lines.append("        on disk: %s %s"
                     % (disk.get("counts"), disk.get("seed")))
        lines.append("        rebuilt: %s %s"
                     % (payload["counts"], payload["seed"]))
    return ok, lines


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paired-root", default=None,
                    help="paired-format root holding frame_meta.csv / "
                         "sonar.json / camera.json (default: %s, or "
                         "$UXO_PAIRED_ROOT)"
                         % " then ".join(PAIRED_ROOT_CANDIDATES))
    ap.add_argument("--out-dir", default=None,
                    help="product directory (default: <platform>/repro, a "
                         "sibling of the paired root)")
    ap.add_argument("--seed", type=int, default=SEED,
                    help="split seed (frozen: %d)" % SEED)
    ap.add_argument("--val-frac", type=float, default=VAL_FRAC,
                    help="validation fraction (frozen: %.2f)" % VAL_FRAC)
    ap.add_argument("--check", action="store_true",
                    help="verify only: no write; also compares with the "
                         "artifact already on disk")
    args = ap.parse_args()

    paired_root = args.paired_root or default_paired_root()
    out_dir = args.out_dir or default_out_dir(paired_root)
    rows = load_frame_meta(os.path.join(paired_root, "frame_meta.csv"))
    payload = build(paired_root, seed=args.seed, val_frac=args.val_frac)
    pool = pool_rows(rows)
    classes, names = load_frame_classes(
        paired_root, [r["sonar_image_id"] for r in pool])

    print("paired root: %s" % paired_root)
    print("out dir:     %s%s" % (out_dir, "  (--check: read only)"
                                 if args.check else ""))
    print("frame_meta:  %d rows, split values %s"
          % (len(rows), dict(sorted(collections.Counter(
              r["split"] for r in rows).items()))))

    ok, lines = check(payload, rows, classes, names)
    for line in lines:
        print(line)

    if not args.check:
        out = write_products(payload, paired_root, out_dir)
        print("products:")
        print("  %s  sha256 %s" % (out["frame_split_json"],
                                   out["frame_split_sha256"]))
        for name in ("sonar.json", "camera.json"):
            roles = json.dumps(out[name], ensure_ascii=False, sort_keys=True)
            print("  %s  images[].split %s"
                  % (os.path.join(out_dir, name), roles))
    disk_ok, disk_lines = compare_with_disk(payload, out_dir) \
        if args.check else (True, [])
    for line in disk_lines:
        print(line)
    ok = ok and disk_ok

    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
