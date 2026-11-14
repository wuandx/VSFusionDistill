# camera_s_test_evaluation

2026-11-13。用户明确要求查看test效果，授权打开当前paired_recording_split冻结的600张新test（不是扩大访问原研究其它test）。只评价已完成camera S640×384 epoch200 actual raw，checkpoint SHA256 edff61c275274a58112e8e408a25a9a76dd308c79de8cfaba3e6474dbdc974a0，固定权重，不根据test选择S/M、阈值、epoch或训练配方。

读取当前交付包中这600身份的相机图、原JSON与元数据；身份/图片hash/标签坐标/类别核对通过后独立test数据索引，不改train/val/原包。预处理、score.01/NMS.65/max100、COCO AP@[.5:.95]/AP50/AP75/AR1/10/100及逐类逐录音与val完全相同。记录test600、每类200、6录音/5保守组与历史使用限制；本次之后该test已查看，后续开发不得把它称未使用或据其调参后继续作为无偏最终评价。

检查失败或非有限预测则停止保留，不重洗split、修标签或更换模型以改善test分数。用户新授权更新旧协议中不执行当前test评价的阶段限制；原研究其余test仍不读。无需训练，输出test_actual_raw_epoch200与指标解释。
