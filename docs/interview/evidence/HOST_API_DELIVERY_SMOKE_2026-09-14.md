# 宿主机 API 交付冒烟（2026-09-14）

## 目的

验证当前工作树能否使用项目虚拟环境真实启动 FastAPI，并区分宿主机运行证据与尚未完成的
Docker 构建证据。检查过程不发送问题、不调用 Qwen Chat 或 Embedding。

## 固定环境

- Python：3.11.15
- FastAPI：0.141.1
- Uvicorn：0.41.0
- 索引清单 SHA256：`7ab947295e6febdcae8ff3e9c43fa58bd84849540abdcbe7b031bb7c30b41eaa`
- 监听地址：`127.0.0.1:8765`

## 命令

```powershell
venv\Scripts\python.exe -m uvicorn controllable_rag.api:app `
  --host 127.0.0.1 --port 8765

Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/ready
```

## 结果

| 检查 | HTTP | 安全摘要 |
|---|---:|---|
| `/health` | 200 | `status=ok` |
| `/ready` | 200 | 密钥存在、manifest 与 Embedding 契约一致、chunks/summaries/quotes 文件完整 |

`/ready` 返回的 scope 为 `local_prerequisites_only`。它不构造 Agent、不反序列化 pickle、
不调用供应商，因此不能证明百炼在线、模型可用或检索语义正确。服务在验证后通过 Ctrl+C
完成正常 application shutdown。

## Docker 检查

执行 `docker version` 时 PowerShell 报告 `docker` 不是可识别的命令。由此只能得出本机没有
可调用的 Docker CLI，不能得出 Dockerfile 构建成功或失败。镜像构建与容器 healthcheck
继续保持为未完成发布门禁；已有静态测试不能替代真实构建。

## 面试可陈述边界

- 可以说：当前工作树在宿主项目 venv 中成功启动，liveness/readiness 均真实返回 200。
- 不可以说：Docker 镜像已经构建通过、百炼服务已被健康检查验证、系统已达到生产可用。

