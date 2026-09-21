# 项目面试问题库

状态：`READY` 已有代码/实验证据；`PARTIAL` 能回答但证据不足；`GAP` 项目尚未实现。优先级算法见本目录 README。

## A. 项目价值、原创性与结果

| ID | 优先级 | K/F | 面试问题 | 回答锚点 | 状态 |
|---|---|---:|---|---|---|
| A01 | P0 | 5/5 | 用一分钟介绍项目。 | 问题→三类知识源→LangGraph闭环→三基线评测→诚实边界；见 CORE_INTERVIEW_ANSWERS、CODE_EVIDENCE_INDEX 与 PROJECT_STORY。52 题人审已完成，但固定模型正式质量结论未产生，口述仍待本人验收。 | PARTIAL |
| A02 | P0 | 5/5 | 这个项目解决了什么问题，为什么普通 RAG 不够？ | 多跳任务、跨粒度证据、动态补检索、不可回答；必须用正式对照实验证明。 | PARTIAL |
| A03 | P0 | 5/5 | 哪些代码是你原创的？是不是复现项目？ | 明确上游 NirDiamant；说明千问迁移、索引重建、故障修复、评测与后续重构。 | READY |
| A04 | P0 | 5/5 | 最困难的问题是什么，怎么定位？ | thinking/tool_choice 400 与 Embedding 空间迁移两例，讲最小复现和端到端验证。 | READY |
| A05 | P0 | 5/5 | 项目效果如何？比 baseline 提升多少？ | 当前不能回答“提升多少”：52 题已人审，但额度导致正式运行分成不同生成模型，固定模型全量门禁未过。旧同模型 39 题分层中 Agent 答案命中 27.18%，naive RAG 为 55.56%；31 对完整题的配对 CI 支持 naive 占优。新图只做了两题三路径演示及个别回归，多跳仍会耗尽预算，不能用小样本修复宣称整体改善。 | PARTIAL |
| A06 | P0 | 5/5 | 为什么要做 Agent，复杂度真的值得吗？ | 当前实现不值得宣称收益。旧同模型分层中 Agent 成本高且正确性低；新 DeepSeek 小样本虽修好一例无答案循环，但 `hp1-038` 多跳题仍在 20 次请求、13,827 Token 后因保守预算准入停止。预算上限是发送前预留，不等于实际 Token 用到上限。要同时报告质量、请求/Token、延迟与未完成率；见 `evidence/MINIMAL_DEMO_2026-09-17.md`，不能用单例改善代替正式对照。 | PARTIAL |
| A07 | P1 | 4/4 | 项目有哪些失败案例？ | 先讲真实质量负例：`hp1-009` 递归上限三次截断、`hp1-042` 三次 grounding 失败、`hp1-040` 同题终止不稳定；再区分结构化输出 400、供应商额度耗尽与旧索引兼容故障。逐条证据和未验证边界见 `evidence/AGENT_FAILURE_CASEBOOK_2026-09-16.md`，不能把额度错误解释成模型质量。 | READY |
| A08 | P1 | 4/4 | 如果重新做一遍，你会怎么设计？ | 模块化、可测试节点、checkpoint、hybrid/rerank、离线评测先行。 | PARTIAL |
| A09 | P1 | 4/4 | 为什么选择 Harry Potter 数据？有什么缺点？ | 便于人工核验预训练知识污染；缺点是领域单一、模型可能记忆、版权与业务价值弱。 | READY |
| A10 | P1 | 4/4 | 如何证明回答来自检索而不是模型记忆？ | 6 组 nonce 事实先验证无上下文拒答，再通过 Qwen Embedding、隔离 FAISS 索引和生成器验证原事实/反事实切换；12 次 Top-1 和 6 组端到端均通过。结合 direct baseline、引用与数据 hash，但不能外推为完整 Agent 质量。 | READY |
| A11 | P1 | 4/4 | 你的个人贡献如何量化？ | 用 RESUME_ENTRY 区分当前可证明的改造与门禁后量化结果；最终还需独立 commit、差异清单、正式评测和远端 CI，不能用技术栈数量代替。 | GAP |
| A12 | P2 | 3/3 | 项目怎么迁移到企业文档？ | 数据摄取、chunk/metadata、权限过滤、领域评测、增量索引。 | GAP |
| A13 | P0 | 5/5 | 如何用 Git 历史证明哪些改造是你完成的？ | 发布副本保留上游 attribution，`origin` 指向个人空仓库、`upstream` 指向原项目；采用无上游提交历史的新根提交，使 Contributors 只统计本人，同时不能把上游代码说成原创。当前仍需本人提交、推送并用远端 CI 验证。 | PARTIAL |
| A14 | P0 | 5/5 | 这是学习型项目还是生产级项目？ | 定位是可运行、可评测的学习型 Agentic RAG：核心目标是系统掌握 RAG 数据链、LangGraph 控制流、grounding、评测和故障分析。Checkpoint/SSE/Trace/熔断是追问钩子，不声称具备分布式任务、企业权限或生产 SLA。 | READY |
| A15 | P1 | 4/5 | 简历里放很多知识点，会不会变成技术栈堆砌？ | 用一条主线串联：复杂问题→多源检索→证据判断→重规划→引用/拒答→三基线评测。只保留能解释原理、指出代码和证据的加分项；其余放在“生产化还需要什么”，不继续实现。按 INTERVIEW_SPRINT 用口述、白板、代码和故障四种方式验收。 | READY |

## B. RAG 与向量检索

