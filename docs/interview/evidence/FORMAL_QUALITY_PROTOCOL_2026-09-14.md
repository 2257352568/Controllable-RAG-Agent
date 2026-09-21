# 正式评测质量协议（预注册于 2026-09-14）

## 为什么需要第二层门禁

`--formal` 的输入门禁只能证明实验使用了至少 50 条人工批准题、完整三系统和模型
裁判。它不能证明结果足以支持“Agentic RAG 值得额外复杂度”：三系统都可能错误率
很高，Agent 也可能显著弱于 naive RAG。

因此在正式黄金集和正式结果产生之前，项目固定了机器可执行协议
`formal-quality-2026-09-14.1`。以后若更换模型或研究问题，应先创建新协议版本再运行，
不能看到失败结果后修改本版本门槛。

## 预注册门槛

| 范围 | 指标 | 门槛 |
|---|---|---:|
| 实验 | 模型 | `qwen3.8-max` |
| 实验 | 每系统人工题数 | ≥50 |
| 实验 | 每题独立重复 | ≥3 |
| 实验 | 配对 bootstrap | ≥2,000 次 |
| 三系统 | 每系统执行错误率 | ≤5% |
| 三系统 | 每系统密钥泄露率 | 0 |
| Agent | answer hit | ≥0.80 |
| Agent | answerability decision accuracy | ≥0.90 |
| Agent | citation evidence recall | ≥0.80 |
| Agent | citation precision | ≥0.75 |
| Agent | judge correctness / relevance / faithfulness | ≥0.80 / 0.85 / 0.85 |
| Agent | claim citation contract pass rate | 1.0 |
| Agent | claim schema 最终失败率 | ≤2% |
| Agent | grounding failure rate | ≤10% |
| Agent 稳定性 | 全重复执行成功 / 终止一致 / 拒答一致 | ≥0.95 / 0.90 / 0.90 |

相对收益门槛以 naive RAG 为对照，在 `answer_hit`、`judge_correctness`、
`judge_faithfulness` 三个主要指标中：

- 至少一个指标的 case-level 配对 bootstrap 95% CI 支持 Agent，且 Agent 减 naive
  的均值差不低于 0.03；
- 任一主要指标若显著支持 naive RAG，则整个质量门禁失败。

这些是本项目为了简历发布而选择的最低标准，不是行业统一标准。通过也不能替代
20% 模型裁判人工校准；裁判审核仍由 `judge-audit-2026-09-12.1` 单独把关。

## 执行与完整性

正式命令要求至少三次重复：

```powershell
venv\Scripts\python.exe evaluation\run_evaluation.py `
  --dataset evaluation\dataset_formal.jsonl `
  --formal --judge --repetitions 3
```

程序先保存 details、summary 和 failures，再生成 `quality-<timestamp>.json`。质量门禁
失败时证据不会被删除，但进程返回非零。summary 记录协议版本、数据集 SHA256、
details SHA256 和记录数；历史结果复验会从逐条 JSONL 重新计算三系统汇总和配对
bootstrap，再比较保存的 summary，避免只改聚合数字绕过门禁：

```powershell
venv\Scripts\python.exe evaluation\verify_formal_quality.py `
  --summary evaluation\results\summary-<timestamp>.json `
  --details evaluation\results\details-<timestamp>.jsonl `
  --dataset evaluation\dataset_formal.jsonl
```

复验器同时校验 dataset 文件 SHA256、case ID 唯一性、题目/参考答案/题型/answerable
字段，以及 case × system × repetition 的完整笛卡尔积；details 与 summary 自洽但来自
删减或替换题集时仍会失败。

实现快照 SHA256：

- `evaluation/formal_quality.py`：`cb144ebd4c1af68d806f0241215328c0707fc0045d6bc9049d8da3d4a8aa40c0`
- `evaluation/verify_formal_quality.py`：`9b54b07ac2a26fc3c12ee94f1e990dea82153ce0b13d0c58c0825836ff9caa6c`
- `evaluation/run_evaluation.py`：`12a15e99e97cc7058c021e156280ce60bd5dcdd18e22839e306e61e6b7d0b7c2`
- `evaluation/test_formal_quality.py`：`17aedf21dfa8891a64202143cd12452957eb7ad40db536bb2180f9927de00ae4`
- `evaluation/test_metrics.py`：`6717e3b68aa22397483ae76ba5243ef889e3c2b1c2be2a25f416bb5249e7300f`

## 当前证据边界

单元测试证明协议在合格合成 summary 上通过，并能识别绝对指标不足、Agent 显著退化、
details 篡改、summary 单独篡改、数据集替换和非法 bootstrap 配置。它没有证明真实项目已经达到任何上述门槛。当前人工黄金集仍为
人审尚未完成（精确进度见 `HUMAN_REVIEW_PROGRESS_2026-09-15.md`），正式三系统结果不存在，所以 ROADMAP 中正式质量发布项保持未通过。

如果未来正式运行失败，正确处理是分析题型与失败标签、修复或简化系统、冻结新代码
和 Prompt 版本后完整重跑；不能删除失败 run、只选有利题目或降低本协议阈值。
