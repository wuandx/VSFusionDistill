# 4836对相机—声呐配对数据

完整两端图像、原相机JSON、YOLO及COCO已独立复制。见[index.html（本地产物说明）](../../ARTIFACTS.md#artifact-4f30fc00fd8b)。新增755对为助手逐对审阅，非专家GT；精密同步未认证。原4081身份/图/框不变，新录音174711接受30对，另725来自19条已有录音。

|split|pairs|recordings|source groups|
|---|---:|---:|---:|
|train|3040|22|19|
|val|961|9|6|
|test|835|7|7|

类别ID：YOLO 0/1/2、COCO 1/2/3 = bomb / mortar / grenade（导出类名沿用原项目）。COCO file_name相对数据集根。新split有旧test评价和开发审阅历史，不称未接触盲测；原研究10条test仍关闭。来源组整体分配，未启动训练，须fresh COCO起点。