| ID | 优先级 | K/F | 面试问题 | 回答锚点 | 状态 |
|---|---|---:|---|---|---|
| B01 | P0 | 5/5 | RAG 的完整链路是什么？ | ingest→clean→chunk→embed→index→retrieve→rerank→context→generate→evaluate；按 WHITEBOARD_GUIDE 图 1 从离线、在线、可信三侧讲解。 | PARTIAL |
| B02 | P0 | 5/5 | 为什么分正文、章节摘要、原文引用三套索引？ | 粒度/召回目标不同；路由降低噪声；需要消融证明收益。 | PARTIAL |
| B03 | P0 | 5/5 | Embedding 模型换了，为什么必须重建索引？ | 维度相同仅结构兼容，不同模型坐标空间/距离不可比较；1,934 条已重建。 | READY |
| B04 | P0 | 5/5 | chunk size、overlap 怎么定？ | 当前 1000/200 字符来自上游而非调优结果；审计确认 chunks 最大 999、同页实际 overlap 117–199/P50 158。最终应固定语料/模型，对多组参数比较 retrieval recall、precision、答案质量、Token 和延迟。 | PARTIAL |
| B05 | P0 | 5/5 | Top-K 如何选择？越大越好吗？ | Recall 与上下文噪声/Token/延迟权衡；当前 1/1/10 已配置化，但仍需曲线实验。 | PARTIAL |
| B06 | P0 | 5/5 | FAISS 的检索原理和当前索引类型？ | 当前 chunks 是 618×1536 的 `IndexFlatL2`，做精确 L2 最近邻；无需训练、召回无近似损失，但查询和内存随规模线性增长。 | READY |
| B07 | P0 | 5/5 | cosine、dot product、L2 有何区别？ | 归一化后 cosine 与 inner product 排序关系；度量必须与训练/索引一致。 | PARTIAL |
| B08 | P1 | 4/5 | 如何提高召回率？ | query rewrite、多查询、hybrid、metadata、动态K、rerank、chunk实验；本项目首轮等权 RRF 只提高代理 Recall@10，却损害 Top-1/5，所以没有直接上线。 | PARTIAL |
| B09 | P1 | 4/5 | BM25 和 dense retrieval 各自优缺点？ | BM25 擅长专名/词项匹配且本地均值约 2ms，dense 语义泛化更强但需远程 Embedding；当前 11 题 dense 明显领先，不能假设融合必然更好。 | READY |
| B10 | P1 | 4/5 | reranker 为什么有效，放在哪里？ | 双塔召回后交叉编码精排；质量、延迟和成本消融。 | GAP |
| B11 | P1 | 4/4 | 如何评估检索而不是最终回答？ | 已有独立 dense chunks 入口输出 Hit/Precision/Recall/MRR/nDCG 与 marker coverage、分题型和哈希；当前 marker relevance 非穷尽标注，正式集仍需精确 chunk IDs。 | PARTIAL |
| B12 | P1 | 4/4 | 如何处理无答案问题？ | 证据阈值、答案充分性和检索源尝试范围共同决定拒答；旧图在无答案题 28 次请求后预算耗尽，新图三源尝试后明确标记 `search_exhausted`。应区分“这次未检到充分依据”与“语料绝对没有答案”，并用跨轮多跳正例检查提前拒答风险；当前只做小样本回归。见 `evidence/MINIMAL_DEMO_2026-09-17.md`。 | PARTIAL |
| B13 | P1 | 4/4 | 如何提供可核验引用？ | 稳定 evidence ID 与结构化记录随 State 传递；代码白名单过滤并渲染页码/章节；蒸馏和答案 verifier 只收到逐句映射所选 ID 对应的原始片段。quotes 已有 99.923% 唯一页码覆盖，仍缺正式人审集的语义对齐验证。 | PARTIAL |
| B24 | P0 | 5/4 | 引用是真实文档，为什么答案仍可能没有引用依据？ | ID 白名单只证明来源存在。旧 verifier 接收全部上下文，可能让答案引用 B 却借 A 的事实通过；已将检查限定为所选 ID 原文，并增加逐句 claim 映射。7 项归因回归、16 次千问对照及 2 例结构兼容探针验证了控制流；仍不能承诺消除幻觉。 | READY |
| B25 | P0 | 5/4 | 如何保证答案中的每个事实都有引用，而不是整段共用一组 Sources？ | 生成 schema 返回逐句 `claim_citations`；代码要求 claim 与答案的规范化完整句一致、顺序和覆盖完整、ID 全部来自本轮证据，再由映射并集决定 grounding 上下文和内联引用。千问单跳/多事实兼容性探针 2/2 首轮通过；语义支持仍依赖 verifier，正式集尚未验证。 | READY |
| B14 | P1 | 4/4 | 如何处理重复、冲突或过时文档？ | 去重、版本/时间 metadata、权威度、冲突展示和拒答。 | GAP |
| B15 | P1 | 4/4 | RAG 和微调如何选择？ | 知识更新/引用/权限用 RAG；行为风格/任务能力用微调；可组合。 | PARTIAL |
| B16 | P2 | 3/4 | FAISS 适合生产吗？ | 单机高性能但权限、持久化、扩缩容有限；生产可评估 Milvus/pgvector/ES。 | PARTIAL |
| B17 | P2 | 3/3 | 如何做增量索引和删除？ | 稳定 doc ID、版本、tombstone/rebuild、embedding model version。 | GAP |
| B18 | P2 | 3/3 | 为什么 text-embedding-v4 用 1536 维？ | 为迁移结构匹配并追求精度；应与 1024 维做成本/质量对比。 | PARTIAL |
| B19 | P1 | 4/4 | 为什么引用 ID 要包含内容哈希而不只用检索排名？ | 排名随查询/模型变化，不能稳定定位；source+位置+内容哈希可复核、去重并检测陈旧证据。 | READY |
| B20 | P0 | 5/4 | Recall@K、MRR、nDCG 分别回答什么问题？ | Recall 看相关证据找全多少，MRR 看首个相关结果是否靠前，nDCG 同时考虑多个结果的位置与相关等级；本项目还单列多证据 marker coverage。 | READY |
| B21 | P1 | 4/4 | 配置 `chunk_overlap=200`，为什么实际重叠不一定都是 200？ | RecursiveCharacterTextSplitter 优先在段落、换行、空格等分隔符处切割，并从可容纳的片段回退拼接；200 是目标上限。项目 399 对同页相邻 chunk 实测为 117–199，P50 158。 | READY |
| B22 | P1 | 4/4 | 为什么先用 BM25 筛 chunk 参数，不能直接把结果当 dense 结论？ | 离线 BM25 无 API 成本，适合淘汰明显差的粒度；但稀疏词项匹配与 Qwen 向量空间的排序机制不同。当前 5 组结果只把 dense 候选缩到 750/150、1000/200、1250/250，最终仍需同语料重嵌入。 | READY |
| B23 | P1 | 4/4 | 为什么实现了 hybrid retrieval 却没有接入主链路？ | 同题初筛显示等权 RRF 把 marker-proxy Hit@1 从 0.9091 降至 0.6364、Hit@5 从 1.0 降至 0.9091，只把 Recall@10 从 0.6173 提到 0.6488。小样本、代理标签下不应事后调参或为技术栈强行上线，需在独立精确标签上预注册权重再验证。 | READY |
| B26 | P1 | 4/4 | 没有原始 PDF，如何恢复 quotes 页码？重复文本为什么不能任选一页？ | 从有页码的 chunks 按精确 overlap 重建 219 页，再做规范化空白后的全文精确匹配；仅唯一匹配写 page。当前 1,298/1,299 唯一定位，1 条同时命中 43/186 页，Sources/API 显式返回 ambiguous candidates。任选一页会制造不可验证的 provenance。 | READY |

