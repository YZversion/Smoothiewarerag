# Dense retrieval 实验报告

## 模型与索引

- **模型**: `BAAI/bge-m3`
- **维度**: 1024
- **License**: MIT（BGE 系列，见 HuggingFace model card）
- **索引**: FAISS `IndexFlatIP`（L2-normalized 向量，内积=余弦）
- **chunk 数**: 1569
- **嵌入格式**:
  ```
  file: {path}
  class: {class}
  symbol: {symbol}
  type: {chunk_type}

  {chunk code text}
  ```

## 权重扫描（tune 组，n=13）

| w_dense | tune mean cov@5 | vocab_mismatch mean |
|---------|-----------------|---------------------|
| 0 | 45.7% | 12.5% |
| 5 | 57.2% | 37.5% |
| 10 | 57.2% | 37.5% |
| 15 | 57.2% | 37.5% |
| 20 | 61.1% | 50.0% |
| 25 | 57.2% | 37.5% |

**选定权重**: `w_dense=20`（tune mean cov@5 最高）

## 全量 48 题 vs baseline（w_dense=0）

| 指标 | baseline | dense@best | Δ |
|------|----------|------------|---|
| 全体 mean cov@5 | 75.9% | 82.5% | 6.6% |
| 原 35 题 mean | 96.4% | 96.4% | 0.0% |
| vocab_mismatch 桶 | 16.7% (n=9) | 46.3% | 29.6% |
| 单文件 holdout | 27/27 | 27/27 | 无回归 |
| **封存 5 题 Recall@5** | 2/5 | 4/5 | +2 |

### Q3/Q4/Q5 cov@5 与归一化值

| ID | cov@5 | 理论上限 | cov@5/上限 |
|----|-------|----------|-------------|
| Q3 | 83.3% | 100.0% | 0.83 |
| Q4 | 57.1% | 71.4% | 0.80 |
| Q5 | 83.3% | 83.3% | 1.00 |

## 耗时（mean per query）

- baseline（无 dense）: 99.09 ms
- dense@best 总查询: 118.31 ms
- dense 通道（embed+检索）: 18.02 ms

## H3 专项：关闭「急停」hint，裸靠 dense

- w_dense=0, hint 急停 ON: cov@5=100.0%, Kernel@5=True
- w_dense=0, hint 急停 OFF: cov@5=50.0%, Kernel@5=False
- w_dense=20, hint 急停 OFF: cov@5=50.0%, Kernel@5=False

top@5 (hint OFF, w=20): `['src/modules/utils/killbutton/KillButton.cpp', 'src/modules/utils/panel/Button.cpp', 'src/modules/utils/killbutton/KillButton.h', 'src/modules/utils/panel/Button.h', 'src/modules/utils/killbutton/KillButton.cpp', 'src/modules/utils/panel/Panel.h', 'src/main.cpp', 'src/libs/Module.h']`

## 退出条件判定

**未触发失败退出条件**（需人工决定是否转正）。

## 转正状态

- **人工裁决**：已通过全部三条退出红线，dense@20 于 2026-07-02 转正。
- 配置与 baseline：见 `notes/baseline_dense_v1.md`。
- 合规留档：见 `notes/model_provenance.md`。