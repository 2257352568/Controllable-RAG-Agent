# 核心面试问题代码证据索引

这份索引解决一个具体问题：面试回答不能停留在概念层，必须能继续指出“代码在哪里、测试
证明了什么、证据边界是什么”。它与 `CORE_INTERVIEW_ANSWERS.md` 的 17 个问题一一对应。

使用时先口述答案，再任选一个“主代码锚点”和一个“验证锚点”展开。不要一次报出所有文件，
也不要把单元测试说成线上质量数据。

## 证据等级

- **L1 设计**：只有方案或协议，能解释但不能声称效果。
- **L2 离线验证**：有代码和自动化测试，能证明契约或控制流。
- **L3 小样本实测**：有真实模型或检索探针，只能陈述该样本结果。
- **L4 正式实验**：固定数据、配置、重复和人审均通过后才可写量化结论；当前尚无 L4。

## 17 题映射

| # | 面试主题 | 主代码锚点 | 验证锚点 | 当前等级与可说结论 |
|---|---|---|---|---|
| 1 | 一分钟介绍 | `controllable_rag/graph.py::create_agent`、`README.md` 的贡献边界 | `tests/test_graph_control.py`、`docs/interview/PROJECT_STORY.md` | L2：可以说完成了本地改造和可测试主链路；不能说完全原创或效果提升。 |
| 2 | 为什么需要 Agent | `controllable_rag/graph.py::create_agent`、`evaluation/run_evaluation.py::SYSTEMS` | `evaluation/test_metrics.py`、`evaluation/test_formal_quality.py` | L2：三基线和门禁已实现；尚无正式结果证明 Agent 更好。 |
| 3 | RAG 完整链路 | `rebuild_vector_stores.py`、`controllable_rag/retrieval.py`、`controllable_rag/index_manifest.py` | `tests/test_api.py` 的 readiness 契约、`evaluation/audit_ingestion.py` | L2：能证明索引构建、加载和模型/维度/hash 契约。 |
| 4 | 三类知识源 | `controllable_rag/retrieval.py::SOURCE_CONFIG`、`controllable_rag/nodes.py::_run_retrieval` | `tests/test_retrieval_policy.py` | L2：能证明按源懒加载、路由和禁用源强制生效；不能声称三源优于单源。 |
| 5 | chunk 与 overlap | `evaluation/run_chunking_ablation.py` | `evaluation/test_chunking_ablation.py`、`docs/interview/evidence/INGESTION_AUDIT_2026-09-12.md` | L2：能解释真实切分分布和离线初筛；1000/200 不是已证明最优参数。 |
| 6 | Top-K | `controllable_rag/config.py::Settings`、`evaluation/run_retrieval_evaluation.py` | `evaluation/test_retrieval_metrics.py`、`docs/interview/evidence/RETRIEVAL_SMOKE_2026-09-11.md` | L3：11 条小样本展示 recall/precision 权衡；不能外推正式质量。 |
| 7 | cosine/dot/L2 | `controllable_rag/retrieval.py::_load_trusted_store`、三个 `index.faiss` | `evaluation/audit_ingestion.py`、索引清单 `index_manifest.json` | L2：当前索引契约为 1536 维 Flat L2；度量优劣仍是原理性讨论。 |
| 8 | LangGraph vs Chain | `controllable_rag/graph.py::create_agent`、`controllable_rag/schemas.py::PlanExecute` | `tests/test_graph_control.py`、`tests/test_checkpointing.py` | L2：能展示显式状态、条件边、循环、终止与 checkpoint。 |
| 9 | plan/replan | `controllable_rag/nodes.py::plan_question`、`replan`、`route_after_replan` | `tests/test_graph_control.py` | L2：能证明契约与控制流；尚无消融证明 replan 的净收益。 |
| 10 | 工具路由 | `controllable_rag/schemas.py::TaskHandlerOutput`、`controllable_rag/nodes.py::route_tool` | `tests/test_retrieval_policy.py`、`tests/test_graph_control.py` | L2：结构化枚举、白名单和禁用源均由代码强制。 |
| 11 | 可控性 | `controllable_rag/config.py::Settings`、`controllable_rag/runtime.py::BoundedAgent`、`controllable_rag/budget.py` | `tests/test_runtime_budget.py`、`tests/test_retrieval_policy.py` | L3：真实千问探针验证请求/Token 预算可在发送前停止；仍是单进程控制。 |
| 12 | 黄金评测集 | `evaluation/dataset.jsonl`、`evaluation/dataset_candidates.jsonl`、`evaluation/review_workflow.py` | `evaluation/audit_dataset.py`、`evaluation/review_progress.py` | L2：52 条候选及 hash 绑定审核流程成立；人审尚未完成，不能称黄金集。 |
| 13 | direct/naive/agentic | `evaluation/run_evaluation.py::run_system`、`evaluate_case` | `evaluation/test_metrics.py`、`evaluation/test_formal_quality.py` | L2：公平对照的执行与聚合骨架已验证；没有正式三系统数据。 |
| 14 | LLM-as-judge | `evaluation/run_evaluation.py::build_judge_prompt`、`evaluation/judge_review.py` | `evaluation/test_judge_review.py` | L2：固定抽检和校准门禁已实现；人评分尚未产生。 |
| 15 | 统计意义 | `evaluation/run_evaluation.py` 的 paired bootstrap 聚合、`evaluation/formal_quality.py` | `evaluation/test_metrics.py`、`evaluation/test_formal_quality.py` | L2：能解释同题配对与最少样本门槛；不能声称已有显著提升。 |
| 16 | Qwen 与兼容接口 | `controllable_rag/config.py::Settings`、`controllable_rag/models.py` | `tests/test_config.py`、`tests/test_models.py`、`docs/interview/evidence/MODERN_LANGGRAPH_MIGRATION_PROBE_2026-09-12.md` | L3：当前使用 Qwen 模型且做过真实兼容探针；`langchain-openai` 只是兼容客户端。 |
| 17 | timeout/retry/限流/熔断 | `controllable_rag/resilience.py`、`controllable_rag/api.py::create_api`、`controllable_rag/runtime.py` | `tests/test_resilience.py`、`tests/test_api.py`、`tests/test_runtime_budget.py` | L2：能证明进程内状态机和准入契约；不具备跨进程全局语义。 |

