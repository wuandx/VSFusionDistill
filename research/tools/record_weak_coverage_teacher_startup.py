"""Register a launch only after matching preflight and real optimizer logs exist."""
from expand_paired_recording_pool import *
from datetime import datetime,timezone
import shutil

BASE=ROOT/'runs/weak_coverage_camera_m_teacher'
DATASET=ROOT/'DataSet/camera_weak_coverage_trainval'


def prepend(path,marker,note):
    previous=path.read_text(encoding='utf-8')
    if marker not in previous:path.write_text(note+'\n\n'+previous,encoding='utf-8')


def main():
    p=read(BASE/'preflight/status.json');s=read(BASE/'train/status.json')
    assert p['status']=='preflight_passed' and s['status'] in ('training','completed')
    for k in ['dataset_sha256','freeze_sha256','initialization_sha256','source_sha256','implementation_sha256','configuration_semantics_sha256']:
        assert p[k]==s[k]
    text=(BASE/'train.log').read_text(encoding='utf-8',errors='replace')
    lines=[line for line in text.splitlines() if 'Epoch(train)' in line and 'loss:' in line]
    assert lines,'No actual optimizer logs; do not call training started'
    last=lines[-1];match=re.search(r'Epoch\(train\)\s*\[(\d+)\]\[\s*(\d+)/(\d+)\]',last)
    assert match and int(match[3])==518 and int(match[2])>0,last
    assert not re.search(r'loss:\s*(nan|inf)\b',last,re.I)
    assert s['epochs']==200 and s['train_images']==4138 and s['val_images']==573
    assert sha(DATASET/'files-sha256.json')==s['dataset_sha256']
    verify=read(DATASET/'verification.json');freeze=read(BASE/'dataset-freeze.json')
    evidence=dict(verified_at=datetime.now(timezone.utc).isoformat(),training_started=True,
        name=s['name'],service='weak-coverage-camera-m-teacher.service',
        actual_train_epoch=int(match[1]),actual_iteration_in_epoch=int(match[2]),iterations_per_epoch=518,
        latest_optimizer_log=last,preflight_passed=True,preflight_train_semantics_hash_match=True,
        checks=p['checks'],train_images=4138,val_images=573,epochs=200,total_updates=103600,
        checkpoint_initialization='fresh COCO-M backbone/neck, no UXO resume',
        frozen_initialization_sha256=s['initialization_sha256'],dataset_sha256=s['dataset_sha256'],
        source_repo_read_only_hashes_match_preflight=True,only_camera_input=True,
        augmentation=False,sonar_training=False,test_content_read=False,automatic_restart=False,
        observed_log_lines=lines[-3:])
    save(BASE/'startup-verification.json',evidence)
    (BASE/'README.md').write_text('''# camera-only YOLOX-M教师：weak_coverage_camera_m_teacher

用户已确认并授权使用paired_weak_scene_coverage_pan_split。冻结camera4138 train/573 val，33/5录音27/5保守组；仅camera图像载入。数据副本：DataSet/camera_weak_coverage_trainval/。冻结详情dataset-freeze.json；训练前真实GPU预检和正式迭代证据startup-verification.json。

COCO-M backbone/neck fresh初始化，随机3类head；200epoch、batch8、seed0，无增广，SD640×360 keep_ratio+右底pad114到640。每epoch518更新（末batch2），共103600更新。SGD/LR/epoch schedule沿用前camera-M；与旧2472/894同时改变数据与更新总量，不作单因素收益结论。

主结果epoch200 actual raw，EMA另存。每10epoch raw val监测，最终val包含pooled/逐类/逐录音；未按best或EMA换主权重。test不复制/载入/评价，不启动sonar。旧val/test使用史保持，新val只有5组且3种场景无val，不称外部盲测。

服务weak-coverage-camera-m-teacher.service，WSL user systemd，Restart=no。launch-status.json是队列阶段；train/status.json是模型阶段，train.log与train/下MMEngine日志反映真实进度。状态configured、preflight_passed或training初始化不是完成，查看实际Epoch(train)迭代。失败保留日志且不自动改配方重启；完成后train/raw_epoch_200.pth、ema_epoch_200.pth和val_actual_raw_epoch200/。
''',encoding='utf-8')
    (BASE/'provenance').mkdir(exist_ok=True)
    for name in ['prepare_weak_coverage_camera_training.py','run_weak_coverage_camera_teacher.py',
        'weak_coverage_teacher_runtime.py','launch_weak_coverage_camera_teacher.py','record_weak_coverage_teacher_startup.py']:
        shutil.copyfile(ROOT/'tools'/name,BASE/'provenance'/name)
    shutil.copyfile(ROOT/'experiment/archive/weak-coverage-camera-m-training-plan.md',BASE/'provenance/plan.md')
    note='''## 2026-11-14 用户确认后仅camera YOLOX-M教师正式训练已启动

用户“确定好数据集就开始训练吧先只训练教师模型的相机，yoloxm”，按[预登记](experiment/archive/weak-coverage-camera-m-training-plan.md)冻结已交付paired_weak_scene_coverage_pan_split，camera-only teacher新run [weak_coverage_camera_m_teacher](runs/weak_coverage_camera_m_teacher/README.md)。camera4138train/573val（33/5录音、27/5组），COCO-M fresh backbone/neck、随机3类head、seed0/batch8/200epoch、518更新/epoch共103600，无增广、keep_ratio fixed640右底114。SGD/LR/epoch schedule沿用原camera-M；数据与总更新数变动必须披露。新增393助手标注血缘单列，原图/框/角色不变，test不复制或载入，无sonar或KD启动。

4711相机图+血缘JSON/hash/解码/原框/COCO身份/组互斥通过，GPU预检batch8前后向/推理/逆几何/COCO张量严格载入/raw–EMA往返与最后batch2 loss/梯度有限；preflight和train实现/源/输入/初始化/配置语义hash相同。持久WSL服务weak-coverage-camera-m-teacher.service (Restart=no)已产生真实Epoch(train)迭代、有限loss，见[startup-verification](runs/weak_coverage_camera_m_teacher/startup-verification.json)。当前实际日志位置{epoch}epoch内{iteration}/518；这是启动快照，后续进度读取train.log及train/status.json，未称完成或有新AP。

主结果固定epoch200实际raw；每10epoch监测val，EMA单独导出，沿用score.01/NMS.65/max100，不选best或切EMA。旧val/test开发使用史保持，val5组、floor ellipse/两bomb flyby缺留出，原研究10test仍关闭。原研究目录只读，旧run/队列不修改或恢复；本授权替代此前审计阶段禁启动训练，范围只本camera-M。当前启动不代表收敛或覆盖收益。
'''.format(epoch=match[1],iteration=match[2])
    marker='## 2026-11-14 用户确认后仅camera YOLOX-M教师正式训练已启动'
    prepend(ROOT/'handoff.md',marker,note)
    prepend(ROOT/'experiment/results.md',marker,note.replace('](experiment/','](../experiment/').replace('](runs/','](../runs/'))
    ev='''## 2026-11-14 用户确认数据并授权camera-M教师训练

冻结paired_weak_scene_coverage_pan_split的camera4138train/573val，在独立train/val副本训练；来源身份与配对集一致，[冻结](../runs/weak_coverage_camera_m_teacher/dataset-freeze.json)、[预登记](archive/weak-coverage-camera-m-training-plan.md)、[启动证据](../runs/weak_coverage_camera_m_teacher/startup-verification.json)。授权仅camera-only YOLOX-M，COCO fresh初始化、200epoch/batch8/seed0、每epoch完整4138样本/518更新共103600，无增广，主权重固定epoch200 actual raw；每10epoch监测raw val，EMA单列，不依据中间峰值换主权重。沿用原score.01/NMS.65/max100、各类AP/AR1和完整pooled/逐录音指标。

这更新旧“尚未授权训练”阶段；不恢复sonar/旧camera扩充队列，不授权test模型评价。仅相机train/val图像装载，test未复制或评价，原研究test关闭。新成员/迭代预算与旧版不同，旧AP不当单因素对照；旧开发使用、助手标注、来源少及场景缺留出的边界保持。
'''
    prepend(ROOT/'experiment/evaluation.md','## 2026-11-14 用户确认数据并授权camera-M教师训练',ev)
    print(dict(epoch=int(match[1]),iteration=int(match[2]),log=last),flush=True)


if __name__=='__main__':main()
