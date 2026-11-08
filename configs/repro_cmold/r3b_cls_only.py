"""R3b: CMOLD classification term only (paper Table 5 ablation, rung 3b).

Paper anchor (plan §0/§4): AP@[.50:.95] 0.771, AP75 0.796 -- the paper's own
ablation, i.e. R2 with the objectness term removed.  Against R3a (obj-only
0.794) this says the classification half is the weaker one, so the pair is
not redundant; against R2 (0.797) it says neither half alone reproduces the
full loss (plan §4).

Delta against r2_cmold_yoloxs.py: exactly one number --
obj_weight 0.5 -> 0.0.  cmold_kd.py drops a term whose weight is zero
(aodet/models/losses/cmold_kd.py:297) rather than scaling it, so the
objectness branch is absent from the loss dict.  Everything else -- student,
data, augmentation, 200-epoch schedule, teacher topology, teacher_ckpt,
routes, tau, score_thr, max_dets, topk -- is inherited unchanged.

Note for anyone touching this file: obj_weight=0 AND score_weight=0 together
degenerate to R0's loss (cmold_kd returns an empty dict, so the run is
bit-for-bit a no-KD run).  That is a useful sanity check, not a config to
train.
"""

_base_ = "./r2_cmold_yoloxs.py"

model = dict(
    cmold=dict(
        # α = 0: keep the classification term only
        obj_weight=0.0,
        score_weight=0.5,
    ),
)
