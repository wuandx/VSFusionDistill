# 相机—声呐标定工具（2026-11-12 核查）

问题：手里是「相机配对声呐」的帧（工程上见 `DataSet/paired_visible_reviewed/`，338 对），没有标定板、没有动捕；
想找能拿这种配对数据做标定的工具代码。

结论先说：**没有「读一批配对图像就自动标定」的通用工具**。现成代码全部假设场景里还有第三种信息——
合作目标（角点/螺栓/反射球）、动捕位姿、或者可比较的运动序列。能用的只有三条路，见文末。

## 一、逐个仓库（都是 2026-11-12 实读 README / 源码）

| 工具 | 平台 | 需要什么 | 解什么 | 对我们的可用性 |
|---|---|---|---|---|
| [apl-ocean-engineering/imaging_sonar_calibration](https://gitlab.com/apl-ocean-engineering/imaging_sonar_calibration) | GitLab，BSD（代码头声明），ROS1 + rosbag + PyQt5 | charuco 板 + 板上螺栓在声呐里可见；`rosbag` 同步录相机/声呐 | 相机↔声呐 6-DoF 外参；误差函数把 3D 点投到声呐系，Nelder-Mead 两段优化（先平移后全量），多帧再联合 | **原版工具**（Lindzey & Marburg, OCEANS 2021, DOI 10.23919/oceans44145.2021.9705956）。无靶标用不上，但 `calibration.py` 的误差函数/优化可直接移植 |
| [yeetina/camera_sonar_calibration](https://github.com/yeetina/camera_sonar_calibration) | GitHub ★5，无 LICENSE 文件 | 同上（8×11 charuco + 螺栓），另需相机内参 json；声呐按 Oculus M3000d 参数（`SonarInfo` 类） | 同上，Python+MATLAB 独立复现，带 GUI（逐帧点螺栓 → 实时重投影误差）；产出 `sonar_cropping_params.json`、`calibration.json` | 方法同 APL；**代码更易读**，`image_sonar_utils.calibrate_sonar` 可单独抽出复用 |
| [bachzz/AutoCalib_Sonar_Camera](https://github.com/bachzz/AutoCalib_Sonar_Camera) | GitHub ★2，无 LICENSE | 相机图 + 声呐图 + **掩膜**；声呐伪点云 + 水下光衰减先验；真实场景数据在其 Google Drive | 免靶标、互信息最大化的外参；但实测脚本只优化 **x 与 yaw 两个自由度**（`script_real_uw_RM.py` 里 `init_ranges` 只有 x、yaw，可选 depth 版） | **最接近「用配对数据标定」**，代价是自由度少、依赖伪点云与掩膜质量。可作为初值估计器 |
| [hwgao1101/sonar_Extrinsics_Calibration](https://github.com/hwgao1101/sonar_Extrinsics_Calibration) | GitHub ★1，无 LICENSE；TIM 投稿 *Lambertian-TRF* 的实验代码 | 四个反射球标定板 + **动捕系统** + ROS 录包 | body↔sonar 外参，最小二乘 + 重投影验证（`src/multiImageCalibration.py`、`test/reProjectionTest.py`） | 需要动捕水池，用不上；但「多点最小二乘 + 重投影自检」的写法值得抄 |
| [Steven-Yang-YDS/Camera-Sonar-calibration](https://github.com/Steven-Yang-YDS/Camera-Sonar-calibration) | GitHub ★0 | — | — | **只有 README + LICENSE，没有代码**（tarball 8.7 KB），不要引用为「有实现」 |
| [CIRS-Girona/opti-acoustic-preprocessing-tools](https://github.com/CIRS-Girona/opti-acoustic-preprocessing-tools) | GitHub ★8，GPLv3，`pyxtf/geopandas/rosbags` | ROS bag + 导航；**侧扫声呐（XTF）** | **配对**（把相机视场 footprint 投到海床与声呐条带求交，`src/matching/camera_to_sonar_matcher.py`），不是标定 | 侧扫+海床场景，与水箱 FLS 不同；配对思路可参考 |
| [apl-ocean-engineering/sonar_image_proc](https://github.com/apl-ocean-engineering/sonar_image_proc) | GitHub ★17，ROS | 声呐图像 | 极坐标↔笛卡尔、绘图、`SonarImageProc`；`acoustic_msgs` 生态（另有 `k2oceanic/acoustic_msgs_tools` ★17、`HippoCampusRobotics/acoustic_msgs`） | 基础设施，不含标定；做投影可视化时可用 |

无代码但方法值得看的：**Pecheux et al., "Self Calibration of a Sonar–Vision System for Underwater Robots" (Sensors 2023, PMC9921679)** ——
靠两路传感器各自的运动轨迹比对做免靶标自标定，思路正对「只有配对序列」的情形，但 GitHub 上查不到作者代码。

## 二、三条可走的路（成本递增）

1. **能放靶标就放靶标**（最省事、精度最高）：打印 charuco 板、四角拧螺栓，按 `yeetina` 或 APL 工具走一遍，
   得 6-DoF 外参 + 重投影误差。前期成本在物理靶标与一小时的采集，后期不用再猜投影。
2. **把已知几何的 UXO 目标当靶标**（不用做新靶标）：手动/自动挑出目标上 4–8 个可对应点（相机侧给 3D、声呐侧给像素），
   直接复用 `calibrate_sonar` 的误差函数（3D 相机点 → 声呐投影 → 与标注点求残差，Nelder-Mead）。
   **只解 3 平移 + yaw/pitch**，roll 与内参固定，否则欠定。前提是目标 3D 位置可信（多视图或已知摆放）。
3. **只有单帧、无 3D 参考**：做不了外参；只能做「声呐内参自检」——用已知尺寸的杆/板拟合 range scale 与角度零点。
   没有现成工具，得自己写（我们现有 `复现/camera-baseline/` 里的近表面拟合脚本已具备一半）。

## 三、事实分层

- 仓库事实（★数、文件、依赖、许可）：2026-11-12 直连 GitHub/GitLab API 与源码读取所得。
- 论文事实：Lindzey & Marburg OCEANS 2021 DOI、Pecheux Sensors 2023 PMC 编号。
- 我方判断：「哪条路适合我们」「欠定/自由度」的判断，不是任何论文的结论。
