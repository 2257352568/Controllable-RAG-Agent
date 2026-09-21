# 私有 nonce 事实 naive-RAG 端到端诊断（2026-09-12）

## 结论

6 组冻结 nonce 事实真实经过千问 Embedding、内存 FAISS Top-1 和千问生成。
原事实与反事实的 12 次检索均命中对应文档，6 组答案均随检索语料切换；无上下文
条件全部拒答。该结果比直接把上下文塞给模型更能排除公开语料记忆，但仍只是小型
naive-RAG 诊断，不是完整 LangGraph Agent 的正式质量评测。

## 命令与配置

```powershell
venv\Scripts\python.exe evaluation\run_private_rag_reliance_evaluation.py
```

- 数据 SHA256：`288ba466d82d339849cdb37ee51f7e9a60f33c664ef09fc2397f068883f07661`
- Chat：`qwen3.8-max`，temperature 0，max output 80
- Embedding：`text-embedding-v4`，1536 维
- 索引：两个独立的 6-document `IndexFlatL2`，分别装载原事实与反事实
- Top-K：1
- Embedding inputs：24（12 document + 12 query）
- Chat：18 次逻辑调用，input 2,299 / output 82 / total 2,381 Token
- SDK HTTP attempts：不可观测；Embedding token usage：供应商响应未返回

## 结果

| 指标 | 结果 |
|---|---:|
| 无上下文预设答案泄漏 | 0/6 |
| 无上下文拒答 | 6/6 |
| 原事实 Top-1 检索 | 6/6 |
| 反事实 Top-1 检索 | 6/6 |
| 原事实答案命中 | 6/6 |
| 反事实答案跟随 | 6/6 |
| 检索与答案均完成配对切换 | 6/6 |

单次本地串行运行的索引构建耗时为 15,625.6694 ms，单次检索平均
1,532.1844 ms，单次生成平均 1,080.5155 ms。检索耗时包含远程 query
embedding，因此不能把它与纯本地 FAISS 搜索混为一谈，也不能由均值推断 P95。

## 为什么使用两个隔离索引

如果把同一问题的原事实和反事实同时放进一个索引，Retriever 可能任意选择两个
相互冲突的近重复文档，实验就同时测了冲突消解与上下文依赖。两个索引保持问题和
非目标文本一致，只切换事实来源，使变量控制更清晰；代价是它不模拟生产环境中的
版本冲突，冲突检索应由另一套测试覆盖。

## 仍不能声称什么

- 6 个短文档无法代表真实长文档、chunking、metadata filter 或大规模近似索引。
- 数据在本次实验前创建且模型无上下文时拒答，但这不是长期保密测试集基础设施。
- 没有运行 planner、router、replanner、grounding judge 和引用链路，不能外推为
  Agentic RAG 端到端准确率。
- 正式 50+ 人工黄金集、三 baseline 与配对置信区间仍是简历发布门槛。

## 面试表达

“我先用 direct 条件确认 nonce 答案不是模型记忆，再建立原事实和反事实两个隔离
FAISS 索引，让同一问题经过真实千问向量检索。12 次 Top-1 和 6 组答案切换全部
成功。隔离索引是为了只操纵事实值，不把冲突检索混进实验。这个结果只证明小型
naive-RAG 的上下文因果依赖，完整 Agent 效果仍由正式三基线评测回答。”