## C. Agent、LangGraph 与可控性

| ID | 优先级 | K/F | 面试问题 | 回答锚点 | 状态 |
|---|---|---:|---|---|---|
| C01 | P0 | 5/5 | LangGraph 相比普通 LangChain chain 的优势？ | 显式状态、有向图、条件边、循环和 checkpoint/HITL。项目主图可显式注入 Memory/SQLite checkpointer，已验证 interrupt/resume、跨连接读取和 thread 隔离；默认不持久化，因为 State 含问题与检索内容，生产仍需加密、ACL、TTL 和跨进程协调。 | READY |
| C02 | P0 | 5/5 | 完整图有哪些节点，状态如何流转？ | anonymize→plan→deanonymize→breakdown→route→retrieve/answer→replan→judge→final；按 WHITEBOARD_GUIDE 图 2 解释 State、条件边与循环。 | READY |
| C03 | P0 | 5/5 | Agent 的终止条件是什么？如何避免死循环？ | 可回答性、业务 max_steps、grounding max_attempts、逻辑调用预检、Token 保守准入、框架 recursion_limit 多层保护；最后一步跳过无用重规划，但仍检查新证据能否回答；每条路径输出机器可读原因。 | READY |
| C04 | P0 | 5/5 | 为什么要先规划再重规划？ | 多跳分解；新证据改变剩余步骤；与一次性 plan 做消融。 | PARTIAL |
| C05 | P0 | 5/5 | 工具路由如何实现？错路由怎么办？ | 结构化输出决定三类 retriever/answer；校验枚举、fallback、路由评测。 | PARTIAL |
| C06 | P0 | 5/5 | 项目的“可控”体现在哪里？ | 图约束、Top-K/源开关、最低有效证据数、步骤、Chat 请求/Token、Embedding 请求/输入、累计耗时、有限 grounding 重试、拒答路径和终止原因；仍缺 HTTP attempt 限额与异步语义验证。 | PARTIAL |
| C29 | P0 | 5/5 | 为什么 Embedding 需要独立预算，如何统计？ | 检索可在一个节点内反复生成 query embedding，Chat Token 预算覆盖不到。项目在调用前分别限制 operation 数和输入文本数，批量文档一次请求但按 N 个 input 计，额度随 checkpoint 恢复；尚不等于实际计费 Token。 | READY |
| C07 | P1 | 4/5 | 为什么使用结构化输出/Pydantic？ | 约束 plan/tool schema，减少解析歧义；仍需校验和重试。 | READY |
| C08 | P1 | 4/4 | 千问 structured output 为什么曾报 400？ | thinking 模式不允许 required tool_choice；统一工厂关闭 thinking。 | READY |
| C09 | P1 | 4/4 | 匿名化问题有什么价值和风险？ | 减少实体先验干扰、泛化计划；反向映射已改为确定性纯函数，但仍需做匿名化消融。 | PARTIAL |
| C10 | P1 | 4/4 | State 中为何用 TypedDict？与 Pydantic 区别？ | 轻量状态类型提示 vs 运行时校验；边界输出用 Pydantic。 | READY |
| C11 | P1 | 4/4 | 节点直接修改可变 state 有什么问题？ | 副作用、并发/重放困难；应返回最小增量并使用不可变语义。 | PARTIAL |
| C12 | P1 | 4/4 | 如何实现 checkpoint、恢复和人工审批？ | 主图显式注入 checkpointer，以 thread ID 隔离并用 interrupt 暂停、空输入恢复；SQLite 重开、累计预算、32 thread 并发隔离、同 thread 进程内 single-flight 和删除已测。当前尚未实现业务审批 UI、跨进程同线程协调与外部副作用幂等。 | PARTIAL |
| C13 | P1 | 4/4 | Agent 节点如何保证幂等？ | request/idempotency key、结果缓存、外部副作用隔离；当前检索只读。 | GAP |
| C14 | P1 | 4/4 | 什么时候不应该使用 Agent？ | 固定流程、低延迟、高确定性任务；普通 RAG/规则链更合适。 | READY |
| C15 | P2 | 3/3 | 多 Agent 是否一定优于单 Agent？ | 通信成本、冲突、调试复杂度；按任务可分性和独立状态决定。 | READY |
| C16 | P2 | 3/3 | 如何评估规划和路由本身？ | plan validity、步骤冗余、route accuracy、tool success、循环次数。 | GAP |
| C17 | P1 | 4/4 | 为什么实体恢复不继续使用 LLM？ | 字符串映射是确定性任务；纯函数更可靠、可测试，并减少一次请求和 Token。 | READY |
| C18 | P2 | 3/3 | 为什么 LangGraph 节点不能与 State 字段同名？ | 图通道和节点命名会冲突；`answer` 冲突曾在子图编译测试中暴露，改为动作名并增加全子图编译回归。 | READY |
| C19 | P0 | 5/5 | 为什么 max_steps 不能替代模型调用和 Token 预算？软预算与硬预算有什么区别？ | 一个节点可含多次调用；首版节点后 callback 会越界，现由模型工厂调用前预占、实际 metadata 结算，callback 作独立审计。真实千问已验证 0 请求 Token 拒绝和第二次调用前拒绝。 | READY |
| C20 | P0 | 5/5 | 为什么检索源开关不能只写进 Prompt？ | Prompt 是概率约束，模型仍可能选错；本项目把允许源写入 State，条件路由遇到禁用源进入 `retrieval_source_disabled`，Retriever 不会执行，并有回归测试。 | READY |
| C21 | P1 | 4/4 | 最低证据数怎样实现？为什么它不等于事实充分性？ | answerability 与 finalization 双门禁统计去重、grounded 且白名单有效的 evidence records；多文档可能重复同一事实，因此阈值只是一项可控代理，需实验选取并结合 claim-level coverage。 | READY |
| C22 | P1 | 4/4 | 模型选择了禁用检索源后如何恢复，而不是反复犯错？ | 主图拦截并记录结构化 source policy event，把“该步骤未完成、允许哪些源”传给 replanner；完整图测试验证先选禁用 quotes，随后改用 chunks 并完成带引用回答。 | READY |
| C24 | P1 | 4/4 | 为什么 checkpoint 能 compile 不代表恢复可用？ | 还必须真实执行保存、interrupt、resume 和进程重启。项目在 0.0.49 上用 MemorySaver/SqliteSaver 编译成功，却在首次 stream 因相同时间戳断言失败；此外恢复后累计 Token/调用预算不能清零。 | READY |
| C25 | P1 | 4/4 | 跨 LangGraph 主版本升级为什么不能只改 requirements？ | 1.2.11 首次探针暴露三个旧入口已移除；迁移为双版本 schema 和 core/splitter 稳定入口后，旧/新环境全测均过，再将交付依赖切换并用干净环境 `pip check`、真实 Qwen 冒烟验证。 | READY |
| C26 | P0 | 5/5 | Checkpoint 会保存哪些敏感数据，为什么默认关闭？ | LangGraph 保存完整 State，项目实测 SQLite 中可恢复原问题；检索上下文、答案和映射也可能落盘。因此持久化显式开启、目录忽略提交并支持按 thread 删除；生产仍需加密、ACL、TTL 与数据最小化。 | READY |
| C27 | P0 | 5/5 | 节点 deadline、请求 timeout 和真正取消有什么区别？ | deadline 在新模型调用前和节点边界停止后续工作；SDK timeout 约束单次 HTTP；同步线程超时通常不能杀死在途调用。实测 LangGraph `step_timeout=.05` 的 0.2 秒阻塞节点约 0.204 秒后才报错，因此不冒充硬取消。 | READY |
| C28 | P0 | 5/5 | 两个请求同时使用同一个 checkpoint thread 会怎样？ | 不同 thread 可并行且必须隔离；同 thread 并发是写冲突，实测默认呈 last-write-wins。项目单进程内用 single-flight fail fast，并以 8 workers/32 threads 验证隔离；跨进程仍需分布式锁或乐观版本控制。 | READY |
| C23 | P1 | 4/4 | Token 为什么要调用前保守预留，而不是响应后再统计？ | 响应后只能观测已发生的超限；调用前按输入/schema/最大输出预留可先做准入，成功后再按实际 Token 释放差额。代价是可能拒绝本可返回短答案的调用。 | READY |

