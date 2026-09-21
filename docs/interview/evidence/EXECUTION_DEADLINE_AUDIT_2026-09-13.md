# 执行 Deadline 与取消语义审计（2026-09-13）

## 结论

项目实现的是累计执行 deadline，不宣称能强制终止同步 Python 节点。deadline 在每次
聊天模型逻辑调用前拒绝新请求，并在节点返回后阻止进入下一节点；单次已发 HTTP 请求
仍由模型客户端的 `QWEN_TIMEOUT_SECONDS` 限制。

## 为什么不直接宣称 LangGraph step timeout

本机使用 LangGraph 1.2.11 做最小阻塞探针：节点 `sleep(0.2)`，设置
`compiled_graph.step_timeout = 0.05`。同步 `stream` 在约 0.204 秒后才抛出
`TimeoutError`，而不是约 0.05 秒返回。这说明该路径至少在此同步阻塞场景不能作为
抢占式取消证据。线程池 future timeout 同样不能安全杀死已经运行的 Python 线程，
后台请求可能继续消费资源。

## 当前契约

- `AGENT_MAX_ELAPSED_SECONDS` 默认 120 秒，必须为正数。
- `BudgetLedger` 用单调时钟累计耗时；checkpoint 保存 `elapsed_seconds`，恢复后不清零。
- 模型调用前 deadline 已耗尽时抛出机器可读
  `execution_deadline_exhausted`，provider 调用次数保持为 0。
- 非模型慢节点返回后，在节点边界产生相同终止原因和 deadline 诊断。
- deadline、请求次数和 Token 是三个独立限制，先命中的控制原因被记录。

## 自动化证据与限制

`tests/test_runtime_budget.py` 使用可控时钟证明超时后的模型调用在 provider 前被拒绝，
另用阻塞假节点证明节点返回后的边界停止。它没有证明在途 HTTP 能被取消，也没有覆盖
操作系统进程隔离。若业务要求硬终止，应把不可控工作放入可撤销进程/任务队列，并用
幂等键处理超时与迟到结果，而不是依赖 Python 线程强杀。
