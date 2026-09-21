# Qwen nonce / counterfactual context reliance（2026-09-12）

## 结论边界

该诊断证明 `qwen3.8-max` 在固定提示下能够拒绝无上下文的未知 nonce 问题，
并随原事实/反事实上下文切换答案。它测试的是生成器 grounding，不经过向量化、
Retriever 或 Agent 图，因此不能证明完整 RAG 的答案一定来自检索。

## 有效运行

```powershell
venv\Scripts\python.exe evaluation\run_context_reliance_evaluation.py
```

- 数据：`evaluation/context_reliance_cases.jsonl`
- 数据 SHA256：`288ba466d82d339849cdb37ee51f7e9a60f33c664ef09fc2397f068883f07661`
- 模型：千问 `qwen3.8-max`，temperature 0，max output 80
- 规模：6 组 × 3 条件 = 18 次逻辑调用
- Token：input 2,299，output 81，total 2,380；usage metadata 完整
- 单调用平均延迟：1,030.2389 ms（单机单次串行，不代表 P95）
- SDK 内 HTTP attempts：当前 wrapper 不可观测，不能把逻辑调用数当 HTTP 请求数

| 指标 | 结果 |
|---|---:|
| 无上下文命中任一预设答案（越低越好） | 0/6 |
| 无上下文明确拒答 | 6/6 |
| 原事实上下文命中 | 6/6 |
| 反事实上下文跟随 | 6/6 |
| 成功随配对上下文切换 | 6/6 |

## 作废的首跑与根因

首跑得到反事实跟随 5/6。检查失败样本后发现，问题询问 `Kestrel-8`，反事实却写成
`Kestrel-8-CF`；模型输出 `NOT_ENOUGH_INFORMATION` 是合理拒答，不应算 grounding
失败。其余样本也存在类似版本后缀，只是模型宽松匹配。该首跑整体作废，未用于
最终结论。

根因是反事实构造同时修改了目标答案和实体/版本，产生混杂变量。修复包括：

1. 六组上下文都保持问题实体、文档版本和措辞不变，仅替换目标答案；
2. 数据校验把答案替换为占位符后比较两个上下文模板，不一致即失败；
3. 增加回归测试，专门覆盖实体身份被一起修改的错误反事实。

## 面试回答

“热门公开语料可能被基础模型记忆，所以我没有仅看 Harry Potter 正确率。我另建
nonce 事实，做 no-context、original-context、counterfactual-context 三条件配对。
首版实验还抓到一个设计错误：反事实误改了版本号，导致拒答被错判。我作废整次
运行并用模板契约保证只替换答案。有效重跑 6/6 随上下文切换。不过这只验证生成
层；同一数据现已补做真实 embedding、FAISS retrieval 与生成验证，完整 Agent
仍需单独评测。”
