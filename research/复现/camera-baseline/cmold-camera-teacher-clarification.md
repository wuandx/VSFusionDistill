# CMOLD相机教师与YOLOX KD对照的区分

2026-11-11，针对用户引用重新直接读取本地paper.pdf全文，并渲染PDF第12页核查表3/5。无新训练。CMOLD公开LaTeX仍未取得；本次证据为PDF原文，不冒充tex。

- PDF第11页（印刷27349），§IV-B：Conventional YOLOX KD的教师为YOLOX-M、学生为YOLOX-S，二者仅用sonar训练。0.661→0.671是该sonar学生对照的AP变化，不能移作相机教师结果或型号证明。
- PDF第12页（27350），Table3：Teacher(Camera) AP@[.5:.95]=0.958、AP50=0.997；Table5是另一个不同方法的sonar比较表。
- PDF第7页（27345）§III-C描述跨模态teacher/student使用相同YOLOX architecture/input resolution；Fig6（PDF第8页）明确相机teacher在带标注RGB训练。没有据此明确给出camera teacher的S/M/L型号。全文YOLOX-M出现于前述sonar-only KD段落，不能把该配置迁移为camera事实。

实施选择：当前目标仍为SD camera-only teacher基线。暂沿用已有YOLOX-S作为我方主基线选择，不声称型号已严格复现CMOLD；如后续做M，应在相同数据/划分/配方下另立容量对照。当前先准备独立SD manifest、原始SD框坐标与覆盖核验，核清173615/175000的框范围及截断规则，冻结recording-level train/dev清单和采样后才进入模型训练。原研究只读、test关闭，不沿用旧已见全部37录音的UXO权重做未见录音主张。

原始材料：[paper.pdf（本地产物说明）](../../ARTIFACTS.md#artifact-b44090068078)、[本次第12页渲染（本地产物说明）](../../ARTIFACTS.md#artifact-99a14056bc38)。这是对既有审计结论的原文复核，不是新型号发现。
