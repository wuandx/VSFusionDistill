# bomb 剩余录音双端审核

2026-11-13，助手逐张审核，不是专家 GT 或精密同步认证。遵循 `experiment/archive/paired-bomb-remaining-plan.md`；原研究、相机框、时间、注册、split、test、训练均未更改。下表“本批”是本报告九个根去重后结果，不与替代提案重复相加。

| recording | 本批已看唯一身份 | 本批接受 | 加旧接受后 | 已有配对源库存 |
|---|---:|---:|---:|---:|
| 171105 | 120 | 93 | 116 | 715 |
| 174439 | 153 | 52 | 105 | 734 |
| 175000 | 60 | 12 | 107 | 793 |
| 175905 | 144 | 107 | 107 | 705 |
| 180506 | 120 | 109 | 109 | 737 |
| 180722 | 120 | 101 | 101 | 743 |
| 181139 | 144 | 111 | 111 | 745 |
| 182317 | 146 | 31 | 31 | 146 |
| 2023-09-21_160551 | 180 | 107 | 107 | 1385 |

175506 原先100已足，本批未改。合并后 bomb 十条中九条达到100，182317只31接受。新增723接受，1187唯一身份实际查看；1664个根内决策含重复替代方案，不作唯一身份数。此处旧23/53/95按此前已有接受合并，最终累计去重由父任务导出负责。

## 边界修订与失败

175905 的 B 含下方支撑，E/G可截断斜端。逐页查看后，在独立 visual_revision 根保存显式坐标，重新生成不可覆盖图，再逐页审核，132中107接受。旧 B/E/G 全部失败记录保留。

160551 的 B/F/G截颈或纳入地面。最后 K 使用固定平滑强度阈值65的连通分量，不裁能量，仍仅作为提案。120逐看后52接受；其余有颈部漏框、地面或相机截断，未接受。再从已授权来源中补充早段与775–914段，212候选只实际查看前60，其中55接受。接受的框覆盖可见亮主体及颈缘，不能将下游阴影整体当作实体；自然raw波束边缘截断保留可见部分。未审核60–119生成页不能计为已看。

182317 全部源候选140–285共146已查看，后段相机目标逐渐出底边。旧22接受不是物理上限：最后对148/151/157/160及166–170九帧做显式声呐边界修订 `[25, 原y0, 101, 218]`，保存新图并实际逐张看后9接受，总31。166–170虽相机标签触360边界，底帽仍可见，不能按标签边界自动判断截断；171–175临界未接受。即使140–175全视为可能，宽松容量上界36仍小于100，176–285已明显截断。此结论只针对现有合法SD配对来源，不能以换声呐模板补回缺失相机内容。

## 审核根与候选血缘

所有根位于 `DataSet/`：

- `paired_assistant_bomb_remaining_review`：578已看/343接受。
- `paired_assistant_bomb_remaining_strong`：264/0。
- `paired_assistant_bomb_primary_return`：168/0；175905只0–47实际审核，其余已生成不计。
- `paired_assistant_bomb_visual_revision`：132/107。
- `paired_assistant_bomb_old_supplement`：321/145。
- `paired_assistant_bomb_source_supplement`：12/12。
- `paired_assistant_bomb_floor_untrimmed`：120/52。
- `paired_assistant_bomb_floor_source`：60/55。
- `paired_assistant_bomb_edge_revision`：9/9。

默认源为 `paired_visible_expansion/candidates.json`。四个附加候选manifest为上述 old_supplement、source_supplement、floor_source、edge_revision 根的 `candidates.json`；old_supplement及edge_revision为原候选的原样子集，source_supplement及floor_source从source-inventory与camera_temporal_all清单构建合法原身份，保留原相机框与来源role。不包含test。

所有决策均保存不可变审核图SHA-256、原声呐与相机SHA-256、明确接受/未决、非专家与未认证同步标记。全1664根内决策逐项校验审核图和源图hash，所有723接受框与审核spec精确一致，重复接受身份无框冲突；结果在 `DataSet/paired_assistant_bomb_remaining_review/verification-final.json`。最终导出由父任务统一完成。本报告没有覆盖旧失败或把未决当负样本。
