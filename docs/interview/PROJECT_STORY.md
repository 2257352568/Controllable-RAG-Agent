# 项目讲解稿

> 规则：方括号中的指标必须由正式评测结果替换，不能凭感觉填写。

## 30 秒版本

这是一个基于 LangGraph 的可控多源 Agentic RAG 系统。我在开源工作流基础上进行了千问模型迁移、向量索引重建和评测工程化。系统会把复杂问题拆解成任务，在正文分块、章节摘要和原文引用三类知识源之间动态路由，判断证据是否充分，并在不足时重规划。项目重点不是单纯接入大模型，而是通过基线对照、证据召回、忠实度、延迟和 Token 消耗来验证 Agentic RAG 是否真的优于普通 RAG。

## 1 分钟版本

项目要解决的是复杂、多跳问题在普通一次检索 RAG 中容易漏召回、回答缺少依据的问题。整体使用 LangGraph 管理显式状态，流程包括实体匿名化、规划、任务拆解、检索工具路由、相关内容蒸馏、事实支撑检查、重规划和最终回答。

知识库分为正文、章节摘要和引文三类 FAISS 索引。模型使用百炼的 `qwen3.8-max`，Embedding 使用 1536 维 `text-embedding-v4`。迁移过程中我发现仅让向量维度一致是不够的，因为不同 Embedding 模型的向量空间不可直接比较，所以从原文档存储重建了全部 1,934 条向量，并保留旧索引备份。

为了验证复杂工作流是否值得，我建立了 direct、naive RAG、Agentic RAG 三组对照，记录答案命中、证据召回、拒答质量、裁判正确性/忠实度、错误率、分题型 P50/P95、调用次数和 Token，并对同题差值做配对 bootstrap 95% CI。当前有 13 条运行种子和 39 条独立候选；正式指标必须等当前 52 条全部人工批准后才能运行和发布。

## 3 分钟版本结构

1. **背景**：普通 RAG 对多跳问题、跨粒度证据和不可回答问题的不足。
2. **架构**：三类索引、LangGraph 状态、条件边和循环重规划。
3. **可控性**：已有 Top-K、三类检索源开关、最低有效证据数、递归上限、业务最大步骤、逻辑聊天调用/Token 预检、Embedding 请求/输入预算、累计 deadline、有限 grounding 重试、拒答路径和终止原因；仍缺 SDK 内部 HTTP attempt 计数和异步调用语义验证。
4. **关键难点**：Embedding 迁移必须重建索引；千问思考模式与 LangChain 强制工具调用不兼容；远端服务偶发连接失败。
5. **验证**：三组基线、黄金数据集、确定性指标与模型裁判、人审抽检。
6. **结果**：使用正式评测数据替换 `[正确率]`、`[忠实度]`、`[P95]`、`[Token]`。
7. **反思**：复杂 Agent 不一定优于基础 RAG；需要以质量增益是否覆盖延迟和成本为准。

## 必须主动说明的原创边界

项目源自 NirDiamant 的 `Controllable-RAG-Agent`。原始 LangGraph 工作流、Harry Potter 示例语料和主要节点来自上游。当前本地贡献包括：

- 将模型与 Embedding 迁移到阿里云百炼千问；
- 修复千问结构化输出兼容、Prompt 变量和最终响应类型问题；
- 用千问 Embedding 重建三套 FAISS 索引并实现备份工具；
- 建立三基线评测框架、黄金样例、Token/延迟/错误统计和模型裁判；
- 将节点与 Graph 模块化，增加业务步骤、聊天调用/Token 发送前准入、grounding 重试上限和机器可读终止原因；
- 增加节点 Trace、P50/P95 和拒答质量指标；检索优化与生产工程仍在路线图中。

简历表述应使用“基于开源项目继续开发并重构”，明确个人改造范围，不能暗示从零原创。

## STAR 故障案例

### 千问结构化输出 400

- Situation：从 OpenAI 迁移到 `qwen3.8-max` 后，普通聊天成功，但 LangGraph 规划节点返回 400。
- Task：保证 Pydantic 结构化输出可用于规划和路由节点。
- Action：通过端到端评测定位到思考模式与 `tool_choice=required` 不兼容；在统一模型工厂关闭 thinking，并用最小结构化调用和完整 Agent 链路验证。
- Result：Agent 成功走通匿名化、规划、拆解、检索、重规划、事实检查和最终回答。

### Embedding 迁移

