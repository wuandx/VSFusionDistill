# doc/logs 索引

本目录是**按日期的叙事日志**，不是台账。能查证的数字与判断进 `doc/experiments.md`（一节一实验，五段格式）；本目录只留"当天怎么查、查到了什么、为什么这样判"。

命名：`YYYY-MM-DD-<主题>.md`，主题用英文短语。新日志不覆盖旧日志；结论被推翻时在旧文件顶部加一行"已被 ××× 取代"，不删原文（保留推翻的痕迹本身是证据）。

---

## 索引（新→旧）

| 日期 | 文件 | 主题 | 状态 |
|---|---|---|---|
| 11-06 | `2026-11-06-e13-caliber-note.md` | E13 三臂主表的口径与表注：`val` / `val_id` 两列不可混用，四条使用限制与"为什么 val_id 才算与文献同性质" | 现行 |
| 11-06 | `2026-11-06-baseline-progress-and-issues.md` | 基线阶段进度与问题汇总（入口文档）；含附录 A 冻结条款与实验阶梯 | 现行 |
| 11-05 | `2026-11-05-literature-comparison-blob.md` | 与同类论文 baseline 对比（主口径 blob，含 val-ID 文献式考场） | 现行 |
| 11-05 | `2026-11-05-projected-label-alignment.md` | 投影标注能否当 GT：对齐实测与口径裁定 | 现行 |
| 11-05 | `2026-11-05-gt-metric-decision.md` | 主口径复裁：all → blob；all 降为诊断 | 现行 |
| 11-05 | `2026-11-05-consolidated-teacher-student-table.md` | 新旧平台教师/学生总表（同考场补齐 all 口径） | 现行 |
| 11-05 | `2026-11-05-sonar-failure-session-diagnosis.md` | 声呐 val 失败场次诊断（不是看不见，是不报） | 现行 |
| 11-04 | `2026-11-04-literature-baseline-protocol-comparison.md` | 九篇同类论文的协议与 baseline 对比（blob 复裁前的版本） | 现行，读数口径以 11-05 为准 |
| 11-04 | `2026-11-04-s0c0-degaug-config-deviation.md` | s0_c0 相机基线配置偏离（AOSampleDegLevel 默认 probs） | 现行 |
| 11-03 | `2026-11-03-e11-final-gt-calib-drift.md` | 终版 GT 标定基点漂移：7/47 越门与 `--calib-from` 收口 | 现行 |
| 11-03 | `2026-11-03-e11-c1-val-id-decomposition.md` | 判据 1 未过的分解：blob 分母异质主导 | 现行 |
| 11-02 | `2026-11-02-e11-difficult-subset-draft.md` | 困难子集草案（四轴 + 复合 DS-hard） | 草案，未采用 |
| 11-02 | `2026-11-02-e11-row-residual-diagnosis.md` | 行残差分型诊断（端部主导 / 均匀差 / 错侧 / 整圈） | 现行 |
| 11-02 | `2026-11-02-e11-prep-chain-interruption.md` | E11 准备链中断记录 | 存档 |
| 11-02 | `2026-11-02-e11-data-gate-infeasible.md` | 数据闸门初判不可行 → 预数据修订转可行性 | 已被 11-03 收口取代 |
| 11-02 | `2026-11-02-tau4-resume-weights-only.md` | τ4 断点续训（weights_only）事故 | 存档 |
| 11-01 | `2026-11-01-e10-literature-check.md` | E10 文献核对：UXO 数据集引用论文与协议（含被引列表） | 存档，结论已被 11-04/11-05 细化 |
| 11-01 | `2026-11-01-e10-camera-audit.md` | E10 相机支路审计 | 存档 |
| 10-31 | `2026-10-31-e05-test-ap-zero-diagnosis.md` | E05 test AP=0 诊断：域移位定性 | 存档 |
| 10-30 | `2026-10-30-f2-codebase-w1-w3.md` | W1–W3：代码库搭建与 COCO 复现门 | 存档 |

---

## 与其他文档的分工

| 文档 | 职责 |
|---|---|
| `doc/experiments.md` | 台账：一个实验一节（目的 / 设置 / 结果 / 解读 / 结论），数字可溯源 |
| `doc/logs/`（本目录） | 日期叙事：当天排查链、事故、诊断过程 |
| `doc/f2-rethink-2026-11-01.md` | 主线复盘（§0 主线、§8 执行纪律、§9 二次审查） |
| `doc/f2-mainline-questions.md` | 主线问答板（Q1–Q6，只记状态与去向，不记数字明细） |
| `doc/topic-f2-…-2026-10.md` | 研究计划全文（问题定义、方法空间、判据） |
| `doc/reviews/` | 代码审查 |
| `doc/evidence/` | 证据图 |
| `doc/survey-2026-11-06/` | 与 CMOLD/CMHD 的协议对齐调查（两份，外部调研，不作台账） |
