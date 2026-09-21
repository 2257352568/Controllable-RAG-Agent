# 正式评测风险覆盖协议（2026-09-14）

## 为什么题目总数不够

原评测池有 50 题和 `single_hop/reasoning/multi_hop/unanswerable/adversarial`
五类标签，但粗粒度的 `adversarial=5` 不能说明错误前提、注入、密钥外泄、证据冲突和
问题歧义分别是否出现。只报告题数会掩盖风险覆盖空洞。

## 预注册门禁

`risk-coverage-2026-09-14.1` 固定以下最低数量：

| 维度 | 最低数 | 当前数 |
|---|---:|---:|
| single hop | 20 | 20 |
| reasoning | 10 | 10 |
| multi hop | 11 | 11 |
| unanswerable | 5 | 5 |
| adversarial | 6 | 6 |
| knowledge absence | 5 | 5 |
| false premise | 4 | 4 |
| prompt injection | 1 | 1 |
| secret exfiltration | 1 | 1 |
| belief/fact conflict | 1 | 1 |
| multi-source disambiguation | 1 | 1 |
| underspecified query | 1 | 1 |
| clarification required | 1 | 1 |

新增 `hp1-051` 要求区分 Harry 对 Snape 的判断与 Quirrell 后来的亲口承认，两段证据
分别定位第 138、208 页；`hp1-052` 故意缺少 professor/event 指代，期望请求澄清而不是
猜测。前者仍需人工确认答案与 supporting chunks，后者必须人工确认“不可回答”标签。

## 轻量执行

```powershell
venv\Scripts\python.exe evaluation\audit_risk_coverage.py `
  --output docs\interview\evidence\RISK_COVERAGE_2026-09-14.json
```

- 无密钥 CI 检查两个池的 schema、跨文件重复和风险最低数。
- 本地可单独运行同一命令查看覆盖矩阵，不增加模型请求。

风险标签属于 case 语义，已进入 `case_content_sha256`；审批后修改标签会使旧人审记录
自动过期。

## 可复现证据

- seed dataset：13 题，SHA256 `aa68b165bdbced3e0245b8da6dc6fa8de1ba51555ad0d2c7989b09c26e12841c`
- candidate dataset：39 题，SHA256 `8a2cf5352f069715de07edd9a19cfd0a4c561d06901ebf81c27f1137c45ff3da`
- JSON 报告 SHA256：`38c478eb828ee525847fe363425e785b0feede01710a347e38067dc91e736b11`
- `audit_risk_coverage.py`：`e7b27882cdba80169f56f02ec05c45f86ac8c6db7616511f85f3d0a70f0fba09`
- `audit_dataset.py`：`2a4cf4ef291f85b87605ca31a07e2fcb18d4b9acf8176ea1f706971fe811114f`

当前报告 `valid=true`，但 `human_approved_cases=0`。这只证明风险结构满足预注册最低数，
不证明题目正确、风险标签已人审或系统能处理这些风险。正式发布门禁仍未通过。
