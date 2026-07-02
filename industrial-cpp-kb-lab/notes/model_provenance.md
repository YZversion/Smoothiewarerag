# 模型合规留档（Phase 7 内网离线部署）

> 本文件记录检索/生成链路所用模型的来源、许可与本地落盘信息，供合规审查使用。

## BAAI/bge-m3（dense 检索，已转正）

| 项 | 值 |
|----|-----|
| 用途 | chunk 语义检索（FAISS IndexFlatIP） |
| 来源 URL | https://huggingface.co/BAAI/bge-m3 |
| License | MIT |
| 模型 revision（HF `sha`） | `5617a9f61b028005a4858fdac845db406aefb181` |
| 维度 | 1024 |
| 本地缓存路径 | `C:\Users\14390\.cache\huggingface\hub\models--BAAI--bge-m3` |
| 本地缓存大小 | 约 4.56 GB（含 blobs + snapshots） |
| 当前 snapshot 大小 | 约 2.29 GB（11 files） |
| 索引产物路径 | `industrial-cpp-kb-lab/data/dense_index/` |
| 索引产物大小 | `index.faiss` 6.43 MB；`chunk_ids.json` 85 KB；`manifest.json` 387 B |
| 构建时间戳 | 见 `data/dense_index/manifest.json` 的 `built_at_utc` |

**合规说明**：该 embedding 模型将随 Phase 7 进入公司内网离线部署；上线前需将 HF 缓存或等价离线包一并迁移，并保留本记录中的 revision 与 License 信息。

## Qwen/Qwen3-32B（vLLM 推理，生成层）

| 项 | 值 |
|----|-----|
| 用途 | 代码问答生成（OpenAI 兼容 API，经 vLLM 部署） |
| 来源 URL | https://huggingface.co/Qwen/Qwen3-32B |
| License | Apache-2.0 |
| 模型 revision（HF `sha`） | `9216db5781bf21249d130ec9da846c4624c16137` |
| 参数量 | 32.8B（HF 元数据：32,762,123,264 params） |
| 官方仓库体积（HF `usedStorage`） | 约 65.5 GB |
| 推荐部署命令 | `vllm serve Qwen/Qwen3-32B --enable-reasoning --reasoning-parser deepseek_r1` |
| 本机当前缓存 | **未下载**（`models--Qwen--Qwen3-32B` 不存在于本机 HF cache） |
| 运行时接入方式 | `LLM_PROVIDER` + `LLM_BASE_URL`（OpenAI 兼容）+ `LLM_MODEL=Qwen/Qwen3-32B` |

**合规说明**：Qwen3 32B 计划作为 Phase 7 内网 vLLM 服务模型；离线部署时需按上述 revision 拉取/镜像完整权重，并保留 Apache-2.0 License 文件（模型仓库内 `LICENSE`）。

## 记录维护

- dense 实验依据：`notes/dense_experiment.md`
- dense 转正依据：`notes/CHANGELOG.md`（2026-07-02）
- baseline 对照：`notes/baseline_dense_v1.md`
