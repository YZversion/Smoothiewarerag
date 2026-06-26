# AGENTS.md — industrial-cpp-kb-lab

> **AI 协作入口（单一事实来源）**  
> 进度与约束只维护本文件。写 `industrial-cpp-kb-lab/src/**` 时另见 [`.cursor/rules/industrial-kb.mdc`](.cursor/rules/industrial-kb.mdc)（写码纪律）。完整 Phase 清单与验收标准见 [`PLAN.md`](PLAN.md)。

## 项目一句话

用 ripgrep + ctags + BM25 + LLM 为工业设备 C++ 代码库构建「代码问答知识库」。练手 Smoothieware，未来复用到 wire bonder：**输入问题 → 源码 + 解释 + 文件:行号引用**。

## 目录速览

```
Smoothiewarerag/
├── PLAN.md                          # Phase 0–7 完整计划（细节查这里，勿在本文件重复）
├── AGENTS.md                        # 本文件：进度 / 约束 / 命令
├── architecture.md                  # 系统设计
├── docs/history.md                  # Session 进度日志
├── .cursor/rules/industrial-kb.mdc  # Cursor：写 src/*.py 时的极简纪律
└── industrial-cpp-kb-lab/
    ├── repos/Smoothieware/          # clone 源码（.gitignore，只读）
    ├── src/                         # 01_ 扫描 → 02_ 符号 → 03_ 分块/检索 → 04_ 问答 → app.py
    ├── data/                        # file_manifest / symbol_index / chunks.jsonl（生成物）
    ├── eval/eval_questions.json     # Recall@K golden set（5 题）
    ├── notes/smoothieware_code_map.md
    ├── prompts/code_qa.md
    └── requirements.txt             # rank-bm25, openai, rich
```

## 当前进度

| Phase | 状态 | 要点 |
|-------|------|------|
| 0 | ✅ | git / python / rg / ctags / dot；Smoothieware 已 clone |
| 1 | ✅ | 代码地图、5 个练习问题、10 个重点文件种子 |
| 2 | ✅ | `file_manifest.json`（269 文件）、`symbol_index.json`（3072 符号，含 end_line） |
| 3.1 | ✅ | `chunks.jsonl`（1569 chunk）；`symbol_start` + `chunk_lines` header |
| 3.2 | ✅ | `03_search.py`；Recall@5=5/5；`QUERY_HINTS`（按意图触发） |
| 3.3 | ✅ | `search(bundle=True)`：overview + 配对 header |
| 4 | ✅ | `04_answer.py` + streaming + `validate_citations` + `trim_context_hits` |
| 5 | ✅ | `app.py` REPL + Rich + `run_regression.py`（`--test`） |
| 6 | ✅ | 检索冻结；验收清单 `kb_acceptance.md`；6.2 暂缓 |
| Plan B | 🔬 | CodeGraph A/B（见 PLAN.md），不阻塞主线 |

## 检索设计原则（可迁移，勿 per-question 硬编码）

- **QUERY_HINTS 按问题意图触发**（短语/共现，非裸子串；例：`入口`  alone 不触发 entry 组）
- **事件驱动加权**：`context_coherence_adjustment()` 按 query/hints 模块名区分同名 `on_*`
- **入口 chunk 优先**：`start_line == symbol_start` 高于子窗口
- **禁止**把 expected_files 文件名硬编码进检索器——Phase 7 wire bonder 没有 golden set 可抄
- **检索已冻结**（2026-06-25）：gate = 全体 **mean cov@5 ≥ 70%**；不为 holdout @5 缺口写规则（H4）

## 核心约束

- 不改 `repos/**`；产物只在 `industrial-cpp-kb-lab/{data,index,prompts,notes,eval}`
- 主线：**rg + ctags + BM25 + LLM**；不上 LangChain / 向量库 / Agent / 知识图谱（Phase 6 前）
- 不做 ARM 构建与烧录；CodeGraph 仅 Plan B 笔记实验
- 每 Phase 验收未过不推进（标准见 `PLAN.md`）

写码时的决策梯、禁止项、eval 驱动增量 → **见 [industrial-kb.mdc](.cursor/rules/industrial-kb.mdc)**。

## 5 个练习问题（eval golden set）

| # | 问题 | 关键路径 | 检索 @5 备注 |
|---|------|----------|--------------|
| Q1 | G-code 从哪里进入？ | `SerialConsole.cpp`, `GcodeDispatch.cpp`, `Player.cpp` | 3/3 expected |
| Q2 | G-code → 运动命令？ | `Robot` → `Planner` → `Conveyor` → `StepTicker` | cov@5 4/5（已冻结，缺 GcodeDispatch @5） |
| Q3 | Motion / Planner / Stepper？ | `robot/`, `StepTicker`, `StepperMotor` | 结构题，不触发 flow_intent |
| Q4 | halt / stop / emergency？ | `Kernel`, `KillButton`, `Endstops` | 部分 expected @5 |
| Q5 | 模块注册与事件？ | `Module`, `Kernel`, `PublicData` | 门槛 PASS |

## 架构速记（G-code → 步进）

```
SerialConsole/Player → GcodeDispatch::on_console_line_received
    → ON_GCODE_RECEIVED → Robot::on_gcode_received
    → Planner → Conveyor → StepTicker → StepperMotor
```

## 技术栈

| 层 | 选型 |
|----|------|
| 关键词 | ripgrep |
| 符号 | Universal Ctags（`--fields=+e`） |
| 检索 | BM25（`rank_bm25`）+ 符号融合 + `QUERY_HINTS` |
| LLM | `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY`（OpenAI 兼容 SDK） |
| CLI | Rich REPL + streaming（`app.py`） |
| 胶水 | Python 3.11 |

## 常用命令

```powershell
cd industrial-cpp-kb-lab
pip install -r requirements.txt

# 重建索引管道
python src/01_scan_files.py
python src/02_extract_symbols.py
python src/03_build_chunks.py

# 问答（须在 industrial-cpp-kb-lab 目录下）
python src/app.py                        # 交互 REPL
python src/app.py "G-code 从哪里进入系统？"
python src/app.py --search-only "关键词"
python src/app.py --demo
python src/app.py --test                 # Recall + bundle 回归

python src/run_regression.py --skip-llm
python src/03_search.py --eval          # Recall + coverage@K（tune/holdout 分项）
```

环境变量见 `industrial-cpp-kb-lab/.env.example`（`LLM_API_KEY` 勿提交 git）。

## 文档索引

| 文件 | 用途 |
|------|------|
| [`PLAN.md`](PLAN.md) | Phase 任务清单与验收标准 |
| [`architecture.md`](architecture.md) | 数据流、检索规则、LLM 约束 |
| [`industrial-kb.mdc`](.cursor/rules/industrial-kb.mdc) | 写 `src/*.py` 时的极简纪律 |
| [`docs/history.md`](docs/history.md) | Session 进度日志 |
| [`eval/eval_questions.json`](industrial-cpp-kb-lab/eval/eval_questions.json) | 检索回归集（15 题，tune/holdout） |
| [`notes/kb_acceptance.md`](industrial-cpp-kb-lab/notes/kb_acceptance.md) | **知识库验收清单**（自动化 + 人工抽测） |
| [`notes/phase6_conclusion.md`](industrial-cpp-kb-lab/notes/phase6_conclusion.md) | Phase 6 检索 vs LLM 结论 |
| [`notes/eval_failures.md`](industrial-cpp-kb-lab/notes/eval_failures.md) | 检索失败根因（已修复/open） |
