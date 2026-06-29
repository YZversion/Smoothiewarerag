# Architecture — industrial-cpp-kb-lab

## 系统定位

**纯本地优先、无向量数据库**的 C++ 代码问答系统：传统 IR（关键词 + 符号 + BM25）召回上下文，LLM 生成解释与引用。

---

## 整体数据流

```
┌─────────────────────────────────────────────────────────┐
│                      离线索引阶段                         │
│  repos/Smoothieware/src/                                │
│    → 01_scan_files.py      → file_manifest.json         │
│    → 02_extract_symbols.py → symbol_index.json (+end_line)│
│    → 03_build_chunks.py    → chunks.jsonl               │
│    → 05_extract_dispatch_index.py → dispatch_index.json │
│    → 03_build_callgraph.py → call_graph.json            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      在线检索阶段                         │
│  query → tokenize + HINT_GROUPS（按意图扩展）             │
│    ├─ search_method/search_class（AST-aware 确定性入口）  │
│    ├─ search_dispatch（G/M-code / 命令号 → handler 证据） │
│    ├─ symbol_index 精确命中（含 on_* 事件加权规则）        │
│    ├─ ripgrep 兜底                                       │
│    ├─ BM25 on chunks.jsonl                              │
│    └─ search_graph()（flow_intent 时追加 ≤3 新文件）      │
│         → merge + diversify + optional bundle             │
│         → Top-K hits（file:line, snippet, score）         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      LLM 生成阶段                         │
│  trim_context_hits（primary 优先，最多 8 chunk）          │
│    → prompts/code_qa.md + context + question            │
│    → OpenAI 兼容 API（streaming）                         │
│    → 解释 + 引用 + validate_citations()                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      CLI（app.py）                        │
│  无参数 → REPL；带问题 → 一次性 streaming + Rich         │
│  --search-only / --demo / --test / --json               │
└─────────────────────────────────────────────────────────┘
```

---

## 索引产物

### file_manifest.json

每文件：`path`, `size_bytes`, `lines`, `top_dir`。跳过 `build/`, `mbed/`, 二进制等。

### symbol_index.json

```jsonc
{
  "name": "on_console_line_received",
  "kind": "function",
  "file": "src/modules/communication/GcodeDispatch.cpp",
  "line": 56,
  "end_line": 489,
  "class": "GcodeDispatch"
}
```

`ctags --fields=+nKze` 提供 `end_line`。

### chunks.jsonl

- `.cpp` 按 function；`.h` 按 class；每文件一个 `file_overview`
- 过长函数子窗口 180 行 / overlap 40
- Context header（子窗口区分函数起点与片段范围）：

```cpp
// file: src/modules/robot/Robot.cpp
// symbol: on_gcode_received
// symbol_start: 488
// chunk_lines: 908-1087
// kind: function
// class: Robot
```

### dispatch_index.json

Phase 8 产物，由 `05_extract_dispatch_index.py` 静态抽取命令 / 事件分发证据。每条记录包含：

```jsonc
{
  "command": "G28",
  "kind": "gcode",
  "handler_file": "src/modules/tools/endstops/Endstops.cpp",
  "handler_symbol": "Endstops::on_gcode_received",
  "target_symbol": "Endstops::process_home_command",
  "line": 1046,
  "evidence": "if ( gcode->has_g && gcode->g == 28) {",
  "confidence": "static-pattern",
  "chunk_id": "src_modules_tools_endstops_Endstops_cpp::997-1176"
}
```

抽取静态可证明模式：`gcode->g/m == N`、`switch + case`、配置默认 M-code、SimpleShell 命令表。动态 `has_letter() + get_value()` 无法确定具体编号时标记 `unknown`，不让 LLM 猜。

---

## 03_search.py — 融合检索

### 多路召回

| 路径 | 权重思路 | 输出 |
|------|----------|------|
| Method | `W_METHOD`；`Class::method` / `Class.method` / 唯一实现符号直达实现 chunk | chunk id |
| Class | `W_CLASS_METHOD`；类名命中时优先实现方法 chunk，压低构造函数 / header class | chunk id |
| Dispatch | `W_DISPATCH`；`G28/M104/...` 先查 `dispatch_index.json`，snippet 对准 evidence line | chunk id |
| Symbol | `W_SYMBOL`；流程题对罕见 `on_*` + 入口 chunk 加权 | chunk id |
| BM25 | 归一化 × `W_BM25` | chunk id |
| ripgrep | `W_RG` | chunk id → chunk_at_line |

融合后加 `chunk_score_bonus`（`.cpp` function +4；构造函数 `symbol==class` −18）。确定性 method / class / dispatch 命中只参与排序和 evidence 定位，不替代源码事实。

### QUERY_HINTS（意图驱动）

中文问句扩展英文代码种子。**触发词按意图分组**，避免「提到 gcode」就注入入口 token：

| 意图 | 触发词示例 | 种子示例 |
|------|------------|----------|
| 入口 | `进入`, `入口` | `GcodeDispatch`, `on_console_line_received`, `call_event` |
| 运动链 | `运动`, `变成`, `命令` | `Robot`, `Planner`, `Conveyor`, `StepTicker` |
| 结构 | `motion`, `planner`, `stepper` | `Planner`, `Block`, `StepperMotor`, `append_block`, `calculate_trapezoid`, `step_tick` |
| 停机 | `halt`, `stop`, `emergency` | `ON_HALT`, `Endstops`, `on_halt` |
| 模块 | `模块系统`, `注册`, `触发` | `Module`, `Kernel`, `register_for_event`, `call_event`, `PublicData` |

