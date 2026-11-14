# 4081对单模态baseline方案严重问题审查

2026-11-13。用户要求审查既定camera-M/sonar-S首轮方案。仅检查现有源码、train/val COCO与录音级表；没有训练、推理、打开test图像或逐帧test COCO。保留现有划分和首轮配方，本文记录问题，不静默改历史。

## 判断

两臂结构、COCO起点、batch8、200epoch、单seed及固定final raw可用于本数据上的首轮受控baseline，没有从方案层面发现必须推倒重来的矛盾。不能把这等同于已验证新版训练实现，亦不能仅据此声称论文级充分比较或部署泛化。

### 1. 已确认：类别与声呐尺寸强混杂

本轮直接按COCO images/annotations/category_id复算：

| role | bomb | mortar | grenade |
|---|---|---|---|
| train | 128×780:773；128×603:115；128×771:78 | 128×441:800 | 128×441:706 |
| val | 128×780:241；128×603:69 | 128×441:272 | 128×441:312 |

因此新版依然可凭原图尺寸完美区分bomb/非bomb。按现AOPairedResize取整后，640高的有效条带宽分别约105/136/106/186，剩余区域固定补边；张量统一640×640不消除这个类别相关线索。这里确认的是数据关联，不是网络实际使用shortcut的证明。

keep_ratio保留raw数组长宽比，不等于米制物理等比例。不能因图像细长就直接认定必须拉伸；将来如做输入几何或padding线索控制，须另登记版本，保持监督和逆变换自洽。单纯stretch也不能认证移除全部采集设置混杂。

按名义等比例计算，train最窄GT框约20.75px，val约30.48px；train/val没有缩至宽<8px的GT框。因此不能仅凭大片padding断言该方案已把目标缩没或无法训练，实际有效分辨率与泛化影响尚未测量。

### 2. 已确认：旧脚本不是新版执行脚本

- `tools/prepare_camera_baseline.py`固定旧1800/600成员、旧数据根，CLASSES为bomb/grenade/mortar。新版COCO为bomb/mortar/grenade；转换及预测反映射必须统一，不可从旧脚本复制一半映射。
- `tools/run_camera_recording_m.py`读取旧camera_recording_baseline、旧split，断言(8,3,384,640)，元数据45000iter，并加载checkpoint.state_dict后命名raw；历史已有EMA身份错误。新版要求fixed640和61800iter，raw须按当前实际保存实现判定字段。
- `tools/run_workstation_baseline.py`同样固定旧trainval路径和S结构；不能用旧命令声称执行新版M/S。
- `AOLoadPaired`遇不存在路径会返回None而非立即报错。准备阶段及实际loader必须检查本模态每张图均加载、整epoch样本数正确，不只做一次首batch检查。

这些是执行前必须解决的兼容性问题；目前尚无新版run，不能声称新版实际已发生类别错位或raw加载错误。

### 3. 已确认：样本筛选不能评价无目标误报

本轮四份train/val COCO均每图一个GT框：camera与sonar各2472train/894val。AP仍能惩罚这些有目标图中的额外预测，但没有纯背景图，无法据此估计无目标水域误报率或完整连续视频运行表现。背景/未决图不能直接当负样本；仅在需要部署误报结论时另建有来源、目标确实缺席的独立验证材料。当前不要求重建数据集或重开原test。

### 4. 场景计数不等于充分覆盖

train八场景实际计数：bomb standard L_to_R627、standard flyby146、floor ellipse115、floor flyby78；mortar standard L_to_R784、flyby16；grenade standard L_to_R598、flyby108。mortar flyby占train约0.65%，每epoch按帧均匀取样时只出现16次，200epoch重复不产生新的独立录音。

val只有六场景；普通bomb flyby与floor bomb flyby没有独立val，mortar flyby仅20帧一个来源。维持用户已确认的split，不凭覆盖不足再次重分；结果按实际场景数和来源组报告。不能用train自评认证train-only场景泛化。val894帧来自9录音/7来源组，置信区间不能按894独立样本计算。

### 5. 无增广与final raw是有效设计选择，但不能冒充优化后的官方配方

YOLOX官方Exp含图像增广、EMA等配置：https://github.com/Megvii-BaseDetection/YOLOX/blob/main/yolox/exp/yolox_base.py 。当前方案刻意无增广并固定epoch200 raw，适合建立可审计对照；不支持声称这是该模型的最佳性能。已有旧camera-S train100%与val落差提示需关注过拟合，但不证明新版M一定过拟合，也不构成直接复制全部COCO增广到raw声呐的理由。

固定final/raw不用改成best/EMA才算正确。主结果沿用既定选择，EMA固定同epoch单列，保存每10epoch的val曲线；后续如切换选择规则或新增一种增广，另版统一比较。不得看test后挑权重。

### 6. “沿用配置”需落实的细节

当前本地配方无mean/std归一化，BGR 0–255输入，norm/bias不作weight decay；这些必须保留并记录。LR warmup0–5，cosine begin5/end185且T_max185，恒定185–200；cosine实际180epoch区间，并非恰好完成T_max，尾值不应写成精确eta_min。该差异并非当前已知严重训练故障；保留实际LR轨迹，不静默修配方后仍称完全沿用。

新版200epoch×309step=61800次更新，旧版45000，不能把新旧表现差全归因于数据。M/S预训练来源不同，不能用两模态差值作纯容量结论。单seed不支持稳定性或显著提升。

## 本轮通过的有限检查

四份train/val COCO引用图片全部存在（未重新逐图解码或重做全量hash）；框均在各自原生边界内；录音表train17/val7来源组互斥；类别和尺寸统计来自当前COCO。未执行新版实际加载器、GPU前后向、权重严格加载、标注视觉复审或专家准确率评估，不能把这些写成已通过。

## 建议

不推翻当前两臂设计。实施前解决新版数据适配、类别映射、画布、预处理和真实raw身份并完成已登记预检；保留尺寸混杂及正样本筛选的解释边界；补逐场景val与训练曲线。扩展成论文主比较时，再加预登记的泛化配方对照和多seed。标注助手来源与物理同步不确定性沿用既有披露，单模态训练不以新增精密跨模态注册为前置门槛。
