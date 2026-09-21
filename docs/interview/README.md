# 面试准备中心

这个目录是项目的面试知识库。目标不是背诵技术名词，而是让每个回答都能落到代码、实验结果或故障记录上。

如果现在对项目几乎没有概念，先读一页 [从零理解这个项目](START_HERE.md)，再进入下面的练习路径；不必一开始读完整问题库。

## 最短练习路径

先只练 6 题，不必从头读完问题库：`A01` 一分钟介绍 → `B01` RAG 完整链路 → `C01` 为什么用 LangGraph → `C03` 如何终止循环 → `D02` 三路径对照的归因 → `A05` 真实效果与边界。每题按“结论—实现—证据—局限”讲 30～60 秒，并能指向一个代码或结果文件。能脱稿回答后，再练 `A06` 的质量/成本取舍和 `A07` 的真实故障；其余问题按追问需要查阅，不作为开始练习的负担。

## 文件导航

- `QUESTION_BANK.md`：项目可能被追问的问题、优先级、回答锚点和当前准备度。
- `START_HERE.md`：零基础导读，只讲“查书回答”的主线、三个基线和最小证据。
- `STUDY_QUEUE.md`：从问题库自动生成的前 50 道冲刺队列，优先暴露高频 GAP/PARTIAL 项。
- `ROADMAP.md`：将项目提升到简历合格线的路线图和验收门槛。
- `PROJECT_STORY.md`：30 秒、1 分钟和 3 分钟项目讲解框架。
- `LEARNING_MAP.md`：核心必学、追问加分点和明确不实现的范围边界。
- `CORE_INTERVIEW_ANSWERS.md`：17 个最高频核心问题的口述答案、追问入口和禁区。
- `CODE_EVIDENCE_INDEX.md`：将 17 个核心回答映射到代码符号、回归测试和证据等级。
- `INTERVIEW_SPRINT.md`：7 天、每天 60–90 分钟的口述、白板、代码和故障训练计划。
- `WHITEBOARD_GUIDE.md`：三张可在面试中现场画出的 RAG、Agent 与评测主线图。
- `RESUME_ENTRY.md`：当前证据支持的内部简历草稿，以及门禁通过后才能填写的量化模板。

## 优先级规则

每道问题分别评估：

- `K`（Knowledge Importance）：知识点对 RAG/Agent 岗位的重要性，1～5。
- `F`（Interview Frequency）：面试中出现频率的经验估计，1～5。
- 综合分：`0.55 × K + 0.45 × F`。

映射规则：

- `P0`：4.50～5.00，必须能脱稿回答并结合代码举证。
- `P1`：3.70～4.49，应能解释原理、取舍和项目实现。
- `P2`：2.80～3.69，需要掌握，允许少量提示。
- `P3`：低于 2.80，拓展知识。

`F` 不是严格统计概率，而是根据当前 AI Agent/RAG 岗位要求及常见项目面试路径得到的启发式分数。项目实践会持续校准它。

`tests/test_interview_docs.py` 会在离线 CI 中验证每一行的字段格式、全局 ID 唯一性、K/F 取值和上述优先级公式，防止问题库扩充后发生编号或优先级漂移。
`evaluation/build_interview_queue.py` 按 P0→P3、GAP→PARTIAL→READY、综合分降序生成冲刺队列；CI 的 `--check` 模式会阻止过期队列。

## 证据原则

面试回答优先采用以下证据顺序：

1. 完整可复现的对照实验；
2. 自动化测试和 CI 记录；
3. 代码实现、日志与故障复盘；
4. 设计文档；
5. 仅有口头理解。

没有证据的数据不进入简历。

## 当前岗位信号

近期岗位描述反复出现的能力包括：LangGraph/Agent 编排、RAG 检索优化、评测与可观测性、成本和 Token 管理、失败恢复、Docker/CI/CD、安全治理、MCP 和生产 API。参考：

- EPAM Senior AI Engineer, Agentic and RAG Systems：https://careers.epam.com/en/vacancy/senior-ai-engineer-agentic-and-rag-systems-blty5mp8mok8tyd6a36_en
- Accenture AI 全栈工程师（Harness/Agent 方向）：https://accenture.wd103.myworkdayjobs.com/en-US/AccentureCareers/job/AI--AI-Agent--_14477302
- Randstad AI Agent 工程师：https://www.randstad.cn/jobs/ai-agent-gong-cheng-shi_shanghai_90M0149830_18305_CN/
