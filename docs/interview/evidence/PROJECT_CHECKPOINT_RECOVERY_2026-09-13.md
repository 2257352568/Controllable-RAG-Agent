# 主图 Checkpoint 与累计预算恢复审计（2026-09-13）

## 目标

验证的不是“图能带 checkpointer 编译”，而是本项目主图的持久化、线程隔离、恢复
预算连续性和删除行为。全部测试离线运行，不调用模型平台。

## 实现契约

- `create_agent(checkpointer=...)` 显式注入 saver；默认 `None`，不会隐式落盘。
- 调用方必须在 `config.configurable.thread_id` 中提供稳定线程标识。
- 每个主图节点结束时，把活动 `BudgetLedger` 的累计请求数、Token 和诊断写回 State，
  使其进入 checkpoint。
- `invoke(None, config=...)` 从已有 checkpoint 恢复；不存在的线程 fail closed。
- `open_sqlite_agent(...)` 管理连接生命周期，`delete_thread(...)` 删除指定线程。
- LangGraph 1.x 的 `__interrupt__` 是控制元事件，不被误当作业务 State。

## 自动化证据

`tests/test_checkpointing.py` 覆盖八项：

1. 主图在 `initialize` 后中断，关闭并重新打开 SQLite，原线程仍停在
   `anonymize_question` 前；另一个 thread ID 没有任何 State。
2. 一个两节点受预算图在首节点调用模型一次并 checkpoint；恢复后第二节点尝试调用，
   因累计请求上限为 1 而在 provider 前停止，provider 总调用次数仍为 1。
3. 独立用例把请求上限放宽、Token 上限设为 540；首节点实际结算 10 Token，恢复后
   第二次保守预留会累计超限并在 provider 前停止，总调用次数仍为 1。
4. 用不存在的 thread ID 恢复会返回明确错误，不会从空状态误启动。
5. 指定线程删除后，其 checkpoint State 为空，SQLite 文件生命周期正常结束。
6. 同一个 SQLite saver 由 8 个 worker 并发执行 32 个不同 thread；每个 marker 都只在
   对应 thread 中恢复，无异常或串线。
7. 用 barrier 强制同一 thread 的两个请求重叠；第二个请求以
   `ConcurrentThreadExecutionError` 立即拒绝，第一个正常结束。
8. 首节点完成一次 query embedding 后暂停；恢复执行第二节点时，累计 Embedding
   request 上限在 provider 前拒绝，实际 provider 仍只收到第一次输入。

原生同 thread 探针曾让 16 个请求全部各自返回，但最终 State 只保留最后写入的 marker，
即 last-write-wins。当前 single-flight 只覆盖共享 `BoundedAgent` 实例所在进程；多实例、
多进程或多副本部署仍需 Redis/数据库租约锁，或带 checkpoint version 的乐观并发控制。

## 隐私与未完成项

测试有意确认 SQLite 能恢复输入问题。这意味着完整 State 中的问题、匿名化映射、
检索上下文和候选答案都可能成为静态敏感数据；它与仅保存白名单字段的 Trace 不是
同一种存储。当前措施只有默认关闭、运行目录不入 Git、调用方显式开启和按线程删除。

因此当前不能宣称生产级持久化。尚需静态加密、访问控制、TTL/定期清理、并发压力、
跨服务 thread 身份授权，以及对未来写 ERP/数据库等副作用节点的幂等键与重放测试。
