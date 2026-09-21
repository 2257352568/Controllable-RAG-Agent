# 7 天 Agent / RAG 项目面试训练

目标不是背完 161 道题，而是在一周内形成一条能讲清、能画图、能指代码、能承认边界的
项目主线。每天建议 60–90 分钟；没有特别说明时只做离线练习，不调用付费模型。

## 统一验收标准

每道核心题按 0–4 分自评：

| 分数 | 能力表现 |
|---:|---|
| 0 | 不知道或只能复述技术名词 |
| 1 | 能解释基本概念，但说不出项目如何实现 |
| 2 | 能按“结论→原理→实现→边界”回答，并指出代码模块 |
| 3 | 能指出具体函数与测试，回答一次自然追问 |
| 4 | 能结合真实故障或实验，回答两次连续追问且不夸大结论 |

核心题不是读完即完成：录音后在 90 秒内答完且达到 3 分，才算一次通过。看着文档回答不计
通过。`READY` 表示仓库已有回答证据，不代表本人已经会答。

## Day 1：一条主线讲完整

**目标：** 面试官先听懂项目做什么、为什么存在、哪些是个人改造。

练习题：A01、A02、A03、A14、A15。

1. 阅读 `CORE_INTERVIEW_ANSWERS.md` 第 1、2 题和 `PROJECT_STORY.md`。
2. 画一遍：用户问题 → plan → 多源检索 → replan → grounding → 引用/拒答。第一次可参考
   `WHITEBOARD_GUIDE.md`，之后必须脱稿。
3. 分别录制 30 秒和 90 秒项目介绍。
4. 主动说出三条边界：基于上游继续开发、学习型而非生产级、正式质量门禁尚未通过。

**通过条件：** 不看稿讲清问题、Agent 增量价值、个人贡献和诚实边界；不罗列技术栈。

## Day 2：掌握 RAG 数据链

**目标：** 能从数据进入系统一直讲到检索结果，而不是只会说“向量数据库”。

练习题：B01–B07、B20–B23。

1. 顺着 `rebuild_vector_stores.py`、`controllable_rag/retrieval.py` 和
   `controllable_rag/index_manifest.py` 读数据链，并对照 `WHITEBOARD_GUIDE.md` 图 1 检查遗漏。
2. 白板解释 chunk size/overlap、Embedding、L2、Top-K 之间的关系。
3. 用 `RETRIEVAL_SMOKE_2026-09-11.md` 解释 K 增大为何 recall 上升、precision 下降。
4. 解释 hybrid 初筛为何没有被强行接入主图。

**通过条件：** B01、B04、B05、B07 各达到 3 分；能说出当前参数来自哪里及为何不能称最优。

## Day 3：读懂 LangGraph，而不是背节点名

**目标：** 能解释为什么图适合 Agent，以及 State、节点、条件边和循环如何配合。

练习题：C01–C07、C10、C14。

1. 阅读 `controllable_rag/schemas.py::PlanExecute` 和 `controllable_rag/graph.py::create_agent`，
   对照 `WHITEBOARD_GUIDE.md` 图 2 后脱稿重画。
2. 任选一个问题，手工写出 State 中 plan、past_steps、evidence、termination_reason 的变化。
3. 阅读 `plan_question`、`handle_task`、`route_tool`、`replan`、`route_after_replan`。
4. 运行：`venv\\Scripts\\python.exe -m unittest tests.test_graph_control`。

**通过条件：** 能脱稿画主图；面对“为什么不用普通 Chain”和“何时不该用 Agent”都能回答。

## Day 4：讲清可控与可信

**目标：** 把“可控”落到具体限制，把“引用”与“事实受支持”区分开。

练习题：C03、C06、C19、C20、B13、B24、B25。

