# 知识库验收清单 — Smoothieware MVP

> **验收对象**：`industrial-cpp-kb-lab` 最小可演示知识库（rg + ctags + BM25 + LLM）  
> **验收日期**：2026-06-25  
> **结论**：**通过** — 可交付 demo / 作为 Phase 7 wire bonder 迁移模板

Phase 6.2（向量 / Doxygen / Web UI）**不纳入本次验收**，见 `PLAN.md` 升级决策。

---

## 1. 环境与产物

| 项 | 要求 | 状态 |
|----|------|------|
| Python 依赖 | `pip install -r requirements.txt` | 手动确认 |
| 工具链 | `rg`、`ctags` 可用 | 手动确认 |
| 源码 | `repos/Smoothieware/` 只读 clone | ✅ |
| `data/file_manifest.json` | Phase 2 产物 | ✅ |
| `data/symbol_index.json` | Phase 2 产物 | ✅ |
| `data/chunks.jsonl` | Phase 3 产物（1569 chunks） | ✅ |
| LLM | `.env` 中 `LLM_API_KEY`（验收含 LLM 时需） | 手动确认 |

---

## 2. 自动化回归（必跑）

在 `industrial-cpp-kb-lab/` 下执行：

```powershell
python src/03_search.py --eval
python src/run_regression.py --top-k 8
```

**CI（Phase 7）：** 每次 push/PR 到 `main` 自动跑相同 gate（无 `LLM_API_KEY` 时 regression 跳过 LLM 段）。  
`data/` 与 `repos/` 不入库 → Actions 内 shallow clone Smoothieware 并重建索引。  
本地镜像：`.\scripts\ci_build_and_eval.ps1`（Windows）或 `bash scripts/ci_build_and_eval.sh`。

| 检查项 | 门槛 | 实测（2026-06-25） |
|--------|------|-------------------|
| 检索 gate | all **mean cov@5 ≥ 70%** | **73% PASS** |
| Recall@5 | 分项报告 | 14/15（H4 open，接受） |
| Bundle（Q1–Q3） | ≥3/3 | **3/3 PASS** |
| LLM 引用（tune Q1–Q5） | citation 无胡编 | **5/5 PASS** |

可选深层评估：

```powershell
python src/eval_answer_layer.py --top-k 8 --llm
```

---

## 3. 功能验收（人工抽测）

| # | 命令 / 操作 | 期望 |
|---|-------------|------|
| F1 | `python src/app.py --search-only "Planner append_block"` | 返回带 score 的命中列表，含 `Planner.cpp` |
| F2 | `python src/app.py "G-code 从哪里进入系统？"` | 中文解释 + Sources + `` `src/...:line` `` 引用 |
| F3 | `python src/app.py`（REPL）输入 1 题 | streaming 输出，无崩溃 |
| F4 | `python src/app.py --demo` | Q1–Q5 均可完成（或抽 2 题） |
| F5 | 回答中代码块 | 来自 context snippet，无 `// ...` 伪注释（prompt 约束） |

---

## 4. 质量边界（如实写入验收报告）

**已达标：**

- 文件级检索：mean cov@5 73%，gate PASS
- LLM 引用合法性：15/15（分层 eval）
- 检索规则可迁移：无 expected_files 硬编码；hint 短语/共现

**已知限制（不阻塞验收）：**

| 限制 | 说明 |
|------|------|
| H4 @5 | holdout 真缺口，戒掉 hint 误触后 FAIL@5，@10 PASS |
| Q2–Q5 coverage@5 | 多跳/多文件题偏低，Recall@5 仍 PASS |
| LLM 完整性 | 约 40% 题未列全所有期望文件（见 `phase6_conclusion.md`） |
| 符号 chunk 对齐 | context sym_cov ~50%，影响深度问答 |

**6.2 明确不做（本次）：**

- 向量检索 — 暂缓（BM25 文件级够用）
- Doxygen / Graphviz — 未做
- 调用链图 — Plan B CodeGraph 可选实验
- Web UI — REPL 已满足 demo

---

## 5. 迁移就绪（Phase 7 预检）

| 项 | 状态 |
|----|------|
| `--repo-root` / `--src-root` CLI 参数 | 管道脚本支持 |
| 检索 / prompt 无 Smoothieware 文件名特判 | ✅ |
| 换仓库后重跑 01→03→eval 流程文档化 | `PLAN.md` Phase 7 |

---

## 6. 验收签字项

- [x] 自动化回归 PASS（eval gate + regression）
- [x] Phase 6 量化结论（`notes/phase6_conclusion.md`）
- [x] 失败案例归档（`notes/eval_failures.md`）
- [ ] 人工抽测 F1–F5（验收人本地执行）
- [ ] LLM 数据合规确认（公司代码外发策略，Phase 7 前必做）

**签署：** 开发侧自动化项已完成；人工抽测与合规由验收人勾选。
