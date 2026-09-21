# Provider 熔断器契约（2026-09-13）

## 目标与范围

保护持续故障的千问兼容端点，避免每个新请求都经历 SDK 重试和完整等待。Chat 与
Embedding 分开熔断；相同 base URL、模型和调用类型的客户端在单进程内共享状态。

## 状态机

- Closed：正常放行；一次成功清零连续故障。
- Open：瞬时失败达到阈值后，在冷却期内 fail fast，不调用 provider。
- Half-open：冷却后仅放行一个探测；成功回到 closed，瞬时失败重新 open。

只有网络连接、timeout、408/409/425/429 和 5xx 被计为可用性故障。400、鉴权、输入
契约和本地解析问题不会打开共享熔断，否则一个坏请求可能阻断所有正常用户。

## 与预算、重试和 fallback 的顺序

模型 SDK 先完成其有限重试，最终仍为瞬时错误时，本次逻辑调用才给熔断器记一次失败。
熔断包装位于 `BudgetedChatModel` 外层，因此 open 状态拒绝发生在请求槽与 Token 预留
之前。熔断不是重试，也不会自动切换模型；未经同数据集评测的 fallback 可能改变质量、
上下文窗口、结构化输出和成本，当前不静默启用。

## 自动化证据

`tests/test_resilience.py` 验证：

1. 瞬时网络/503 与永久 400 分类不同；
2. threshold=1 后第二次调用被 open circuit 拒绝，provider 总调用一次，预算也只计一次；
3. 可控时钟推进冷却期后，half-open 成功并恢复 closed；
4. 连续永久错误不会打开 circuit。

节点观测包装器会保留 `CircuitOpenError`，并只附加 node、duration、`circuit_state`
和 `retry_after_seconds`。Trace schema `2026-09-13.1` 对这些字段做白名单投影；测试确认
provider URL 等未授权字段不会落盘。因此失败报告能区分熔断拒绝，同时不保存请求内容、
端点或模型输入。

完成离线回归后，又通过熔断包装后的真实客户端做最小冒烟：`qwen3.8-max` 返回
`OK.`，17 input + 2 output = 19 Token；`text-embedding-v4` 返回 1536 维向量，
两条路径均无 warning。这只证明包装接口兼容，不是熔断故障注入或可用率指标。

## 未完成项

当前熔断状态只在单 Python 进程中共享，进程重启会清零，多副本也不会互相感知。生产
部署还需 Redis 等共享状态、指标告警、随机抖动、按租户隔离以及经过正式质量/成本
评测的 fallback 策略。离线状态机测试不等于真实故障注入或远端 SLA 证明。