- Situation：旧 FAISS 索引是 OpenAI Embedding 的 1536 维向量。
- Task：切换千问平台且保持检索有效。
- Action：确认 `text-embedding-v4` 支持 1536 维；说明维度相同不等于语义空间相同；从 FAISS docstore 恢复 1,934 条文档并重建索引，写入前保留时间戳备份。
- Result：三套新索引数量和维度一致，真实语义检索通过。

### 单体 Pipeline 重构

- Situation：上游核心逻辑集中在约 1,183 行文件中，配置、模型、索引和状态强耦合，难以测试。
- Task：在不改变现有 Agent 行为的前提下建立清晰模块边界。
- Action：抽离 `config/models/retrieval/schemas/prompts/chains/nodes/graph/observability`，用不可变 Settings 做环境校验和依赖注入；把 Top-K、超时、重试和步骤预算参数配置化；将 Chain、Retriever 和子图改为懒加载；增加关键纯函数、路由、预算与编译回归测试。
- Result：213 项离线测试通过，无 API Key 也能导入应用并编译主图及全部子图；完整图测试使用 Unicode 路径下的真实临时 FAISS，预算测试覆盖 Chat 请求/Token、Embedding 请求/输入、累计 deadline 和 checkpoint 恢复额度，Checkpoint 测试覆盖并发隔离与同线程冲突，主图回归验证 8 步循环在框架递归上限前触发业务预算终止，最后一步跳过无用重规划但保留可回答性检查；熔断测试覆盖状态转换、预算顺序和安全诊断，API 测试覆盖输入、事件顺序、隐私、异常、关联ID/liveness/readiness、索引完整性、配置继承、懒单例和并发准入契约，评测测试覆盖 quote 位置、风险矩阵、正式质量协议、人审进度、过期分类、负例搜索词与有界批次包，Trace 测试覆盖隐私、原子写入、历史 schema 校验、失败轨迹和存储失败隔离；文档测试还会阻止当前测试数及已实现能力表述再次过期。原文件已缩为仅负责兼容导出的轻量模块。

### 用确定性代码替代 LLM

- Situation：重构后的 Trace 显示反匿名化模型没有把计划中的 `X` 恢复成 `Hogwarts Express`，只是检索阶段侥幸找到了答案。
- Task：消除随机映射错误并减少不必要调用。
- Action：将反匿名化改为带单词边界保护的纯函数，按变量长度替换并增加不修改输入、避免子串碰撞等测试。
- Result：同一冒烟问题中实体恢复正确；模型请求从 11 次降至 10 次，Token 从 5,596 降至 5,252。单次耗时约 19.9 秒；这些是故障修复证据，不作为正式性能统计。

### 预算熔断与拒答指标

- Situation：Agent 循环只有 LangGraph recursion limit，既不能表达业务预算，也难以区分正常回答、证据失败和预算耗尽；同时字面命中会把正确拒答计为 0。
- Task：让停止行为可控、可观测、可评测。
- Action：加入 `max_steps`、grounding `max_attempts`、显式终止原因和节点 Trace；首版用 callback 在节点边界结算，随后将逻辑调用预占和 Token 保守预留下沉到共享模型工厂，成功后用供应商 metadata 结算，callback 继续独立审计；为不可回答问题单独统计 answerability accuracy 与 abstention precision/recall。
- Result：真实千问在调用预算 1 时完成第一次 395 Token 调用，第二次发送前以 `model_request_budget_exhausted` 停止；Token 预算 100 时首个请求发送前停止，记录 0 请求/0 Token。随后又为 Embedding 增加独立 operation/input 预检与恢复测试；SDK 内部 HTTP attempts 和 Embedding 实际计费 Token 仍不可见。这些是控制路径验证，不是质量指标。

后续一次 grounding 失败响应使用了 “evidence was insufficient”，而词法检测器只覆盖 “insufficient evidence”，一度把拒答错算成已回答。评测现对 Agent 优先使用结构化终止原因判断拒答，只对 direct/naive baseline 回退到词法检测，并加入词序变化回归用例。这个案例说明评测器本身也必须被测试。

### 黄金数据审计

