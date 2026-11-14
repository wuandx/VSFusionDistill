# 已知弱场景条件覆盖优先的5229配对重划分

[浏览（本地产物说明）](../../ARTIFACTS.md#artifact-8b45d34fb11a)。只改角色；旧5229两端图像、标签、全部身份保留。所有已登记scene内z/tilt/roll联合条件进入train，unique来源优先训练，因此floor ellipse和两种bomb flyby没有独立留出；两类其余flyby只有val。见protocol.json、scene-coverage.json和role-changes.csv。

新分配使用旧val/test诊断定义开发目标，不称未触碰测试集；无新训练或推理，无AP增益。原研究10条test关闭；7未决没有纳入。类别及COCO file_name根沿用旧5229，新增相机assistant_labels和原标签original_labels的血缘不变。历史393样本COCO以previous_added393_historical命名，仅供血缘，不作当前train索引。须fresh COCO训练后才可评价本版。
