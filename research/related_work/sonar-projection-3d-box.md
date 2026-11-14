# 相机 → 声呐：3D 模型 / 3D 框的投影（文献面）

查询日期 2026-11-13。问题：有没有论文做「把相机侧的 3D 模型（或 3D 框）投到声呐图像上，得到声呐侧的框/区域」这一步。
事实分层：`[原文]` = 读 LaTeX / abs 原文；`[元数据]` = 仅标题摘要作者；`[我方判断]` = 推断。

---

## 0. 一句话结论

**没有**任何一篇公开论文把「相机侧的 3D 框（或 CAD 网格）投影到前视声呐图像、生成声呐侧 2D 框标签」当作方法贡献。`[我方判断]`

文献里存在的是**三条相邻但各自缺一环**的线：

| 线 | 有什么 | 缺什么 |
|---|---|---|
| A. 声呐投影模型 / PnP·AnP | 3D 点 ↔ 声呐像素的解析正向模型与位姿求解 | 只处理**点**，不处理物体、框、可见性 |
| B. 声呐渲染 / 仿真 | 3D 场景 → 声呐图的正向成像（含多径、折射） | 目标是**像真**，不产出标注框 |
| C. 声-光共配准 / 配对数据集 | 相机与声呐的空间对齐、像素级对应、配对帧 | 对齐到**像素/语义**，未到**检测框**；多为侧扫、非 FLS |

也就是说：**几何零件都齐了，但没人把它们拼成「3D 模型 → 声呐框」这条标注流水线**——这正是本项目 `projected` blob 所处的位置。`[我方判断]`

---

## 1. A 线：声呐投影模型与位姿（点级别）

| arXiv | 日期 | 题目 | 关键内容 |
|---|---|---|---|
| 2504.04445 | 2025-04 | A Convex and Global Solution for the PnP Problem in 2D Forward-Looking Sonar | `[原文]` 2D FLS 的球坐标 (r, θ, φ) → 像素只保留 (r, θ)；用 point-to-line 3D 配准 + 正交近似处理非线性成像；对偶最优解保证全局最优；共面情形做零空间分析 |
| 2503.16066 | 2025-06 | Rejecting Outliers in 2D-3D Point Correspondences from 2D FLS Observations | `[原文]` 外点率可达 90%；利用声呐窄视场；说明真实数据上 3D↔声呐对应**很不可靠** |
| 2411.17521 | 2024-11 | BESTAnP: Bi-Step Efficient and Statistically Optimal Estimator for Acoustic-n-Point | `[原文]` AnP = n 组 3D-2D 对应求声呐位姿；平移 → range-only 定位，旋转 → azimuth-only 特征分解，两步解耦；统计最优 |
| 2507.05410 | 2025-07 | Feature Geometry for Stereo Sidescan and Forward-looking Sonar | `[原文]` 显式写出 `Π_ss(r,θ,φ)=r`、`Π_fl(r,θ,φ)=[r,θ]`；仿相机极线几何，做**把一侧声呐观测到的特征投到另一侧声呐**（FLS↔侧扫，双向），并分析特征位置与相对位姿对投影的影响；投影只在对方视场内有效 |
| 2307.16160 | 2023-07 | Motion Degeneracy in Self-supervised Learning of Elevation Angle Estimation for 2D FLS | `[原文]` 仰角 φ 不可观测；自监督学仰角存在运动退化 |
| 2208.00233 | 2022-07 | Learning Pseudo Front Depth for 2D FLS-based Multi-view Stereo | `[原文]` 单张 FLS 反演 3D 有严重歧义，需多视图立体 |

**为什么这条线是本项目的几何底座**：`projected` 标签要的正是 `Π_fl`，即把相机坐标系下的 3D 点（框角点/网格顶点）先变换到声呐坐标系，再取 (r, θ) 落到像素。2504.04445 与 2507.05410 给出了这套正向模型的规范写法，可用作方法节的引用与公式来源。`[我方判断]`

**这条线的硬限制**：φ 被丢弃 ⇒ 一个 3D 点的像是一条**弧**（同一 r、θ 上所有 φ 都落在同一像素），于是一个 3D 框的 8 个角点投出来是一组弧段，包围盒**不是**物体真实轮廓——前后面重叠、远近不分。`[我方判断]`

---

## 2. B 线：3D 场景 → 声呐图的正向仿真

| arXiv | 日期 | 题目 | 关键内容 |
|---|---|---|---|
| 2001.03539 | 2020-01 | A rasterized ray-tracer pipeline for real-time, multi-device sonar simulation | `[原文]` 有专节 "Geometry of the sonar projection"：笛卡尔 3D 点 ↔ 球坐标 (r,θ,φ)；GPU 混合管线，光栅求首次交点 + 仅反射区域光线追踪；多设备声呐 |
| 2503.01074 | 2025-08 | OceanSim: A GPU-Accelerated Underwater Robot Perception Simulation Framework | `[原文]` 物理渲染 + 实时成像声呐渲染 |
| 2606.06130 | 2026-06 | Towards Realistic 3D Sonar Simulation | `[原文]` 体积 3D 声呐模型 + 折射/多径，模块化；**库内已有，★23 有代码** |
| 2504.00159 | — | SonarSplat（库内） | `[元数据]` 成像声呐新视角合成 |
| 2402.03309 | 2024-08 | AONeuS: A Neural Rendering Framework for Acoustic-Optical Sensor Fusion | `[原文]` 物理驱动的声-光联合神经表面重建，把 RGB 高分辨率与声学观测在同一 3D 表面假设下对齐 |

