# sonar_fixed_mesh_beam_sign：仅 beam 方位符号修订候选

2026-11-11，先登记再生成。沿用用户授权的固定 mesh→target 投影和跨帧/跨轨迹 QA。

目的：区分三维方位→原始 beam 列的符号约定与 mesh 注册问题。初版 18 帧已经检查，属于开发诊断；本版不称独立留出验证。初版保存不动。

独立依据：官方 `related_work/uxo-upstream-history/scripts/view_recording.py:178-180` 注明原始 beams 从右向左，并水平翻转显示；`prep_2_aris_to_polar.py:174-207` 将 beam table 正角显示到左侧。公开 transforms.yaml 中 setup/sonar 与当前 setup/camera 旋转相同；若两者采用 optical +x 向右，则 sonar 方位到 beam table 应取负号。该证据足以提出一个符号修订候选，但尚未取得已知三维控制点到真实 beam 的物理认证，不能宣称已无歧义证明原作者坐标。

唯一改动：`beam_azimuth_deg = -degrees(atan2(sonar_x, sonar_z))`。range、elevation、gantry/ARIS/外参、全部 FOV 和 padding、采样点、18 个身份不变。mesh 直接读取初版冻结的 s/R/t，复制其 JSON 字节，必须保持 SHA256 `31e18b860fbbb6ac489156d9d2f4f3ffa57953301e95ab35f1e9fa0bcc8722c7`。本版不重估 PCA、不改任何模型参数、不换目标世界位姿，不进行回波拟合或逐帧修正，不搜索其他角度/尺度/平移。

对照：初版原图/投影与新符号投影。继续检查完整距离×beam 图与扇形图；主坐标为原始图，fan 仅自有显示，不能移植到官方 polar2 图。本版 QA 单独保存，与初版逐身份并排，失败不得剔除。assistant 目视 QA 不冒充人工专家真值；无清晰目标的样本继续允许 uncertain。

判定：独立复算确认只有 beam 方位反号、s/R/t 和所有源 hash 不变；逐类两录音首中末是否均有可解释的距离/方位/框。视觉改善只支持符号候选，不能据此认证实测外参、物理注册、±7°垂直视场或声学边界。未辨认目标不自动判负样本。

停止：本版最多这一个符号候选；若完整性失败则停止。保留所有异常，不再自动调整全局注册或扩大录音。不生成正式训练 GT、不改旧 GT/划分、不训练、不访问 test。
