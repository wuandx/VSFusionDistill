# Camera错位的原因追溯：已定位到发布数据，最初机制仍未知

2026-11-10，接续[首批核查](mortar-camera-misalignment.md)。目的：回答错位由哪一步引入；只读、只检查已允许的两个mortar开发recording，没有训练、模型推理、test图像访问或标签修正。

## 当前结论

**三个已确认的错位例子，其本地JPG及JSON与Zenodo官方发布归档的文件大小和CRC32均一致。结合paired/native图像hash及框坐标核对，问题可进一步定位到官方发布的camera图像—标签组合，而不是本地配对转换或可视化新引入的偏移。**

证据强度须写清：本次是官方归档目录里的CRC32+size匹配，不是重新下载并对远端每个文件做SHA-256，也不能证明这两条录音每帧都错。最初为什么生成了不对应的框，仍缺原始标注工程/标注所用SD帧与完整处理记录，不能判定为人工画框错误或某个确定的时间偏移。

## 逐层定位

| 层级/候选原因 | 查到的证据 | 目前判断 |
|---|---|---|
| 浏览页缩略图、48px标题条、训练padding | 原始native图+原始标签x3已复现三处错位；绘图直接作用于未resize图像，标题另外拼接 | 不能用这些显示/训练操作解释已存在的native错位 |
| 本地paired转换错配/改框 | 两录音268张paired图与同名native图hash一致，框全部是native坐标x3；converter读取同idx图像与JSON，camera监督直接写出 | 未发现本地转换在这268张上额外引入变化 |
| 漏乘3或尺度误读 | 维护者在官方issue#2确认SD640×360标注对应FHD1920×1080，应乘3；本项目已乘3，仍错位 | 已知尺度问题已处理，不能把剩余问题归于漏乘3 |
| 下载/本地解压后把文件弄坏 | 三个错位sample各JPG/JSON，共6个文件，官方归档size与CRC32全匹配 | 有力支持问题已存在于发布组合；不声称CRC是完整密码学身份证明 |
| sonar投影或相机—sonar外参 | camera框直接读取原生JSON；官方export注明labels是在export后生成，公开export本身不生成这些labels | sonar几何误差不是这批camera原生框错位的直接计算来源 |
| 人工错框、框定义/标注过程有误 | 已看到框落背景/漏主体，但没有原始标注工程 | 保留候选，无法确认最初操作 |
| 标注帧号/时间、SD与FHD标注帧对应不一致 | 官方GoPro通过时间匹配并按ARIS索引命名，涉及offset；但没有这批标签的生成/关联代码或SD标注工程 | 值得排查的候选，不能据导出代码有offset就认定发生错配，更不能指定统一偏移帧数 |

## 官方归档核对方法与结果

运行 `python tools/check_uxo_release_metadata.py`。只对[Zenodo记录13778485](https://zenodo.org/records/13778485)的`data_export_recordings.7z`做HTTP Range读取，再调用py7zr 1.1.4的list()解析7z文件目录；**没有extract任何归档成员**。归档总大小16,658,054,765 bytes，本次仅传输933,860 bytes（签名及编码目录头），不是重新下载16.7GB数据，更没有解码test图像。文件目录元数据包含全归档文件名，但仅针对以下非test样本读取本地文件并比较。

| sample_id | JPG size/CRC32 | JSON size/CRC32 |
|---|---|---|
| 2023-09-21_101622_0822 | 均匹配 | 均匹配 |
| 2023-09-21_103140_0223 | 均匹配 | 均匹配 |
| 2023-09-21_103140_0309 | 均匹配 | 均匹配 |

详细member路径、大小、CRC值、本地SHA-256、每次Range与下载字节hash见 [release-header-comparison.json](../../../related_work/uxo/source-check/release-header-comparison.json)。这项新证据缩小“本地extracted副本是否被更改”的疑点，不能补足缺失的最初标注过程。

## 官方代码能说明什么

公开代码固定于`323ac6cf45bb6129806c8e3ed8ec31e22e1a392d`，下载文件与hash见[code-source-log.json](../../../related_work/uxo/source-check/code-source-log.json)。

- [release_1_export.py](https://github.com/dfki-ric/uxo-dataset2024/blob/323ac6cf45bb6129806c8e3ed8ec31e22e1a392d/scripts/release_1_export.py#L87)：按ARIS frame index命名JPG，图像内容通过时间取GoPro帧；末尾注释明确labels是在export之后生成，脚本不掌握它们。该公开代码不能还原这批JSON是谁如何画出/关联的。
- [matching_context.py](https://github.com/dfki-ric/uxo-dataset2024/blob/323ac6cf45bb6129806c8e3ed8ec31e22e1a392d/scripts/common/matching_context.py#L150)：GoPro帧索引由ARIS相对时间、fps和gopro_offset计算。说明帧号不是天然等于原始GoPro视频帧号；不证明其与后生成labels一定错配。
- [prep_8_gopro_downsample.bash](https://github.com/dfki-ric/uxo-dataset2024/blob/323ac6cf45bb6129806c8e3ed8ec31e22e1a392d/scripts/prep_8_gopro_downsample.bash#L16)：公开命令分别scale到1920×1080及640×360，没有提供这批label生成步骤。
- [维护者issue#2回复](https://github.com/dfki-ric/uxo-dataset2024/issues/2)：确认学生标SD图而发布FHD图的已知差错，并建议坐标x3。回复没有解释本轮“x3之后仍局部错位”的两个recording，也不能作为它们已修复的证据。

本地`notes.txt`中101622还有“bad, needs repeat”，但这是采集备注、没有指明camera标注错误或具体原因，不能拿它来证明本轮根因。

## 如何表达与处理

现在可以说：“**camera源数据中已有标注与对应画面不一致的问题，转换忠实继承了它。**”暂时不能说：“确定是统一延迟N帧”“确定是标注学生画错”“换标定矩阵即可修好”或“这就是模型泛化差的全部原因”。

优先取得/核对原始标注SD帧、labelme工程或生成/重命名记录，与同一时刻FHD逐帧比较；这才能区分源画框错误与帧关联错误。未取得前保留待复核角色，不对整录音盲目平移或删掉困难样本，不改历史结果。没有联系作者，本轮未获对外发送消息授权。
