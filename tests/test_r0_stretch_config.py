"""Config test for the R0s geometry arm (r0_stretch_yoloxs.py).

The arm is only interpretable if it changes one thing.  These checks pin
that against r0_baseline_yoloxs.py: same model, optimiser, schedule, split,
loss weights, hooks; pipeline differs in keep_ratio alone.  CPU only.

Run: ./.venv/bin/python -m pytest tests/test_r0_stretch_config.py -q
"""

import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmengine.config import Config  # noqa: E402

CFG = os.path.join("configs", "repro_cmold")
R0 = os.path.join(CFG, "r0_baseline_yoloxs.py")
R0S = os.path.join(CFG, "r0_stretch_yoloxs.py")

IMG_SHAPE = (640, 640)


def _load(path):
    return Config.fromfile(path)


def _plain(obj):
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def test_inherits_r0_directly():
    with open(R0S, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=R0S)
    bases = [ast.literal_eval(node.value) for node in tree.body
             if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "_base_"
                     for t in node.targets)]
    assert bases == [["r0_baseline_yoloxs.py"]]


@pytest.mark.parametrize("loader", ["train_dataloader", "test_dataloader"])
def test_only_keep_ratio_moves(loader):
    mine = _plain(_load(R0S)[loader].dataset.pipeline)
    theirs = _plain(_load(R0)[loader].dataset.pipeline)

    assert [t["type"] for t in mine] == [t["type"] for t in theirs]
    flipped = 0
    for step, ref in zip(mine, theirs):
        if step["type"] != "AOPairedResize":
            assert step == ref, step["type"]
            continue
        flipped += 1
        assert tuple(step["camera_size"]) == IMG_SHAPE
        assert tuple(step["sonar_size"]) == IMG_SHAPE
        assert step["keep_ratio"] is False and ref["keep_ratio"] is True
    assert flipped == 1


def test_everything_else_is_identical():
    cfg, ref = _load(R0S), _load(R0)

    assert _plain(cfg.model) == _plain(ref.model)
    assert _plain(cfg.optim_wrapper) == _plain(ref.optim_wrapper)
    assert _plain(cfg.param_scheduler) == _plain(ref.param_scheduler)
    assert _plain(cfg.custom_hooks) == _plain(ref.custom_hooks)
    assert _plain(cfg.train_cfg) == _plain(ref.train_cfg)
    assert _plain(cfg.test_cfg) == _plain(ref.test_cfg)
    assert cfg.val_cfg is None
    assert _plain(cfg.model.loss_weights) == dict(
        camera=0.0, fused_sonar=0.0, uncoupled_sonar=1.0)
    assert _plain(cfg.model.data_preprocessor) == _plain(
        ref.model.data_preprocessor)

    for loader in ("train_dataloader", "test_dataloader"):
        mine = dict(_plain(cfg[loader].dataset))
        theirs = dict(_plain(ref[loader].dataset))
        mine.pop("pipeline"), theirs.pop("pipeline")
        assert mine == theirs, loader
    assert cfg.train_dataloader.batch_size == ref.train_dataloader.batch_size
    assert cfg.test_dataloader.dataset.split == "val"


def test_deviation_is_registered():
    dev = _plain(_load(R0S).known_deviations)
    for key in ("mosaic_mixup", "sync_flip", "multiscale", "geometry_probe"):
        assert key in dev, key
    assert "not a rung" in dev["geometry_probe"]


def test_no_rung_points_at_this_arm():
    """Nothing in the ladder may load r0_stretch's checkpoint by accident."""
    for name in ("r1_kd_yoloxs.py", "r2_cmold_yoloxs.py",
                 "r3a_obj_only.py", "r3b_cls_only.py"):
        text = open(os.path.join(CFG, name), encoding="utf-8").read()
        assert "r0_stretch" not in text, name


def test_config_stays_within_79_columns():
    with open(R0S, encoding="utf-8") as f:
        wide = [(i, len(line.rstrip("\n"))) for i, line in enumerate(f, 1)
                if len(line.rstrip("\n")) > 79]
    assert not wide, wide
