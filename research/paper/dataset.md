> 版本提示：这是历史论文草稿，内容对应较早的数据/实验版本，尚未更新为当前5229对划分。当前事实以[研究进展入口](../README.md)及其链接的冻结记录为准。

# 数据集构建与标注 / Dataset Construction and Annotation

## 中文

本研究基于公开UXO多模态数据集构建相机—声呐目标检测子集[1]，包含航空炸弹、迫击炮弹和燃烧手榴弹三类目标。沿用发布数据中的帧对应关系，将ARIS声呐帧与具有原始边界框的RGB图像关联。RGB图像保留640×360分辨率及原始标注；声呐图像保留原始方向和像素坐标。

原始声呐图像缺少目标边界框，因此采用候选框生成与视觉语言模型逐帧审阅相结合的标注流程。首先根据回波强度与连通区域生成候选框，再并列查看RGB图像、声呐原图及局部放大图，检查目标可辨性和候选框范围；对于边界不合适的候选，另行修订并再次审阅。声呐框采用轴对齐矩形，包围可辨认的主要目标回波，避免向可分离的背景回波扩张。相机目标部分出画时，只要剩余部分仍可辨认且原框合理包围画面内可见部分，即可保留，不估计画面外范围。无法可靠判断的样本暂不纳入，也不作为负样本。

经过筛选，共保留3398对候选标注。从每类10条录音中，按已接受帧的时间顺序均匀选取每条100对，形成包含3000对图像的类别平衡子集，每类1000对；其余398对单独保留为备用，不计入该子集。每对样本均提供RGB与声呐图像、两侧边界框及可追溯的录音和帧索引，并核验文件一致性、重复图像和标注格式转换。

## English

We construct an RGB–sonar object detection subset from the public multimodal UXO dataset [1], covering aircraft bombs, mortar shells, and incendiary grenades. ARIS sonar frames are associated with RGB images carrying original bounding boxes using the frame correspondences provided with the release. RGB images retain their original 640×360 resolution and annotations, while sonar images retain their native orientation and pixel coordinates.

Because the original sonar images lack bounding boxes, annotations are obtained through candidate generation followed by framewise review with a vision–language model. Candidate boxes are first generated from echo intensity and connected regions. The RGB image, full sonar image, and magnified sonar region are then inspected together to assess target visibility and box extent; unsuitable boundaries are revised and reviewed again. Axis-aligned sonar boxes enclose the identifiable main target echo while avoiding extensions into separable background returns. Partially out-of-frame camera targets are retained when the remaining portion is identifiable and the original box reasonably encloses its visible extent; no out-of-frame extent is inferred. Uncertain samples are withheld rather than treated as negatives.

This screening yields 3,398 pairs with candidate annotations. From ten recordings per category, 100 pairs per recording are selected at uniform positions in the temporally ordered accepted frames, producing a balanced subset of 3,000 pairs, with 1,000 pairs per category. The remaining 398 pairs are retained separately as reserves and are excluded from this subset. Each pair includes both images, modality-specific bounding boxes, and traceable recording and frame identifiers. File consistency, duplicate images, and annotation-format conversions are checked.

## 数据来源 / Data Source

[1] Dahn, N., et al. *An Acoustic and Optical Dataset for the Perception of Underwater Unexploded Ordnance*. OCEANS 2024 Halifax, 2024, pp. 1–6. [UXO dataset repository](https://github.com/dfki-ric/uxo-dataset2024).
