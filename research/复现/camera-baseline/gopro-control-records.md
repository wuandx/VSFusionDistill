# 原始设置、标定与AprilTag尺寸/布局记录追查

2026-11-11，`gopro_control_records`，[执行前登记](../../experiment/archive/gopro-control-records-plan.md)。**本轮仍未取得足以认证旧录音的原始设置/水下标定/marker实测布局；已完成具体来源排查，并准备了未发送的作者询问草稿。** 不运行没有独立依据的同步/姿态优化。

## 新增检查及边界

1. **本地processed原包完整成员目录。** 对`D:/pby/data_processed.7z`（61,513,277,947 B）只读7z目录，198,915项；含98,937 PGM、98,937 PNG、386 CSV、210 YAML、228 MP4及目录。未提取成员或解码样本；目录命名检索未发现calibration/apriltag/checkerboard/intrinsic/camera_info/marker/cube、ROS bag或独立GPMF文件。210个YAML均属ARIS目录的配置/标记类文件；不能因此断言所有CSV/YAML内容都不含任何线索，本轮未打开全体文件，尤其没有读取其他录音或test内容。没有从目录找到未裁剪相机文件或原始标定工程。见[完整目录（本地产物说明）](../../ARTIFACTS.md#artifact-a00833fc2351)与[摘要](../../related_work/gopro-control-records/processed-archive-summary.json)。这不是重新MD5核验61.5GB归档。
2. **公开calibration/model包目录。** 已核验发布包calibration只有4份模式参数和transforms.yaml；model包只有4种目标OBJ/MTL/JPG，没有cube CAD、marker布局/有效边长表。复用已保存的官方成员目录，不重新下载大包，也没有据目标尺寸推算cube。
3. **官方Git历史。** camera_tilt仅初始加入及移动路径两个提交，camera参数仅一次加入；可见历史路径没有独立标定程序/角点观测/marker CAD。初始notebook中的0.30/0.247写法已经存在，未找到后续修正或说明。保留“示例中的数字”，未认证成物理尺寸。
4. **官方组织与相关公开账户目录。** DFKI-RIC组织首100条返回68仓库、ndahn返回24仓库，均少于请求的100条（未保存Link响应头）；按名称/描述没有发现另一份明确关联UXO成像标定或cube布局的仓库。身份不确定的`mbandefirvida`猜测账户404，不能由此断言作者没有账户。按UXO calibration、组织OCEANS检索的仓库搜索各0结果；这只是有限仓库搜索，**不是全网或GitHub代码搜索**。contributors、proneetsharma及jmohrmann目录请求403 rate limit，未完成这些路径，不反复请求绕限。

前轮确认的模式/水下成像未知状态保持，详见[前轮报告](gopro-imaging-model.md)。相关公开issue5前轮复查无回复；本轮没有向作者发消息、公开评论或创建issue。

## 为何不能先选一个尺寸跑出位姿

0.247m和0.30m可能对应不同边界，但目前只是候选解释。相同归一化图像下，PnP平移会随marker边长同比缩放；选0.30代替0.247可令平移尺度相对增加约21.46%，无法由同一标记的低重投影误差自行消除这个歧义。现有示例没有说明哪个边界被测量，也缺录音间cube是否搬动的记录。

当前有真实tag像素观测，可以在成像模型固定后作不依赖UXO mesh的控制；但不能同时用这些点选择畸变、尺度、外参、同步，再宣称同一批点独立验证了它们。保留所有已有四角和失败例，不重新拟合旧注册。

## 已落盘的可交接结果

- [原始记录最小清单](../../related_work/gopro-control-records/required-records.md)：逐录音设置、可执行成像模型、水下标定血缘、tag黑边真实边长、cube面布局、稳定性及同步/姿态证据，各自给最低验收条件。
- [英文询问草稿（未发送）](../../related_work/gopro-control-records/author-request-draft.md)：列出6条recording与实际clip名，优先复用现有issue5背景，要求区分0.247/0.30和标定介质；不把当前拟合问题预先归咎给作者。
- [检索记录](../../related_work/gopro-control-records/retrieval-log.json)及补充来源清单记录URL、成功hash、404/403/速率限制；未将失败算作否定证据。

下一项依赖是取得上述资料；现有公开范围尚未给出。用户如决定联系作者，草稿可直接用于审核后发送，但本轮未获得发送指令，因此仅准备草稿。若资料无法取得，应明确保留旧数据物理几何未认证的限制；新采集可以另立试点，不能倒推证明旧录音设置/同步。

## 验证与访问

本轮新增访问是公开目录/静态来源、归档成员名称与本地文件结构，没有新视频解码、图像或逐帧标注访问。正式GT继续HOLD；0训练、模型推理、同步/姿态求解、正式GT和新split。原研究目录只读，旧注册结果保留。完整成员名可含其他录音名称，但未提取/打开其样本内容；不把“没打开内容”写成“从未见过test录音名”。