## 三条推荐现场演示路径

### 路径 A：为什么这是 Agent，而不是普通 RAG

1. 打开 `controllable_rag/graph.py::create_agent`，画出条件边和 replan 循环。
2. 打开 `controllable_rag/schemas.py::PlanExecute`，说明共享状态如何承载计划、证据和预算。
3. 打开 `evaluation/run_evaluation.py::SYSTEMS`，说明最终要由三基线验证复杂度，而非凭架构下结论。

### 路径 B：如何降低无证据生成

1. 打开 `controllable_rag/citations.py`，说明 evidence ID、白名单和逐句映射。
2. 打开 `controllable_rag/nodes.py::verify_answer` 与 `finalize_answer`，说明验证、有限重试和拒答。
3. 运行 `python -m unittest tests.test_citations tests.test_citation_grounding`，展示契约回归。

### 路径 C：如何防止 Agent 失控

1. 打开 `controllable_rag/config.py::Settings`，说明步骤、请求、Token、时间和 Embedding 五类限制。
2. 打开 `controllable_rag/runtime.py::BoundedAgent`，说明节点边界停止与机器可读终止原因。
3. 运行 `python -m unittest tests.test_runtime_budget tests.test_checkpointing`，展示发送前拒绝和恢复后累计预算。

## 回答纪律

- “有实现”至少需要 L2；“真实跑过”至少需要 L3；“效果提升”必须达到 L4。
- 现场展示优先选主线代码，不先展示 FastAPI、SSE、熔断等加分项。
- 文件名找不到时不硬背行号，记住模块、函数/类名和它解决的问题。
- 若被问到生产化，只说明缺口和设计方向，不临时扩大项目完成度。
