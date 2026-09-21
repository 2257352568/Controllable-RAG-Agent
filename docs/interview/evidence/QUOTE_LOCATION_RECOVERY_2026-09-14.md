# Quotes 引用位置恢复证据（2026-09-14）

## 问题与约束

上游 `book_quotes_vectorstore` 的 1,299 条 `Document` 均无位置 metadata，引用只能显示
`location unavailable`。仓库不包含原始 PDF，因此不能按列表顺序猜页码，也不能调用模型
生成位置。本次只使用仓库控制的 chunks/quotes pickle；反序列化必须显式传入
`--trust-local-index`。

## 方法

1. 按页分组 618 个 chunks，并用相邻文本的最长精确 suffix-prefix overlap 重建 219 页。
2. 将 page 与 quote 的空白规范化后做全文精确包含匹配，不使用模糊阈值。
3. 唯一命中才写 `page`；多页命中只写 `location_candidates`；零命中使命令非零退出。
4. quote pickle 通过同目录临时文件和 `os.replace` 更新，再刷新 `index_manifest.json`。
5. 唯一页渲染为 page；歧义项保持 `quotes-doc-*` ID，Sources 和 API 返回候选页并标明 ambiguous。
6. 再次完整运行，确认输出 pickle 与 manifest 哈希不再变化。

执行命令：

```powershell
venv\Scripts\python.exe evaluation\repair_quote_locations.py `
  --trust-local-index --write `
  --output docs\interview\evidence\QUOTE_LOCATION_RECOVERY_2026-09-14.json
venv\Scripts\python.exe evaluation\repair_quote_locations.py `
  --trust-local-index --write `
  --output docs\interview\evidence\QUOTE_LOCATION_RECOVERY_STABILITY_2026-09-14.json
venv\Scripts\python.exe evaluation\audit_ingestion.py `
  --trust-local-index `
  --output docs\interview\evidence\INGESTION_AUDIT_2026-09-14.json
```

## 结果

- 唯一页码：1,298/1,299，覆盖率 `0.999230`（99.923%）。
- 歧义：1 条，quote index 1041，同时精确命中第 43、186 页；没有写入虚假单一页码。
- 缺失：0；非法 metadata：0；摄取审计 `valid=true`。
- 首次输入 quote pickle SHA256：`772fe5e8ae705ed2a5520a6bdc763cf8a667427c55fce7e8f6d0374f908d7103`。
- 稳定后的 quote pickle SHA256：`5ef903db2cbc0d25783a812b5ab2c09e1c925f393835a776e354834a1775769c`。
- quote FAISS SHA256 始终为 `5a5c43eb688ca2e0b79fb7673bcffda8880e58daedecc7bc272044563afc2682`，未重新 embedding。
- 最终 manifest SHA256：`7ab947295e6febdcae8ff3e9c43fa58bd84849540abdcbe7b031bb7c30b41eaa`。

第一次写入后重新加载旧 LangChain/Pydantic pickle 时，新版运行时对内部模型状态做了一次规范化，
导致 pickle SHA 从 `03ef...` 变为 `5ef9...`；随后两次完整写入均保持 `5ef9...`，不是向量或
业务 metadata 漂移。原始首次输出和稳定性输出分别保留在同目录两个 JSON 文件中。

## 代码证据与边界

- `evaluation/repair_quote_locations.py` SHA256：`6137275c1479817fb5669392eba219047b0109aa39d4cd25cdb790a84b1df228`
- `evaluation/audit_ingestion.py` SHA256：`7876e3d5beeb566778cc5d089e2fc04bc50ea92c652d8e19e2c3b1581bd82dcd`
- `evaluation/test_quote_locations.py` SHA256：`386b7ed9edbf7819b4adf995472b198f4766b9b62a707ad32a1823bf24d33b05`
- `controllable_rag/citations.py` SHA256：`4924475229c9b72f24755ef6676900fd73fb25fe53349782aa674b949b965874`
- `controllable_rag/api.py` SHA256：`22cb94367bf892e13cc99f7759e85b3fc38f18fc78317a7dab8dfd2af6db508b`
- `tests/test_citations.py` SHA256：`2cebc6e6335418bf070f433fb634538ff00fcbf341c352a8b3ba7850a63c34a0`
- `tests/test_api.py` SHA256：`92d9bf04b61650be0750769edf64787bf6d7b1a1d10b674cea2edcb1bc4b0200`

这证明当前 quote 位置能够按确定性规则回查，并且歧义不会被伪装成确定位置；不证明 quote
检索相关性、claim 的语义支持或正式 Agent 质量。后者仍必须由 50 条人工集和正式协议验证。
