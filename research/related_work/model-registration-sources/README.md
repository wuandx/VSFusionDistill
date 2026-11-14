# 注册与标定来源

2026-11-11。结论见[核查报告](../../复现/camera-baseline/sonar-model-registration-consistency.md)。

- [网络获取日志](acquisition-log.json)：GitHub issues/comments/PR与Zenodo v1元数据；第三方PR源码只检查，未执行。
- [git来源与hash](history-provenance.json)：官方历史快照与精确commit/path/hash。克隆在`../uxo-upstream-history`，当前可见公开历史的[全部路径（本地产物说明）](../../ARTIFACTS.md#artifact-1c989e5fcb1a)已保存。
- [安装角修改diff（本地产物说明）](../../ARTIFACTS.md#artifact-13654b9a5306)、[notebook历史标定](notebook-era-transforms.yaml)、[当前标定](current-transforms.yaml)、[原始notebook（本地产物说明）](../../ARTIFACTS.md#artifact-a488d355342f)。
- [历史README尺寸与测量说明](historical-README.md)、[早期测点笔记](object-notes-9a0ebad3.md)。这些是官方仓库历史，不是CMHD论文或已认证OBJ注册。
- [作者外参精度回复](issue-3-comments.json)；[issue5](issue-5-comments.json)抓取时无回复。第三方提问内容不能升级为官方事实。
- [第三方PR6静态源码](third-party-pr6-log_to_rerun.py)：明确OBJ仍在独立未注册坐标，不能用其可视化替代GT。

下载包在`../sonar-projection-audit-assets/`，此前已核验官方MD5。本轮Zenodo v1元数据表明calibration和3dmodels的包MD5与已获取版本相同，未重复下载大包。UXO原论文PDF获取403的问题仍未解决；第三方对其内容的转述没有作为本报告的论文事实依据。