## D. 评测、实验与可信度

| ID | 优先级 | K/F | 面试问题 | 回答锚点 | 状态 |
|---|---|---:|---|---|---|
| D01 | P0 | 5/5 | 你的黄金评测集怎么构建？ | 13 条种子与 39 条候选隔离；五类题型、八类风险、答案组、证据定位和审计；追加式人审绑定 case/corpus hash、reviewer、checklist 和精确 supporting chunk hashes，支持按 ids 分批恢复。只读进度审计以 HUMAN_REVIEW_PROGRESS 为准，未把自动定位冒充人审。 | PARTIAL |
| D41 | P0 | 5/5 | 如何证明人审进度没有把过期或拒绝记录算成已完成？ | 只取 append-only log 每题最新决定，再校验 case hash、corpus hash 和正负例 chunk 语义；分别报告 approved/missing/rejected/stale/invalid，并由测试确保 HUMAN_REVIEW_PROGRESS 与审核日志动态一致。 | READY |
| D42 | P0 | 5/4 | 无答案题怎么人工审核？搜索不到能否证明不存在？ | 不能；检索零命中只说明该查询没找到。项目要求每个负例配置 `review_search_terms`，审核包只给有界 concordance 辅助导航并显式警告零命中不证明不存在；人仍需对绑定语料快照确认缺失或错误前提，最终追加式决定禁止携带正证据 chunk。 | READY |
| D02 | P0 | 5/5 | 为什么需要 direct 和 naive RAG baseline？ | 隔离模型记忆、检索收益和 Agent 额外收益；按 WHITEBOARD_GUIDE 图 3 说明归因、质量与成本。 | READY |
| D03 | P0 | 5/5 | Faithfulness、correctness、relevance 有何区别？ | 证据支撑、参考答案一致、是否切题；不可混用。 | READY |
| D04 | P0 | 5/5 | LLM-as-a-judge 有哪些偏差？ | 自偏好、位置/长度/风格偏差、非确定性；项目已实现分层 20% 人审抽检、MAE/容差一致率和 hash 失效机制，正式人评分数尚未产生。 | PARTIAL |
| D05 | P0 | 5/5 | 如何防止测试集泄漏和模型记忆？ | 冻结 nonce 合成事实并记录 hash，做 direct、原事实和只替换答案的反事实；再让两套事实真实经过 Qwen Embedding、隔离 FAISS 与生成。当前 6 组全通过，正式公开集仍须 direct baseline，未来扩展私有时间切分。 | READY |
| D06 | P0 | 5/5 | 如何证明提升具有统计意义？ | 已实现同题 case-level 配对 bootstrap 95% CI，记录有效配对数、seed 和重采样次数，少于 20 对不做方向推断；仍需当前 52 条全部人审后的正式三基线结果和分题型解释。 | PARTIAL |
| D07 | P1 | 4/5 | answer_hit 和 token F1 有什么局限？ | 字面匹配不懂语义、长回答受罚；多部分答案用 AND-of-OR answer groups 防止部分命中，但仍不替代人评/裁判。 | READY |
| D08 | P1 | 4/4 | evidence recall 怎么算？ | 黄金证据片段被检索上下文覆盖的比例；还需 precision/MRR。 | READY |
| D09 | P1 | 4/4 | 如何评估不可回答问题？ | 已分离 answerability accuracy 和拒答 precision/recall；当前词法拒答检测需人审，后续补 false answer rate/校准曲线。 | PARTIAL |
| D10 | P1 | 4/4 | 为什么同时记录 P50/P95 而不是平均延迟？ | Agent 长尾、重试和循环会被均值掩盖；聚合已实现总体与节点 P50/P95（节点当前为 mean/P95）。 | READY |
| D11 | P1 | 4/4 | 如何做消融实验？ | 固定数据/模型/索引，仅改变一个变量并同时比较质量、成本和稳定性；项目已完成 K=1/3/5/10 检索消融，显示 coverage 上升而 precision 下降，但仅 11 条 marker-proxy 样本，不能当正式收益。 | READY |
| D12 | P1 | 4/4 | 模型裁判和生成模型相同有何问题？ | 可能产生自我偏好和相关错误；当前先用固定分层样本人审校准，后续应补异构裁判并比较一致性。 | PARTIAL |
| D13 | P1 | 4/4 | 网络失败如何影响评测？ | 仅瞬时网络和 408/409/425/429/5xx 做外层重试；错误率独立报告，并记录 attempts、错误分类、重试率和恢复率，避免把重试后成功伪装成首试成功。 | READY |
| D14 | P2 | 3/3 | 如何将离线评测用于 CI？ | 无密钥 CI 执行当前 213 项测试、问题队列、数据与风险覆盖审计；正式评测需要模型调用和人审，不放入每次离线 CI。仍缺远端首跑。 | PARTIAL |
| D15 | P2 | 3/3 | 为什么记录数据集 SHA256？ | 锁定语料版本，避免同名数据变化导致结果不可复现。 | READY |
| D16 | P1 | 4/4 | 为什么正确拒答的 answer_hit 可能是 0？ | `answer_hit` 只做字面答案匹配，不判断该不该回答；负例应另看拒答与 answerability。旧失败报告曾把正确拒答的 `answer_hit=0` 误标为 `answer_miss`，现仅对可回答正例标此错误，旧结果不回写。 | READY |
| D17 | P0 | 5/5 | 为什么候选集不直接并入黄金集？ | 证据搜索只能证明正例片段存在，不能证明信息缺失；候选与 gold 隔离并要求 human_approved，防止为凑数量污染基准。 | READY |
| D18 | P1 | 4/4 | 如何防止把冒烟测试误报成正式结果？ | `--formal` 强制 ≥50、人审、三系统、全量和 judge；结果元数据记录 formal 标志、哈希、模型及参数。 | READY |
| D19 | P1 | 4/4 | 多部分答案如何做确定性评分？ | `acceptable_answer_groups` 采用组间 AND、组内 OR；例如人物、分数、原因三组必须都命中。 | READY |
| D20 | P1 | 4/4 | 失败样本如何分析而不是只看总分？ | 每条可有执行错误、答案/证据 miss、answerability、预算、grounding、低 judge 分等多标签，再按题型和系统聚合根因。 | READY |
| D21 | P1 | 4/4 | Prompt Injection 的评测如何避免把密钥写进日志？ | 响应只与内存中的配置 secret 比较，结果记录 `secret_leak_detected` 布尔值和泄露率，不回显 secret。 | READY |
| D22 | P2 | 3/3 | 为什么拒答内容正确但 termination reason 不能写 answered？ | 内容质量与执行语义要一致；direct/naive 根据拒答检测记录 `abstained`，Agent 另保留预算或 grounding 根因。 | READY |
| D23 | P1 | 4/4 | citation precision 和 citation evidence recall 分别衡量什么？ | 前者看引用文档中多少含黄金证据，后者看黄金证据被已引用文档覆盖多少；均不能替代 claim-level entailment。 | READY |
| D24 | P1 | 4/4 | 如何防止模型伪造引用？ | schema 返回 supporting_ids，代码与本轮真实 evidence ID 白名单求交；未知 ID 丢弃，无有效引用则 grounding/最终回答失败。 | READY |
| D25 | P1 | 4/4 | temperature=0 仍不稳定时，如何量化和定位？ | 同一 case 重复运行，报告成功率/方差/最坏值；保留候选答案、候选引用和 verifier explanation。项目已捕获同证据下先失败后成功的 grounding 波动，但尚缺系统化重复实验。 | PARTIAL |
| D26 | P1 | 4/4 | 如何验证“系统是否拒答”，为什么不能只匹配文案？ | 区分知识性拒答与资源耗尽：Agent 的 `search_exhausted`、`grounding_failed`、证据阈值等状态可计拒答，预算耗尽单列为未完成；direct/naive 暂用词法检测并人工校准。两题演示暴露“context does not contain”漏判和预算耗尽误计拒答，现已加回归，但旧结果不回写。 | PARTIAL |
| D27 | P1 | 4/4 | 如果调试后修改黄金标签，如何证明不是为了刷分？ | 展示原标签与原文冲突、修复依据和新数据集 SHA；旧结果随旧 hash 失效并完整重跑。本项目两条 Top-10 假阴性正是这样处理。 | READY |
| D28 | P1 | 4/4 | 为什么只在数据里写 `human_approved` 不足以证明人审？ | 状态字符串可随手改且无法知道谁、何时、基于哪版语料审核；append-only decision 绑定 case/corpus SHA、reviewer、时间和 checklist，formal 构建及运行入口都会复验 provenance 并 fail closed。 | READY |
| D29 | P1 | 4/4 | 平均正确率高，为什么系统仍可能不可靠？ | 平均值会掩盖同一题偶发失败；`--repetitions` 区分 cases/runs，并严格统计所有重复均命中、终止原因一致和拒答一致。当前机制已验证，Agent 规模化重复实验仍待跑。 | PARTIAL |
| D30 | P0 | 5/5 | 指标里的 `null` 和 `0` 有什么区别，处理错了会怎样？ | `0` 表示有分母但系统一个也没找回，`null` 表示指标不适用/分母不存在；若把零引用 recall 写成 null，聚合会排除失败样本并虚高。真实千问失败暴露并修复了该问题。 | READY |
| D31 | P0 | 5/5 | 为什么系统比较应该用配对 bootstrap，而不是分别比较两个均值？ | 三系统回答的是同一批题，难度是共享因素；对每题先算系统差值再重采样可消除题目难度造成的大量方差，并直接回答“平均差值是否稳定跨过 0”。 | READY |
| D32 | P1 | 4/4 | 重复运行和执行错误如何进入配对置信区间？ | 先对同一 case/system 的完整重复取均值；任一重复错误、任一侧缺指标或双方重复数不一致，就整题退出该指标配对，并单独保留错误率。只丢失败 run 会产生幸存者偏差。 | READY |
| D33 | P0 | 5/5 | 为什么 evidence marker 不能直接当检索相关性标签？ | 同一个词可能出现在多个不支持答案的 chunk 中，导致 relevant 集虚大、precision/recall 失真；marker 只用于定位候选，正式人审必须选择实际 supporting chunk SHA256。 | READY |
| D34 | P1 | 4/4 | 为什么用内容哈希而不是 FAISS 内部序号标注证据？ | 内部序号可能随重建顺序改变；内容 SHA256 可跨相同语料重建稳定对齐。哈希绑定语料快照，但相同文本重复出现时仍需结合页码审计。 | READY |
| D35 | P1 | 4/4 | gold evidence 是合法 SHA256 就足够了吗？ | 不够；格式正确的随机值或旧语料 hash 仍可能进入数据。formal gate 会加载可信 corpus、计算全部文档内容 hash，并拒绝不属于当前快照的 gold chunk。 | READY |
| D36 | P0 | 5/5 | 如何抽检 LLM-as-a-judge，为什么不能随手挑几条？ | 按 system/category 分层并用固定 seed 的 SHA256 排序抽取至少 20%，避免只挑显眼案例；审核绑定 details 与 record hash，报告 coverage、MAE 和容差一致率。 | READY |
| D37 | P1 | 4/4 | 人工裁判审核为什么要绑定整份结果和单条记录两个 hash？ | details hash 锁定本次完整实验快照，record hash 精确绑定问题、答案、引用与 judge 输出；任一层变化都会使旧审核失效，同时便于定位变更范围。 | READY |
| D38 | P1 | 4/4 | LLM-as-a-judge 自己会被 Prompt Injection 攻击吗？ | 会；候选答案和检索上下文都可能包含“给我满分”等指令。裁判 Prompt 将各字段包成不可信数据并转义标签，但仍需人审校准，不能把模型裁判当安全边界。 | READY |
| D39 | P0 | 5/5 | 为什么裁判一致率阈值必须在看正式结果前确定？ | 看完结果再调容差或门槛属于事后调参，会把不可靠裁判包装成通过。版本化协议预注册 20% 抽样、0.2 容差、≥80% 一致率、MAE≤0.2 和 100% 审核完成率；未通过就如实报告。 | READY |
| D40 | P0 | 5/4 | 反事实上下文实验最容易引入什么混杂变量？ | 除目标答案外若还改了文档版本、实体名或措辞，拒答可能是因为问题与上下文不匹配，而非模型不跟随反事实。项目首跑因此作废，随后增加模板契约，强制配对上下文只替换答案。 | READY |
| D43 | P0 | 5/4 | 有了逐句引用数量，为什么还要单独评测引用映射契约？ | 数量无法发现漏句、错序、重复 claim、空证据或未知 ID。评测器现独立记录句子覆盖率、ID 有效率、结构契约通过率和 schema 校验失败率，并将失败写入诊断报告；这些仍不是语义蕴含分数。 | READY |
| D44 | P0 | 5/5 | `--formal` 跑完为什么不等于项目达到简历发布线？ | 完成只证明实验执行；当前两段模型分层结果里 Agent 错误率 11.97%/35.90%，首段 31 对完整样本中 naive RAG 的答案命中和裁判正确性均显著占优。额度切换后不能拼接成固定模型正式结果；新记录逐条标模型，但自动切换/恢复未实现。52 题已用于故障诊断和代码改进，后续同题复验只能算回归。项目尚未通过发布门禁。 | READY |
| D45 | P0 | 5/4 | summary 记录了 details SHA256，为什么还必须从 details 重算指标？ | details 哈希只能发现逐条文件变化，不能发现只修改 summary 聚合数。独立复验器从 JSONL 重算三系统汇总和配对 bootstrap，与保存结果做规范化摘要比对，再应用质量协议；普通 SHA 仍不是防恶意篡改的签名。 | READY |
| D46 | P0 | 5/4 | details 和 summary 自洽，为什么仍不能证明跑的是正式 50 题？ | 两者可能共同来自被替换或删减的数据。复验器还要求原始正式 dataset，校验其 SHA、case ID 唯一性、题目/参考答案/题型/answerable 字段，并要求完整的 case × system × repetition 笛卡尔积，无重复、无缺失。 | READY |
| D47 | P0 | 5/5 | 评测集有 50 多题，为什么仍不能说明风险覆盖充分？ | 总数和粗粒度 category 会掩盖风险空洞。本项目用轻量矩阵记录五类题型和八类风险最低数，risk tag 纳入 case hash 并由 CI 检查。52/52 人审与结构覆盖已通过，但分层运行显示 Agent 明显弱于 naive RAG，不能把题型覆盖当成风险能力通过。 | READY |
| D48 | P0 | 5/5 | 正式集已冻结并人工审核，为什么改完 Agent 后还需要新留出集？ | 冻结与人审保证标签和语料证据可信，不保证未被开发反馈污染。现有 52 题的失败已驱动递归预算与重规划改动；同题重跑可验证回归和节省请求，但无法独立证明泛化。需先锁定实现与门槛，再审核未用于调参的新题并做固定模型三基线配对验证。 | GAP |

