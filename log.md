# 修改日志

日期：2026-06-26

## 本次修改

1. 修复引用校验过宽的问题
   - `04_answer.py` 中 `validate_citations()` 改为严格校验：
     - 至少需要 1 个 `file:line` 引用。
     - 任何越界或不在检索上下文内的引用都会使 `ok=false`。
   - 新增 `has_citations` 字段，区分“无引用”和“引用越界”。

2. 修复 app streaming 路径不校验引用的问题
   - `app.py` 的 Rich streaming 答案现在会收集完整输出文本。
   - 输出完成后调用 `validate_citations()`。
   - 在终端显示 `Citation Check: OK/WARN` 面板。

3. 修复 JSON 输出覆盖 `citations` 的问题
   - `app.py` 不再把 source 列表写回 `citations`。
   - source 列表改名为 `context_citations`。
   - `citations` 保留为 `{valid, invalid, has_citations, ok}` 校验结果。

4. 修复 `03_search.py` CLI 迁移性问题
   - 新增 `--repo-root`。
   - `--src-root` 不传时自动使用 `<repo-root>/src`。
   - 普通查询和 `--eval` 都会使用传入的 repo/src root。

5. 修复 bundle 回归漏检
   - `run_regression.py` 中 `check_bundle()` 不再把“没有 primary implementation chunk”当作 PASS。
   - bundle 检查现在会报告失败原因。
   - bundle 通过条件改为必须达到 `len(BUNDLE_IDS)`。

6. 补充检索 hit 元数据
   - `03_search.py` 的 `hit_from_chunk()` 现在输出 `class` 字段。
   - `eval_answer_layer.py` 增加模块加载失败检查。

7. 扩充检索评测集
   - `eval/eval_questions.json` 从 15 题扩展到 30 题。
   - 新增 H11-H25，覆盖：
     - Config / FileConfigSource / ConfigCache
     - SlowTicker / Adc / Watchdog
     - Extruder / Laser / Switch / FilamentDetector
     - ZProbe / DeltaGridStrategy / CartGridStrategy
     - PID_Autotuner / Thermistor / CurrentControl

## 验证结果

已执行：

```powershell
python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in pathlib.Path('src').glob('*.py')]; print('syntax ok')"
python src/03_search.py --eval
python src/run_regression.py --skip-llm
python src/app.py --test
python src/eval_answer_layer.py
```

30 题检索结果：

- `Recall@5`: 29/30 = 96.7%
- `mean_cov@5`: 86%
- gate: PASS（要求 `mean_cov@5 >= 70%`）

离线回归结果：

- retrieval: PASS
- bundle: 3/3 PASS
- citation: skip（未设置 `LLM_API_KEY`，未调用 LLM）

引用校验单元检查：

- `src/a.cpp:12` 落在 chunk 内：`ok=true`
- `src/a.cpp:99` 超出 chunk：`ok=false`
- 无引用：`ok=false`

## 仍需注意

- 30 题中 H4 在 `Recall@5` 仍失败，但 `Recall@10` 通过；这是之前冻结时保留的真实缺口。
- `eval_answer_layer.py` 的符号覆盖率只有 50%，说明”文件能找对”和”具体符号能进入 trimmed LLM context”仍是两层问题，后续可以单独优化。

---

# 修改日志（续）

日期：2026-06-29（Session 6）

## Phase 8 — AST-aware 符号检索 + dispatch index

1. `03_search.py` 新增 `search_method()` / `search_class()`
   - 支持 `Class::method`、`Class.method`、唯一实现符号精确命中
   - 直接拉实现 chunk，与 BM25 / symbol / rg 融合排序
   - 方法 chunk 优先于构造函数和 header class

2. 新建 `src/05_extract_dispatch_index.py` → `data/dispatch_index.json`
   - 175 entries / 110 fixed commands
   - 静态抽取 `gcode->g/m == N`、`switch + case`、SimpleShell 命令表
   - 动态 `has_letter()` 无法确定编号时标记 `unknown`，不让 LLM 猜

3. `03_search.py` 新增 `search_dispatch()`
   - query 含 `G28` / `M104` / `M221` / `M907` 等命令号时先查 dispatch index
   - 命中结果 preview 对准 evidence line

