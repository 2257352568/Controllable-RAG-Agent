# LangGraph checkpoint 兼容性审计（2026-09-12）

> 历史故障记录：交付依赖随后已迁移到 LangGraph 1.2.11。旧版失败仍保留用于说明
> 升级原因；后续主图接线与恢复语义验证见
> `PROJECT_CHECKPOINT_RECOVERY_2026-09-13.md`。

## 结论

当前依赖 `langgraph==0.0.49` 不能在本机可靠启用 checkpoint。两节点最小图分别
使用 `MemorySaver` 与 `SqliteSaver(:memory:)`，都能 compile，但都在第一次
`stream`、业务节点执行前触发：

```text
AssertionError: Timestamps must be monotonically increasing,
got <timestamp> <= <same timestamp>
```

因此项目保持 checkpoint 关闭并继续把它列为发布缺口。没有通过 sleep、修改
site-packages 或 monkey patch 绕过，因为这不能证明跨进程恢复与生产可靠性。

## 环境与交叉验证

- Python：项目 Python 3.11 venv
- LangGraph：`0.0.49`
- langchain-core：`0.1.53`
- Saver 1：`MemorySaver()`
- Saver 2：`SqliteSaver.from_conn_string(":memory:")`
- 图：`a → b → END`
- 配置：`{"configurable": {"thread_id": "t1"}}`
- interrupt：`interrupt_after=["a"]`

两个 saver 命中完全相同的断言，说明故障发生在 saver 写入之前的通用 checkpoint
创建路径。检查已安装源码发现 `create_checkpoint` 连续读取 ISO 时间，并强制新值
严格大于旧值；本次运行两次取值相同。这里只记录可观察根因，不把具体操作系统
时钟粒度当作已证明结论。

## 为什么不直接升级后提交

截至审计日，PyPI 的当前 LangGraph 为 `1.2.11`，而项目停留在 `0.0.49`，跨越
多个主版本。`pip --dry-run` 显示新版本要求 `langchain-core>=1.4.7`，当前环境是
`0.1.53`，还会引入拆分的 checkpoint/prebuilt/sdk 包。它不是一个可以只改版本号
的补丁升级。

- [LangGraph PyPI](https://pypi.org/project/langgraph/)
- [LangGraph persistence 官方文档](https://docs.langchain.com/oss/python/langgraph/persistence)

官方文档确认 checkpoint 按 `thread_id` 组织并用于状态恢复；这只是目标语义，
不能替代本仓库的运行证据。

## 迁移验收门槛

1. 现有主图、三个检索子图、回答子图和全部回归测试通过；
2. interrupt 后从正确下一节点恢复，而非重跑已完成节点；
3. 关闭进程、重新打开 SQLite 后仍可恢复；
4. 不同 thread ID 状态隔离，并发写入有明确事务策略；
5. checkpoint 会保存完整问题、上下文与答案，必须默认关闭、目录忽略、权限和
   retention 明确，不能拿脱敏 trace 的安全结论套用到 checkpoint；
6. 恢复时累计模型调用和 Token 消耗延续，不能重新获得完整预算；
7. 外部副作用节点必须以 idempotency key 或 outbox 防止重放。

## 面试表达

“我没有把 `compile(checkpointer=...)` 当作功能完成。最小恢复实验在旧版 LangGraph
上复现了通用时间戳断言，Memory 和 SQLite 都失败。我没有在框架内部加 sleep
掩盖它，因为升级还涉及状态 API、敏感数据落盘和恢复后预算累计。于是先保留失败
证据和迁移验收表，checkpoint 仍明确标成 release blocker。”
