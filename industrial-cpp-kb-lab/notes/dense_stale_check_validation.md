# Dense 索引过期检测验证

> 目的：验证“chunk 集合与 dense 索引版本不匹配时，检索启动会显式报错”，而非静默使用过期索引。

## 实现位置

- `src/search/dense_index.py`
  - `chunks_fingerprint()`：对 `chunks.jsonl` 做 SHA256（前 16 hex）
  - `verify_compatibility()`：比对 manifest 与当前 chunks 指纹
  - manifest 必填字段：`model`, `dim`, `chunk_count`, `chunks_fingerprint`, `built_at_utc`
- `src/search/index.py`
  - `load_dense_index()` 在加载 FAISS 后调用 `verify_compatibility()`
  - 不匹配时抛 `KBIndexError`，提示重建：`python scripts/build_dense_index.py`

## 实测步骤（2026-07-02）

1. 读取当前 manifest 指纹：`ab144e1b8e428ad3`
2. 备份 `data/chunks.jsonl` → `data/chunks.jsonl.bak_stale_test`
3. 向 `chunks.jsonl` 末尾追加一个空格（不改业务 chunk 内容语义，仅改变文件哈希）
4. 执行 `SearchIndex().load_index()`（默认 dense 开启）
5. 观察报错并立即还原 `chunks.jsonl`

## 实测结果

触发异常（符合预期）：

```text
KBIndexError
dense index stale/incompatible; rebuild required. chunks fingerprint mismatch: index=ab144e1b8e428ad3 chunks=5addd7bbd5eccb8c. Run: python scripts/build_dense_index.py
```

还原后再次 `load_index()` 可正常加载。

## 结论

- “实现了检测” ✅
- “验证过检测会触发” ✅（本文件即为证据）
