# camera-only：新增录音与增广的train/val对照

用户再次明确要求增加录音并验证覆盖和增广影响。本轮执行数据扩充和审核，随后按此协议开展训练；先完成准入、实现与GPU预检，不以未审候选直接训练。

目的：在固定val894与现有test715成员不动的条件下，区分更多独立相机录音与训练增广带来的收益。camera-only不再要求新样本先有可用声呐框；新增相机数据不冒称paired数据。

四项对照：camera_coverage_original_plain（原train2472、无增广）；camera_coverage_expanded_plain（扩充train、无增广）；camera_coverage_original_aug（原train、增广）；camera_coverage_expanded_aug（扩充train、同一增广）。同一COCO YOLOX-M起点、batch8、seed0、640等比补边114、最终实际raw。已有原train200epoch结果保留，不能把不等优化步数的新旧结果直接当计算量受控因果比较。

训练前冻结共同61800次更新及同一按更新步数定义的LR计划；先在小批量验证增广与框变换，val保持无增广。拟用水平翻转p=.5、亮度/对比度扰动、温和尺度平移；具体参数与图像/框验证结果须在启动前落盘，不引入Mosaic/MixUp或会翻转重力方向的垂直翻转。所有四项使用同预算，数据量不同时披露实际等效epoch。不得加载旧UXO权重续训。原train无增广如完整复用旧结果，必须证明优化步数和LR计划逐步一致，否则重跑。

扩充规则：审核94条元数据；仅当前三类、非原研究test、非当前val/test来源组，复用已修复的SD时间映射和原SD框。先从有原标签的10条提案，每条最多100个时间均匀且SD索引唯一的有效框样本。坐标越界/缺SD明确登记，不自动clip；样本准入以修正后的逐图审核为准。4条有相机但无框另列待标注，不把它们当背景负样本。原21条训练录音及其2472帧全部保留。本轮不借用val/test标签或预测选择新增训练帧。

source group：除当前冻结组外，在全部94条metadata上按相同非空gopro_file/gantry_file构建连通分量，检查间接关联；任何连接当前val/test或原研究test的候选停止纳入。跨角色图像hash复核，只读取已授权train/val副本；当前test仅用已存hash元数据，不新增内容访问。

判定：主指标pooled val mAP@[.5:.95]，同时报AP50/AP75、每类AP/AR1、逐录音和场景pooled指标，记录最差来源变化及train自评。至少+1个百分点作为值得复核的探索性增益，不把单seed当显著性；增广收益分别在原数据和扩充数据上比较，交互效应另列。覆盖表按class/placement/trajectory以及z/tilt/roll与来源组数报告，不把8宽场景覆盖当细条件完整。

停止条件：新增heldout关联、图像/框身份/hash不一致、非有限loss/梯度、OOM、raw/EMA身份不能认证、增广后框变换不通过。失败产物保留，不自动改配方。test不参与本轮选择，也不自动再评价。

## 启动前实施细化

实际扩充为9条×100张=900张，camera-only train3372张/30条/26个现有规则下的来源组，val894张/9条/7组原字节不变。全部36张概览900帧已由助手查看并接受，沿用可辨认截断政策；非专家标注认证。原2472帧及全部原框不变，像素hash/解码、标签hash、跨train/val与已有test哈希元数据重复检查通过。173615的797个候选框全部数值越界，本批不clip；另4条缺原标签继续列待标注。

计算量实现：每个epoch按seed+epoch生成全训练身份的randperm，取2472个不同样本，200epoch×309次更新=61800。原集长度2472时与原DefaultSampler顺序一致；扩充集每epoch随机取2472/3372而非额外训练200个完整大epoch，累计约146.62次全扩充集等效遍历。所有variant的LR配置及loader长度相同。新增2条mortar flyby使该场景训练来源1→3、帧16→216；不是新增宽场景，主要增加已有场景内来源和细条件。

增广最终冻结：水平翻转p=.5；以图中心缩放[.9,1.1]，平移±5%图宽高；若新变换会截断原框则最多20次重采样，仍失败则保留恒等几何（可翻转），不裁GT；contrast[.8,1.2]、brightness[-20,20]，BGR像素clip到[0,255]。仿射外填114，之后沿用640等比补边。val无增广。独立翻转已知坐标、翻转两次恢复像素/框、已知仿射坐标控制及实际增广batch前后向需通过。

实现为workflow-local run_camera_coverage.py、camera_coverage_runtime.py；旧脚本和原研究不改。一张16GB GPU，三个新增M实验顺序执行，先expanded_plain、再original_aug、再expanded_aug，各自先GPU preflight，通过后从COCO fresh训练。原original_plain沿用既有after_pilot结果前，核对关键模型/优化器/LR/采样顺序与初始权重、数据、源码一致；若不一致则补重跑。队列任一失败停止，不自动重启。不自动评价test。
