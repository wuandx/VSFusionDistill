# 文献来源与论文协议核查

日期：2026-11-10。本文记录可获得的原始来源，不以先前 AI 摘要代替论文。

## 来源结果

CMOLD（Aydogmus & Erer, IEEE Access 2026, DOI `10.1109/ACCESS.2026.3666096`）的 Crossref 记录确认标题、作者与出版物，primary URL 为 `https://ieeexplore.ieee.org/document/11397899/`。Semantic Scholar 也只给出 DOI 形式的开放 PDF。以完整英文标题检索 arXiv API 返回 `totalResults=0`，GitHub 精确标题仓库检索返回 `total_count=0`。在本次可核查的公开渠道内没有找到作者 LaTeX 源。

因此，本工作区保存的是用户已有 IEEE PDF 的副本 `related_work/cmold/paper.pdf`，SHA-256 为 `f60d51937d9864c6aa6b2c35d610f7beba575f5c53b93f19add7b7099db64d41`。不能把它改名为 LaTeX 或声称已读源文件。以下结论以论文正文抽取为证据；表内数字来自先前已逐格核对的表图，标为表图证据。后续若作者提供 LaTeX，应重新核对全部行号。

CMHD（*Lightweight Underwater Sonar Object Detection via RGB-Guided Heterogeneous Distillation*, Sensors 2026）保存了出版方 JATS XML `related_work/cmhd/source/fulltext.xml`，SHA-256 为 `7e1cf91e74e20f063656fd91c8c64e8f0b59c1b2d4c7272e597fdd261f3f9601`。它是结构化全文，不是 LaTeX；直接解析 XML 的 §3、§4，不依赖旧中文总结。

YOLOX（Ge et al., arXiv:2107.08430）的源包已从 `https://arxiv.org/src/2107.08430` 下载，归档保存在 `related_work/yolox/downloads/source.tar.gz`，安全展开后正文为 `related_work/yolox/source/yolox.tex`。其 §4.2 明确给出 Mosaic 与 MixUp 增广，及关闭增广的最后 15 epoch；这些是 YOLOX 的 recipe，不是 CMOLD 已披露 recipe。

## CMOLD 对数据实际说了什么

论文只写 nearly 4700 image pairs were used for training and validation；另有同模态 KD 比较中 teacher/student 使用 identical data splits。它没有给 split 比例、split 单位、seed、test set 身份，也没有说明表中指标计算于哪个具体集合。当前 PDF 抽取文本 `D:\agent_workspace\水下\声呐目标检测\docs\investigation\cmold_numbered.txt:550,575,610-612` 与专项核查一致。

由此只能写“论文未述”。不得从 UXO 数据是连续录制、或教师分数很高，反推论文一定使用帧级随机划分；也不能断言论文一定没有 recording-level 划分。论文未给输入尺寸、resize、增强清单、初始化与 checkpoint 选择，不能把这些空格补成“标准做法”后称为论文复现。

论文表 3 的相机教师为 AP 0.958、AP50 0.997、AP75 0.997、AR@1/10/100 均为 0.969。出处为表图 `D:\agent_workspace\水下\声呐目标检测\docs\investigation\cmold_t3.png`，不是 LaTeX 正文中的可检索数字。这些绝对值不能与不同数据池、不同划分的本地结果作能力差分解。

## CMHD 提供的参考协议，而非 CMOLD 的隐藏答案

CMHD XML §3.1 明写：原 UXO 有 95 trajectories、74,437 sonar frames、48,462 camera-paired frames、37,278 camera annotated frames；高时间冗余。其 UXO† 每类随机选 10 条完整 paired-RGB 标注轨迹，每条均匀取 100 帧，再按 trajectory level 分 train/val/test = 6:2:2，得 1800/600/600，类别均衡。

这直接支持“按 recording/trajectory 隔离”为本项目正常的主泛化协议。它不代表 CMOLD 的秘密 split，也不意味着 CMHD 的几何投影 sonar 标签与本地 camera 原生标注是相同任务。CMHD 自身说明投影经过人工检查但非逐帧 exhaustive manual annotation，且研究是 focused case-study，不应被升级为普遍泛化证明。

## 对当前基线的约束

`t_camera_s` 采用 YOLOX-S 相机分支、200 epoch、COCO backbone/neck 初始化、SGD 和 letterbox 几何，属于合理的“论文未披露项的我方选择”。它缺少 YOLOX 完整训练 recipe 的 Mosaic/MixUp/HSV、多尺度等部分；这可以作为本地训练配方差异，但不能当作与 CMOLD 已证实的差异。

研究目标应从“达到 CMOLD 的 0.997”改为“在我方可复核的数据协议上验证 camera-only teacher，并把与论文的可比项和未知项同时列出”。绝对 AP 对齐在论文测试身份未知时没有唯一可证解。
