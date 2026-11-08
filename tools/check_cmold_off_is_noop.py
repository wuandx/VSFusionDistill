#!/usr/bin/env python
"""Proof that the CMOLD wiring is a no-op when the config has no ``cmold`` key.

The check loads the *committed* version of
``aodet/models/detectors/two_stream_yolox.py`` (``git show <ref>:<path>``, i.e.
the pre-CMOLD code) next to the working-tree version, gives both the same
weights and the same batch, and compares ``loss()`` term by term -- bitwise.

Run with the repository ``.venv`` from the repository root::

    ./.venv/bin/python tools/check_cmold_off_is_noop.py
    ./.venv/bin/python tools/check_cmold_off_is_noop.py --ref 41dafa5

Exit code 0 when every term is bitwise identical and the loaded baseline has
no ``cmold`` attribute at all; 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import aodet.models  # noqa: E402,F401  (registers the extensions)
from mmengine.registry import init_default_scope  # noqa: E402

init_default_scope("mmdet")

IMG = (128, 160)


def _stream_cfg(num_classes=3):
    norm = dict(type="BN", momentum=0.03, eps=0.001)
    act = dict(type="Swish")
    common = dict(norm_cfg=norm, act_cfg=act)
    backbone = dict(type="CSPDarknet", deepen_factor=0.33, widen_factor=0.25,
                    out_indices=(2, 3, 4), **common)
    neck = dict(type="YOLOXPAFPN", in_channels=[64, 128, 256],
                out_channels=64, num_csp_blocks=1, **common)
    head = dict(type="YOLOXHead", num_classes=num_classes, in_channels=64,
                feat_channels=64, stacked_convs=2, strides=(8, 16, 32),
                **common,
                loss_cls=dict(type="CrossEntropyLoss", use_sigmoid=True,
                              reduction="sum", loss_weight=1.0),
                loss_bbox=dict(type="IoULoss", mode="square", eps=1e-16,
                               reduction="sum", loss_weight=5.0),
                loss_obj=dict(type="CrossEntropyLoss", use_sigmoid=True,
                              reduction="sum", loss_weight=1.0),
                loss_l1=dict(type="L1Loss", reduction="sum", loss_weight=1.0))
    return backbone, neck, head


def _kwargs(kind):
    """Two representative configs: B0 (sonar only) and B2 (camera + fusion)."""
    sbb, snc, shd = _stream_cfg()
    common = dict(
        sonar_backbone=sbb, sonar_neck=snc,
        train_cfg=dict(assigner=dict(type="SimOTAAssigner",
                                     center_radius=2.5)),
        test_cfg=dict(score_thr=0.01,
                      nms=dict(type="nms", iou_threshold=0.65)),
        data_preprocessor=dict(type="PairedDataPreprocessor",
                               mean=[0, 0, 0], std=[1, 1, 1],
                               bgr_to_rgb=False, pad_size_divisor=32),
    )
    if kind == "b0":
        return dict(common, uncoupled_sonar_head=shd)
    cbb, cnc, chd = _stream_cfg()
    _, _, fused_hd = _stream_cfg()
    return dict(common, camera_backbone=cbb, camera_neck=cnc, camera_head=chd,
                fused_sonar_head=fused_hd,
                loss_weights=dict(camera=1.0, fused_sonar=0.5,
                                  uncoupled_sonar=0.5))


def _sample(n_obj=2):
    from mmdet.structures import DetDataSample
    from mmdet.structures.bbox import HorizontalBoxes
    from mmengine.structures import InstanceData
    ds = DetDataSample()
    ds.set_metainfo({"img_id": 0, "img_shape": IMG, "ori_shape": IMG,
                     "scale_factor": (1.0, 1.0),
                     "batch_input_shape": IMG, "pad_shape": IMG})
    gt = InstanceData()
    gt.bboxes = HorizontalBoxes(
        torch.tensor([[20.0, 20.0, 60.0, 50.0],
                      [80.0, 60.0, 120.0, 100.0]][:n_obj], dtype=torch.float32))
    gt.labels = torch.zeros(n_obj, dtype=torch.long)
    ds.gt_instances = gt
    return ds


def _batch(b=2):
    import numpy as np
    rng = np.random.default_rng(0)
    return {
        "img_sonar": [torch.from_numpy(
            rng.integers(0, 255, (3, *IMG), dtype=np.uint8)) for _ in range(b)],
        "img_camera": [torch.from_numpy(
            rng.integers(0, 255, (3, *IMG), dtype=np.uint8)) for _ in range(b)],
        "data_samples_sonar": [_sample() for _ in range(b)],
        "data_samples_camera": [_sample() for _ in range(b)],
    }


def _load_baseline(ref):
    """Import the committed detector file as a second, independent module.

    The class is decorated with ``@DET_MODELS.register_module()``; the name
    ``TwoStreamYOLOX`` is already taken by the working-tree class, so the
    registry is made a pass-through for the duration of the exec and restored
    afterwards.  Neither class is built through the registry anyway.
    """
    from mmdet.registry import MODELS

    path = "aodet/models/detectors/two_stream_yolox.py"
    src = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=REPO,
                         check=True, capture_output=True, text=True).stdout
    tmp = Path(tempfile.mkdtemp()) / "two_stream_yolox_baseline.py"
    tmp.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("cmold_baseline_tsyx", tmp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod

    original = MODELS.register_module

    def _passthrough(name=None, force=False, module=None):
        if module is not None:
            return module
        return lambda cls: cls

    MODELS.register_module = _passthrough
    try:
        spec.loader.exec_module(mod)
    finally:
        MODELS.register_module = original
    return mod.TwoStreamYOLOX, len(src.splitlines())


def _run(model, data):
    model.train()
    prepped = model.data_preprocessor(data, training=True)
    return model.loss(prepped["inputs"], prepped["data_samples"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="HEAD",
                    help="git ref holding the pre-CMOLD detector file")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    from aodet.models.detectors.two_stream_yolox import TwoStreamYOLOX as New
    Old, lines_old = _load_baseline(args.ref)
    sha = subprocess.run(["git", "rev-parse", "--short", args.ref], cwd=REPO,
                         capture_output=True, text=True).stdout.strip()
    print(f"baseline: {args.ref} ({sha}), "
          f"{lines_old} lines, class {Old.__module__}")
    print(f"current : working tree, class {New.__module__}")

    ok = True
    for kind in ("b0", "b2"):
        torch.manual_seed(args.seed)
        old = Old(**_kwargs(kind))
        sd = {k: v.clone() for k, v in old.state_dict().items()}
        torch.manual_seed(args.seed + 7)      # different RNG stream on purpose
        new = New(**_kwargs(kind))
        new.load_state_dict(sd, strict=True)  # same weights, same buffers

        same_keys = set(sd) == set(new.state_dict())
        baseline_clean = not hasattr(old, "cmold_teacher")
        new_clean = new.cmold_teacher is None and new.cmold_cfg is None

        data = _batch()
        lo = _run(old, data)
        ln = _run(new, data)

        print(f"\n[{kind}] state_dict keys identical: {same_keys}; "
              f"params={sum(p.numel() for p in new.parameters())}; "
              f"baseline has cmold attr: {not baseline_clean}; "
              f"new model idle: {new_clean}")
        print(f"[{kind}] loss terms: {len(lo)} vs {len(ln)}")
        ok &= same_keys and set(lo) == set(ln) and baseline_clean and new_clean
        ok &= not any(k.startswith("cmold/") for k in ln)
        worst = 0.0
        for k in lo:
            eq = bool(torch.equal(lo[k], ln[k]))
            d = float((lo[k] - ln[k]).abs().max()) if k in ln else float("inf")
            worst = max(worst, d)
            ok &= eq
            print(f"  {k:<28} old={float(lo[k]):.8e}  new={float(ln[k]):.8e}  "
                  f"bitwise_equal={eq}")
        print(f"[{kind}] max |old-new| over all terms: {worst:.3e}")

    print("\nRESULT:", "NO-OP PROVEN (bitwise identical, no cmold key)"
          if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
