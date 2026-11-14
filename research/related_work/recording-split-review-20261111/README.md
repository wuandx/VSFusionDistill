# UXO及相近声呐数据的划分调查

日期：2026-11-11（Asia/Shanghai）。任务是调查并提出建议，不是执行新split。未访问原test图像/逐帧标注/预测，未启动训练或伪标签生成，原研究只读。

## 结论

最直接证据来自同一UXO数据集的CMHD：按完整capture trajectory划分，按类别均衡抽取轨迹并均匀抽帧。CMOLD未披露split单位，不能称其按帧随机，也不能将CMHD划分冒充CMOLD协议。本地推荐先采用按类别分层的recording-level train/val约3:1，保留原test关闭；比例是我方选择，借鉴CMHD的train:val=6:2，不是复刻其完整6:2:2。

当前40条允许开发录音为12/12/16条，若全部通过准入，可对应train 9/9/12条、val 3/3/4条，总计30/10。该规模由录音数定义，不保证抽帧前后的图像数严格3:1。

## 1. 来源与证据层级

| 来源 | 实际阅读格式 | 已查到的划分 | 可支持与限制 |
|---|---|---|---|
| UXO官方发布，Dahn et al. OCEANS 2024 | 本轮重新获取官方README、config与release_1_export.py；作者机构论文入口HTML | 已查文件未定义train/val/test；官方脚本按recording导出 | 在所查公开入口未找到标准split，不等于证明所有附件均无split。原论文PDF下载403，本轮未读该PDF，不能把README结论冒充论文结论 |
| CMOLD，IEEE Access 2026 | 本地PDF第5–7、11页的本会话直接阅读与已保存抽取正文 | 约4700 image pairs用于training and validation；核验同一capture moment的配对 | 未披露按帧/轨迹的单位、精确train/val数量、seed、逐样本清单；不存在支持“帧级随机划分”的原文依据 |
| CMHD，Sensors 26(14):4340，§3.1 | 重新获取Europe PMC JATS XML，与既有XML SHA256相同；非LaTeX | 每类随机选10条完整capture trajectories，每条均匀采100帧；按trajectory分6:2:2；train/val/test=1800/600/600且类别均衡 | 最直接的同数据参考。按类别每个角色分别6/2/2条轨迹是由原文推算，不是公开录音名单。未恢复其exact split、seed或抽帧索引 |
| UATD，Scientific Data 9:739，Data Records | 原始论文JATS XML，另读Nature HTML；非LaTeX | 发布9200张sonar图与XML标注，7600 train、800 Test_1、800 Test_2 | 此处pairs指图像—标注，不是RGB–sonar；已查全文未明确录音隔离，不足以作为recording-level依据。Technical Validation的randomly assigning指分配给标注者，不能写成训练随机划分 |
| Marine Debris FLS，arXiv:2503.22880v1，§III-D | 原始arXiv HTML；非LaTeX | 区分watertank/turntable/quarry与多个任务，说明数据文件组织；本轮未定位可直接复用的完整录音split规则 | 可参考受控采集结构，不能据此创造按轨迹划分或比例。本轮曾探测TeX源包可获取，但没有保存/解包/阅读，故不以TeX作为证据 |

CMHD原文关键句：

> For sampling, we first randomly selected 10 complete capture trajectories with paired RGB bounding-box annotations for each category, then uniformly sampled 100 frames from each trajectory, and finally split the data at the trajectory level into train/val/test with a ratio of 6:2:2.

注意：这是**完整轨迹进入候选选择、从轨迹均匀抽帧、不同角色轨迹不交叉**。不等于把抽出的图像混在一起随机6:2:2。“均匀100帧”解决冗余/长录音支配，轨迹隔离解决跨角色相邻帧泄漏，两者职责不同。

## 2. 对本地40条候选的只读核对

输入仅为已经限定允许开发范围的`DataSet/camera_temporal_all/manifest-resolved.json`，读取其recordings与items中的recording/category/paired_role；没有再解析含test的frame_meta或camera.json。

