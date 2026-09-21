# 现代 LangGraph 隔离迁移探针（2026-09-12）

## 目的与隔离方式

为了验证旧版 checkpoint 故障能否通过正式升级解决，而不破坏当时 151 项通过的
项目环境，先在系统临时目录创建独立 Python 3.11 venv。第一阶段探针未改仓库
requirements、主 venv 和业务代码；探针通过后才进行正式迁移。

隔离环境解析出的核心版本：

| 包 | 版本 |
|---|---:|
| langgraph | 1.2.11 |
| langgraph-checkpoint | 4.2.0 |
| langgraph-checkpoint-sqlite | 3.1.1 |
| langchain | 1.4.0 |
| langchain-core | 1.6.3 |
| langchain-community | 0.4.2 |
| langchain-openai | 1.6.2 |

## Checkpoint 结果

两节点图为 `START → a(+1) → b(+10) → END`，在 `a` 后 interrupt。

### 内存 saver

`InMemorySaver` 首次运行得到 `n=1`、下一节点为 `b`；以同一 thread ID 和空输入
恢复后只执行 `b`，最终 `n=11`。旧版的单调时间戳断言没有复现。

### SQLite 跨进程

第一个 Python 进程将 thread `cross-process` 暂停在 `n=1`、`next=('b',)` 并退出。
第二个 Python 进程重新打开同一 SQLite 文件，恢复前读取到相同状态，随后以空输入
继续并得到 `n=11`、`next=()`。数据库大小为 20,480 bytes。

这证明现代框架的目标机制在本机可行，但只覆盖最小图，不等于本项目已迁移。

## 项目兼容性探针

直接用现代环境导入 `controllable_rag.graph` 失败：

```text
ModuleNotFoundError: No module named 'langchain_core.pydantic_v1'
```

临时在进程内把该旧路径映射到 `pydantic.v1` 后继续探测，得到下一层断点：

```text
controllable_rag.chains: No module named 'langchain.prompts'
evaluation.run_chunking_ablation: No module named 'langchain.docstore'
```

全量 discovery 首次只运行到 65 项并出现 16 个 import errors，因此当时不能用最小
checkpoint 成功宣称项目兼容。

随后将 PromptTemplate、Document、TextSplitter 切换到稳定 core/拆分包入口，并为
schema 增加新旧 Pydantic 导入。修复后旧环境与现代隔离环境当时的 151 项测试都
通过，完整主图可编译；现代环境真实 `qwen3.8-max` 返回 `OK.`（19 Token），
`text-embedding-v4` 返回 1536 维、L2 范数平方 1.0，且不再产生 `extra_body` 警告。
交付依赖随后正式切换到现代组合并新增依赖门禁，当前共 152 项测试。

干净隔离环境执行 `pip check` 返回 `No broken requirements found`。随后把同一组依赖
安装进长期使用的主 venv 时，安装本身成功，但 `pip check` 发现该环境此前遗留的
`langchain-groq`、`googleapis-common-protos`、`opentelemetry-proto` 与新版本 core /
protobuf 冲突。它们不在精简交付清单中，因此没有擅自卸载；这不是干净交付环境的
失败，也不能表述为“主 venv 无冲突”。复现和 CI 应从全新 venv / 镜像开始。

## 迁移顺序

1. 将 schema 从 LangChain 的 Pydantic v1 shim 迁到 Pydantic v2，并验证结构化输出；
2. 将 PromptTemplate、Document、text splitter 等旧入口迁到现代 core/拆分包；
3. 适配 `START`、StateGraph compile/stream 与新的 checkpoint 配置；
4. 将 SQLite saver 作为显式依赖，默认关闭持久化；
5. 恢复时从 checkpoint 延续累计调用与 Token 预算；
6. 验证敏感 State 落盘、retention、thread 隔离、并发和副作用幂等；
7. 全量离线测试、真实 Qwen 冒烟和跨进程恢复全部通过后才更新能力声明。

## 失败记录

第一次创建隔离 venv 时使用 `py -3.11`，Windows launcher 只登记 3.9/3.13，创建
失败；改用项目 venv 内实际存在的 Python 3.11.15 后成功。这说明可执行文件真实
路径比 launcher 别名更可靠，也应写入迁移脚本。
