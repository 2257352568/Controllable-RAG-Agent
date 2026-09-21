# 逐句 Claim-to-Evidence 兼容性探针（2026-09-14）

## 目的

验证 `qwen3.8-max` 能否在答案子图中稳定返回嵌套的逐句引用结构，并验证代码会
fail closed：每个答案的规范化完整句必须按原顺序恰好映射一次、至少包含一个本轮
证据 ID；未知 ID、非原句、错序、重复映射、漏映射及重复答案句都会被拒绝。通过验证的 ID 并集才会进入
grounding verifier，最终响应按句渲染引用。

这项探针验证的是结构化输出和控制流兼容性，不是正式回答质量评测。

## 运行方式与固定配置

```powershell
venv\Scripts\python.exe evaluation\run_claim_citation_probe.py
```

- 数据：`evaluation/claim_citation_cases.json`
- 数据 SHA256：`29ad10750e7e048809bd5c31e9e40e53f276c30f39f8d67ea7322f69e6bddc32`
- 模型：`qwen3.8-max`，DashScope OpenAI-compatible endpoint
- Prompt 版本：`2026-09-14.2`
- temperature：0；max output tokens：2,000
- 每题最多 2 次 answer/verify 尝试；总上限 8 次模型调用、12,000 Token、120 秒
- 范围：编译后的答案生成与 grounding 子图，不含检索和完整 Agent

原始运行报告为本地忽略文件
`evaluation/results/claim-citation-11fbaa20136f46578d5e4e7fec3664ff.json`，其 SHA256
为 `59dc49aae3e5cfa54e77826c2ee67888d9543c9d324f44e572acabe683d88dec`。
仓库内归档副本为
`docs/interview/evidence/CLAIM_CITATION_PROBE_2026-09-14.json`；归档仅改变 JSON
排版，字段内容已做语义一致性检查。

## 结果

| 指标 | 结果 |
|---|---:|
| 样本 | 2 |
| 通过 | 2/2 |
| 错误 | 0 |
| 模型调用 | 4 |
| Token | 1,873 |
| 总耗时 | 22.063 秒 |

- 单事实题首轮通过：一句答案映射到预期的一个证据 ID；824 Token，12.596 秒。
- 双事实题首轮通过：两句答案分别映射到两条不同证据，预期证据覆盖完整；1,049
  Token，9.466 秒。
- 两题均完成 answer 生成和 grounding 判断，未触发第二次生成尝试。

运行报告同时冻结了当时的实现哈希：

- `controllable_rag/citations.py`：`3825e1c3340a14329f194b19fcbb607debb1e8574dfda9f830340503782bd029`
- `controllable_rag/nodes.py`：`a71437a9fafd5ba18e44482c01530672bb61853ba9ec733759a875a34189355c`
- `controllable_rag/prompts.py`：`804d362a3305f331e684dd5285bf1e9f7f98dffe3f964989715e847bc15ef9db`
- `controllable_rag/schemas.py`：`a11ca2a8cddb6d23736473c08137f8e13796be2f07e55fbc59370d270eac510b`
- `evaluation/run_claim_citation_probe.py`：`1c414a6b55154b73b17c94458036c12b14ee6d16a4542c585904013fc576778d`

探针之后又补了重复答案句拒绝、映射顺序和中文句界的确定性回归，因此归档中的
`citations.py` 哈希只代表本次在线运行时的版本，不应冒充当前文件哈希。

## 结论边界

可以据此回答：千问模型能够遵循本项目逐句引用 schema；代码不是只依赖 Prompt，
而是对句子覆盖和证据 ID 做确定性检查，并把逐句映射传到 API、评测记录和安全
Trace 计数。

不能据此声称：

- 2 个自编样本能代表 50 题正式集或生产分布；
- 映射存在就等于语义蕴含正确，语义判断仍依赖同一供应商的 LLM verifier；
- 已完成人工逐 claim 标注、引用定位到原文 span，或消除了幻觉；
- 已验证检索、完整 Agent、重复运行稳定性和 Qwen/DeepSeek 横向对比。

下一步应先完成人工黄金集，再预注册 claim 支持率、错误归因率、拒答准确率和重复
运行协议；在独立裁判或人工复核下比较 direct、naive RAG 与 agentic RAG。

## 本地回归证据

- `python -m unittest discover -v`：203/203 通过（`tests/` 与 `evaluation/`）。
- Ruff：项目、评测、测试及入口脚本检查通过。
- 面试问题库：153 题，自动生成的前 50 题冲刺队列通过一致性检查。
- 种子 13 题、候选 37 题与本地受信语料的审计均通过；语料 SHA256 为
  `b2f74c7eace8a8517d27e027cfea18e50098febec4ed2af6f5af10a7f9aaa26b`。
- 本探针执行时人工审核进度为 0/50；当天随后新增冲突与歧义题，当前权威进度已变为
  当前权威进度见 `HUMAN_REVIEW_PROGRESS_2026-09-15.md`。这条历史结果不追改为 52 条实验输入，
  ROADMAP 的正式评测与简历发布门禁仍保持未通过。

## 面试表达

先解释故障：整段 Sources 即使都是真文档，也无法证明每个事实都由所引来源支持。
再讲设计：生成器输出逐句映射，代码验证完整覆盖和 ID 白名单，verifier 只看这些
来源，终端按句展示。最后主动限定证据：目前只有 2 例真实模型兼容性探针和离线
契约回归，正式语义质量仍由人工黄金集门禁决定。