4. `eval/eval_questions.json` 扩展到 35 题（5 tune + 30 holdout）
   - 新增 H26–H30 五道 dispatch 题

5. 新增 `notes/phase8_symbol_dispatch_audit.md`

## 验证结果（Phase 8）

- `03_search.py --eval`：35/35 Recall@5，mean_cov@5 **94%**
- `eval_answer_layer.py`：mean sym_cov@trim **71%**（Phase 6 基线 54%）
- H4 G28 命中 `Endstops.cpp`（dispatch evidence line 直接命中）

---

# 修改日志（续）

日期：2026-06-29（Session 7）

## Phase 9 — Repomap PageRank A/B（默认关闭）

1. 新建 `src/03_build_repomap.py`
   - 图边来源：mention / same-file / include / dispatch
   - 输出 `data/repomap_graph.json`（1569 nodes / 26774 edges）、`repomap_scores.json`
   - 低噪声符号过滤：920 low-noise symbols

2. `03_search.py` 新增 `search_reporank()`
   - `ENABLE_REPORANK=1` 或 `--enable-reporank` 时启用
   - 以 primary hits + method/class/dispatch hits 为 personalized seeds
   - 最多追加 ≤3 个新文件 extras

3. A/B 结论：两种模式 mean cov@5 同为 94%，Q2-Q5 均为 68%，未达 +5pp 门槛
   - `eval_answer_layer.py` sym_cov@trim 开启后从 71% 降至 68%
   - 默认保持关闭，Phase 9 作为实验完成

## 验证结果（Phase 9）

- 两种模式 35/35 Recall@5，mean cov@5 94%

---

# 修改日志（续）

日期：2026-06-29（Session 8）

## Phase 10 — LLM 答案完整性 + Q3–Q5 检索补齐

1. `04_answer.py`
   - 新增 `validate_answer_coverage()`：检查答案是否覆盖 trimmed context 中每个 primary 文件
   - `citation_in_hits()` 接受 `symbol_start` 引用（修 H26/H30 引用校验）
   - `build_prompt()` 注入 `{{primary_checklist}}` / `{{primary_count}}`

2. `prompts/code_qa.md` 更新
   - 增加 primary 文件清单段 + 自检句

3. `eval_answer_layer.py` 增强
   - 报告 `ctx_primary` / `expected` / `cite`；新增 `--resume` / `--ids`

4. `03_search.py` 检索补齐（Q3–Q5）
   - `halt` / `module` hint 扩展
   - `multi_file_structure_query` 触发 `per_file=1` diversify
   - structure 题跳过 call_graph extras
   - `expand_bundle` 两阶段（先全 primary，再补 overview/header）

5. 新增 `scripts/diagnose_retrieval.py`：四层检索缺口诊断

## 验证结果（Phase 10）

- tune LLM expected：**5/5**；tune citation：**5/5**
- Q3 bundle@8 6/6，Q4 7/7，Q5 6/6
- 35 题 mean cov@5：**94%** PASS

---

# 修改日志（续）

日期：2026-06-30（Session 9–10）

## 第二阶段 Phase A — 工程化 CLI

1. `src/search/` 包（模块拆分）
   - `search/index.py`：`SearchIndex` 类（加载 / 检索 / bundle / eval 合为一体）
   - `search/__init__.py`：re-export 接口
   - `03_search.py` 重写为轻量 CLI shim（`_INSTANCE = SearchIndex()`）
   - `kb_cli/runtime.py` 更新为返回 `SearchIndex` 实例

2. 新建 `kb_cli/manifest.py`（`IndexManifest`）
   - 字段：`created_at`、`repo_root`、`git_sha`、`file_count`、`chunk_count`、`symbol_count`、`dispatch_count`、`version`
   - `kb index build` 自动写入，`kb index check` 读取验证

3. 新建 `kb_cli/errors.py`（`KBIndexError` / `KBSearchError`）

4. 新建 `kb_cli/logging.py`，支持 `LOG_LEVEL` 环境变量

5. 查询 / 错误日志
   - 每次 `kb ask` / `kb search` 追加一行到 `logs/query.jsonl`
   - `kb index build` 失败时追加到 `logs/error.jsonl`

6. 新建 `config/default.toml`（index / llm / search / serve 四节）

