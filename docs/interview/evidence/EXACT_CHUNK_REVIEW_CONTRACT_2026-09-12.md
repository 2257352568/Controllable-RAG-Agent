# 精确 Chunk 黄金证据审核契约（2026-09-12）

## 暴露的问题

旧检索评测把“包含任一 evidence marker 的 chunk”都视为 relevant。角色名等宽泛 marker 会在大量不支持答案的页面出现，因此 marker-proxy precision/recall 不能作为正式检索质量。

## 改造

- 人工审核正例时展示带页码、内容哈希和编号的语料片段。
- 正例批准必须选择至少一个真正支持参考答案的 chunk；负例禁止绑定正证据。
- 选择结果以 `gold_evidence_chunk_sha256` 写入追加式审核记录，并随 formal dataset provenance 固化。
- checklist 版本升级为 `2026-09-12.2`，旧版审核自动失效。
- 正式检索评测优先使用精确内容哈希；未完成人审的数据仍明确标记为 `marker_proxy`。
- formal gate 重新计算当前 corpus 的文档内容哈希集合，不属于该集合的 gold hash 即使格式合法也会被拒绝。

## 验证

- 正例无精确 chunk 时 fail closed。
- 负例携带正证据时 fail closed。
- 检索测试构造 marker 命中错误 chunk、人工 hash 指向正确 chunk 的冲突，确认正式标签覆盖 marker proxy。
- 全套 113 项离线测试、两套数据证据审计和 `git diff --check` 通过。

## 边界

当前完成的是审核与消费机制，不是 50 条标签本身。内容哈希解决索引序号漂移，但相同文本重复出现仍需结合页码审计。人工选择可能漏掉其他相关 chunk，因此正式报告应称为 gold supporting-chunk recall，而不是宣称穷尽式全语料 relevance recall。
