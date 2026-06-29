# Phase 10 — LLM 答案完整性（2026-06-25）

## 实现摘要

- `04_answer.py`：`context_primary_files`、`validate_answer_coverage`、`citation_in_hits` 支持 `symbol_start` 引用
- `build_prompt()` 注入 `{{primary_checklist}}` / `{{primary_count}}`
- [code_qa.md](../prompts/code_qa.md)：必须覆盖清单 + 自检段
- `eval_answer_layer.py`：`ctx_primary` / `expected` / `cite`；`--json` / `-o` / `--split` / `--resume` / `--ids`
- `scripts/diagnose_retrieval.py`：四层检索缺口诊断（raw@K → bundle → trim）
- `run_regression.py`：[4/4] coverage 报告（非阻断）

## Q3–Q5 检索修复（2026-06-29）

见 [q345_retrieval_diagnosis.md](q345_retrieval_diagnosis.md)。

| 改动 | 目的 |
|------|------|
| `halt` / `module` hint 扩展 | Q4 通信链、Q5 main/头文件 |
| `multi_file_structure_query` → `per_file=1` | Q3 Robot 等多文件挤占 |
| 跳过 structure 题的 call_graph extras | Q5 噪声（Robot/GcodeDispatch） |
| `expand_bundle` 两阶段 + primary 升级 | Module.h/Kernel.h 不被 header 去重吃掉 |
| `citation_in_hits` 接受 `symbol_start` | H26/H30 引用校验 |

修复后 bundle@8：Q3 **6/6**、Q4 **7/7**、Q5 **6/6**；35 题 mean cov@5 **94%** PASS。

## LLM eval

### tune 5 题（修复后，`notes/phase10_tune_after_fix.json`）

| ID | cite | ctx_primary | expected |
|----|------|-------------|----------|
| Q1 | OK | 5/5 | 3/3 |
| Q2 | OK | 5/5 | 5/5 |
| Q3 | OK | 8/8 | **6/6** |
| Q4 | OK | 8/8 | **7/7** |
| Q5 | OK | 7/8 | **6/6** |

- **Citation tune**: 5/5 ✅
- **expected 全列**: **5/5** ✅（检索补齐后 LLM 跟满）
- **ctx_primary**: 4/5 全列；mean ratio **98%**

### 全量 35 题（修复前 baseline，`notes/phase10_after.json`）

| 指标 | phase6 | phase10 全量（修复前） | 修复后 tune |
|------|--------|------------------------|-------------|
| Citation OK | 100% | 33/35 (94%) | tune 5/5 |
| All expected | 40% | 83% | **100%** (5/5) |
| H26/H30 cite | — | WARN | **OK**（symbol_start 校验） |

## 验收状态

| 项 | 状态 |
|----|------|
| 代码与度量管线 | **完成** |
| tune citation 5/5 | **通过** |
| 全体 expected ≥55% | **通过**（修复前全量 83%） |
| tune expected ≥4/5 | **通过**（5/5） |
| H26/H30 citation | **通过** |
| 两阶段 LLM | **不需要**（检索修完 tune 已满） |

## 复现

```powershell
cd industrial-cpp-kb-lab
python scripts/diagnose_retrieval.py --ids Q3,Q4,Q5
python src/03_search.py --eval
python src/eval_answer_layer.py --llm --top-k 8 --split tune -o notes/phase10_tune_after_fix.json
python src/run_regression.py --top-k 8
```

CI 主 workflow 仍 **skip LLM**；完整性为本地报告项。