7. CLI 命令整理
   - `kb index build / check / stats`
   - `kb serve`（FastAPI + `POST /ask` + `GET /health`）

8. 新建 `docs/deployment.md`

## 第二阶段 Phase B — 规模压测（80 万行）

- scale_test 语料：abseil-cpp（246k）+ raylib（389k）+ Dear ImGui（90k）+ googletest（76k）= **800,617 行 / 895 文件**
- 索引全程 27s，ctags 成功率 890/895（99.4%）
- 原始 Smoothieware P95=2,426ms；BM25 候选限流 top 200 + rg 只扫候选文件 + rg timeout=2s 后 P95=**143ms**
- 新建 `docs/benchmark_report.md`

### Phase B 泛化修复（d43eec9 recall 38%）

scale_test 原始 Recall@5=9/20，mean_cov@5=38%；根因分析：
- `.cc/.cxx/.hh/.hxx` 未被扫描
- macro/enum/typedef 符号未加载
- C++ 三段限定名未解析
- 裸 `error` 触发 Smoothieware 专用 halt hint

修复内容（`search/index.py`、`01_scan_files.py`、`03_build_chunks.py`）：
- 扫描 `.cc/.cxx/.hh/.hxx`
- 加载 macro/enum/typedef 符号
- 解析多段限定名 `A::B::C`
- 移除 halt hint 中裸 `error` 触发词
- 缓存模块 stem 加速融合排序

修复后 scale_test：Recall@5 **17/20**，mean_cov@5 **75%**，P95 **75ms**  
新建 `docs/generalization_audit.md`、`docs/generalization_followup_diagnosis.md`  
Smoothieware 回归：35/35 PASS，mean_cov@5 **95%**（scale_test 扩展使 BM25 更通用）

## 第二阶段 Phase C — `kb probe` + 迁移文档

- 新建 `src/kb_probe.py`：文件统计 / 编码检测 / ctags 结构统计 / 风险文件识别 / 索引可行性评估
- `kb probe --repo-root <path> --out <report.md>` 生成 Markdown 报告
- 生成 `reports/scale_test_probe.md`、`reports/smoothieware_probe.md`
- 新建 `docs/wire_bonder_migration_plan.md`（6 步接入流程 / 数据安全边界 / 回滚策略）

## 第二阶段 Phase D — 外部试点准备包

- 新建 `eval/wirebonder_questions_template.json`（20 题模板，覆盖 8 类问题）
- 新建 `docs/wire_bonder_intake_checklist.md`（可直接发给软件部）
- 新建 `docs/first_pilot_acceptance.md`（成功 / 部分成功 / 失败标准）
- 新建 `docs/capability_boundary.md`（能做 / 不做边界）
- 新建 `docs/stakeholder_pitch.md`（向软件部申请只读目录话术）
- 新建 `docs/demo_script.md`（5 分钟 Smoothieware 映射演示脚本）

## 验证结果（Phase A–D）

```powershell
python src/03_search.py --eval        # 35/35 PASS, mean_cov@5=95%
python src/run_regression.py --skip-llm  # REGRESSION PASSED
kb index build → check → stats → ask  # 全链路走通
```

---

# 修改日志（续）

日期：2026-06-30（Session 11）

## Smart Search — LLM Query Planner + 多路检索融合

1. 新建 `src/query_planner.py`
   - `QueryPlan` dataclass：`intent` / `normalized_question` / `entities` / `symbols` / `search_queries` / `must_have` / `target_kinds`
   - `plan_query(raw, llm_cfg)`：调 LLM 将自然语言问题拆解为多个源码检索子查询；失败时返回 `fallback_plan`，不抛异常
   - intent 分类：`symbol_lookup / entry_point / call_flow / error_trace / module_summary / config_lookup / unknown`
   - prompt：`prompts/query_planner.md`

2. 新建 `src/search/smart_search.py`
   - `smart_search(idx, query, top_k, plan=None)`：LLM plan → 多路 `SearchIndex.search()` → `_merge_hits()` 融合
   - `_merge_hits()`：多查询命中同一 chunk 时 `MULTI_HIT_BOOST=0.15`；`must_have` 未命中时降权 `MUST_HAVE_PENALTY=0.25`
   - 最多 10 条子查询（`MAX_SUB_QUERIES`）；命中来源标注为 `+smart`

