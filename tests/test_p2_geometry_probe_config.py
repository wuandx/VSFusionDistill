"""Config tests for the P2 geometry probe (t_camera_s_stretch_yoloxs.py).

The probe is only worth running if it changes exactly one thing.  These
checks pin that: same model, same init, same optimiser and schedule, same
split and data root, same pad value, and a pipeline that differs from the
letterbox arm in keep_ratio alone.  CPU only, no training started.

Run: ./.venv/bin/python -m pytest tests/test_p2_geometry_probe_config.py -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mmengine.config import Config  # noqa: E402

CFG = os.path.join("configs", "repro_cmold", "teachers")
LETTERBOX = os.path.join(CFG, "t_camera_s_yoloxs.py")
STRETCH = os.path.join(CFG, "t_camera_s_stretch_yoloxs.py")

IMG_SHAPE = (640, 640)


def _load(path):
    return Config.fromfile(path)


def _plain(obj):
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def test_inherits_the_letterbox_arm_directly():
    """One _base_ line: the comparison is against that exact run."""
    import ast

    with open(STRETCH, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=STRETCH)
    bases = [ast.literal_eval(node.value) for node in tree.body
             if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "_base_"
                     for t in node.targets)]
    assert bases == [["t_camera_s_yoloxs.py"]]


@pytest.mark.parametrize("loader", ["train_dataloader", "test_dataloader"])
def test_only_keep_ratio_moves(loader):
    """Same transforms in the same order, geometry flag flipped."""
    mine = _plain(_load(STRETCH)[loader].dataset.pipeline)
    theirs = _plain(_load(LETTERBOX)[loader].dataset.pipeline)

    assert [t["type"] for t in mine] == [t["type"] for t in theirs]
    for step, ref in zip(mine, theirs):
        if step["type"] != "AOPairedResize":
            assert step == ref, step["type"]
            continue
        assert tuple(step["camera_size"]) == IMG_SHAPE
        assert tuple(step["sonar_size"]) == IMG_SHAPE
        assert step["keep_ratio"] is False
        assert ref["keep_ratio"] is True
        # same sizes in both arms, so the flag is the only difference
        assert step["camera_size"] == ref["camera_size"]
        assert step["sonar_size"] == ref["sonar_size"]


def test_everything_else_is_identical():
    """No silent second variable: recipe, model, data wiring, hooks."""
    cfg, ref = _load(STRETCH), _load(LETTERBOX)

    assert _plain(cfg.model) == _plain(ref.model)
    assert _plain(cfg.optim_wrapper) == _plain(ref.optim_wrapper)
    assert _plain(cfg.param_scheduler) == _plain(ref.param_scheduler)
    assert _plain(cfg.custom_hooks) == _plain(ref.custom_hooks)
    assert _plain(cfg.train_cfg) == _plain(ref.train_cfg)
    assert _plain(cfg.test_cfg) == _plain(ref.test_cfg)
    assert cfg.val_cfg is None

    mine = dict(_plain(cfg.train_dataloader.dataset))
    theirs = dict(_plain(ref.train_dataloader.dataset))
    mine.pop("pipeline"), theirs.pop("pipeline")
    assert mine == theirs
    assert cfg.train_dataloader.batch_size == ref.train_dataloader.batch_size

    mine_t = dict(_plain(cfg.test_dataloader.dataset))
    theirs_t = dict(_plain(ref.test_dataloader.dataset))
    mine_t.pop("pipeline"), theirs_t.pop("pipeline")
    assert mine_t == theirs_t
    assert cfg.test_dataloader.dataset.split == "val"

    # pad value stays: with keep_ratio=False it simply never fires
    assert _plain(cfg.model.data_preprocessor) == _plain(
        ref.model.data_preprocessor)


def test_checkpoint_goes_to_its_own_directory():
    """No rung may load this arm by accident."""
    cfg, ref = _load(STRETCH), _load(LETTERBOX)
    assert cfg.teacher_checkpoint != ref.teacher_checkpoint
    assert cfg.teacher_checkpoint.endswith("/epoch_200.pth")
    assert "t_camera_s_stretch" in cfg.teacher_checkpoint
    for rung in ("r2_cmold_yoloxs.py", "r3a_obj_only.py", "r3b_cls_only.py"):
        block = _load(os.path.join("configs", "repro_cmold", rung)).model
        named = block.get("cmold", {}).get("teacher_ckpt")
        assert named == ref.teacher_checkpoint, rung


def test_deviation_is_registered_with_the_run():
    """The log config must say what this arm is and what it is not."""
    dev = _plain(_load(STRETCH).known_deviations)
    for key in ("mosaic_mixup", "sync_flip", "multiscale", "teacher_init",
                "geometry_probe"):
        assert key in dev, key
    assert "not a rung" in dev["geometry_probe"]
    assert dev["teacher_init"].startswith("COCO")


def test_config_stays_within_79_columns():
    with open(STRETCH, encoding="utf-8") as f:
        wide = [(i, len(line.rstrip("\n"))) for i, line in enumerate(f, 1)
                if len(line.rstrip("\n")) > 79]
    assert not wide, wide
