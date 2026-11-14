# 5229对相机—声呐配对数据

[浏览（本地产物说明）](../../ARTIFACTS.md#artifact-9940a746ec7f)；新增393对/4录音/3保守组进入train，train3433、val961、test835。旧4836成员/图像/框/角色保持，val/test COCO和身份文件字节不变；旧版目录保留。

本目录两侧图像、COCO与YOLO自包含；审核历史可指向上游目录。COCO file_name相对本数据根，类别沿用100lbs_aircraft_bomb / mortar_shell / incindiary_grenade，ID分别1/2/3（YOLO为0/1/2）。新增相机JSON是assistant_labels，不是原始标签；旧相机JSON在original_labels。新增7未决仅在unresolved中，不在训练/COCO/YOLO。

助手实际双端目视标注，非专家GT，未认证精密同步。原研究10条test关闭；既有835 test仅复制和完整性核验，无新模型评价。没有训练；后续须单独预登记并从COCO初始化。未解决其他flyby覆盖缺口，不报告AP增益。
