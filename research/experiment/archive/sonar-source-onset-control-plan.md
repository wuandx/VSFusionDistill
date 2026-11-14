# sonar_source_onset_control

2026-11-12，执行前登记。source motion audit发现bomb171105/173329的match gantry_offset相对源gantry首运动提前6.1394667s/1.75175s，其余四开发录音相同。

唯一改动：采用原gantry CSV首个XY向量位移时刻作为offset，保留原ARIS onset、frame时间、pan/tilt/roll、外参、target、mesh尺度/姿态、图像、观察不变。不是拟合回波选时间。由于ARIS onset也可能受手动pan影响，此对照为待验证假设，不直接修改官方matches/生产标定。

固定旧18开发身份，重算gantry与原点/旧PCA模型投影；只显示既有副本。旧17相机端部控制保持首末fit、其余check的同一协议，比较旧/源onset时间下重投影误差。不改变K，不拟合时间/角度。判据：两bomb录音的粗投影和相机check均改善才支持时间对应问题；仅fit改善不认证。仍保留相机模型及端部观察不确定性、uncertain声呐帧，不据此产生GT。

源onset投影检查后追加：保持前轮同一端部区域与±7°，只替换上述已冻结的gantry位置，复算两帧反投影区域距离。沿用两seed差分进化200代，和原距离对照；不修改区间/mesh/时间、也不把距离小当同名端部已证实。