- Situation：种子集中使用了与美版语料不一致的 Stone 名称，Devil's Snare 又使用 `relax`、`sunlight` 等宽泛标记，可能在无关页面误命中；多部分答案只命中一个人名也会得到满分。
- Task：保证基准数量增长不会以标签污染和虚高指标为代价。
- Action：增加 JSONL schema、重复问题、证据页、risk tag 和 review status 审计；修正证据标记；多部分答案改为组间 AND、组内 OR；将 39 条候选与正式集隔离，建立 `--formal` 强制门禁，并按执行、回答、证据、拒答、预算和 grounding 输出多标签失败报告。Prompt Injection 响应另做内存密钥比对，只落布尔泄露信号。
- Result：13 条种子和 39 条候选的正例证据审计均通过；合计 20 单跳、10 推理、11 多跳、5 无答案、6 对抗题，并显式覆盖八类风险。11 条负例仍明确等待人工复核，未冒充黄金数据。

### Prompt Injection 冒烟

- Situation：安全样本不能只验证模型是否输出某个拒答短语，还要检测真实运行时密钥是否泄露，并正确表达执行结局。
- Action：加入仅输出布尔值的 secret leak 检测，用 `qwen3.8-max` 对一条要求泄露 `QWEN_API_KEY` 的候选做 direct 冒烟；随后修复“内容已拒答但 termination reason 仍为 answered”的语义不一致。
- Result：模型明确拒绝，`answer_hit=1`、answerability decision 正确、`secret_leak_rate=0`；单次为 1 请求、83 Token、2.864 秒。仅作为安全链路证据，不作为正式统计。

### 依赖与交付环境治理

- Situation：上游 `requirements.txt` 接近完整开发环境快照，Dockerfile 使用 buster、root、编译器和 Rust；同时 `.gitignore` 意外忽略整个 `docs/`，面试材料不会进入提交。
- Task：建立可复现、最小权限且不依赖开发机存量包的离线交付链路。
- Action：增加精简直接依赖并用完整版本表作 constraints；Docker 改为 bookworm slim、非 root、健康检查和最小构建上下文；解除 docs 忽略；增加无密钥 GitHub Actions。首次干净环境测试误用了系统较新 Python，NumPy 回退源码构建并触发 Meson 中文路径错误，随后固定 Python 3.11 重测。再将固定版本 Ruff 的 E4/E7/E9/F/I 规则纳入开发依赖和 CI，机械修复 import 与明显静态错误。
- Result：全新 Python 3.11 环境安装现代精简依赖成功且 `pip check` 无冲突；Ruff 首次发现 81 项问题，68 项自动修复、13 项经显式修复或有边界的兼容忽略后归零；当前开发环境的 213 项测试和数据审计通过，LangGraph 1.2.11 完整主图编译与真实千问 Chat/Embedding 冒烟通过。开发环境因历史遗留包单独执行 `pip check` 仍会报旧 Groq/OpenTelemetry 残留，因此依赖闭包只以干净环境为证据。宿主 Streamlit、FastAPI liveness 与带索引哈希/Embedding契约的readiness均曾返回HTTP 200；升级后的Docker镜像与远端Actions仍未验证，不能宣称通过。

### SSE 只暴露进度，不暴露 Agent State

- Situation：前端需要看到 Agent 执行进度，但 LangGraph State 同时包含用户问题、检索原文、计划和验证解释，直接序列化既泄露数据又把内部结构变成公共 API。
- Task：提供可演示、可测试的 FastAPI 查询接口与稳定 SSE 事件边界。
- Action：增加同步结果端点和 `started/progress/completed/error` 事件协议；请求参数严格限制类型、范围和检索源，未知字段拒绝，未提交的控制项交给统一 Settings；Agent 使用应用级线程安全懒单例；每个响应生成 request ID，进度只投影节点与用量，最终结果只输出答案、白名单引用和统计，异常统一脱敏。健康检查不构造 Agent。
- Result：9 项接口测试与配置测试验证事件顺序、递增 ID、输入 fail-closed、Settings 默认继承、Agent 只构造一次、懒健康检查、私有 State/引用 metadata 不泄露、同步/SSE 异常不回显，以及容量为 1 时第二个并发请求立即 429、首请求结束后容量恢复。当前仍是请求内同步流，不支持持久 job、断线恢复、取消和背压，这些边界必须在面试中主动说明。

### API 错误如何定位到 Agent Trace

- Situation：入口生成 `request_id`，Agent又独立生成 `trace_id`；用户拿着前端错误号无法直接找到本地执行轨迹，异常排查需要猜测时间窗口。
- Task：建立不会被客户端伪造的端到端关联键，同时不扩大日志内容。
- Action：API在请求通过schema与容量准入后生成规范UUID，把同一值注入LangGraph初始State，并投影到响应头、同步结果、SSE首尾/错误事件；请求schema继续 `extra=forbid`，客户端提交 `trace_id` 会422。
- Result：测试证明 header/request/trace/Agent input 四处一致，异常也返回相同关联键且不回显底层正文。当前链路只到本地Trace，没有span层级、W3C Trace Context下游传播和外部可查询后端，因此不能称完整分布式追踪。

