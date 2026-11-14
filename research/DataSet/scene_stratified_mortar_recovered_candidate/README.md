# 迫击炮flyby恢复后的场景候选

[浏览（本地产物说明）](../../ARTIFACTS.md#artifact-318e1cce8c85)。4081对=原4061+105856新增20。train2472/val894/test715，37录音/31来源组。新录音整条val，旧4061身份/框/角色保持。

迫击炮flyby现在train110049/val105856，test仍缺；110229/110411未通过本次复核。5种场景完整、迫击炮flyby部分覆盖、普通及地面炸弹flyby仍train-only。更多录音不等于不同实物/采集批次。

6份COCO的file_name以本候选根解析；旧图引用scene_stratified_paired_expansion，新增图保存本目录。原SD框/raw像素保留。不修改旧版，不启动训练；待用户审阅、精密同步/专家未认证。若采用需冻结后固定COCO起点重训。候选test有开发史；原研究test关闭。
