# 学习型简历项目就绪审计（2026-09-21）

## 结论

代码与基础演示已达到学习型项目的技术展示条件；正式质量评测未通过，目前不能宣称 Agent 优于普通 RAG。由于项目所有者尚不能独立讲解项目，且本地改动没有整理到个人仓库与提交历史中，当前不建议直接写入并投递简历。

## 已验证通过

- Ruff 全量检查通过；`unittest discover -q` 为 213/213 通过。
- FastAPI `/health` 与 `/ready` 返回 HTTP 200；readiness 覆盖密钥配置、Embedding 契约、manifest 和三类索引文件。
- 正式数据集 52/52 人工审核通过，无 missing、rejected、stale 或 invalid approval。
- 同一 `deepseek-v4-pro-0813`、同一图版本的两题三路径演示产生 6 条无执行错误记录：有证据题三组答对，Agent 有有效引用；无证据题 direct 误答，naive RAG 与 Agent 拒答。原始 details SHA256 为 `a16959c3d7cdd5a3129e558f571c818917b2e50abcb300c2490867de7a33bf1b`。
- 评测入口记录数据集/模型/配置/成本/错误并支持预注册质量验证；直接脚本与 `python -m` 两种正式校验入口均可运行。

## 未通过或尚未完成

- 正式质量 verifier 返回 `passed=false`，共 15 项失败；其中 Agent `answer_hit=0.2718`、answerability accuracy `0.4660`、citation evidence recall `0.3215`、judge correctness `0.4107`，均低于预注册门槛。
- Agent 相对 naive RAG 没有任何主要指标达到预注册优势，`answer_hit` 与 judge correctness 出现显著退化。
- 多跳题 `hp1-038` 在 20 次模型请求、13,827 Token 后预算耗尽，没有形成答案。
- 已建立不含上游 Git 历史的发布副本，配置个人空仓库为 `origin`、原项目为 `upstream`，并保留 README attribution 与 Apache-2.0 License；尚未由所有者本人提交、推送或通过远端 CI，因此个人仓库归属门禁仍未完成。
- 项目所有者当前自述对项目了解接近 0，尚不能完成最低口述验收。

发布卫生复核中发现 `tmp/` 含个人简历渲染图片但原先未被忽略，现已加入 `.gitignore`，文件未删除；旧 `.env.example` 只有过时的 OpenAI/Groq 变量，现已替换为不含真实密钥的百炼最小配置模板。当前 `git ls-files` 未发现 `.env`、运行 Trace、评测结果或临时目录被跟踪；发布副本还修正了会使 `helper_functions.py` 在新根提交中漏交的忽略规则。本人提交前仍应再次执行密钥扫描和 staged diff 检查。

随后对当前已跟踪文件和未忽略的待提交文本执行只读模式扫描：未发现 `sk-` 风格的长密钥；两处通用 `api_key/secret` 赋值命中均为自动化测试中的显式假值（`configured-secret`、`key`、`sk-test-secret`），不是真实凭据。该结果只覆盖当前工作区的两类常见模式，不能替代推送前对实际 staged 内容使用专用 secret scanner。

## 简历使用边界

完成个人仓库整理和最小口述验收后，可以将其定位为“Agentic RAG 学习与评测项目”，描述多源检索、证据引用/拒答、预算控制、三路径评测和真实失败复盘。不得写准确率提升、Agent 优于 baseline、显著降低幻觉、生产级或从零原创。

在上述两项完成前，技术实现可以继续作为学习材料和本地演示，但不建议作为可经受面试追问的正式简历项目投递。

## 首次远端发布复核

个人仓库已由所有者本人创建根提交并推送，远端 `main` 与本地提交 `7d1cb7628d737315a31e137bcea796615cdec649` 一致，仓库不是 fork，当前 Git 历史只有所有者一名作者。首个 `Offline quality gates` 在 55 秒后失败，失败步骤为 `Verify prioritized interview queue`。根因是发布前更新了 `QUESTION_BANK.md` 的 A13 答案，但没有同步重生成派生文件 `STUDY_QUEUE.md`；这不是模型质量或运行逻辑故障。现已运行 `python evaluation/build_interview_queue.py`，162 道题的队列重新生成且本地 `--check` 通过。修复仍需所有者本人提交、推送并确认第二轮 CI 通过。

第二次提交 `5f34034e744b0de005b42a4a73fda7e98ec86261` 修复题库后，远端 CI 在 `Audit ingestion and index distributions` 失败。本地同一命令通过，进一步对比干净提交文件后确认：`.gitignore` 的 `*.ipynb` 把审计入口依赖的 `sophisticated_rag_agent_harry_potter.ipynb` 排除在 Git 历史外，而本地工作区仍有该文件，形成“本地通过、CI 缺文件”的环境漂移。现已为这一份 356 KiB 的上游 Notebook 增加精确反向规则；其余 Notebook 仍默认忽略。该修复需由所有者提交并以新一轮远端 CI 验证。