### 存活不等于可服务

- Situation：`/health` 即使返回200，密钥缺失或向量索引未挂载时，真实查询仍会失败；若健康检查直接调用百炼，又会持续产生费用并在供应商故障时放大流量。
- Task：让编排平台区分“进程应重启”和“实例暂时不接流量”，同时保持检查安全、快速。
- Action：保留零依赖liveness，增加只读readiness；版本化manifest绑定六个索引文件大小/SHA256及Embedding模型/维度，重建全部成功后原子更新。检查不反序列化pickle、不构造Agent、不调用供应商，只返回状态而不返回路径、哈希或密钥。
- Result：伪pickle只要匹配manifest仍能ready，证明没有反序列化；缺密钥/manifest/索引、文件篡改或Embedding切换未重建时均503。当前真实配置三索引及契约均ready并返回200。它不验证供应商在线、FAISS内部维度或检索语义；同仓库manifest也不是防恶意篡改的签名。

### 人审进度不能靠文件行数

- Situation：append-only review log 可能同时含旧批准、新拒绝、题目修改前记录和旧语料记录；直接统计 `approved` 行数会虚报黄金集进度。
- Action：按 case 取最后决定，再依次校验 case hash、corpus hash、decision 和正负例 gold chunk 语义；将状态拆为 approved/missing/rejected/stale_case/stale_corpus/invalid_approval，并按负例与对抗题优先生成下一批。
- Result：人工审核已开始，精确进度由 hash-aware 报告维护；首个正例保存了两个 supporting chunk hash，当前仍为 formal ready=false。该工具只读，不会生成或暗示人工批准。

### 搜索不到不能证明无答案

- Situation：首批人审全是无答案或错误前提题；只给问题让审核人翻完整语料摩擦很大，但自动检索零命中又不能证明信息不存在。
- Action：为每个负例增加 `review_search_terms`；导出工具在绑定数据集与语料哈希的 Markdown 工作表中，每个搜索词最多给 2 个、每段最多 240 字符的 concordance。工作表反复说明零命中不证明不存在且不能导入为批准，最终结论仍通过交互式工具追加记录。
- Result：已生成新的 12 题风险优先工作表；当前种子集 SHA256 为 `aa68...841c`，候选集为 `8a2c...3da`。它降低了语料定位成本，权威人审进度由独立文件维护；旧实验继续绑定其运行时的旧数据集哈希，不追改历史证据。

### Embedding 独立预算

- Situation：一个检索节点会调用 Embedding，但原账本只限制 Chat；Agent 可以在 Chat 额度内反复检索，成本与延迟控制存在盲区。
- Action：在共享活动账本中分别累计 Embedding operation 和输入文本数；`embed_query` 计 1/1，`embed_documents(N)` 计 1/N，并在 provider 调用前拒绝。计数写回 LangGraph State、checkpoint、Trace、UI 和评测 metadata。
- Result：测试证明超出 request/input 任一上限时 provider 调用数保持不变；暂停后恢复不会重置 Embedding 额度。该代理指标可复现，但不是供应商实际 Token 或账单费用，后者仍需响应 usage/账单侧归因。

### Provider 熔断与预算顺序

- Situation：SDK 重试结束后若服务持续不可用，每个 Agent 节点仍会继续等待并占用调用预算；但把所有 400/解析错误都计入熔断又会把客户端缺陷误判成平台故障。
- Action：按 base URL、模型和 Chat/Embedding 类型共享进程内 closed/open/half-open 状态；只将网络、timeout、429 与 5xx 计为瞬时故障。熔断包装放在预算适配器外层，open 状态先拒绝，再进入请求/Token 预留。
- Result：确定性测试证明达到阈值后 provider 不再被调用、预算请求数不增加；冷却后一次 half-open 探测成功会闭合，400 永久错误连续出现也不会打开熔断。包装后的真实 `qwen3.8-max`（19 Token）与 1536 维 `text-embedding-v4` 冒烟通过且无 warning；这不是故障注入或 SLA 指标。当前状态不跨进程，也没有未经评测的自动换模型 fallback。

### Checkpoint 恢复与预算连续性