### 可迁移的符号加权（非文件名硬编码）

1. **`flow_intent_query`**：问句含「如何/进入/变成/halt…」→ 流程题
2. **`is_distinct_event_handler`**：`on_*` 且全库出现次数 ≤ 20（排除泛滥的 `on_gcode_received`）
3. **`hint_coherent_symbol`**：handler 所在模块名须在 query/hints tokens 中
4. **`flow_entry_query`**：入口题对与 hints 一致的 `on_main_loop` 轻度加权

### Snippet 生成

默认 10 行；扫描至 `call_event` / `THEKERNEL->call_event`（上限 28 行），避免 SerialConsole 截断在 `reserve(20)` 处。

### Bundle（Phase 3.3）

`search(..., bundle=True)`：primary + 同文件 `file_overview` + 配对 `.h` class。

### Mention Graph 扩展（Phase 3.4）

`03_build_callgraph.py` 扫描每个 function/class chunk 文本，记录其中出现的已知符号名，输出：
```
call_graph.json: {mentioned_by: {sym: [chunk_id,...]}, mentions: {chunk_id: [sym,...]}}
```
- 986 chunks with mentions，5719 edges（Smoothieware 当前值）
- `search_graph(primary_hits)`：对 primary hits 的 symbol 查 `mentioned_by`，追加 ≤3 新文件 hit
- 仅当 `flow_intent_query()` 为 True 时触发；文件不存在时 no-op
- **已知限制**：事件总线（`call_event(ON_XXX, ...)`）的动态分发边无法通过文本 mention 捕获

### Dispatch Index（Phase 8）

`search_dispatch()` 解析 query 中的 `G28` / `M104` / `M109` / `M221` / `M907` 等命令号，先查 `dispatch_index.json`，再与 method / class / symbol / BM25 / rg 融合排序。命中结果会把 preview 对准条件判断、`case` 或命令表证据行，避免只靠 BM25 碰到同名文本。

### 评估

`eval/eval_questions.json`（35 题：5 tune + 30 holdout）→ Recall@5 / coverage@K / Recall@10。  
**Gate：** 全体 **mean coverage@5 ≥ 70%**。Phase 8 当前：35/35 Recall@5，mean coverage@5 94%，`eval_answer_layer.py` mean sym_cov@trim 71%。

---

## 04_answer.py — LLM 问答

- `answer()` / `answer_stream()`：检索 bundle → `build_prompt()` → LLM
- **`trim_context_hits`**：先保留全部 `primary`，再用 slot 填 overview/header（默认最多 8 chunk）
- **`validate_citations()`**：检查回答中 `` `file:line` `` 是否落在 hit chunk 行范围
- 环境变量：`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`

---

## prompts/code_qa.md

硬约束：原文引用代码、覆盖 context 相关文件、`symbol_start` vs `chunk_lines`、禁止 `// ...` 伪注释与错误 markdown 围栏。

---

## CLI

### kb_cli（新，推荐）

`src/kb_cli/`：Typer 子命令 + Textual TUI。

| 命令 | 行为 |
|------|------|
| `.\kb tui` | Textual TUI（5 区布局；j/k 导航；? help；q 退出） |
| `.\kb search "query"` | 检索表格 + preview |
| `.\kb ask "question"` | 检索 + LLM 流式回答 |
| `.\kb sources "query"` | 仅显示来源 |
| `.\kb symbol "Cls::fn"` | 符号定位 |
| `.\kb eval` | Recall + coverage dashboard |
| `.\kb repl` | 交互 REPL |

若 `.\kb` 不在 PATH：`python -m kb_cli <subcmd>`（需在 `industrial-cpp-kb-lab/` 下运行）。

### app.py（旧，仍兼容）

| 命令 | 行为 |
|------|------|
| `python src/app.py` | Rich REPL |
| `python src/app.py "问题"` | Streaming + Rich + Sources 表 |
| `--search-only` | 仅检索 |
| `--json` | 纯 JSON（管道用） |
| `--test` | `run_regression.py` |

默认 `--top-k 8`。

---

## 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 检索 | BM25 + rg + ctags | 无 GPU，可迁移 |
| 不用向量库 | Phase 6 再评估 | 避免过早复杂化 |
| chunk 边界 | ctags `end_line` | 工业 C++ 可靠 |
| Hint 策略 | `HINT_GROUPS` 具名触发函数 | 避免 Q1/Q2 互污染；可测试 |
| Mention graph | text-scan，不引入新工具 | 补直接调用；事件总线盲区已知 |
| 不加文件名白名单 | 泛化规则 only | Phase 7 无 golden set |
| LLM | OpenAI 兼容 SDK | 智谱/OpenAI 可换 |
| eval 规模 | 5 题 | 易过拟合；Phase 6 扩 hold-out |

---

## Plan B — CodeGraph

独立实验，不接入 `app.py`。产物在 `notes/*_findings.md`、`comparison.md`。

---

## Phase 7 迁移

```powershell
python src/01_scan_files.py --repo-root path/to/wire_bonder --src-root path/to/wire_bonder/src
python src/02_extract_symbols.py --repo-root path/to/wire_bonder
python src/03_build_chunks.py
python src/app.py "你的设备问题"
```

检索规则（意图 hints、`on_*` 频率抑噪、trim primary）应随事件驱动 C++ 架构迁移；Smoothieware 专属文件名调参不应迁移。
