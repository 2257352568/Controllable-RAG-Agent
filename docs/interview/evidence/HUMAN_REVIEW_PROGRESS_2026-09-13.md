# 黄金集人审进度审计（2026-09-13）

执行：

```powershell
venv\Scripts\python.exe evaluation\review_progress.py --format markdown --next-limit 10
```

当前权威结果：

- approved：0/50
- missing：50
- rejected：0
- stale_case：0
- stale_corpus：0
- invalid_approval：0
- formal gate ready：false

风险优先的下一批为：`hp1-012`、`hp1-013`、`hp1-043` 至 `hp1-050`。这些是
unanswerable/adversarial 类型；自动语料搜索不能证明“不存在”或错误前提成立，所以优先
要求人工阅读判断。之后依次处理 multi-hop、reasoning、single-hop。

进度函数只读取数据集、review log 和 corpus hash，不反序列化语料、不写 review log，
也不会自动批准。它按每题最后一条决定统计，并把 case hash 变化、corpus hash 变化、
拒绝和正负例证据语义错误分开报告。当前不存在 `evaluation/reviews.jsonl`，因此 0/50
是预期且真实的发布阻断状态，不是工具故障。
