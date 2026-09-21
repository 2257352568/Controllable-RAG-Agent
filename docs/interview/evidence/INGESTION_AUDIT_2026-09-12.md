# 摄取与切分参数审计（2026-09-12）

## 所有权与来源

`sophisticated_rag_agent_harry_potter.ipynb` 明确声明并调用 `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)`。这是上游配置，本地 Qwen 迁移从原 docstore 恢复文档并重新 embedding，没有重新选择切分参数。

## 当前索引事实

- chunks：618 条，字符数 min/mean/P50/P95/max 为 42/837.39/944/995/999，metadata 含 page/source。
- summaries：17 条，字符数为 1147/1549.29/1505/1939.2/2000，metadata 含 chapter。
- quotes：1299 条，字符数为 50/161.03/112/430.4/1494，当前无位置 metadata。
- chunks 中有 399 对同页相邻文档，精确 suffix-prefix overlap 为 117–199 字符，mean 162.09、P50 158、P95 194，没有零重叠。

完整 notebook、pickle 和 FAISS 哈希保存在同目录的 `INGESTION_AUDIT_2026-09-12.json`。

## 为什么不是固定 200

RecursiveCharacterTextSplitter 会优先按段落、换行、空格等分隔符递归切割，再在长度约束内组合片段。因此 overlap 是目标上限，不保证每个相邻 chunk 精确复制 200 个字符。

## 边界

审计证明当前索引与上游 1000/200 字符契约一致，不证明这组参数最优。要回答最优性，仍需从原始 PDF 对多组 chunk size/overlap 重建临时索引，在固定 embedding、问题集和 Top-K 下比较精确 supporting-chunk recall、precision、答案质量、Token、延迟及索引规模。
