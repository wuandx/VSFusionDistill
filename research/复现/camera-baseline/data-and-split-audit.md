# 数据与划分审计：camera-only teacher

日期：2026-11-10。仅使用元数据、配置、已有预测与结果文件；不查看 test 图像，不计算 test 指标，不训练，不修改原研究。此项由主审计补全；另一并行数据审计因服务限流未完成，本文件不冒充其独立报告。

## 结论

新分支的 830 帧 val 不是简单到“没有价值”，而是回答的问题不同：它适合验证相机训练与评测管线是否工作、同录音内插值是否良好，不适合作为未见录音教师基线的验收集。当前原始相机标注每帧一框、三类均有，且没有 sonar blob/projected 标签问题，故应保留作为辅助诊断集，而非删除。

## 已直接复核的数据结构

`D:\pby\uxo-full\repro\frame_split.json:1-7` 固定 seed 0、train 3,322、val 830。其 `per_class`、`pool`、`source` 与 `recordings` 段显示：三类 val 分别为 bomb 228 / grenade 265 / mortar 337；池为 4,152 帧、37 条录音，排除了原 split 的 test 1,500 与 val_id 594；train 和 val 的录音清单相同。

使用 Python `-I` 只读解析 `D:\pby\uxo-full\paired\frame_meta.csv` 得到：train 2,652 帧/27 录音，val 1,500/10，test 1,500/10，val_id 594/27。新池恰为原 train+val 的 4,152 帧。因此“新 val 37 条录音”不代表它们是新录音：每条都在新训练集内。

两个独立并行核查一致重建了帧间距离：830/830 个 val 帧均有同录音 train 帧，最近 `frame_idx` 距离中位数 5、最大 19，766/830（92.29%）在 5 以内。原 val_id 的缓冲留出在同录音诊断上更保守：27 条录音，最近距离最小 15、中位 57。近邻关系是统计事实，但近邻图像相似度没有重新计算；不能把“近邻”进一步写成逐像素重复率。

读取 `D:\agent_workspace\水下\声呐目标检测\code\VSFusionDistill\aodet\datasets\repro_frame_split.py` 与 `configs\repro_cmold\uxo_frame_split.py:104-135` 可确认，loader 按 split 文件的 sonar image id 过滤；相机损失直接使用原生 camera GT。`sonar_gt_sources=(blob,projected)` 对纯相机训练不构成相机标签来源，不能把声呐标签争议移植到此模型。

## 测试集应该是什么样

论文未提供测试集身份，所以不存在可被原文证明的“CMOLD 正常测试集”。对于本项目声称的跨录音泛化，合理的主协议是：以完整 recording 为互斥单位划分 train/validation/test，所有来自同一 recording 的相邻帧只能处于一个集合；在划分前记录类别、采集几何、gain、resolution、range 和可用标定质量，分层时优先保证各类别和主要采集条件在三个集合中都有覆盖。若某些组合样本太少，应报告覆盖缺口，而不是用帧级拆分补齐。

建议主结果为 recording-disjoint test，validation 用于教师选择与有限的配方对照；同录音留出作为次要诊断，报告插值能力与管线健康，不能称泛化测试。论文中的 nearly 4700 pairs 是规模参考，不是划分依据；不能为了凑数将 test 录音混入训练。

当前数据集已连续采集且每条 recording 有类别与场景属性，所以独立单位至少应是 recording，而非 image id。若要声称跨采集条件或现场泛化，还需按采集条件组、日期或独立数据集额外留出；当前 recording-level test 不能支持那些更强的主张。

## 既有 900 帧集合的地位

早期 E11 使用 10 条 recording-disjoint val 和 10 条 test，概念上比新帧级 val 更接近主协议。可是当前分支的相机模型已经在原 test 900 帧上产生过读数并与 E13-cam 比较；这意味着那 10 条已参与开发性模型比较，不能再被描述为“从未接触的最终测试集”。其历史结果可以保留，但应降级为 external/dev 对照，不用于继续选高分的模型。

本地 `D:\pby\uxo-full\paired\frame_meta.csv` 的 val/test 各为 1,500 帧，而旧文档和新结果常写 900 帧。这不是可以静默忽略的小差异：它表明存在不同转换/采样平台或版本。未取得对应 900 帧的 frame list、annotation hash、resolved config 前，不能把当前 paired 的 900/1500 子集与历史 dense/uxo_full 结果自动等同。

## 保留、停止使用、待重建

保留 `t_camera_s` 及其同录音 val 830 的完整产物，名称固定为 frame-level same-recording validation。保留旧 E11/E13 的权重、日志与读数，分别标明平台和证据完整度。停止使用“文献式考场”“论文 80/20”“严格零重叠最终 test”这些未证实或已被开发污染的命名；这里的“停止使用”不表示删除文件。

下一轮应生成一个新的、版本化的 recording-level manifest，记录每条的 class、几何与采集元数据、frame list、annotation hash 和排除理由。先固定 train/dev，剩余录音为最终 test；在所有模型与配置决定完成后只评一次。若可用录音不足，优先采用 recording-level grouped cross-validation 做开发，并保留独立 test，而非退回帧级切分。

新测试集不需要刻意“很难”或包含弱回波。对相机任务，它应代表原生 camera GT 可支持的完整部署分布，不能套用声呐 blob-only 过滤，也不能只挑清晰帧。按 recording、class、geometry 与 acquisition setting 报告覆盖和分维度结果，才是防止“简单测试集”争议的正确方式。
