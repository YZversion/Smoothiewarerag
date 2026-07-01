# Notes Index

`notes/` 存放历史实验、诊断和验收证据。这里的文件原则上保留原始结论，不为了整洁重写历史数据。

## 当前仍常用

| 文件 | 用途 |
|---|---|
| [`smoothieware_code_map.md`](smoothieware_code_map.md) | Smoothieware 代码地图和核心模块入口 |
| [`kb_acceptance.md`](kb_acceptance.md) | Smoothieware MVP 验收清单 |
| [`eval_failures.md`](eval_failures.md) | eval 失败案例和修复模式 |
| [`phase10_conclusion.md`](phase10_conclusion.md) | Phase 10 LLM 完整性与 Q3-Q5 检索补齐结论 |
| [`q345_retrieval_diagnosis.md`](q345_retrieval_diagnosis.md) | Q3-Q5 四层检索诊断 |

## Phase 结论与 A/B 实验

| 文件 | 用途 |
|---|---|
| [`phase6_conclusion.md`](phase6_conclusion.md) | 检索层与 LLM 层分离评估 |
| [`phase8_symbol_dispatch_audit.md`](phase8_symbol_dispatch_audit.md) | AST-aware 符号入口和 dispatch index 审计 |
| [`phase9_ab_report.md`](phase9_ab_report.md) | Repomap PageRank A/B，默认关闭依据 |
| [`comparison.md`](comparison.md) | rg/BM25 vs CodeGraph A/B 结论 |

## 历史对照

| 文件 | 用途 |
|---|---|
| [`smoothieware_rg_findings.md`](smoothieware_rg_findings.md) | 早期 rg/BM25 探索记录 |
| [`smoothieware_codegraph_findings.md`](smoothieware_codegraph_findings.md) | CodeGraph 探索记录 |
| [`eval_hint_triggers_baseline.md`](eval_hint_triggers_baseline.md) | hint 修复前基线 |
| [`eval_hint_triggers_after.md`](eval_hint_triggers_after.md) | hint 修复后对照 |

## 维护规则

- 新的执行型计划放到 `../docs/`，不要放在 `notes/`。
- 新的自动生成报告放到 `../reports/`。
- `notes/` 只放人工诊断、实验结论和历史证据。
