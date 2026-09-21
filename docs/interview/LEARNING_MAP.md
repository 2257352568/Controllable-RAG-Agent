# Agent / RAG 系统学习地图

## 项目定位

这是一个用于系统学习和面试讲解的 Agentic RAG 项目，不以复刻完整生产平台为目标。
合格标准是：主链路能够运行；关键设计有对照或测试；能解释为什么这样设计、失败会发生
在哪里、有哪些边界；面试官沿着简历中的关键词追问时，可以回到代码和证据。

## 第一层：必须掌握并能演示

| 学习主题 | 项目落点 | 面试追问 | 对应题目 |
|---|---|---|---|
| RAG 完整链路 | ingest→chunk→embed→FAISS→retrieve→generate→evaluate | chunk、Embedding、Top-K 如何影响结果？ | B01–B07 |
| Agent 状态机 | LangGraph State、节点、条件边、循环 | 为什么不是普通 Chain？状态怎样流动？ | C01–C03 |
| 规划与重规划 | plan→task handler→retrieve/answer→replan | 哪类问题需要 Agent？何时停止？ | C04–C06 |
| 多知识源路由 | chunks/summaries/quotes 三类索引 | 粒度为什么不同？错路由怎么办？ | B02、C05 |
| Grounding 与引用 | evidence ID、逐句 claim 映射、拒答 | 有引用为什么仍可能幻觉？ | B13、B24、B25 |
| 评测基本方法 | direct/naive/agentic 三基线、题型切片 | 如何证明 Agent 值得复杂度？ | A05、A06、D01–D06 |
| 可控终止 | step/request/token/evidence 限额 | 如何避免死循环和失控成本？ | C03、C06 |

这七项构成项目主线。面试前应能白板画图、运行 Demo，并用“结论—原理—实现—证据—
边界”结构回答。

## 第二层：用于引导追问的加分点

这些能力保留轻量实现或实验，不继续扩展为完整平台：

| 钩子 | 简历/讲解中的一句话 | 希望引出的知识点 |
|---|---|---|
| Checkpoint | 支持 thread 隔离与恢复 | durable execution、幂等、HITL |
| SSE/FastAPI | 提供同步与流式接口 | 流式事件、断线、背压边界 |
| Trace | 记录节点耗时、路由、Token、终止原因 | 可观测性、关联 ID、隐私 |
| 熔断与预算 | 调用前限额与进程内 circuit breaker | retry/limit/circuit breaker 区别 |
| Prompt Injection | 检索内容按不可信数据处理 | 指令层级、数据/指令边界 |
| 统计评测 | 重复运行与配对 bootstrap | 长尾、方差、统计显著性 |
| 风险覆盖 | 题型之外记录错误前提、冲突、歧义等标签 | 测试集覆盖不等于题目数量 |

面试时主动说明这些是“学习型实现或验证”，不要表述成生产级能力。

## 第三层：第一个项目明确不继续做

- Kubernetes、服务网格、完整微服务拆分。
- Redis/Kafka 持久任务平台、多副本分布式配额和跨进程锁。
- 外部商业 Trace 平台、全链路 W3C 传播、企业级审计合规。
- 为了技术栈数量强行加入 MCP、多智能体或 Spring Boot。
- 没有评测需求支撑的 reranker、向量数据库迁移和复杂缓存。
- 与第二个“多智能体企业采购助手”重复的 ERP、MCP、审批流能力。

这些内容可以回答“生产化还需要什么”，但不作为当前仓库的实现任务。

## 推荐学习顺序

1. 先画出 RAG 数据流，解释三套索引、chunk、Embedding、Top-K。
2. 再画 LangGraph 控制流，逐节点说明输入、输出、条件边和终止。
3. 用一个成功回答和一个拒答案例解释 evidence、grounding、citation。
4. 对比 direct、naive RAG、Agentic RAG，明确评测指标和正式结果缺口。
5. 选择两个真实失败案例讲定位过程，例如模型参数 400、旧 pickle 兼容问题。
6. 最后准备 checkpoint、SSE、Trace、熔断、安全等追问，不主动把它们说成生产平台。

## 面试官常见追问链

### 从“为什么用 Agent”开始

普通 RAG 的边界 → 多跳与跨粒度检索 → plan/replan → 额外调用和延迟 → 三基线评测 →
如果收益不显著是否应退回 naive RAG。

### 从“如何降低幻觉”开始

检索证据 → answerability → evidence ID 白名单 → 逐句 claim 引用 → grounding verifier →
无证据拒答 → verifier 本身的不稳定性。

### 从“是否能生产使用”开始

当前可靠性措施 → checkpoint/timeout/limit/circuit breaker 的区别 → 本地 Trace 能证明什么 →
跨进程、权限、持久任务和外部可观测性尚未实现 → 为什么第一个项目有意止步于此。

### 从“项目是不是抄的”开始

上游架构与许可证 → 本地千问迁移 → 索引重建 → 模块化、评测、引用和可靠性改造 →
Git 历史与远端 CI 仍是发布前必须补齐的证据。

## 使用方式

- 学习主线：按本文件第一层逐项理解代码。
- 口述训练：按 `CORE_INTERVIEW_ANSWERS.md` 练习结论—原理—实现—证据—边界。
- 代码举证：按 `CODE_EVIDENCE_INDEX.md` 将核心回答落到实现符号、测试和证据等级。
- 白板表达：脱稿画出 `WHITEBOARD_GUIDE.md` 的 RAG 数据链、Agent 控制流和三基线评测。
- 每日练习：使用 `STUDY_QUEUE.md`，优先回答 P0/GAP/PARTIAL。
- 短期冲刺：按 `INTERVIEW_SPRINT.md` 用 7 天完成口述、白板、代码与故障训练。
- 讲项目：使用 `PROJECT_STORY.md`，只引用已有证据。
- 写简历：先用 `RESUME_ENTRY.md` 组织内部草稿；量化模板和最终发布必须等全部门禁通过。
- 决定是否继续开发：先检查 `ROADMAP.md`，若属于第三层则停止实现，只记录设计边界。