3. `kb_cli/main.py` 新增 `kb smart` 命令
   - `.\kb smart "gcode运行流程"`：LLM plan + 多路检索 + 自动 LLM 解释
   - TUI 内 `/smart <query>` 触发

4. TUI 升级（Milestone C）
   - 搜索 worker 改为线程安全（Worker 独立线程，`threading.Thread` + 结果队列）
   - TUI 内 `/smart <q>` 支持：显示 plan 摘要 → 多路检索结果 → LLM 流式解释
   - `_format_plan_preview()`：右侧 preview 展示 intent / entities / search_queries / must_have
   - 历史导航 `↑ / ↓` 循环上一次查询

5. 新建 `docs/demo_visual_plan.md`
   - 3 个低成本 Mermaid 动态图设计（检索流水线 / 引用对比 / 安全边界）

6. 新建 `scripts/setup_dev.ps1`、`scripts/start_kb.ps1`
   - `setup_dev.ps1`：一键安装 Python 依赖（在仓库根或 industrial-cpp-kb-lab/ 下均可）
   - `start_kb.ps1`：日常一键启动 TUI

## 验证结果（Session 11）

已执行：
```powershell
python src/03_search.py --eval        # 35/35 PASS, mean_cov@5=95%
python src/run_regression.py --skip-llm  # REGRESSION PASSED
.\kb smart "gcode运行流程"            # LLM plan 正常返回，多路检索合并
```

---

# 修改日志（续）

日期：2026-06-26（Session 5）

## Phase 3.4 — 轻量 Mention Graph

1. 新建 `src/03_build_callgraph.py`
   - 扫描所有 function/class chunk 文本，提取已知符号名（来自 symbol_index.json），自引用过滤
   - 输出 `data/call_graph.json`：`{mentioned_by: {sym: [chunk_id,...]}, mentions: {chunk_id: [sym,...]}}`
   - 规模：986 chunks / 827 symbols / 5719 edges

2. `03_search.py` 新增
   - `W_GRAPH = 25.0`、`CALL_GRAPH_PATH`、`_CALL_GRAPH` 全局
   - `load_call_graph()`：文件不存在时 no-op
   - `search_graph(primary_hits)`：对 primary hit symbols 查 `mentioned_by`，返回 ≤3 新文件 hit
   - `search()` 末尾：`flow_intent_query()` 为 True 时追加 graph_extras

3. eval 对比
   - Q5 cov@5：50% → 67%（+17pp，Module.h 通过 graph 补入）
   - all mean_cov@5：86% → 87%；tune：68% → 71%
   - Q2/Q3/Q4 无变化（事件总线盲区，mentor graph 无法捕获）

## Phase 5 — kb_cli 包 + Textual TUI Milestone B

4. `src/kb_cli/__main__.py` 新建
   - 支持 `python -m kb_cli <subcmd>` 调用方式

5. `kb.cmd` 更新
   - 从 `python src/app.py %*` 改为 `set PYTHONPATH=src && python -m kb_cli %*`
   - 支持 `.\kb tui`、`.\kb search`、`.\kb ask` 等所有子命令

6. `src/kb_cli/tui.py` — Textual TUI Milestone B
   - 新增 `_HELP_TEXT` 常量和 `HelpScreen(ModalScreen)` 浮层
   - `on_data_table_row_highlighted`：光标移动时右侧 preview 实时刷新
   - `action_table_down / action_table_up`：j/k 导航，自动 focus table
   - `action_show_help` 改为 `push_screen(HelpScreen())`
   - HelpScreen 绑定 Esc/q/? 关闭

## 文档更新

7. `AGENTS.md`、`README.md`、`architecture.md`、`docs/history.md` 全部同步至 Session 5 状态

## 验证结果

```powershell
python src/03_build_callgraph.py      # 生成 call_graph.json
python src/03_search.py --eval        # all mean_cov@5: 87% PASS
python -c “import py_compile; py_compile.compile('src/kb_cli/tui.py', doraise=True); print('OK')”
.\kb --help                           # Typer CLI 正常启动
.\kb eval                             # 30 题 eval 输出正常
```
