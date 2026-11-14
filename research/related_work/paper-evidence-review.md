# 论文证据复核：CMOLD、CMHD 与 YOLOX

日期：2026-11-10。本轮只读原研究，未运行训练或评测，未读取 test 样本。本文是新增更正记录，不覆盖 `source-and-protocol-audit.md` 或原研究历史报告。

结论：**目前不能将本地 camera-only teacher 称为 CMOLD 数字复现；可以复现论文已披露的训练超参，其他缺失项必须登记为我方选择。** CMOLD 的训练轮数并非完全未知，Table 2 明确列出 200 epoch；此前报告忽略表图而把它列入未知，需要更正。教师具体 YOLOX 规模仍不能从同模态 KD 的 YOLOX-M 推得。

## 1. LaTeX 获取结果与证据限制

| 文献 | 本轮核查结果 | 实际阅读的格式 |
|---|---|---|
| CMOLD，Aydogmus & Erer，IEEE Access 14，27339–27353，DOI 10.1109/ACCESS.2026.3666096 | [作者所在机构记录](https://research.itu.edu.tr/en/publications/cross-modality-object-level-knowledge-distillation-for-enhanced-u/)仅提供 DOI 与 Scopus；[IEEE 页面](https://ieeexplore.ieee.org/document/11397899/)在当前工具要求 JavaScript 验证。完整标题 arXiv API 查询为 0，GitHub repository 精确短语查询为 0；未找到公开 LaTeX | 已有 PDF 抽取正文、已有表图。**没有把它们当作 LaTeX** |
| CMHD，Sensors 26(14):4340，DOI 10.3390/s26144340 | 完整标题 arXiv API 查询为 0；MDPI 页面本轮返回 429。通过 [Europe PMC JATS 全文接口](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13417324/fullTextXML)重新下载，SHA-256 与既有 XML 完全相同 | JATS XML，非 LaTeX；[PMC 全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC13417324/)可交叉核查 |
| YOLOX，arXiv:2107.08430v2 | [arXiv 页面](https://arxiv.org/abs/2107.08430)有 TeX Source。重新下载[带版本源包](https://arxiv.org/src/2107.08430v2)，与既有归档逐字节一致；归档中 `yolox.tex` 与当前展开文件逐字节一致 | 真正的作者 LaTeX，正文主要读 `yolox/source/yolox.tex` |
| UXO 数据集论文，OCEANS 2024，DOI 10.1109/OCEANS55160.2024.10754316 | [DFKI 论文入口](https://www.dfki.de/en/web/research/projects-and-publications/publication/15133)公开 PDF；[官方处理仓库](https://github.com/dfki-ric/uxo-dataset2024)递归 tree 中没有 `.tex`；完整标题 arXiv API 查询为 0 | 本轮只核查官方元数据与源码 tree，未追加 PDF 阅读 |

以上负面检索只证明**在所查入口未找到**，不能证明作者没有 LaTeX 或不存在未索引版本。没有向作者发送邮件；用户未授权对外联系。后续得到作者源文件时应追加来源与重新核查记录，不伪造 `.tex`。

获取记录在 `source-check-20261110/acquisition-log.json`、`arxiv-retry-log.json`、`cmhd-xml-retrieval.json` 与 `local-source-manifest.json`。Python urllib 对 arXiv 的本机证书验证失败也被保留；随后通过 PowerShell 正常证书验证完成 API 查询与 YOLOX v2 下载，未绕过 TLS 验证。GitHub API 返回 0 的是仓库搜索，不是授权的全站代码搜索，不能夸大覆盖范围。

## 2. CMOLD：已披露项与未知项

本地证据为 `cmold/evidence-existing/cmold_numbered.txt` 与 `cmold_t1.png` / `cmold_t2.png` / `cmold_t3.png`。它们只读复制自原研究 `docs/investigation/`，本轮直接看过三张图；它们是**既有 PDF 衍生产物**，本轮没有重新渲染 PDF，不能宣称新取得作者源文件。原 PDF 与复制件的 hash 均登记在 manifest。

| 项目 | 可支持的陈述 | 不可支持的升级 |
|---|---|---|
| 模态与架构 | §III-C，正文行 389–398：camera teacher、sonar student，共享 YOLOX architecture 与 input resolution；Figure 6/正文行 414–416 说明 camera teacher 在标注 RGB 上训练 | 不能据此确定具体 S/M/L 型号、深宽、参数量或分辨率数值；也不能把“同架构”直接升级为逐层代码相同 |
| 训练超参 | **Table 2 图**：200 epoch、batch size 8、SGD、initial LR 0.00125、final LR 6.25e-5、momentum 0.9、weight decay 5e-4 | 表没有分别列出 camera 独立预训练、sonar baseline 与 KD 各阶段的全部 resolved config；不能补写 scheduler、warmup、EMA 或 checkpoint 选择 |
| 数据规模 | §IV-A，正文行 575：约 4700 image pairs 用于 training and validation | 不是“4700 训练帧”，不是公开 split manifest，也不能推出 test 存在与否、比例、seed、按帧或按 recording 划分 |
| 标签 | §III 开头行 282–288：camera fully labeled；sonar 使用少量人工标签与 pseudo-label 扩充 | 不等于本地 blob/projected 构造，也不能将 sonar 标注差异直接当成纯相机监督的差异 |
| 相机指标 | **Table 3 图**：mAP@[.5:.95]=0.958，AP50=0.997，AP75=0.997，AR@1/10/100=0.969 | 评测集样本身份、具体 split 与评测代码未披露，不能把本地数字之差称为同协议模型能力差 |
| 同模态 KD 容量 | §IV-B，行 607–617：YOLOX-M teacher、YOLOX-S student，**两者 exclusively on sonar**，并给约 25.3M/9.0M 参数与 73.8/26.8 GFLOPs | 25.3M 不是 CMOLD camera teacher 已披露容量；identical splits 的这段明确属于该 sonar-only KD 对照，不能移植为 camera teacher 的划分证明 |
| 预处理与选择 | 具体输入数值、resize/pad、完整增广、初始化来源、训练/验证/test manifest、checkpoint 选择仍无足够证据 | 不用“标准 YOLOX 都如此”填空，也不能反向声称论文一定没有做增强或预训练 |

Table 2 的已知超参与当前 `t_camera_s` 的 200 epoch / batch 8 / SGD 家族存在可核对的一致项。这是保留当前分支的理由之一，但不足以认证数据协议或跨 recording 泛化。

**数据规模比较还需更正分母。** 当前 3322 是 train，830 是 val，合计 4152；论文约 4700 的描述是 train+validation。可写“我方开发池 4152 vs 论文约 4700，具体样本对应关系未知”。不能用 3322 vs 4700 量化训练规模不足，论文单独 train 数未知。

## 3. CMHD：可参考的协议，不是 CMOLD 的隐藏配置

XML 原文可用稳定 `id` 定位；为便于逐段核查，另生成 `cmhd/source/sections-indexed.txt`，未改动原 XML。

- §2.1，XML `sec2dot1-sensors-26-04340`，索引行 13–18：RGB teacher 明确为 **YOLOX-M**；这是 CMHD 的事实，不能转写成 CMOLD 的规模。
- §3.1，`sec3dot1-sensors-26-04340` 的第 2 个 `p`，索引行 57：每类选 10 条完整 capture trajectories，每条均匀采 100 帧，再按 trajectory 分为 6:2:2；train/val/test 为 1800/600/600，各类均衡。该段也承认是受控场景 case study，并非普遍泛化证明。
- §3.2，`sec3dot2-sensors-26-04340`，索引行 59–60：640×640、50 epoch、batch 8、SGD、initial/final LR 0.00125/6.25e-5、momentum .9、weight decay 5e-4。不能把 50 epoch 与 CMOLD 的 200 epoch 混为一项。
- §3.1 与 Data Availability：sonar GT 为几何投影后检查，完整生成标注需向作者合理请求；原始 UXO 可公开获取不等于 UXO† split/sonar 标注已公开。[CMHD 原文](https://pmc.ncbi.nlm.nih.gov/articles/PMC13417324/)

本项目可将 recording-level split 作为**我方主泛化协议**，CMHD 为同领域直接参考；不能说它揭示了 CMOLD 的真实 split。是否有未使用的 recording 可以组成新 test，还需要数据血缘核查，不能只用“原数据有 95 条轨迹”减去当前 37 条就认定剩余全部可用。

## 4. 真正读 LaTeX 后，对 YOLOX 配方的更正

`yolox/source/yolox.tex` 是 arXiv v2 原始文件；保留归档和注释，不将注释掉的段落作为正文。

| LaTeX 定位 | 原文支持的内容 | 对本项目的意义 |
|---|---|---|
| §2.1 Implementation details，行 123 | COCO 300 epoch、5 warmup、SGD、cosine LR、multiscale 448–832 | 这是原始 YOLOX COCO recipe，不是 CMOLD 的已披露 200 epoch 配置 |
| §2.1 Strong data augmentation，行 153 | 一般实验引入 Mosaic/MixUp，最后 15 epoch 关闭；该阶段后续实验从头训练 | 不证明 CMOLD 从头训练；本地 COCO 初始化是我方选择 |
| §2.2 Model size and data augmentation，**行 253** | 对 **YOLOX-S、Tiny、Nano 去掉 MixUp**，并把 Mosaic scale range 从 [.1,2] 减弱到 [.5,1.5] | 旧报告把“缺 MixUp”一概列为未遵循完整 YOLOX-S recipe，不准确；不应为了补齐所谓标准而盲加 MixUp |
| 表 `table:yolov5`，行 212/214 | 标准 COCO YOLOX-S/M 为 9.0M/25.3M 参数 | 不是本地三类检测器精确参数，更不能确定 CMOLD camera teacher 容量 |

早前 `source-and-protocol-audit.md` 称 YOLOX“§4.2”给出增强，不准确；本源文件对应 §2.1/§2.2。缺 Mosaic/多尺度等可列为**相对 YOLOX 原始配置**的候选配方差异；不能升级为“已查明与 CMOLD 的差异”，更不能认定它解释了全部泛化问题。[YOLOX v2 与作者源码入口](https://arxiv.org/abs/2107.08430v2)

## 5. 本轮更正清单与后续取舍

1. 撤回“CMOLD 训练时长未披露”的笼统说法：Table 2 已有 200 epoch 与多项超参；仅各阶段完整训练细节未知。
2. 撤回把约 4700 当作论文训练帧数的规模比较，改为同层级开发池 4152 vs 约 4700，精确样本关系未知。
3. 更正 YOLOX-S 增强：LaTeX v2 的 small-model 配方明确不含 MixUp；若未来试 MixUp，应作为预登记的本地消融，不能称补回已知 CMOLD 配方。
4. 保留 CMOLD camera teacher 容量未知的边界；CMHD 的 YOLOX-M、CMOLD sonar-only KD 的 YOLOX-M 与 camera teacher 是三件事。
5. 保留现有 camera-only 训练与同 recording val 产物；暂缓增加容量、蒸馏与复杂融合。首要缺口是录音级开发协议及数据血缘，不是再追一个无法同协议比较的论文 AP50。

这些取舍属于本项目决策，不是论文结论。本轮不新增训练实验，不以 test 读数选择配置。