1. 阅读 `controllable_rag/config.py::Settings` 与 `controllable_rag/runtime.py::BoundedAgent`。
2. 按步骤、Chat 请求、Token、Embedding、deadline、grounding 重试列出六层终止保护。
3. 阅读 `controllable_rag/citations.py`、`verify_answer` 和 `finalize_answer`。
4. 运行：`venv\\Scripts\\python.exe -m unittest tests.test_runtime_budget tests.test_citations tests.test_citation_grounding`。

**通过条件：** 能解释“真实引用仍可能不支持答案”以及为什么预算必须在调用前检查。

## Day 5：评测决定 Agent 是否值得

**目标：** 能设计公平实验，也能在没有正式结果时给出专业回答。

练习题：A05、A06、D01–D06、D30、D31、D36、D39、D44。

1. 阅读 `evaluation/run_evaluation.py::SYSTEMS`、`evaluate_case` 和聚合逻辑，用
   `WHITEBOARD_GUIDE.md` 图 3 解释三组各自隔离了什么变量。
2. 画 direct、naive RAG、Agentic RAG 的控制变量表。
3. 解释 correctness、faithfulness、evidence recall、拒答、延迟和 Token 分别回答什么。
4. 阅读 `evaluation/formal_quality.py`，解释为什么阈值要在正式结果前固定。
5. 对 A05/A06 使用当前正确答案：**尚无正式提升数据，不能声称 Agent 更优。**

**通过条件：** 能解释三基线、配对 bootstrap、LLM judge 偏差和权威人审状态；不引用冒烟数据作最终效果。

## Day 6：准备两个真实故障故事

**目标：** 证明自己实际调试过项目，而不是只复述架构。

必选故事：

- Qwen `thinking` 与 `tool_choice` 组合导致 400，如何最小复现并修复。
- 检索评测发现标签假阴性，如何区分模型失败与评测数据错误。

备选故事：checkpoint 旧版本故障、FAISS 中文路径、引用 B 却借用 A 通过验证、错误 Python
环境导致依赖缺失。

每个故事按 STAR 练习，但 Result 只陈述已有证据：

1. Situation：观察到什么现象。
2. Task：需要证明什么，而不是先猜根因。
3. Action：最小复现、对照、修复、回归。
4. Result：哪些验证通过、哪些仍不能外推。

**通过条件：** 两个故事各在 2 分钟内讲完，并能回答“你怎么证明真的是这个根因”。

## Day 7：完整模拟面试

**目标：** 串联项目介绍、原理、代码、实验和边界。

按顺序完成：

1. 90 秒项目介绍。
2. 随机抽取 3 道 RAG、3 道 Agent、3 道评测题。
3. 从 A04、A07 中抽取一个故障故事。
4. 回答“这个项目能否生产使用”“Agent 如果不优于 naive RAG 怎么办”。
5. 选择 `CODE_EVIDENCE_INDEX.md` 的 A、B 或 C 路径做 5 分钟代码讲解。

**通过条件：** 10 道题中至少 8 道达到 3 分，且没有出现以下红线：虚构指标、混淆上游与
个人贡献、把测试当线上效果、把 OpenAI-compatible 说成 OpenAI 模型、把学习实现说成生产能力。

## 每周复盘表

| 项目 | 本周结果 |
|---|---|
| 90 秒介绍是否通过 | 待填写 |
| P0 随机抽题通过数 / 抽题数 | 待填写 |
| 最弱的 3 个问题 ID | 待填写 |
| 能讲清的故障故事 | 待填写 |
| 能现场展示的代码路径 | 待填写 |
| 本周发现的新追问 | 待填写；录入 `QUESTION_BANK.md` 后重新生成队列 |

## 当前不能靠学习替代的发布缺口

- 52 条评测数据仍需本人逐条人工审核。
- 正式三基线实验必须在人审完成后运行，不能用背诵替代实验。
- 个人 Git remote、主题提交和远端 CI 需要仓库所有者实际建立。

训练可以让项目“讲得明白”，但只有这些发布门禁完成后，才可以把项目写成已有量化效果的
简历项目。
