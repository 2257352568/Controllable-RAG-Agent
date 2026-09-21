# LLM-as-a-Judge 人工抽检契约（2026-09-12）

## 目的

正式结果不能因为“开启了模型裁判”就可信。需要对裁判分数做人审校准，并避免研究者在看到结果后随意挑选容易一致的样本。

## 实现

- 从成功且包含 judge 输出的记录中，按 `system × category` 分层。
- 每层使用固定 seed 与 record key 的 SHA256 排序，至少抽取该层 20%。
- 人工填写 correctness、relevance，以及适用时的 faithfulness，分值范围为 0 到 1。
- 审核记录追加写入，绑定 details SHA256、record SHA256、reviewer、时间和审核版本。
- 答案、引用摘录、judge 输出或整份 details 变化后，旧审核被标记 stale。
- 报告 coverage、各指标 MAE 和给定容差内的一致率；`--require-complete` 可作为 fail-closed 门禁。
- 版本化协议 `judge-audit-2026-09-12.1` 在正式结果前固定：抽样率 20%、评分容差 0.2、容差内一致率至少 80%、MAE 不高于 0.2、抽中记录完成率 100%；`--require-quality-gate` 未达标即非零退出。
- 为 faithfulness 人审，details 对模型裁判实际看到的每条检索上下文保存最多 1,200 字符摘录、页码和内容 hash；控制字符会删除，结果目录不提交 Git。人和模型由此使用相同证据范围。
- 裁判 Prompt 同样把 question/reference/candidate/context 视为不可信评测数据并转义伪造标签，避免候选答案或检索文档直接注入“给满分”等裁判指令。

## 验证

- 固定 seed 重复抽样结果一致，且每个 system/category 分层均被覆盖。
- 人工分数的范围、必填指标和 SHA256 格式 fail closed。
- details 或单条回答变化会使审核失效。
- MAE、容差一致率、覆盖率和 complete 状态均有确定性测试。
- 全套 128 项离线测试、两套数据审计和 `git diff --check` 通过。

## 边界

目前完成的是抽检机制，尚未产生正式三基线结果或实际人评分数。`0.2` 容差只是工具默认值，不应事后按结果调整；发布前需要预先声明可接受阈值。单一人工 reviewer 也不能测量 reviewer 间一致性，后续可增加双人重叠样本和 Cohen's kappa/ICC。
