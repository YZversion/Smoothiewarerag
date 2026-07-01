# AGENTS.md — industrial-cpp-kb-lab

> **AI 协作入口（单一事实来源）**  
> 进度与约束只维护本文件。写 `industrial-cpp-kb-lab/src/**` 时另见 [`.cursor/rules/industrial-kb.mdc`](.cursor/rules/industrial-kb.mdc)（写码纪律）。完整 Phase 清单与验收标准见 [`PLAN.md`](PLAN.md)。

## 项目一句话

用 ripgrep + ctags + BM25 + LLM 为工业设备 C++ 代码库构建「代码问答知识库」。练手 Smoothieware，未来复用到 wire bonder：**输入问题 → 源码 + 解释 + 文件:行号引用**。

## 目录速览

```
Smoothiewarerag/
├── PLAN.md                          # Phase 0–12 完整计划（细节查这里，勿在本文件重复）
├── AGENTS.md                        # 本文件：进度 / 约束 / 命令
├── architecture.md                  # 系统设计
├── docs/history.md                  # Session 进度日志
├── .cursor/rules/industrial-kb.mdc  # Cursor：写 src/*.py 时的极简纪律
└── industrial-cpp-kb-lab/
    ├── repos/Smoothieware/          # clone 源码（.gitignore，只读）
    ├── src/                         # 01–05 管道 + kb_cli/（Typer CLI + Textual TUI）
    ├── data/                        # file_manifest / symbol_index / chunks / call_graph / dispatch / repomap
    ├── eval/eval_questions.json     # Recall@K golden set（35 题：5 tune + 30 holdout）
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
| 3.2 | ✅ | `03_search.py`；Recall@5=5/5；`HINT_GROUPS`（具名触发函数，按意图触发） |
| 3.3 | ✅ | `search(bundle=True)`：overview + 配对 header |
| 3.4 | ✅ | `03_build_callgraph.py`：mention graph（986 chunks / 5719 edges）；`search_graph()` 对 flow_intent 查询追加 ≤3 新文件 |
| 4 | ✅ | `04_answer.py` + streaming + `validate_citations` + `trim_context_hits` |
| 5 | ✅ | `kb_cli` 包（Typer）；`.\kb tui` Textual Search Cockpit Milestone A+B；`app.py` 旧入口保留 |
| 6 | ✅ | 35 题 eval；mean_cov@5≥70% gate |
| Plan B | ✅ | CodeGraph A/B；`comparison.md` |
| 7 | ✅ | GitHub Actions Eval 绿；`scripts/ci_build_and_eval.ps1` |
| 8 | ✅ | AST-aware `search_method/search_class` + `dispatch_index.json`；35 题 Recall@5=35/35；mean_cov@5=94%；sym_cov@trim=71%；H4 PASS |
| 9 | ✅ | Repomap PageRank A/B 完成；`ENABLE_REPORANK` 默认关闭（Q2–Q5 +0pp，不并入默认路径） |
| 10 | ✅ | primary 清单 + `validate_answer_coverage`；Q3–Q5 检索补齐；tune **5/5 expected**；见 `phase10_conclusion.md` |
| A | ✅ | 工程化 CLI / IndexManifest / query logs / deployment doc |
| B | ✅ | scale_test 修复：Recall@5 17/20，mean_cov@5 75%，P95 75ms；`.cc/.cxx/.hh/.hxx` 扩展；macro/enum/typedef 加载；限定名 3 段；`error` hint 收窄；Smoothieware 回归 35/35，mean_cov@5=**95%** ✅ |
| C | ✅ | `kb probe` + wire bonder 迁移摘要；scale_test / Smoothieware probe 报告已生成 |
| D | 🟡 | 外部试点准备包完成：pilot plan、真实问题评估手册、问题模板、intake checklist；待真实目录 + 10 题 |
| Smart | ✅ | `query_planner.py` + `search/smart_search.py`；`kb smart` CLI 命令；TUI `/smart <q>`；线程安全 worker；`demo_visual_plan.md` |
| E | ⬜ | Level 1 修改建议（不生成 patch） |

## 检索设计原则（可迁移，勿 per-question 硬编码）

- **HINT_GROUPS 按问题意图触发**（短语/共现具名函数，非裸子串；`入口` alone 不触发 entry 组）
- **事件驱动加权**：`context_coherence_adjustment()` 按 query/hints 模块名区分同名 `on_*`
- **入口 chunk 优先**：`start_line == symbol_start` 高于子窗口
- **AST-aware 确定性入口**（Phase 8）：`search_method()` / `search_class()` 基于 ctags + `symbol_index.json` 直拉实现 chunk，方法 chunk 优先于构造函数和 header class
- **命令分发索引**（Phase 8）：`dispatch_index.json` 只从源码静态条件 / case / 命令表抽取 `G28/M104/... -> handler`，命中必须带 evidence line
- **call graph 扩展**（Phase 3.4）：`flow_intent_query` 为 True 时追加 ≤3 条新文件 mention graph 命中；事件总线动态分发无法通过 mention 捕获（已知限制）
- **Repomap PageRank**（Phase 9）：`ENABLE_REPORANK=1` / `--enable-reporank` 才启用；A/B 未达 +5pp，默认仍用旧 `search_graph()`
- **Smart search**（Phase Smart）：`query_planner.py` 调 LLM 将自然语言问题拆解为 ≤10 条子查询；`smart_search.py` 多路调 `SearchIndex.search()` 并融合排序；失败时退回单路 fallback；LLM 只用于 query 拆解，不用于事实生成
- **多文件结构题**（Phase 10）：`motion_structure` / `halt` / `module` 触发时 `per_file=1` diversify；跳过 call_graph extras；`expand_bundle` 两阶段避免 header 去重吃掉 primary
- **禁止**把 expected_files 文件名硬编码进检索器——Phase 11 wire bonder 没有 golden set 可抄
- **检索 gate**：全体 **mean cov@5 ≥ 70%**；当前 35 题 mean_cov@5=**94%**（Phase 10 后 tune Q3–Q5 bundle@8 满覆盖）

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
| Q2 | G-code → 运动命令？ | `Robot` → `Planner` → `Conveyor` → `StepTicker` | cov@5 4/5（@10 满；LLM expected 5/5） |
| Q3 | Motion / Planner / Stepper？ | `robot/`, `StepTicker`, `StepperMotor` | bundle@8 **6/6**（Phase 10） |
| Q4 | halt / stop / emergency？ | `Kernel`, `KillButton`, `Endstops`, 通信链 | bundle@8 **7/7**（Phase 10） |
| Q5 | 模块注册与事件？ | `Module`, `Kernel`, `PublicData`, `main.cpp` | bundle@8 **6/6**（Phase 10） |

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
| 检索 | BM25（`rank_bm25`）+ 符号融合 + `HINT_GROUPS` + mention graph + dispatch index；`SearchIndex` 类 |
| Smart search | `query_planner.py`（LLM 拆解子查询）+ `smart_search.py`（多路融合）|
| LLM | `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY`（OpenAI 兼容 SDK） |
| CLI | `kb_cli`（Typer）+ Textual TUI（线程安全 worker）；`app.py` 旧入口保留 |
| 胶水 | Python 3.11 |

## 常用命令

```powershell
cd industrial-cpp-kb-lab
pip install -r requirements.txt

