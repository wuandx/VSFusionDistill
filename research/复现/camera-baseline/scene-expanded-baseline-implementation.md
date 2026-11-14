# 新版camera-M/sonar-S执行适配

2026-11-13。用户要求解决旧1800/600、旧类别顺序、M画布、raw/EMA身份、旧45000iter五项问题。按[预登记](../../experiment/archive/scene-expanded-baseline-implementation-plan.md)在工作流目录新增实现；原研究代码与历史训练入口/结果不覆盖，未启动200epoch正式训练。

## 五项修复

| 项目 | 新实现 |
|---|---|
| 数据 | `tools/prepare_scene_baselines.py`只读候选train/val COCO与录音级表，生成`DataSet/scene_expanded_baseline_trainval`独立副本；各模态2472train/894val |
| 类别 | 读取并严格验证COCO类别bomb/mortar/grenade=1/2/3，适配数据标签0/1/2，预测+1逆映射；不继承旧CLASSES |
| 画布 | `SceneFixedCanvas`在pack后仅补图像右/底，保持原img_shape和scale_factor，实际有效输入8×3×640×640；两模态均keep_ratio |
| 权重 | `SceneWeightIdentityHook`在EMA保存hook之后，将保存字段逐张量比对live raw模型及live EMA；checkpoint记录实际字段身份，最终导出明确`raw_epoch_200.pth`和`ema_epoch_200.pth` |
| 更新次数 | 从实际dataset长度、batch和epoch计算steps及总更新，并与实际loader长度核对；2472/8=309，200epoch共61800次；最终检查checkpoint epoch/iter |

训练入口`tools/run_scene_baseline.py`必须显式指定`--config-only`、`--preflight`或`--train`；默认不启动。camera-M使用已有作者转换COCO backbone/neck，sonar-S使用MMDetection COCO S，三类head随机，不用UXO权重。预处理BGR 0–255、无mean/std、norm/bias不衰减，其他已登记配方保持。每10epoch只监测val实际raw，不按AP选checkpoint。训练只接受与数据、初始化、实现、原研究源码hash一致的预检证明。

评测入口`tools/evaluate_scene_baseline.py`只允许train/val，显式`--kind raw|ema`，读取已标明身份的最终导出权重并检查父checkpoint hash，拒绝覆盖已有评价。正式训练结束自动评价epoch200 raw的val；EMA与train自评通过该独立入口另列。

## 数据与功能核验

- 准备阶段全量6732图像解码、原生尺寸/uint8/声呐灰度通道检查、源/副本hash一致、框范围、三类身份、双端成员一致及train17/val7来源组互斥通过；cross-role图像hash重复0。源四COCO与录音表hash保存。
- Windows独立核验6741个文件hash和源输入hash通过，未读test逐帧内容。首次核验命令使用Windows默认GBK读取UTF-8报告时失败，显式UTF-8后通过；没有改数据，问题保留在独立核验JSON。
- 实际RTX5060Ti / torch2.7.1+cu128 / mmengine0.10.7 / mmdet3.3.0下，camera-M和sonar-S的真实batch8前后向、有限loss、有效分支梯度、val推理、COCO参数逐项加载、类别与几何逆变换、实际checkpoint保存/加载raw身份均检查。结果见各`runs/scene_*_baseline/preflight/status.json`。
- camera逆变换最大误差0，sonar约3.052e-5像素；sonar的train四种尺寸及val三种尺寸、三类均进入固定8样本预检。
- checkpoint往返通过：在一次性预检模型上显式扰动raw参数令raw/EMA不同，实际保存后raw匹配live模型、EMA不同；本环境记录raw_field=`ema_state_dict`、ema_field=`state_dict`。正式保存每次重新比对，不将该字段关系无条件硬编码。
- `tools/check_scene_baseline_contracts.py`对两个模态各894val做真正评测器控制：完美GT预测mAP1.0，循环错类别预测mAP0.0；缺失图片在dataset构建阶段拒绝，未标明身份的权重拒绝。详见`runs/scene_expanded_baseline_controls/checks.json`，这些是合成预测控制，不是训练模型AP。
- 初次M/S预检完成后，仅将更新次数元数据改为从实际配置/样本量推导并纳入独立评测脚本hash；初次产物保留`preflight_initial`，最终代码重新预检到`preflight`。无正式训练或旧结果覆写。

## 执行命令（记录，未执行正式训练）

在本机WSL，Python为`/home/ty/mycode/VSFusionDistill/.venv-gpu/bin/python`。下面均在WSL中运行，根目录路径保持实际值：

```bash
task_root=/mnt/d/agent_workspace/水下/声呐目标检测_workflow
task_repo=/mnt/d/agent_workspace/水下/声呐目标检测/code/VSFusionDistill
task_python=/home/ty/mycode/VSFusionDistill/.venv-gpu/bin/python

# 正式训练：本轮未执行；预检已保存在默认路径
"$task_python" -B "$task_root/tools/run_scene_baseline.py" --modality camera --repo "$task_repo" --checkpoint "$task_root/assets/checkpoints/yolox_m_coco_backbone_neck.pth" --train
"$task_python" -B "$task_root/tools/run_scene_baseline.py" --modality sonar --repo "$task_repo" --checkpoint /home/ty/.cache/torch/hub/checkpoints/yolox_s_8x8_300e_coco_20211121_095711-4592a793.pth --train

# 训练完成后，EMA另列；raw val已由训练入口自动评价
"$task_python" -B "$task_root/tools/evaluate_scene_baseline.py" --run-dir "$task_root/runs/scene_camera_m_baseline/train" --split val --kind ema
"$task_python" -B "$task_root/tools/evaluate_scene_baseline.py" --run-dir "$task_root/runs/scene_sonar_s_baseline/train" --split train --kind raw
```

换机器需显式指定源码、COCO权重和已复制数据根，重做本机预检；数据清单本身可迁移，不使用其中来源绝对路径加载。已有run目录拒绝覆盖。完整checkpoint保留优化器/scheduler等，当前新入口只提供fresh train，不声称已验证长时中断resume。

## 边界

预检没有运行优化器训练循环、没有新模型AP、没有test访问。已接受框未被重新标注或专家认证；尺寸—类别混杂、正样本筛选分布和flyby独立留出缺口继续披露。原候选protocol中的历史状态不静默重写，当前独立执行副本按明确用户指令准备。

文献对尺寸/补边的核对见[单独记录](sonar-input-size-literature.md)：通用YOLOX确实采用等比例缩放+114右底补边，CMHD只明确640统一resize，CMOLD具体resize规则不明，UATD明确高512/宽按比例。这些不能作为已消除本数据类别—设置混杂的证据。
