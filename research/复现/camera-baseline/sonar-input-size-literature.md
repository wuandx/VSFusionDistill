# 论文如何处理声呐尺寸、缩放与补边

2026-11-13，针对4081数据baseline审查后的追问。以下区分论文原文、官方代码、我方推断；不以默认YOLOX代码反推某论文必然使用相同管线。

| 来源 | 已明确的处理 | 尚不能推出的内容 |
|---|---|---|
| CMHD §2.2.1 | RGB和sonar统一resize到640×640；训练和评价统一尺度 | 未在所核对段落明确keep_ratio、stretch、补边位置/数值及原生类别×尺寸分布；不能认证它解决了类别—尺寸混杂 |
| CMOLD PDF正文与表2 | 使用polar-domain声呐，说明不同gain/resolution/range设置；表2列200epoch/batch8/SGD等超参 | 本次检查材料没有明确letterbox/stretch规则，也未见专门排除类别—尺寸线索的对照；不能因用YOLOX就认定采用官方默认预处理 |
| UATD原论文benchmark | 输入高度缩放到512，宽度按原比例缩放，train/inference一致 | 原文该段没有把它描述为强制拉伸至512×512；复杂度表的512×512不应替代实际预处理说明；未据此证明消除采集设置与类别关联 |
| YOLOX官方`preproc`代码 | `r=min(H/h,W/w)`等比例缩放，图放左上，其余填114；ValTransform调用它 | 这认证的是通用YOLOX官方代码，不认证CMOLD/CMHD实际调用了它，更不是声呐去混杂算法 |

证据格式及链接：

- CMHD：本地`related_work/cmhd/source/fulltext.xml`、`sections-indexed.txt`及[发布商HTML](https://www.mdpi.com/1424-8220/26/14/4340)，不是LaTeX。
- CMOLD：本地[PDF（本地产物说明）](../../ARTIFACTS.md#artifact-b44090068078)、既有PDF提取`cmold_numbered.txt`约543–587行及本轮实际查看的`cmold_t2.png`，不是LaTeX。文章DOI：[10.1109/ACCESS.2026.3666096](https://doi.org/10.1109/ACCESS.2026.3666096)。表2没有给输入尺寸或补边规则。
- UATD：优先核对本地`related_work/fls-multibeam-detection-dataset/source/main.tex`的Object detection benchmarks段，另核对[原论文HTML](https://arxiv.org/html/2212.00352v1)。
- YOLOX：核对[作者官方预处理实现](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/yolox/data/data_augment.py)，`preproc`及`ValTransform`。我方resize按最近整数取尺寸，官方该函数使用int向下取整，最多约1px差异；只能称相同的等比例缩放/右底补边原则，不能称逐像素完全复刻。

## 对本项目的含义

等比例缩放并补边是已有检测器采用的常规办法，不是本项目独有的错误。真正需要区分的是：(a) 输入/框几何自洽；(b) 采集条件和类别混杂。前者可通过加载和逆变换预检解决，后者不因网络张量统一尺寸自动解决。

当前数据尺寸能完全区分bomb/非bomb，仍未证明网络实际使用它。checked论文未提供足够证据让我们声称“他们已经专门消除了这个关联”。不能以论文没有讨论此项来认证我方无风险，也不能因此宣称它们结果无效。

本轮保持已经约定的keep_ratio+fixed640 baseline。若后续要检查补边线索，另做固定数据、模型、起点和预算的输入几何对照；stretch可去掉由原长宽比决定的空白条带宽度，但改变目标形状和采样，不是纯粹只去一个线索，亦不能消除增益、range、纹理等其他采集关联。更直接的数据证据是同类跨设置、不同类共享设置的独立来源评价；当前不据此强制重建数据或重分现有成员。