# 重建索引管道（顺序执行）
python src/01_scan_files.py
python src/02_extract_symbols.py
python src/03_build_chunks.py
python src/05_extract_dispatch_index.py # Phase 8：G/M-code dispatch index
python src/03_build_callgraph.py        # Phase 3.4：mention graph
python src/03_build_repomap.py          # Phase 9：optional PageRank A/B graph

# 新 CLI（须在 industrial-cpp-kb-lab 目录下）
.\kb tui                                 # Textual TUI（j/k 导航，? 帮助）
.\kb search "G-code 从哪里进入系统？" --top-k 5 --preview
.\kb smart "gcode运行流程"               # LLM plan + 多路检索 + 自动解释（需 LLM_API_KEY）
.\kb ask "halt emergency 逻辑在哪里"
.\kb sources "halt error stop 调用链在哪里"
.\kb symbol "Planner::append_block"
.\kb index build --repo-root repos/Smoothieware  # 构建索引
.\kb index check --index data             # 验证索引完整性
.\kb probe --repo-root repos\Smoothieware --out reports\smoothieware_probe.md
.\kb serve                                # HTTP 接口（POST /ask, GET /health）
.\kb eval                                # Recall dashboard
.\kb repl                                # REPL 模式
# 若 kb 不在 PATH，用：python -m kb_cli <subcmd>
# TUI 内部命令：/smart <q>、/ask <q>、/copy N、/clear、↑/↓ 历史导航

# 旧入口仍兼容
python src/app.py "G-code 从哪里进入系统？"
python src/app.py --test                 # Recall 回归

python src/run_regression.py --skip-llm
python src/03_search.py --eval          # Recall + coverage@K（gate mean cov@5≥70%）
python scripts/diagnose_retrieval.py --ids Q3,Q4,Q5  # 四层检索缺口诊断
python src/eval_answer_layer.py --llm --top-k 8 --split tune  # Phase 10 完整性报告
python src/03_search.py --eval --enable-reporank  # Phase 9 A/B（默认不启用）

