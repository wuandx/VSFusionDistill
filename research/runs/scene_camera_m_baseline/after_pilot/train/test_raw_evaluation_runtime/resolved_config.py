_YOLOX_S_COCO = 'https://download.openmmlab.com/mmdetection/v2.0/yolox/yolox_s_8x8_300e_coco/yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth'
_backbone = dict(
    deepen_factor=0.33,
    init_cfg=dict(
        checkpoint=
        'https://download.openmmlab.com/mmdetection/v2.0/yolox/yolox_s_8x8_300e_coco/yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth',
        prefix='backbone.',
        type='Pretrained'),
    out_indices=(
        2,
        3,
        4,
    ),
    type='CSPDarknet',
    widen_factor=0.5)
_backbone_s = dict(
    deepen_factor=0.33,
    out_indices=(
        2,
        3,
        4,
    ),
    type='CSPDarknet',
    widen_factor=0.5)
_head = dict(
    feat_channels=128, in_channels=128, num_classes=3, type='YOLOXHead')
_head_s = dict(
    feat_channels=128, in_channels=128, num_classes=3, type='YOLOXHead')
_neck = dict(
    in_channels=[
        128,
        256,
        512,
    ],
    init_cfg=dict(
        checkpoint=
        'https://download.openmmlab.com/mmdetection/v2.0/yolox/yolox_s_8x8_300e_coco/yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth',
        prefix='neck.',
        type='Pretrained'),
    num_csp_blocks=1,
    out_channels=128,
    type='YOLOXPAFPN')
_neck_s = dict(
    in_channels=[
        128,
        256,
        512,
    ],
    num_csp_blocks=1,
    out_channels=128,
    type='YOLOXPAFPN')
_yolox_s_ckpt = 'https://download.openmmlab.com/mmdetection/v2.0/yolox/yolox_s_8x8_300e_coco/yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth'
auto_scale_lr = dict(base_batch_size=8, enable=False)
base_lr = 0.00125
custom_hooks = [
    dict(
        ema_type='ExpMomentumEMA',
        momentum=0.0001,
        priority=49,
        type='EMAHook',
        update_buffers=True),
    dict(type='FiniteCameraLossHook'),
    dict(type='SceneWeightIdentityHook'),
    dict(
        data_root=
        '/mnt/d/agent_workspace/水下/声呐目标检测_workflow/DataSet/scene_expanded_baseline_trainval',
        interval=10,
        modality='camera',
        type='ScenePeriodicValHook'),
]
custom_imports = dict(
    allow_failed_imports=False,
    imports=[
        'aodet.datasets',
        'aodet.models',
        'aodet.engine',
        'camera_baseline_runtime',
        'scene_baseline_runtime',
    ])
data_root = '/mnt/d/pby/uxo-full/paired'
dataset_type = 'FrameSplitPairedSonarCameraDataset'
default_hooks = dict(
    checkpoint=dict(
        interval=10, max_keep_ckpts=2, save_last=True, type='CheckpointHook'),
    logger=dict(interval=50, type='LoggerHook'),
    param_scheduler=dict(type='ParamSchedulerHook'),
    sampler_seed=dict(type='DistSamplerSeedHook'),
    timer=dict(type='IterTimerHook'))
default_scope = 'mmdet'
env_cfg = dict(
    cudnn_benchmark=False,
    dist_cfg=dict(backend='nccl'),
    mp_cfg=dict(mp_start_method='fork', opencv_num_threads=0))
experiment_name = 'scene_camera_m_baseline'
img_scale = (
    640,
    640,
)
keep_ratio = True
known_deviations = dict(
    classes=[
        '100lbs_aircraft_bomb',
        'mortar_shell',
        'incindiary_grenade',
    ],
    data='4081-pair accepted split: train/val only',
    geometry='keep_ratio fixed640 right/bottom114',
    initialization='COCO backbone/neck; random 3-class head',
    primary_weights='epoch200 raw verified against live model at save')