| 类别（清单原值） | 录音数 | native camera候选帧 | 历史paired身份数 | 历史train/val_id录音 | 历史val录音 | 无历史paired角色的额外录音 |
|---|---:|---:|---:|---:|---:|---:|
| 100lbs_aircraft_bomb | 12 | 8997 | 1294 | 7 | 3 | 2 |
| incindiary_grenade | 12 | 7932 | 1524 | 9 | 3 | 0 |
| mortar_shell | 16 | 9832 | 1928 | 11 | 4 | 1 |
| 合计 | 40 | 26761 | 4746 | 27 | 10 | 3 |

保留清单中`incindiary_grenade`原拼写，此处不改类别映射。4746含历史val_id身份，不能与旧3322+830开发图数4152混称。

额外3条是2023-09-20_175000、2023-09-20_182317、2023-09-21_110049。它们无该清单历史paired角色，**不等于没有时间对应的sonar，也不证明从未用于整个研究历史**。不得直接接入train；需独立核查配对、GT与历史。

## 3. 我方建议，尚未冻结

1. 分组单位采用完整recording；核查一个真实capture trajectory是否被拆成多个recording/片段，若有则这些片段须合并为同组。只靠文件名不同不足以证明独立。
2. 以共同配对候选与录音级来源元数据核查类别、日期、采集设置（range/gain/resolution等可获得字段）、重复轨迹及历史使用。字段未知就标未知，不看模型分数挑val。
3. train/val按类别分层约3:1。如果40条都合格，建议类别录音数为9/3、9/3、12/4，总30/10。该比例仅为本地development，不新建或宣称有独立final test。
4. 优先审查能否保留现有10条开发val（每类3/3/4条）的身份，再决定其余录音；这样避免没有理由地重洗开发集。保留前仍须核查更高层轨迹是否重叠、条件覆盖与标注。额外3条通过准入才可补充train；未通过就保持deferred，不强凑30条。
5. 若需要重分，预先固定按类分层的算法、seed与条件约束，保留生成候选和选择依据；只依据来源/覆盖，禁止跑多个split后按AP挑选。随机seed本身不能保证轨迹独立或类别覆盖。
6. 录音角色先定，抽帧后定。可借鉴CMHD每条均匀100帧，作为后续采样候选规则；目前不冻结100帧，也不由此推导已有4000对可用。应先统计共同有效配对范围，明确不足100帧、重复映射、断续覆盖和标注暂缓的处理。
7. 一个paired样本的camera与sonar必须共享role；相机教师、sonar-only基线和CMOLD共用该角色表。样本QA失败记deferred，不因此把该录音余下帧改到另一个role。
8. 用固定COCO起点重训。旧camera权重已见原37条录音，保留历史val身份并不能让旧权重得到新录音泛化资格。

recording隔离只回答相应分布中的跨录音开发验证；UXO受控采集且同类可能共享同一物体/环境，不能升级为未见物体实例、跨场景或真实海域泛化。

## 4. 真正冻结时的交付物

- 录音角色表：group_id、recording、category、train/val角色、来源、历史角色、采集条件、资格/待核原因。
- split规则：分组依据、类别名映射、比例、算法/seed（若使用）、人工约束、已知限制及版本hash。
- 检查结果：group/recording交集为0，各类覆盖，camera/sonar角色一致，额外录音准入有依据，原test保持关闭。
- 后续单独保存抽帧/时间配对规则与逐样本manifest。角色表不会因为稍后个别帧被defer而重洗。

本轮没有生成上述正式角色表，没有改旧split或启动训练。完整来源响应、时间、字节数、SHA256和403失败保存在`acquisition-log.json`；获取工具在`tools/investigate_recording_split_sources.py`。

## 原始入口

- UXO官方仓库：https://github.com/dfki-ric/uxo-dataset2024
- UXO作者机构论文入口：https://robotik.dfki-bremen.de/en/research/publications/15133
- CMOLD DOI：https://doi.org/10.1109/ACCESS.2026.3666096
- CMHD全文：https://pmc.ncbi.nlm.nih.gov/articles/PMC13417324/ ，§3.1
- UATD全文：https://www.nature.com/articles/s41597-022-01854-w ，Data Records
- Marine Debris FLS：https://arxiv.org/html/2503.22880v1 ，§III-D