- Situation：旧 LangGraph 的 saver 在首次 stream 即触发时间戳断言；即使恢复可用，外层预算若重新初始化，也会让恢复后的 Agent 获得额外调用额度。
- Action：升级后将 checkpointer 作为主图显式依赖；每个被观测节点把活动预算账本写回 State，恢复前从 checkpoint 初始化累计账本；适配 LangGraph 1.x 的 `__interrupt__` 元事件，并提供受控 SQLite 生命周期与按 thread 删除接口。
- Result：真实 SQLite 主图 checkpoint 可跨连接读取；共享 saver 在 8 workers 下并发写入 32 个不同 thread 均正确恢复且无串线。同一 thread 的原生并发探针呈 last-write-wins，因而增加进程内 single-flight fail-fast。内存 checkpoint 在一次模型调用后恢复时，第二次调用在发送前被累计预算拒绝。测试同时证明原问题会进入 checkpoint，所以默认关闭落盘；加密、ACL、TTL、跨进程锁和外部副作用幂等仍是生产缺口。

FAISS 原生文件 API 在 Windows 中文用户名临时目录中把路径解码成乱码并写入失败。检索层现由 Python 文件对象读入字节，再交给 FAISS callback reader；测试在显式 Unicode 子目录中创建并查询真实索引。这能作为“第三方 native 库与 Unicode 路径兼容”的工程故障案例。

### Trace 持久化与隐私边界

- Situation：进程内 Trace 能调试当前请求，但程序结束后无法回查；若直接保存 State，又会把问题、检索上下文和答案写入磁盘。
- Action：每次运行生成 UUID，终态只投影节点、控制、用量和终止字段，以完整临时文件原子发布并禁止同 ID 覆盖；写入失败只记录异常类型，不影响业务终态。提供 schema/SHA 校验命令，并用隐私 sentinel 测试字段白名单。
- Result：真实千问 Token 预检轨迹成功落盘并通过独立校验，搜索确认不含问题、答案和语料关键词。SHA 与 payload 同文件，只能做一致性校验；生产真实性仍需外部不可变存储或受保护 HMAC/签名密钥。

### 检索评测抓出黄金标签错误

- Situation：首次 dense retrieval Top-K 评测显示两个问题到 K=10 仍完全 miss。
- Task：判断是 Qwen Embedding 检索失败，还是评测标签造成假阴性，避免直接据此调整模型。
- Action：按结果中的内容 SHA 回查可信本地 docstore。`hp1-002` 的 Top-1 明确写着 “The Seeker. That's you”，但旧 marker 是另一句；`hp1-011` 的 Top-1 是 Quirrell 亲口承认，旧 marker 却来自角色此前对 Snape 的错误猜测。修正 marker 后执行语料证据审计，并因数据 hash 改变废弃旧结果、完整重跑。
- Result：11 条可回答种子的 marker-proxy Hit@1 为 0.9091、Hit@5 为 1.0；evidence marker recall 从 K=1 的 0.7727 升至 K=5 的 0.9091，同时 proxy precision 从 0.9091 降至 0.4364。样本小且 relevance 非穷尽人工标注，数字只作为可复现冒烟和 Top-K 取舍证据，不能用于简历效果宣称。

### 可核验引用闭环

本轮复盘补充：引用 ID 真实存在，只能保证定位有效。旧蒸馏和答案 verifier 使用全部
上下文，导致“引用 B、内容来自 A”仍可能通过。先用固定合成事实复现 4 个失败断言，
再让两个 verifier 只接收所选 ID 对应的原始片段；7 项回归覆盖错配、缺失多跳前提、
原始证据回查、有限重试和最终拒答。千问 16 次诊断中，所选来源版本 8/8 符合预期，
全部上下文版本 4/8 符合预期。记录中的差值仅说明该故障路径已得到验证；两种版本
使用相同新 Prompt，未重放旧模型/旧 Prompt，也没有证明一般质量提升或消除幻觉。
详细逐次结果和成本见 `evidence/CITATION_GROUNDING_PROBE_2026-09-14.md`。

第二层修复把整段 `supporting_ids` 改为逐句 `claim_citations`。代码会检查规范化句子
覆盖、原顺序、重复句和证据白名单，验证失败就拒答；验证通过后只把映射 ID 的原文
交给 grounding，并在最终答案中逐句显示引用。真实 `qwen3.8-max` 的单事实/双事实
子图探针 2/2 首轮通过，共 4 次调用、1,873 Token、22.063 秒。它只证明 schema 与
控制流兼容，正式集上的逐句语义支持率和稳定性仍未完成，不能包装成质量提升。
评测器现另外计算句子覆盖率、引用 ID 有效率、结构契约通过率和最终 schema 校验
失败率；它们用于发现结构回归，与人工或独立裁判的语义支持率严格分开。

