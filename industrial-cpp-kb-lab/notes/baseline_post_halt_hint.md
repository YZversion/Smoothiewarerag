# Baseline 记录 — halt hint 转正后（2026-06-25）

转正后跑 `python src/03_search.py --eval`（35 题，扩题前口径）：

| 指标 | 值 |
|------|-----|
| 全体 mean cov@5 | **96.4%** |
| holdout mean | 98.3% |
| holdout single-file | 100% |
| H3 | 100%（原 50%） |
| H8 | 50%（未变） |
| gate_ok | True |

与 `notes/kernel_fix_validation.md` 中 **hint_only** 配置一致。

扩题后全 48 题见 `notes/eval_expansion_report.md`。