load_from = None
log_level = 'INFO'
log_processor = dict(by_epoch=True, type='LogProcessor', window_size=50)
max_epochs = 200
model = dict(
    camera_backbone=dict(
        deepen_factor=0.67,
        init_cfg=dict(
            checkpoint=
            '/mnt/d/agent_workspace/水下/声呐目标检测_workflow/assets/checkpoints/yolox_m_coco_backbone_neck.pth',
            prefix='backbone.',
            type='Pretrained'),
        out_indices=(
            2,
            3,
            4,
        ),
        type='CSPDarknet',
        widen_factor=0.75),
    camera_head=dict(
        feat_channels=192, in_channels=192, num_classes=3, type='YOLOXHead'),
    camera_neck=dict(
        in_channels=[
            192,
            384,
            768,
        ],
        init_cfg=dict(
            checkpoint=
            '/mnt/d/agent_workspace/水下/声呐目标检测_workflow/assets/checkpoints/yolox_m_coco_backbone_neck.pth',
            prefix='neck.',
            type='Pretrained'),
        num_csp_blocks=2,
        out_channels=192,
        type='YOLOXPAFPN'),
    data_preprocessor=dict(
        bgr_to_rgb=False,
        mean=None,
        pad_size_divisor=32,
        pad_value=114.0,
        std=None,
        type='PairedDataPreprocessor'),
    fused_sonar_head=None,
    fusion=dict(type='NoneFusion'),
    loss_weights=dict(camera=1.0, fused_sonar=0.0, uncoupled_sonar=0.0),
    sonar_backbone=dict(
        deepen_factor=0.33,
        init_cfg=None,
        out_indices=(
            2,
            3,
            4,
        ),
        type='CSPDarknet',
        widen_factor=0.5),
    sonar_neck=dict(
        in_channels=[
            128,
            256,
            512,
        ],
        init_cfg=None,
        num_csp_blocks=1,
        out_channels=128,
        type='YOLOXPAFPN'),
    test_cfg=dict(
        max_per_img=100,
        min_bbox_size=0,
        nms=dict(iou_threshold=0.65, type='nms'),
        nms_pre=1000,
        score_thr=0.01),
    train_cfg=dict(
        assigner=dict(
            candidate_topk=10, center_radius=2.5, type='SimOTAAssigner')),
    type='TwoStreamYOLOX',
    uncoupled_sonar_head=None)
num_classes = 3
num_last_epochs = 15
optim_wrapper = dict(
    clip_grad=dict(max_norm=35, norm_type=2),
    optimizer=dict(
        lr=0.00125,
        momentum=0.9,
        nesterov=True,
        type='SGD',
        weight_decay=0.0005),
    paramwise_cfg=dict(bias_decay_mult=0.0, norm_decay_mult=0.0),
    type='OptimWrapper')
paired_root = '/mnt/d/pby/uxo-full/paired'
param_scheduler = [
    dict(
        begin=0,
        by_epoch=True,
        convert_to_iter_based=True,
        end=5,
        type='QuadraticWarmupLR'),
    dict(
        T_max=185,
        begin=5,
        by_epoch=True,
        convert_to_iter_based=True,
        end=185,
        eta_min=6.25e-05,
        type='CosineAnnealingLR'),
    dict(begin=185, by_epoch=True, end=200, factor=1, type='ConstantLR'),
]
randomness = dict(deterministic=False, seed=0)
resume = False
split_file = '/mnt/d/pby/uxo-full/repro/frame_split.json'
teacher_checkpoint = 'work_dirs/repro_cmold_teacher/t_camera_s/epoch_200.pth'
test_cfg = None
test_dataloader = None
test_evaluator = None
test_pipeline = [
    dict(type='AOLoadPaired'),
    dict(
        camera_size=(
            640,
            640,
        ),
        keep_ratio=True,
        sonar_size=(
            640,
            640,
        ),
        type='AOPairedResize'),
    dict(type='AOPackPairedInputs'),
]
train_cfg = dict(max_epochs=200, type='EpochBasedTrainLoop', val_interval=10)
train_dataloader = dict(
    batch_size=8,
    collate_fn=dict(type='pseudo_collate'),
    dataset=dict(
        ann_file=
        '/mnt/d/agent_workspace/水下/声呐目标检测_workflow/DataSet/scene_expanded_baseline_trainval/camera-train-dataset.json',
        pipeline=[
            dict(type='AOLoadPaired'),
            dict(
                camera_size=(
                    640,
                    640,
                ),
                keep_ratio=True,
                type='AOPairedResize'),
            dict(type='AOPackPairedInputs'),
            dict(type='SceneFixedCanvas'),
        ],
        serialize_data=False,
        type='SceneSingleModalDataset'),
    num_workers=2,
    persistent_workers=True,
    sampler=dict(shuffle=True, type='DefaultSampler'))
train_pipeline = [
    dict(type='AOLoadPaired'),
    dict(
        camera_size=(
            640,
            640,
        ),
        keep_ratio=True,
        sonar_size=(
            640,
            640,
        ),
        type='AOPairedResize'),
    dict(allow=True, prob=0.0, type='AOPairedSyncFlip'),
    dict(type='AOPackPairedInputs'),
]
val_cfg = None
val_dataloader = None
val_evaluator = None
vis_backends = [
    dict(type='LocalVisBackend'),
]
visualizer = dict(
    name='visualizer',
    type='DetLocalVisualizer',
    vis_backends=[
        dict(type='LocalVisBackend'),
    ])
warmup_epochs = 5
work_dir = '/mnt/d/agent_workspace/水下/声呐目标检测_workflow/runs/scene_camera_m_baseline/after_pilot/train/test_raw_evaluation_runtime'