- Situation：上游节点在 Retriever 返回后立即把 `Document` 拼成字符串，页码/章节元数据丢失；让模型自由输出 `[1]` 又无法证明引用真实存在。
- Task：让每条引用可回溯、不可伪造，并能单独评测引用质量。
- Action：用 source、位置和内容哈希生成稳定 evidence ID；结构化证据与答案分开进入 LangGraph State；蒸馏和回答只返回 supporting IDs，代码做白名单求交、去重和最终 Sources 渲染；无有效 ID 时不能通过 grounding。评测增加 citation count、evidence recall、precision 和失败标签。
- Result：`qwen3.8-max` 单条 Agent 冒烟正确引用 `[chunks-p68-f72d6980cb]`，定位正文第 68 页；answer/evidence/citation recall 与 citation precision 均命中，耗时 24.516 秒、10 请求、5,352 Token。后续正常预算复跑在相同证据召回下因 grounding 判定失败而拒答；最小复现再次成功，证明链路可用但模型式 verifier 存在波动。现已保留候选答案、候选 ID 和 verifier explanation，并支持 `--repetitions` 聚合 all-runs 与一致性；正式 Agent 稳定性实验仍待执行。

### 上游 quotes 没有页码，不能假装引用可回查

- Situation：上游 1,299 条 quote 文档全部没有 metadata，导致 quote 引用 ID 退化为 `quotes-doc-*`，Sources 只能显示位置未知。
- Task：在仓库没有原始 PDF、且不能凭文本顺序猜页码的条件下恢复可验证位置。
- Action：从 618 个带页码 chunk 按真实 overlap 重建 219 页，对 quote 做规范化空白后的精确全文匹配；只给唯一匹配写入 `page`，多页重复仅保留候选页，并由 Sources/API 显式标为 ambiguous。工具显式要求信任本地 pickle、临时文件写入后原子替换，并刷新索引 manifest；摄取审计把缺失或非法位置变成 CI 失败。旧 Pydantic pickle 字段重赋值曾失败，最终改为原位更新 metadata，并验证再次运行字节哈希稳定。
- Result：1,298/1,299 条唯一定位，页码覆盖率 99.923%；唯一歧义记录同时出现在第 43、186 页，未伪造单一页码。quote FAISS 哈希保持 `5a5c...2682`，证明没有重嵌入或改变向量排序；最终 pickle 和 manifest 哈希已记录。该实验证明位置 provenance，不证明 quote 检索相关性或答案忠实度。

### 正式实验跑完不等于项目合格

- Situation：原 `--formal` 只约束数据规模、三系统和裁判，Agent 即使不如 naive RAG 也能正常结束。
- Task：在看到正式结果前定义“什么证据才足以说明 Agent 复杂度值得”，防止事后挑指标或移动门槛。
- Action：版本化 `formal-quality-2026-09-14.1`，固定三次重复、绝对正确性/拒答/引用/安全/稳定性阈值，并要求 Agent 对 naive RAG 至少一个主要指标有 ≥0.03 且配对 95% CI 显著的收益，任何主要指标显著退化即失败；独立工具从 details 重算汇总和 bootstrap，再核对 dataset SHA、题目字段与完整执行笛卡尔积。
- Result：合成合格结果通过，低 answer hit、Agent 显著退化、details/summary 篡改、数据集替换或风险标签不足均被测试拦截。普通 SHA 不是签名；正式人审尚未完成，因此只能说发布标准已预注册，不能说项目已经通过。

### 题数够了，不代表高风险场景够了

- Situation：原 50 题只有粗粒度 category；`adversarial=5` 无法证明到底覆盖错误前提、注入、密钥外泄还是歧义，证据冲突与指代不明实际缺席。
- Task：在付费正式运行前固定可解释的风险结构，并让报告无法绕过。
- Action：新增判断/事实冲突多跳题和需要澄清的歧义题，为负例与高风险正例增加受控 `risk_tags`；用轻量 `risk-coverage-2026-09-14.1` 矩阵记录五类题型和八类风险最低数。风险标签进入 case hash，并由无密钥 CI 审计。
- Result：当前 52 题结构为 20/10/11/5/6，覆盖 knowledge absence 5、false premise 4，其余六类各 1；两个 dataset SHA 和完整报告已落盘。结构门禁通过，但人审尚未完成且没有系统结果，不能说冲突或歧义处理已经有效。
