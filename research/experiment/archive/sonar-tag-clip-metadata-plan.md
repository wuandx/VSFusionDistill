# sonar_tag_clip_metadata：单录音容器证据核查

2026-11-13。现有GoPro元数据审计的六录音不含123500。唯一新增访问：按已冻结manifest从`D:/pby/data_processed/gopro/`读取该录音的SD/FHD/UHD三份对应MP4，仅解析顶层box与moov/track handler，不解码像素、不读mdat。以同一源文件的三分辨率作对照，记录明确的GoPro遥测轨/镜头或稳定字段、元数据hash和文件stat。如果processed剪辑没有可解释的设置字段，不推断实际镜头或防抖关闭，不访问其他录音或试图从分辨率确定镜头。
