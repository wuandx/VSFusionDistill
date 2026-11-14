# UXO 官方数据说明与全文获取复查

日期：2026-11-11。范围：论文元数据、官方 README、官方示例与已下载模型包目录；无数据样本读取、投影生成或训练。

## 已直接核实的官方表述

`related_work/uxo-upstream-history/README.md` 第 12–19 行逐项包含用户提出的性质：

- “Sonar scans of multiple UXO using an ARIS Explorer 3000 imaging sonar.”
- “Matched GoPro UHD frames for most sonar frames.”
- “Known and accurate transforms between sonar and targets.”
- “Known details of UXO targets including munition types, dimensions, and 3D models.”
- “Tracked scan trajectories that are typical and achievable for non-experimental environments.”
- Zenodo 数据链接和 GitHub 导出脚本链接。当前 README 的 Zenodo 指向 v1.1 记录 13778485；用户列的是早期记录 11068046。

原文来源：[官方仓库](https://github.com/dfki-ric/uxo-dataset2024)。这是官方 README 的直接证据，不冒充已阅读正式论文全文。以上输入当然可以用于几何投影与复现；我方候选投影不吻合不能推翻官方数据的可用性。

## 已知变换与网格注册的具体接口

`related_work/uxo-upstream-history/calibration/transforms.yaml` 提供传感器安装变换及 target→world 变换。`demo/transforms.py` 第 17–35 行按 frame_id→parent_frame_id 构建变换管理器。

`related_work/uxo-upstream-history/demo/transforms_nb.ipynb` 第 753 行，官方示例为：

```python
fig.plot_mesh(filename=os.path.join(ROOT_MESH, "100lbs_aircraft_bomb/100lbs_aircraft_bomb.stl"), s=np.ones(3), A2B=tm.get_transform("target/100lbs", "world"))
```

其直接含义是这个示例把指定 STL 的顶点当作已能以单位比例放入 `target/100lbs` 的坐标。这里没有公开可见的额外 PCA/长度归一化/极值中点操作。

已下载模型包目录 `related_work/sonar-projection-audit-assets/data_export_3dmodels.7z.members.json` 第 3–14 行实际列出 `100lbs.obj`、`incindiary.obj`、`mortar_shell.obj` 等 OBJ/MTL/JPG，未列上述 STL。该有限事实不能证明作者没有注册，也不能证明公开所有入口都没有注册；它说明不能仅凭这个示例就把我方对 OBJ 做的 PCA 和极值中点处理认定为作者原坐标约定。

从已知 target→sonar 变换到准确框，中间仍须让所用网格顶点和 target frame 一致，并使用一致的声呐点到像素定义。问题应表述为“本地实现尚未接准这些接口”，不能表述为“UXO 提供的数据不能使用”。

## 正式论文边界

论文：*An Acoustic and Optical Dataset for the Perception of Underwater Unexploded Ordnance (UXO)*，OCEANS 2024 - Halifax，[DOI](https://doi.org/10.1109/OCEANS55160.2024.10754316)。机构页面保存于 `related_work/recording-split-review-20261111/uxo-institution.html`，第 45 行摘要明确包含 raw/polar sonar frames、annotated camera frames、sonar and target poses、textured 3D models、calibration matrices。

本轮尝试的 [DFKI 官方 PDF](https://www.dfki.de/fileadmin/user_upload/import/15133_20240801_oceans24_uxo_dataset_full.pdf) 和 [ResearchGate 论文页](https://www.researchgate.net/publication/386124306_An_Acoustic_and_Optical_Dataset_for_the_Perception_of_Underwater_Unexploded_Ordnance_UXO) 均返回 HTTP 403。替代 DFKI 主机路径返回 404。OpenAlex DOI 查询成功，但只给元数据/摘要，无可下载全文地址。请求结果与成功响应 SHA256 已保存在 `acquisition-log.json`，响应为 `openalex.json`。

对原研究 `literature/` 文件名检索未发现 UXO/Acoustic/Optical/OCEANS/Unexploded 命名的正式 PDF；这不是对所有编号 PDF 内容的全文普查。未获得正式论文全文和公开 LaTeX，因此不能断言论文不存在更多坐标/精度/注册说明，也不能对不存在于已读材料的内容制造页码或引文。

本轮已查资料没有提供对我方 `beam=-atan2(...)` 候选的论文直接认证；beam 的物理符号仍应由官方坐标和像素约定核实。
