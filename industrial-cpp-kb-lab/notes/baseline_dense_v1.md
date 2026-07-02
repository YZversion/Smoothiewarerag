# Baseline Dense v1（48 题对照基准）

> 取代此前“无 dense、原 35 题 mean cov@5=96.4%”版本。  
> 数据来源：`notes/dense_experiment_data.json`（final@w_dense=20，2026-07-02）。

## 配置快照（影响检索结果的项）

| 配置项 | 值 |
|--------|-----|
| dense 通道 | **默认开启**，`w_dense=20` |
| dense 紧急禁用 | `KB_DISABLE_DENSE=1`（默认不设置） |
| dense 模型 | `BAAI/bge-m3`，1024 维，IndexFlatIP，top-50 |
| dense 融合 | 单路加性信号（`merge_scores` 内 `dense` 通道） |
| halt hint | `_hint_halt` 含 `急停/紧急停止`（已转正） |
| halt hint 诊断开关 | `KB_DISABLE_HALT_SYNONYMS=1`（仅实验，默认关闭） |
| rg 预筛文件数 | `RG_CANDIDATE_FILE_LIMIT=12` |
| reporank | 默认关闭（`ENABLE_REPORANK` 未设） |
| graph 扩展 | 默认 `search_graph()`（flow_intent 且非 multi-file 结构题） |
| diversify | 多文件结构题 `per_file=1`，其余 `per_file=2` |
| 封存题 eval 输出 | sealed 仅总分，明细需 `--unseal` |

## 48 题分桶数字（dense@20）

| 桶 | n | mean cov@5 | Recall@5（宽松口径） |
|----|---|------------|----------------------|
| 全体 | 48 | **82.5%** | 46/48 |
| 原 35 题 | 35 | **96.4%** | 35/35 |
| 新 13 题（H31–H43） | 13 | **45.1%** | 11/13 |
| 单文件题 | 27 | **100.0%** | 27/27 |
| 多文件题 | 21 | **60.0%** | 19/21 |
| vocab_mismatch 桶 | 9 | **46.3%** | 7/9 |
| 封存 5 题 | 5 | — | **4/5**（仅总分） |

### Q3/Q4/Q5（cov@5 + 归一化）

| ID | cov@5 | 理论上限 | cov@5/上限 |
|----|-------|----------|------------|
| Q3 | 83.3% | 83.3%（6/6） | 1.00 |
| Q4 | 57.1% | 71.4%（5/7） | 0.80 |
| Q5 | 83.3% | 83.3%（5/6） | 1.00 |

## 口径说明（防误读）

- **Recall@5**：每题“命中至少 1 个 expected file 即算 hit”的宽松口径，用于监测“完全失明率”。
- **工作指标始终是 cov@5**：`coverage@5 = |hit expected files| / |expected_files|`。
- 因此某题 Recall@5=PASS 但 cov@5 仍可能显著低于 100%（多文件题常见）。
- 封存题（`dev_split=sealed`）在默认 eval 输出中只展示 PASS/FAIL 总分，避免调参偷看。

## HINT_GROUPS 与 dense 的分工结论

依据 `notes/dense_experiment.md` 的 H3 专项：

| 配置 | H3 cov@5 | Kernel@5 |
|------|----------|----------|
| hint 急停 ON, w=0 | 100% | ✅ |
| hint 急停 OFF, w=0 | 50% | ❌ |
| hint 急停 OFF, w=20 | 50% | ❌ |

**结论**：

- **dense** 负责“功能性描述 → 符号/实现”的语义匹配（vocab_mismatch 桶 +29.6pp）。
- **HINT_GROUPS** 降级为领域黑话（如“急停”→ halt/Kernel）的精修补丁，不可替代 dense。
- Phase 7 策略：优先保留/扩展意图触发型 hint（短语与共现），避免回退到 per-question 文件名硬编码。

## 变更记录

- 2026-07-02：dense@20 人工裁决转正，建立本 baseline。