# CI 本地镜像（与 GitHub Actions 相同步骤）
.\scripts\ci_build_and_eval.ps1
```

环境变量见 `industrial-cpp-kb-lab/.env.example`（`LLM_API_KEY` 勿提交 git）。

## 文档索引

| 文件 | 用途 |
|------|------|
| [`PLAN.md`](PLAN.md) | Phase 任务清单与验收标准 |
| [`architecture.md`](architecture.md) | 数据流、检索规则、LLM 约束 |
| [`industrial-kb.mdc`](.cursor/rules/industrial-kb.mdc) | 写 `src/*.py` 时的极简纪律 |
| [`docs/history.md`](docs/history.md) | Session 进度日志 |
| [`docs/README.md`](industrial-cpp-kb-lab/docs/README.md) | 文档导航与维护规则 |
| [`notes/README.md`](industrial-cpp-kb-lab/notes/README.md) | notes 历史实验索引 |
| [`reports/README.md`](industrial-cpp-kb-lab/reports/README.md) | probe/report 产物索引 |
| [`eval/eval_questions.json`](industrial-cpp-kb-lab/eval/eval_questions.json) | 检索回归集（35 题：5 tune + 30 holdout） |
| [`notes/phase8_symbol_dispatch_audit.md`](industrial-cpp-kb-lab/notes/phase8_symbol_dispatch_audit.md) | Phase 8 符号 chunk / dispatch 审计 |
| [`notes/phase9_ab_report.md`](industrial-cpp-kb-lab/notes/phase9_ab_report.md) | Phase 9 Repomap PageRank A/B 结论 |
| [`notes/kb_acceptance.md`](industrial-cpp-kb-lab/notes/kb_acceptance.md) | **知识库验收清单**（自动化 + 人工抽测） |
| [`notes/phase10_conclusion.md`](industrial-cpp-kb-lab/notes/phase10_conclusion.md) | Phase 10 LLM 完整性结论 |
| [`notes/q345_retrieval_diagnosis.md`](industrial-cpp-kb-lab/notes/q345_retrieval_diagnosis.md) | Q3–Q5 四层检索诊断 |
| [`notes/eval_failures.md`](industrial-cpp-kb-lab/notes/eval_failures.md) | 检索失败根因（已修复/open） |
| [`notes/comparison.md`](industrial-cpp-kb-lab/notes/comparison.md) | Plan B：rg/BM25 vs CodeGraph A/B 结论 |
| [`docs/benchmark_report.md`](industrial-cpp-kb-lab/docs/benchmark_report.md) | Phase B 规模压测与 P95 修复记录 |
| [`docs/generalization_audit.md`](industrial-cpp-kb-lab/docs/generalization_audit.md) | Phase B 泛化审计：scale_test 38% 根因与已证明边界 |
| [`docs/generalization_followup_diagnosis.md`](industrial-cpp-kb-lab/docs/generalization_followup_diagnosis.md) | Phase B 泛化修复：scale_test 38%→75%，剩余 3 题不修复决策 |
| [`reports/scale_test_probe.md`](industrial-cpp-kb-lab/reports/scale_test_probe.md) | Phase C scale_test probe 报告 |
| [`reports/smoothieware_probe.md`](industrial-cpp-kb-lab/reports/smoothieware_probe.md) | Phase C Smoothieware probe 报告 |
| [`docs/wire_bonder_pilot_plan.md`](industrial-cpp-kb-lab/docs/wire_bonder_pilot_plan.md) | wire bonder 只读试点主入口 |
| [`docs/real_problem_evaluation_plan.md`](industrial-cpp-kb-lab/docs/real_problem_evaluation_plan.md) | 真实问题评估流程 / 评分表 / 下一阶段 gate |
| [`docs/wire_bonder_migration_plan.md`](industrial-cpp-kb-lab/docs/wire_bonder_migration_plan.md) | wire bonder 迁移计划摘要（详细流程已合并到 pilot plan） |
| [`docs/capability_boundary.md`](industrial-cpp-kb-lab/docs/capability_boundary.md) | 能力边界与风险控制说明 |
| [`docs/stakeholder_pitch.md`](industrial-cpp-kb-lab/docs/stakeholder_pitch.md) | 向软件部申请只读目录和真实问题的话术 |
| [`docs/demo_script.md`](industrial-cpp-kb-lab/docs/demo_script.md) | 5 分钟 Smoothieware 映射演示脚本 |
| [`docs/demo_visual_plan.md`](industrial-cpp-kb-lab/docs/demo_visual_plan.md) | 演示动态图设计（Mermaid 检索流水线 / 引用对比 / 安全边界） |
| [`eval/wirebonder_questions_template.json`](industrial-cpp-kb-lab/eval/wirebonder_questions_template.json) | wire bonder 真实问题采集模板（20 题） |
| [`docs/wire_bonder_intake_checklist.md`](industrial-cpp-kb-lab/docs/wire_bonder_intake_checklist.md) | 向软件部索取只读目录 / 编码 / 问题 / 验收人的清单 |
| [`docs/first_pilot_acceptance.md`](industrial-cpp-kb-lab/docs/first_pilot_acceptance.md) | 首轮试点验收摘要（评分表以 real_problem_evaluation_plan 为准） |
| [`docs/bias_bonding_next_steps.md`](industrial-cpp-kb-lab/docs/bias_bonding_next_steps.md) | 偏焊证据链、trace 字段和后续路线摘要 |
| [`docs/mcp_feasibility_review.md`](industrial-cpp-kb-lab/docs/mcp_feasibility_review.md) | MCP / SQLite / tree-sitter / Neo4j 可行性审查 |
