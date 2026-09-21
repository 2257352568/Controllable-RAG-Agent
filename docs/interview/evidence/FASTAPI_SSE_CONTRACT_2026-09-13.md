# FastAPI / SSE 接口契约验证（2026-09-13）

## 范围

- `GET /health`：只验证进程存活，不创建 Agent、不调用模型、不读取向量索引。
- `GET /ready`：检查密钥、Embedding模型/维度清单契约，以及所有启用索引的大小与
  SHA256；不构造Agent、不调用供应商、不反序列化pickle，缺失/不匹配返回503且不泄露路径、哈希或密钥。
- `POST /v1/query`：返回一次执行的最终答案、确定性白名单引用、用量和 request ID。
- `POST /v1/query/stream`：按序输出 `started`、零到多个 `progress`、最终
  `completed` 或 `error`。

公共事件没有直接序列化 LangGraph State。进度只包含节点、步数、检索次数、Chat /
Embedding 调用数、Token 和累计耗时；最终引用只保留 ID、来源、排名、页码和章节。
问题、计划、检索原文、聚合上下文、grounding explanation、额外 metadata 与底层异常
正文均不返回。

每个已准入请求由服务端生成规范 UUID，同一值进入 `X-Request-ID`、响应中的
`request_id`/`trace_id`、SSE started/completed/error 与 LangGraph 初始 State；客户端
不能在严格请求 schema 中提交 `trace_id`。因此开启本地 Trace 时，前端错误号可直接
映射到 `<trace_id>.json`，无需记录问题或答案。

## 验证

```powershell
venv\Scripts\python.exe -m unittest tests.test_api -v
```

结果：13/13 API 测试通过，另有Settings/交付配置测试；覆盖服务端关联ID、防客户端覆盖、liveness/readiness、索引篡改与Embedding契约失配、Agent线程安全懒
单例、Settings 默认值继承、严格输入、同步结果白名单、同步异常脱敏、SSE 顺序与字段
白名单、SSE 终态异常脱敏，以及容量满载时立即 429、请求完成后恢复。SSE 使用响应
background cleanup，在正常结束或连接关闭时释放进程内槽位。

真实 HTTP liveness 使用 Uvicorn 启动后请求 `/health`，返回 HTTP 200、
`application/json` 和 `{"status":"ok"}`。全新 Python 3.11 临时 venv 从
`requirements-runtime.txt` 安装后，`pip check` 返回 `No broken requirements found`，
且可导入 API app。临时环境验证后已删除。

长期使用的开发 `venv` 曾因遗留 `langchain-groq`、旧 OpenTelemetry 与 protobuf 版本
产生 `pip check` 冲突，因此没有拿该环境证明依赖闭包；干净环境才是本次交付证据。
第一次尝试用 Windows `py -3.11` 创建环境还发现 launcher 只注册了 3.9/3.13，随后
改用当前已核实为 Python 3.11.15 的项目解释器创建隔离环境。这个故障说明解释器路径
本身也应进入可复现环境检查。

## 声明边界

这是同步 Agent 的节点级事件流，不是模型 Token 流。事件 ID 只在当前连接内递增；没有
持久任务存储，因此尚不支持 `Last-Event-ID` 断线续传、跨进程取消、队列排队、背压或
多副本共享状态。客户端断开也不保证能杀死已经进入供应商 SDK 的同步请求。

`RAG_API_MAX_CONCURRENT_REQUESTS` 控制单进程同时在途的 Agent 请求，默认 8；达到上限
返回 429、`Retry-After: 1` 和安全错误码 `server_overloaded`。它不是按用户或租户的
时间窗口限流，也不是流式消费者背压；多 worker 部署还需要 Redis/网关等共享准入层。

本机当前文件重新校验：`api_key`、manifest、Embedding契约与
`chunks/summaries/quotes`均为`ready`。manifest的六个文件哈希与既有摄取审计一致。
该结果不代表百炼在线，也不读取FAISS内部维度或验证语义质量；manifest和索引同仓库，
能检测意外漂移但不是受密钥保护的签名。