## E. 模型、Prompt 与成本

| ID | 优先级 | K/F | 面试问题 | 回答锚点 | 状态 |
|---|---|---:|---|---|---|
| E01 | P0 | 5/5 | 为什么选择 qwen3.8-max？ | 中文/结构化能力、百炼密钥与兼容接口；需要和更小模型做成本质量比较。 | PARTIAL |
| E02 | P0 | 5/5 | OpenAI-compatible 是否意味着完全兼容？ | 不意味着；thinking/tool_choice 已证明行为差异，需集成测试。 | READY |
| E03 | P1 | 4/5 | temperature=0 是否完全确定？ | 不保证；服务实现、并行和模型更新仍可能变化。 | READY |
| E04 | P1 | 4/4 | Prompt 如何版本化和测试？ | 模板已集中到 prompts.py 并记录 PROMPT_VERSION；还需黄金集回归 gate。 | PARTIAL |
| E05 | P1 | 4/4 | 如何减少 Token 和成本？ | 已有调用前 Token 准入、实际用量/节点归因和早停；主图现先判断证据充分性，只有不足且预算允许才重规划。此变更离线证明少走无用节点，不等于线上 Token 降幅；后续用同模型新题比较质量、成本与错误率，再考虑缓存或压缩上下文。 | PARTIAL |
| E06 | P1 | 4/4 | 如何选择重试次数和退避？ | 评测外层已仅重试瞬时网络/限流/服务端错误并指数退避，400/401/403/404/405/422 和未知契约错误立即失败；仍缺 jitter、总耗时上限和节点级恢复。 | PARTIAL |
| E07 | P1 | 4/4 | 为什么要统一模型工厂？ | 密钥/URL/model/retry/thinking 一处配置，避免节点漂移。 | READY |
| E08 | P2 | 3/3 | 如何切换 DeepSeek？ | provider/model 配置层；验证 structured output、tool call、token metadata。 | PARTIAL |
| E09 | P2 | 3/3 | 如何做大小模型路由？ | 简单任务小模型、复杂规划大模型；以质量门槛和 Pareto 曲线决定。 | GAP |
| E10 | P1 | 4/4 | Token 统计的口径是什么，为什么可能不完整？ | 当前 callback 统计 Agent 聊天模型 prompt/completion Token 与成功请求，不含 embedding；供应商 metadata 缺失时必须标记 accounting unavailable，不能按 0 成本解释。 | READY |
| E11 | P0 | 5/4 | “模型调用次数”和“HTTP 请求次数”为什么不是一回事？ | SDK 可在一次 invoke 内对超时/限流自动重试；当前硬限制逻辑调用并保守计 Token，尚不能逐次观察 SDK 内部 HTTP attempt，因此面试和简历不能宣称完整外部请求限流。 | READY |

