# Smoothiewarerag — industrial-cpp-kb-lab

[![Eval](https://github.com/YZversion/Smoothiewarerag/actions/workflows/eval.yml/badge.svg)](https://github.com/YZversion/Smoothiewarerag/actions/workflows/eval.yml)

工业设备 C++ 代码问答知识库：用 **ripgrep + ctags + BM25 + LLM** 实现「输入问题 → 返回源码 + 解释 + 文件:行号引用」。

当前以 **Smoothieware**（LPC17xx OOP C++ G-code / CNC 控制器）练手，验证后通过 `--repo-root` 迁移到公司 wire bonder 代码库。

---

## 快速上手

**第一次安装（Windows）：**

```powershell
# 仓库根目录（Smoothiewarerag/）或 industrial-cpp-kb-lab/ 均可
.\scripts\setup_dev.ps1
```

**日常启动 TUI：**

```powershell
# 仓库根目录
.\scripts\start_kb.ps1

# 或进入子目录后
cd industrial-cpp-kb-lab
.\scripts\start_kb.ps1
.\kb              # 默认进入 TUI（等价于 .\kb tui）
```

**高级用法：**

```powershell
.\kb search "G-code 从哪里进入系统？"
.\kb smart "gcode运行流程"              # LLM plan + 多路检索 + 自动解释
.\kb ask "halt emergency 在哪里处理？"
.\kb eval                                # Recall@5 / coverage@K 报告
.\kb repl                                # Rich REPL（旧式交互）
```

**手动安装（无脚本时）：**

```powershell
cd industrial-cpp-kb-lab
pip install -r requirements.txt
```

**重建索引管道：**

```powershell
python src/01_scan_files.py
python src/02_extract_symbols.py
python src/03_build_chunks.py
python src/05_extract_dispatch_index.py # dispatch index（Phase 8）
python src/03_build_callgraph.py        # mention graph（Phase 3.4）
python src/03_build_repomap.py          # optional PageRank A/B（Phase 9）
```

**旧入口仍兼容：**

```powershell
python src/app.py                        # Rich REPL
python src/app.py "G-code 从哪里进入系统？"
python src/app.py --test                 # 检索回归
```

LLM 配置：复制 `.env.example` → `.env`，设置 `LLM_API_KEY`（智谱/OpenAI 等 OpenAI 兼容接口）。

---

## 示例输出

```
问题：G-code 从哪里进入系统？

简要解释：
串口由 SerialConsole::on_main_loop 收行后 call_event(ON_CONSOLE_LINE_RECEIVED)；
GcodeDispatch::on_console_line_received 解析并分发 G-code。

关键文件 / 函数：
  `src/modules/communication/SerialConsole.cpp:249` — 串口主循环
  `src/modules/communication/GcodeDispatch.cpp:56`  — G-code 行处理入口
  `src/modules/utils/player/Player.cpp:422`         — SD 卡播放入口
```

---

## 项目结构

```
Smoothiewarerag/
├── README.md              # 本文件
├── PLAN.md                # Phase 0–12 + 第二阶段 A–E 计划与验收
├── AGENTS.md              # AI 协作入口（进度 / 约束 / 命令）
├── architecture.md        # 系统架构
├── docs/history.md        # 进度日志
├── scripts/
│   ├── setup_dev.ps1      # 一键安装依赖
│   └── start_kb.ps1       # 日常一键启动 TUI
└── industrial-cpp-kb-lab/
    ├── src/
    │   ├── 01_scan_files.py           # 文件扫描（含 .cc/.cxx/.hh/.hxx）
    │   ├── 02_extract_symbols.py      # ctags 符号提取（含 macro/enum/typedef）
    │   ├── 03_build_chunks.py
    │   ├── 03_build_callgraph.py      # Phase 3.4：mention graph
    │   ├── 03_build_repomap.py        # Phase 9：optional PageRank A/B
    │   ├── 03_search.py               # CLI shim（SearchIndex 向后兼容入口）
    │   ├── 04_answer.py               # 检索 + LLM + streaming + coverage 度量
    │   ├── 05_extract_dispatch_index.py
    │   ├── query_planner.py           # Smart search：LLM 拆解自然语言为子查询
    │   ├── kb_probe.py                # Phase C：新代码库结构扫描
    │   ├── app.py                     # 旧 REPL / Rich CLI（保留兼容）
    │   ├── run_regression.py
    │   ├── eval_answer_layer.py       # Phase 10：检索 vs LLM 分层 eval
    │   ├── search/
    │   │   ├── index.py               # SearchIndex 类（检索 / bundle / eval）
    │   │   └── smart_search.py        # 多路检索融合
    │   └── kb_cli/                    # Typer CLI + Textual TUI
    ├── scripts/                       # diagnose_retrieval、benchmark_queries
    ├── config/default.toml            # 默认配置（index / llm / search / serve）
    ├── data/                          # 生成物（chunks / call_graph / dispatch_index / repomap 等）
    ├── eval/
    │   ├── eval_questions.json        # Smoothieware 35 题
    │   └── scale_test_questions.json  # 跨项目 20 题（Phase B 泛化验证）
    ├── prompts/
    │   ├── code_qa.md                 # LLM 问答 prompt
    │   └── query_planner.md           # Smart search query planner prompt
    ├── reports/                       # probe 报告
    ├── docs/                          # deployment / benchmark / migration / demo 等
    ├── notes/smoothieware_code_map.md
    └── repos/Smoothieware/            # 源码（.gitignore）
```

---

## 当前进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 0–2 | 环境 / 探索 / 扫描符号 | ✅ |
| 3.1–3.3 | 分块 + 融合检索 + bundle | ✅ |
| 3.4 | mention graph（`03_build_callgraph.py`）+ `search_graph()` | ✅ |
| 4 | LLM 问答 + 引用校验 | ✅ |
| 5 | `kb_cli` Typer CLI + Textual TUI（j/k / help / search） | ✅ |
| 6 | 35 题 eval；mean cov@5≥70% gate | ✅ |
| Plan B | rg/BM25 vs CodeGraph A/B 对比完成 | ✅ |
| 7 | CI（GitHub Actions ✅ + 本地镜像脚本） | ✅ |
| 8 | AST-aware 符号检索 + dispatch index；35 题 Recall@5=35/35，mean cov@5=94% | ✅ |
| 9 | Repomap PageRank A/B；默认关闭 | ✅ |
| 10 | primary 清单 + coverage 度量；tune 5/5 expected；Q3–Q5 检索补齐 | ✅ |
| A | 工程化：`SearchIndex` 类 / `IndexManifest` / 查询日志 / `kb index` 命令 / `kb serve` | ✅ |
| B | 规模压测（80 万行）；P95 修复；scale_test Recall 17/20，mean_cov@5 75% | ✅ |
| C | `kb probe` + `wire_bonder_migration_plan.md` | ✅ |
| D | 外部试点准备包：问题模板 / intake checklist / 首轮验收标准 | 🟡 待真实目录 |
| Smart | LLM query planner + 多路检索（`kb smart` / TUI `/smart`） | ✅ |
| 11–12 | wire bonder → CLI 产品化 | ⬜ |

检索回归：`.\kb eval` 或 `python src/03_search.py --eval` → mean cov@5 **≥70%** gate（当前 **95%**）。  
CI：[![Eval](https://github.com/YZversion/Smoothiewarerag/actions/workflows/eval.yml/badge.svg)](https://github.com/YZversion/Smoothiewarerag/actions/workflows/eval.yml) — 每次 push/PR 自动 shallow clone + 重建索引 + eval。本地镜像：`.\scripts\ci_build_and_eval.ps1`。

---

## 设计要点

- **无向量库 / 无 LangChain**：本地可跑，第一版够用再升级
- **ctags `end_line` 定 chunk 边界**，子窗口标注 `symbol_start` vs `chunk_lines`
- **QUERY_HINTS 按意图扩展**中文问句，避免关键词污染
- **AST-aware 符号入口**：`search_method()` / `search_class()` 对精确方法、类与唯一 symbol 直拉实现 chunk
- **dispatch index**：静态抽取 `G28/M104/... -> handler` 的条件判断 / case / 命令表证据行
- **Smart search**：`query_planner.py` 将自然语言问题拆解为多路子查询，`smart_search.py` 融合排序；失败退回单路检索
- **Repomap PageRank 默认关闭**：`--enable-reporank` / `ENABLE_REPORANK=1` 仅用于 A/B
- **可迁移检索规则**：事件驱动 `on_*` 加权 + hint 一致性，不写死文件名
- **泛化扩展**：`.cc/.cxx/.hh/.hxx` + macro/enum/typedef 符号，scale_test 20 题 mean_cov@5 75%

---

## 文档

- [PLAN.md](PLAN.md) — 完整计划（Phase 0–12 + 第二阶段 A–E）
- [AGENTS.md](AGENTS.md) — 协作入口与命令
- [architecture.md](architecture.md) — 架构与设计决策
- [docs/history.md](docs/history.md) — Session 日志
- [industrial-cpp-kb-lab/docs/deployment.md](industrial-cpp-kb-lab/docs/deployment.md) — 部署指南
- [industrial-cpp-kb-lab/docs/benchmark_report.md](industrial-cpp-kb-lab/docs/benchmark_report.md) — 规模压测报告
- [industrial-cpp-kb-lab/docs/generalization_followup_diagnosis.md](industrial-cpp-kb-lab/docs/generalization_followup_diagnosis.md) — scale_test 修复根因诊断
- [industrial-cpp-kb-lab/docs/wire_bonder_migration_plan.md](industrial-cpp-kb-lab/docs/wire_bonder_migration_plan.md) — wire bonder 接入流程
- [industrial-cpp-kb-lab/docs/capability_boundary.md](industrial-cpp-kb-lab/docs/capability_boundary.md) — 能力边界说明
- [industrial-cpp-kb-lab/docs/demo_visual_plan.md](industrial-cpp-kb-lab/docs/demo_visual_plan.md) — 演示动态图设计
- [industrial-cpp-kb-lab/notes/phase10_conclusion.md](industrial-cpp-kb-lab/notes/phase10_conclusion.md) — Phase 10 结论
- [industrial-cpp-kb-lab/notes/smoothieware_code_map.md](industrial-cpp-kb-lab/notes/smoothieware_code_map.md) — 代码地图
