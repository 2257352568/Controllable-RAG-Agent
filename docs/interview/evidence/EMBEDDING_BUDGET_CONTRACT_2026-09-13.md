# Embedding 独立预算契约（2026-09-13）

## 问题

Chat 请求数和 Token 不能覆盖检索器内部的 Embedding 调用。一个 Agent 节点还可能
批量编码多个文本，因此“调用次数”和“输入文本数”也不是同一指标。

## 契约

- `AGENT_MAX_EMBEDDING_REQUESTS` 默认 12，限制 embedding operation 数。
- `AGENT_MAX_EMBEDDING_INPUTS` 默认 20，限制送入的文本总数。
- `embed_query(text)` 消耗 1 request / 1 input。
- `embed_documents([N texts])` 消耗 1 request / N inputs。
- 两种限制都在 provider 前原子检查；失败原因分别为
  `embedding_request_budget_exhausted` 和 `embedding_input_budget_exhausted`。
- 计数进入 State、checkpoint、脱敏 Trace、Streamlit 汇总和正式评测 metadata。
- 熔断器位于预算外层，因此 open circuit 的快速拒绝不会消耗 Embedding 额度。

## 验证

`tests/test_runtime_budget.py` 证明第二个 query 超过 request 上限时不会到 provider，
以及三文本 batch 超过 input 上限时整个 batch 在发送前拒绝。`tests/test_checkpointing.py`
证明第一次 query 的计数会进入 checkpoint，恢复后第二次 query 仍被累计上限拒绝。

真实 `text-embedding-v4` 也在活动账本下执行：第一次 query 返回 1536 维并累计
1 request / 1 input；第二次 query 以 `embedding_request_budget_exhausted` 在本地
拒绝，最终计数仍为 1/1。该验证只发送了第一次输入。

完整离线测试当前 171 项通过。评测结果还会分别聚合 `embedding_requests` 与
`embedding_inputs`，并允许用 `--max-embedding-requests`、
`--max-embedding-inputs` 固定实验配置。

## 声明边界

这些指标控制逻辑操作数和输入条数，不代表 tokenizer Token、供应商内部 HTTP 重试数
或实际账单金额。批量大小、文本长度与缓存都会影响真实成本；在供应商返回可靠 usage
或能接入账单明细前，不应把 input count 写成“节省了多少 Embedding Token/费用”。