**用途**：若要论证「投影框到底包住了什么」，最干净的办法不是解析投影，而是**用仿真器渲染**：给定物体 3D 位姿 → 渲染声呐回波 → 看能量落在哪。B 线提供了这条验证路径，`2606.06130` 与 `2503.01074` 都带代码。`[我方判断]`

---

## 3. C 线：声-光共配准与配对数据集（最接近「跨模态标注迁移」）

| 来源 | 关键内容 |
|---|---|
| **2608.23479**（库内，本次补 LaTeX） | `[原文]` 几何驱动的声-光共配准：先用 IMU 约束 SfM 得到海床 3D 网格作为几何真值，再把光学侧投到侧扫声呐几何上，建立**像素级对应**；摘要明写 "eliminating the need for manual acoustic annotation"、"generate perfectly co-registered opti-acoustic datasets"。**这是最接近「投影生成声呐侧标注」的一篇，但目标是像素级（底栖生境），不是检测框，传感器是侧扫而非 FLS** |
| 2610.07472 SURGE / 2603.14457 / 2508.03408 / 2508.12071 OASIS | `[元数据]` 声-光融合重建与体积建图；OASIS（WHOI, IROS 2025）有代码但只做重建/融合 |
| 2603.13585 Sonar-MASt3R（库内） | `[元数据]` 浑浊水域的声-光配准/融合 |
| 2406.07189 RGBS50（库内） | `[元数据]` 配对 RGB-声呐数据集 + SRST 合成「声呐样」图像 |
| 2610.23759 HaCKRS | `[原文]` Garmin LiveScope + 俯视 RGB 锦鲤，>105,000 时间对齐帧对；原只读 literature 已有 PDF |
| 2606.01398 | `[元数据]` 声呐-视觉跨模态数据集（原目录已有 PDF） |
| 2410.08612 Synth-SONAR（库内） | `[元数据]` 光学→声呐的生成式合成 |

---

## 4. 会不会是我漏了「3D 框 → 声呐」这条？

搜过的口径（arXiv HTML 搜索，abstract 字段，18+ 组 query）：
`"forward-looking sonar" projection`、`sonar "3D bounding box"`、`sonar annotation projection`、`acoustic-n-point`、`sonar rendering simulator`、`opti-acoustic registration`、`sonar stereo geometry`、`project labels sonar` 等。命中里**没有**同时满足「相机 3D 框/网格 + 投影 + 声呐框标签」的工作。`[我方判断]`

另需注意一个语义分叉：**SonarVoxNet（2610.01644）**做的是「3D 声呐点云里的 3D bbox」（潜水员，含 pitch/roll 的全身朝向），不是「把 3D 框投到 2D 声呐」。它原文指出 2D FLS 丢仰角、3D 声呐稀疏含噪、现有 3D 检测器只假设直立 + 仅绕 yaw 旋转。若我们的写作里出现「3D 框」，务必区分这两件事。`[原文]`

---

## 5. 对本项目 `projected` blob 写法的三条口径建议

1. **不能说「已有方法这样做」**：没有先例，因此 `projected` 必须写成本文的工程选择，并给出完整定义（相机侧标注的什么几何、用什么外参、投到声呐的哪一帧、怎么取包围盒）。`[我方判断]`
2. **必须区分「完整投影框」与「可见表面框」**（brainstorm.md 已记）：由于 φ 缺失，3D 框的投影是一个区域；若按 8 角点取外接框，会把物体厚度方向的深度差全部摊平，框会**系统性偏大**。建议同时保留两个量：(a) 8 角点投影的外接框（可复现、可审计）；(b) 由仿真/可见性判据得到的「真正被声呐照到的部分」。二者差多少，本身就是一条可报告的实验结果。
3. **可以用 2504.04445 / 2507.05410 的 `Π_fl` 作为唯一投影实现**，用 2001.03539 / 2503.01074 / 2606.06130 做交叉验证（解析投影 vs 渲染），这样「projected 标签是否可信」就有了独立检查，而不是自证。

可直接进 related work 的一句（待核后使用）：
> While sonar projection models are well established for single points (AnP/PnP) and 3D sonar simulation is mature, we are not aware of prior work that projects camera-side 3D object geometry into forward-looking sonar images to obtain detection labels.

---

## 6. 获取记录

- 本次新入库 11 篇（全部拿到 PDF + LaTeX）：2504.04445、2503.16066、2411.17521、2507.05410、2001.03539、2503.01074、2208.00233、2307.16160、2402.03309、2610.01644、2608.23479。
- 文献库现为 **102 篇，96 篇带作者 LaTeX**（`related_work/lit-2026-11-12/`，`index.md` / `README.md` 已重建）。
- 其中 2610.01644、2608.23479 在原只读目录 `D:\agent_workspace\水下\声呐目标检测\literature\` 已有 PDF，此次为补 LaTeX 而重下；两处并存不冲突。