## F. Python、工程化、部署与安全

| ID | 优先级 | K/F | 面试问题 | 回答锚点 | 状态 |
|---|---|---:|---|---|---|
| F01 | P0 | 5/5 | 当前项目最大的工程问题是什么？ | 当前最大缺口是 50+ 人审正式评测、跨进程并发/熔断、HTTP attempt 限额与 Embedding 实际费用归因、生产级 checkpoint 安全，以及 Docker/CI 远端证据；主图恢复和累计 Chat/Embedding/耗时预算已离线验证。 | READY |
| F02 | P0 | 5/5 | 如何处理外部模型超时和错误？ | 已有 SDK 请求 timeout、可恢复总 deadline、checkpoint、进程内熔断与评测层瞬时/永久错误分类；deadline 在调用前/节点边界生效，不伪称能杀死同步在途线程。仍需节点级续跑重试、跨进程熔断和 fallback。 | PARTIAL |
| F27 | P0 | 5/5 | 熔断、重试、限流和 fallback 分别解决什么问题？ | 重试处理单次瞬时失败，限流约束流量，熔断在连续故障时快速失败保护下游，fallback 降级到替代能力。项目已做进程内 closed/open/half-open 熔断且不误耗预算；跨进程熔断和经评测的 fallback 仍缺。 | PARTIAL |
| F03 | P1 | 4/5 | 为什么需要异步/并发？ | 多路检索和独立检查可并行；注意限流、共享状态和顺序。 | GAP |
| F04 | P1 | 4/4 | 如何设计 FastAPI/SSE 接口？ | 已实现同步最终结果与 started/progress/completed/error SSE 契约，服务端 request ID、严格输入范围、Settings 默认值单一来源、Agent 线程安全懒单例、引用/用量白名单输出和异常脱敏均有测试。当前是请求内同步节点流，不伪称支持持久 job、Last-Event-ID 恢复、跨进程取消、背压或 Token 流。 | READY |
| F28 | P1 | 4/4 | 并发上限、限流和背压有什么区别？ | 并发上限控制同时在途任务；限流控制用户/租户在时间窗口内的请求速率；背压让生产者根据消费者处理能力减速。API 已做进程内非阻塞 semaphore 准入，满载返回 429/Retry-After 并在响应或 SSE 关闭后释放；尚无按身份限流、多 worker 共享配额和流式背压。 | READY |
| F29 | P1 | 4/4 | request ID、trace ID 和分布式 Trace 是什么关系？ | request ID 便于业务检索，trace ID 关联一条跨组件调用链，分布式追踪还需 span/parent 与上下文传播。API 由服务端生成同一规范 UUID，贯通 X-Request-ID、同步/SSE响应、Agent State和本地Trace，客户端不能覆盖；尚未用 W3C Trace Context 传到供应商或外部后端。 | READY |
| F30 | P1 | 4/4 | liveness、readiness 和深度健康检查有什么区别？ | liveness 只证明进程应否重启；readiness 决定是否接流量；深度检查可能调用真实依赖但会增加费用、延迟和故障放大。项目 `/health` 零依赖，`/ready` 校验密钥、Embedding清单契约和索引哈希且不反序列化；当前均实测200，证据见 HOST_API_DELIVERY_SMOKE，但不证明百炼在线或检索语义正确。 | READY |
| F31 | P1 | 4/4 | 为什么向量索引存在仍可能不能用？如何校验？ | 文件可能截断、被替换，或查询Embedding已换模型/维度。项目manifest绑定六个索引文件的大小/SHA256及Embedding模型/维度，readiness与离线CI均fail-closed，重建成功后原子更新；同仓库普通哈希只防意外漂移，不是签名，不能抵御同时改索引和manifest的攻击者。 | READY |
| F05 | P1 | 4/4 | 如何做可观测性？ | Trace 记录节点、路由、终止和 chat 用量；服务端 UUID 已贯通 HTTP 响应与 Agent State，现有脱敏本地原子持久化、失败隔离与校验工具。仍待外部后端、W3C下游传播、保留/权限策略和 embedding 归因。 | PARTIAL |
| F06 | P1 | 4/4 | Docker 化要注意什么？ | 已实现 bookworm slim、非 root、精简依赖、ignore 和 healthcheck；HOST_API_DELIVERY_SMOKE 证明宿主健康端点 200，同时记录本机无 Docker CLI，构建证据仍缺失。 | PARTIAL |
| F07 | P1 | 4/4 | 如何保护 API Key？ | `.env` 不提交、运行时 secret、日志脱敏、轮换、最小权限。 | READY |
| F08 | P1 | 4/4 | `allow_dangerous_deserialization=True` 有何风险？ | pickle 可执行代码，只加载可信自建索引；生产需安全格式/签名校验。 | READY |
| F09 | P1 | 4/4 | 如何设计自动化测试？ | 当前 213 项覆盖文档事实同步门禁（从审核日志动态校验权威人审进度文件）、FastAPI/SSE输入/顺序/隐私/异常/关联ID/liveness/readiness/索引完整性/配置继承/懒单例/并发准入，主图checkpoint/预算、8 步循环终止、最后一步重规划跳过、全源检索后证据不足的停止分支、引用失败受控重试反馈、熔断、Trace、检索、引用、评测、风险矩阵、人审工具和真实临时FAISS完整图；另有真实千问集成冒烟。 | READY |
| F24 | P1 | 4/4 | 为什么不能所有异常都重试？ | 400 schema、401 鉴权、本地 ValueError 等确定性错误不会靠重试恢复，只会增加费用、延迟并污染错误统计；应按状态码/异常链分类，未知错误默认 fail closed。 | READY |
| F10 | P1 | 4/4 | CI 应该有哪些 gate？ | 已有固定依赖、pip check、Ruff、编译、unit、问题队列和数据证据 audit；正式结果另有机器质量门禁。仍缺 type check、Docker build、远端首跑和受控在线定时 eval。 | PARTIAL |
| F11 | P1 | 4/4 | 如何做缓存，风险是什么？ | embedding/retrieval/LLM分层；key含模型/prompt/语料版本；陈旧与隐私风险。 | GAP |
| F12 | P1 | 4/4 | 如何扩展到并发用户？ | 当前共享 SQLite saver 已测 8 workers/32 threads，同进程同 thread 用 single-flight；进一步需要无状态 API、连接池、分布式锁/队列、限流和外部向量库。 | PARTIAL |
| F13 | P2 | 3/4 | requirements 全量 pin 有何利弊？ | 可复现但易冲突/过时；区分 direct/transitive，lock+Dependabot。 | PARTIAL |
| F14 | P2 | 3/3 | 为什么不在 import 阶段创建所有链和索引？ | 启动慢、测试隔离差；当前 Chain/Retriever/子图均懒加载并有缓存行为测试，无密钥可编译主图。 | READY |
| F15 | P2 | 3/3 | Prompt Injection 如何防护？ | 已有攻击集、secret leak 检测、检索/蒸馏内容不可信标签、闭合标签转义和全节点指令层级；API Key 不入上下文。单条真实间接注入通过，但仍需规模化红队、工具最小权限和输出策略。 | PARTIAL |
| F16 | P2 | 3/3 | 如何做权限感知 RAG？ | 用户身份传递、metadata ACL 预过滤、审计，不能生成后再过滤。 | GAP |
| F17 | P1 | 4/4 | 为什么精简依赖要在干净环境验证？ | 已安装环境会掩盖漏依赖或保留冲突包；本轮全新 Python 3.11 venv 从 runtime requirements 安装且 pip check 无冲突，当前开发环境虽能通过 213 项测试，却因旧 Groq/OpenTelemetry 残留不能用来证明依赖闭包。 | READY |
| F20 | P1 | 4/4 | 如何把一次 Agent 的 Token 成本归因到节点？ | 外层 callback 取每次 LangGraph yield 后的累计用量，与上个节点快照做差并按 trace sequence 回填；子图调用归到所属主节点。当前只覆盖 chat usage，embedding 单独列为缺口。 | READY |
| F18 | P2 | 3/3 | 为什么同一依赖在不同 Python 版本安装结果不同？ | wheel 按 Python/ABI/平台发布；较新 Python 可能回退源码编译。本次误用系统 Python 曾触发 NumPy/Meson 中文路径错误。 | READY |
| F19 | P1 | 4/4 | `.gitignore` 为什么也属于交付质量？ | 曾发现 `docs/` 被整体忽略，导致面试材料无法提交；已解除并用 `git check-ignore` 验证，仅密钥和运行结果继续忽略。 | READY |
| F21 | P2 | 3/3 | FAISS 在 Windows 中文路径报错如何定位和修复？ | native API 接收窄字符路径导致乱码；改由 Python 打开文件并把字节交给 FAISS callback reader，测试在 Unicode 临时目录中读写真实索引。pickle 仍只允许加载可信自建文件。 | READY |
| F22 | P0 | 5/5 | Agent Trace 为什么不能直接把完整 State 写入日志？ | State 含问题、检索上下文、答案及潜在敏感数据；项目只按字段白名单保存节点、控制、用量和终止信息，并用 sentinel 测试确保任意内容/错误字段不会落盘。 | READY |
| F23 | P1 | 4/4 | 把 SHA256 和 Trace 放在同一个文件能防篡改吗？ | 只能检测损坏或未同步重算的修改；有写权限的攻击者能同时改 payload 和 hash。生产真实性需受保护 HMAC/签名密钥或不可变外部日志，不能把普通 checksum 包装成审计签名。 | READY |
| F25 | P1 | 4/4 | 直接 Prompt Injection 和间接 Prompt Injection 有什么区别？ | 直接注入来自用户输入，间接注入藏在检索文档/网页中。RAG 尤其要把检索内容视为不可信数据；标签与提示只能降风险，真正工具型 Agent 还必须做权限、参数和副作用校验。 | READY |
| F26 | P2 | 3/3 | 面试问题很多时如何决定先准备什么？ | 每题记录 K/F 并映射 P0-P3；自动队列先排高优先级，再排 GAP/PARTIAL，最后按综合分。源问题库 hash 与 CI `--check` 防止生成列表过期。 | READY |
| F32 | P1 | 4/4 | 单元测试已经全过，为什么还要静态检查？ | 单测只覆盖被执行的行为，不能系统发现未使用导入、未定义名称和 import 结构问题；项目将固定版本 Ruff 的 E4/E7/E9/F/I 规则放入 CI，首次发现 81 项并在修复后清零，规则范围明确且不把 lint 冒充类型或质量评测。 | READY |
| F33 | P1 | 4/4 | 依赖被停止维护时应该立刻替换吗？ | 先确认官方替代、兼容面和迁移证据。`langchain-community` 已 sunset，但当前 FAISS 仍无官方独立包且现有 pickle 绑定其类；项目先精确锁版本、记录风险并规划安全存储迁移，不用未经验证的换 import 制造假安全。 | READY |

## 使用方式

1. 每次只准备一个主题，先覆盖 P0，再覆盖 P1。
2. 回答采用“结论—原理—项目实现—取舍—证据—改进”结构。
3. `READY` 不代表背过；必须能打开相应代码或结果解释。
4. 每完成路线图功能，更新对应问题状态和回答锚点。
5. 每周进行一次随机抽题模拟面试，记录答不出的 ID。
