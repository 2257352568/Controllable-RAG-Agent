# Dense / BM25 / RRF hybrid retrieval 初筛（2026-09-12）

## 结论

首轮证据不支持把等权 RRF hybrid 接入主图。Dense 在高价值的前排指标上领先；
hybrid 只在较深的 `Recall@10` 上有小幅增益。保留实现与评测入口，用正式人审集
复验，而不是为了简历技术名词强行上线。

## 可复现配置

```powershell
venv\Scripts\python.exe evaluation\run_hybrid_retrieval_evaluation.py `
  --trust-local-index --ks 1 3 5 10 `
  --candidate-pool 50 --rrf-constant 60
```

- 数据：`evaluation/dataset.jsonl`，SHA256
  `cacf6e16c83089df1f9780aa35045e01d081794a1ec6929a97d4ee383380e25a`
- chunks：618 个，FAISS `IndexFlatL2`
- FAISS SHA256：`dab1276f8aed2a84ee6afe3a4db11f9e7420cf40a86661b8a9c728d17fea5b74`
- docstore SHA256：`b2f74c7eace8a8517d27e027cfea18e50098febec4ed2af6f5af10a7f9aaa26b`
- Embedding：千问 `text-embedding-v4`，1536 维
- BM25：`k1=1.5`、`b=0.75`
- Hybrid：dense 与 BM25 各取 50，等权 RRF，`rank_constant=60`
- 样本：11 条 answerable 种子；11 次 Embedding query；0 次聊天模型调用
- 时间：2026-09-12T22:43:12+08:00

## 结果

| 系统 | Hit@1 | Hit@5 | Recall@5 | Recall@10 | MRR@10 | marker recall@10 | 查询均值 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.9091 | 1.0000 | 0.5254 | 0.6173 | 0.9318 | 0.9091 | 778.9532 |
| BM25 | 0.7273 | 0.8182 | 0.3899 | 0.5055 | 0.7556 | 0.7727 | 2.0225 |
| RRF hybrid | 0.6364 | 0.9091 | 0.4189 | 0.6488 | 0.7318 | 0.9091 | 781.3567 |

延迟是单机单次串行测量；hybrid 包含 dense、BM25 与本地融合，不能当容量或
P95 结论。Embedding SDK 没有返回可核验 token 用量，因此不虚构 token 数。

## 为什么融合变差

等权 RRF 不理解两个检索器的绝对质量。BM25 在 3/11 题的 Top-1 未命中，仍与
dense 获得同等投票权，可能把 dense 的正确首位文档向后推。实际逐题结果中，
`hp1-002`、`hp1-009`、`hp1-011` 都出现 dense Top-1 命中而 BM25 与 hybrid
Top-1 未命中；`hp1-010` 则是 BM25 命中但 hybrid 仍未排到首位。

## 约束与下一步

1. 当前 relevance 是 evidence marker 命中文档集合，不是穷尽式人工标签；指标
   只能称 marker-proxy，不能写进简历作为正式 Recall。
2. 11 题与配置已被观察，不应继续在同一小集合上试权重、RRF 常数并挑最好结果，
   否则产生评测集过拟合。
3. 完成 50+ 精确 chunk 人审后，在独立开发集选择融合方式；在冻结测试集上只跑
   一次，并同时比较答案质量、Top-K、P95、成本和错误率。
4. 若加 reranker，应比较 `dense`、`hybrid`、`dense+rerank`、`hybrid+rerank`，
   只有端到端收益覆盖额外延迟与调用成本才接入主链路。

## 面试可讲失败

“我先实现确定性 RRF 和同题评测，没有因为 hybrid 是热门关键词就上线。首轮结果
显示它牺牲了前排命中，仅改善深层召回，因此我保留为实验能力并冻结配置，等待
独立精确标签复验。这说明检索架构选择必须由目标指标和成本驱动。”
