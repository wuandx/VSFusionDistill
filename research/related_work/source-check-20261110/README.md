# 来源获取记录

2026-11-10 的独立复核记录；仅新增工作流文件，未修改原研究。

- `acquisition-log.json`：Crossref、机构入口、GitHub API、首次 arXiv 请求结果与 hash。arXiv 首次 Python urllib 请求因本机证书链失败，未取得结果。
- `arxiv-retry-log.json`：PowerShell 重新查询 CMOLD、CMHD、UXO 完整标题，HTTP 200、三项 `totalResults=0`。这只是精确标题查询，不能证明没有任何公开版本。
- `cmold-crossref.json`：论文 DOI 元数据；`cmold-institution.html` 是作者机构的文献入口，不是全文。
- `cmold-github-repositories.json`：repository 精确短语查询，`total_count=0`；不代表完成 GitHub 全站代码搜索。
- `uxo-github-tree.json`：官方仓库递归 tree，commit/tree SHA 为 `323ac6cf45bb6129806c8e3ed8ec31e22e1a392d`，没有 `.tex` 文件。
- `cmhd-xml-retrieval.json` 与 `cmhd-europepmc-fulltext.xml`：Europe PMC 接口重取的 JATS XML，与 `cmhd/source/fulltext.xml` hash 相同。实际下载来源是 Europe PMC；文章出版方为 MDPI，不能把镜像接口写成作者 LaTeX 或 MDPI 源码下载。
- `local-source-manifest.json`：本地源文件与只读复制的 CMOLD 表图/正文 hash；YOLOX 明确版本下载与既有归档/展开 `.tex` 的一致性验证。新下载的同字节 YOLOX 重复归档验证后未保留；保留原 `yolox/downloads/source.tar.gz`。

关键 SHA-256：

| 文件 | SHA-256 |
|---|---|
| CMOLD 已有 PDF | `f60d51937d9864c6aa6b2c35d610f7beba575f5c53b93f19add7b7099db64d41` |
| CMOLD 既有 Table 2 图 | `30b35ee007aecc4dd3e142639d0ac0481e7cd14b4e5442f3055ec64de159c487` |
| CMHD JATS XML | `7e1cf91e74e20f063656fd91c8c64e8f0b59c1b2d4c7272e597fdd261f3f9601` |
| YOLOX arXiv v2 源归档 | `ae28850a510b059de76d836972bac8032f3040b37ce30c5c94dd2a22054a6f34` |
| YOLOX 原始 `yolox.tex` | `d74fd1f208bd3bbeab7782074910929dad704e0cbd5fdebf806a652019d387c4` |

论文事实、XML stable id、LaTeX 行号和历史更正见 `../paper-evidence-review.md`。未取得的 LaTeX 不创建替代 `.tex`，没有用 PDF 转文本冒充作者源文件。
