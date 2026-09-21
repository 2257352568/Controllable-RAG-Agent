# 修复后单题开发回归：`hp1-042`

这是已有 52 题开发集中的一题，不能当独立留出集或正式质量结论。

- 结果文件：`evaluation/results/diagnostic-agent-postfix-20260916/details-20260916-202502.jsonl`（Git 忽略）。SHA256：`70c9e4a2f76f7fed5af8d3bff5250d3487aa99cac545840ffaec8f0abce60f60`。
- 数据集 SHA256：`5a713470ef679196c07d92bb709ec6a49319eeceeff4f096b2bc389142ea3bf3`。
- 生成模型：`qwen3.7-flash-2026-07-15`；无裁判。Prompt `2026-09-16.1`，主图 `2026-09-16.1`；只启用 chunks，Agent 一题一次、无重试，`max_steps=8`、聊天请求上限 20、Token 上限 12,000、执行期限 120 秒。
- 结果：无执行异常，但 `token_budget_exhausted`，`answer_hit=0`、零引用；3 步、2 次检索、16 次聊天请求、记录 6,550 Token、61.211 秒，未进入最终答案生成。
- 截止原因：下一次调用需保守预留 5,502 Token，已提交 6,550 Token，和为 12,052，超过 12,000 的准入上限。模型未发送该调用；这不等于实际已经用完 12,000 Token。
- 账本快照 `budget_accounting_complete=false`，而旧运行顶层 `token_accounting_available=true`，暴露了预算终态标记不一致。现已修改运行时代码使顶层沿用账本完整性标记；**旧 JSONL 不回写**。

旧 `hp1-042` 三次运行的预算为 20,000 Token，且其时主图、Prompt 不同；本次 12,000 Token 单题回归不能与旧数据做质量或成本改进对比。它只证实：控制流没有抛递归异常，但当前方案仍可能在形成答案前耗尽保守准入预算。下一步应先减少规划/检索调用，并以固定配置的小样本验证质量和成本，再考虑完整评测；不要靠单纯提高预算包装为质量改进。
