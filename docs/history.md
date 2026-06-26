# 进度日志 — industrial-cpp-kb-lab

记录每次工作的实际进展、关键发现和遗留问题。

---

## 2026-06-25 — Session 1

### 完成内容

**Phase 0 验收**
- git 2.45.2 ✅、Python 3.11.9 ✅ 已在 PATH
- rg / ctags / dot 通过 winget 安装，二进制在 WinGet Packages 目录，需重开终端刷新 PATH
- `repos/Smoothieware/` 已 clone

**Phase 1.1 — 读3个文档**

*README*（`README.creole`）
- 项目定位：G-code interpreter + CNC controller，OOP C++，目标硬件 LPC17xx / Cortex-M3
- 运动控制部分移植自 grbl

*Module Example*（从源码直接读 `src/libs/Module.h` + `Kernel.h`）
- 9个事件枚举：`ON_MAIN_LOOP` / `ON_CONSOLE_LINE_RECEIVED` / `ON_GCODE_RECEIVED` / `ON_IDLE` / `ON_SECOND_TICK` / `ON_GET_PUBLIC_DATA` / `ON_SET_PUBLIC_DATA` / `ON_HALT` / `ON_ENABLE`
- `Kernel` 是单例，`hooks` 数组（`array<vector<Module*>, 9>`）存所有订阅
- 模块调 `register_for_event()` 订阅，`call_event()` 广播

*Motion Control*（从 `Robot.h` / `Planner.h` / `StepTicker.h` 读）
- 链路：`Robot` → `Planner::append_block()` → `Block` → `Conveyor` → `StepTicker`（定时中断）→ `StepperMotor`
- 关键参数：`junction_deviation`、`z_junction_deviation`、`minimum_planner_speed`
- StepTicker 用 2.62 定点数做步进计算（`STEPTICKER_FPSCALE = 1LL<<62`）

**Phase 1.2 — 锁定5个练习问题**

| # | 问题 | 关键文件 |
|---|------|---------|
| Q1 | G-code 从哪里进入系统 | `SerialConsole.cpp`, `GcodeDispatch.cpp`, `Player.cpp` |
| Q2 | G-code 如何变成运动命令 | `Robot.cpp` → `Planner.cpp` → `StepTicker.cpp` |
| Q3 | Motion/Planner/Stepper 代码在哪 | `src/modules/robot/`, `src/libs/StepTicker.cpp` |
| Q4 | halt/stop/emergency 逻辑 | `Kernel.cpp::immediate_halt`, `KillButton.cpp`, `ON_HALT` |
| Q5 | 模块注册/触发/通信 | `Module.h`, `Kernel.h::hooks`, `PublicData.cpp` |

**文档创建**
- `architecture.md` — 系统架构（数据流/模块说明/设计决策）
- `docs/history.md` — 本文件

### 关键发现

- `GcodeDispatch` 订阅的是 `ON_CONSOLE_LINE_RECEIVED`（不是 `ON_GCODE_RECEIVED`），它解析后再广播 `ON_GCODE_RECEIVED` 给其他模块
- `SerialConsole` 有 `halt_flag`，收到 `!` 字符直接触发 halt，无需经过 G-code 解析
- `Player` 是 SD 卡 G-code 文件的入口，和串口入口最终汇合到同一个 `GcodeDispatch`

### 遗留

- Phase 1.3：ripgrep 实际搜索，统计高频文件 ✅
- Phase 1.4：写 `notes/smoothieware_code_map.md` ✅
- Phase 1.5：选定 10 个重点文件 ✅
- Phase 2：`01_scan_files.py` / `02_extract_symbols.py` ✅

---

## 2026-06-25 — Session 1（续）

### Phase 1.3 ripgrep 探索结果

运行4类搜索，统计每文件命中行数：

**最高频文件（跨4个搜索总命中）：**

| 文件 | 总命中 | 主要角色 |
|------|:------:|---------|
| `Robot.cpp` | 265 | 运动核心，Gcode解析 + 运动学 |
| `Endstops.cpp` | 213 | 限位检测 + halt逻辑 |
| `SimpleShell.cpp` | 102 | 命令行 shell，大量 Gcode/halt 命令 |
| `GcodeDispatch.cpp` | 79 | G-code 解析分发入口 |
| `ZProbe.cpp` | 89 | 探针，大量 Gcode 处理 |
| `Extruder.cpp` | 98 | 挤出机（3D打印专用，运动相关） |
| `Kernel.cpp` | 32 | 模块系统中枢 |
| `KillButton.cpp` | 37 | 硬件急停按钮 |
| `Player.cpp` | 64 | SD 卡 G-code 文件播放 |

**关键发现：**
- `Endstops.cpp` halt 命中 122 次，是整个系统 halt 逻辑最集中的文件（超过 KillButton）
- `main.cpp` 模块命中 26 次，是所有模块注册的起点
- `SimpleShell.cpp` 跨3个类别命中，是调试/命令行接口的枢纽

### Phase 1.4 代码地图

已写入 `industrial-cpp-kb-lab/notes/smoothieware_code_map.md`，含：
- ripgrep 高频文件统计表
- 按5个分区（Communication / Robot-Motion / Kernel / Error-Halt）的文件职责表
- 10个第一批知识库输入文件

### Phase 1.5 选定10个重点文件

```
1.  src/libs/Module.h
2.  src/libs/Kernel.cpp
3.  src/modules/communication/GcodeDispatch.cpp
4.  src/modules/communication/SerialConsole.cpp
5.  src/modules/robot/Robot.cpp
6.  src/modules/robot/Planner.cpp
7.  src/modules/robot/Conveyor.cpp
8.  src/libs/StepTicker.cpp
9.  src/modules/utils/killbutton/KillButton.cpp
10. src/modules/robot/Endstops.cpp
```

---

## 2026-06-25 — Session 2

### Phase 2 完成

- `industrial-cpp-kb-lab/src/01_scan_files.py` 已完成并生成 `data/file_manifest.json`
- `industrial-cpp-kb-lab/src/02_extract_symbols.py` 已完成并生成 `data/symbol_index.json`
- 脚本已参数化，支持 `--repo-root`、`--src-root`、`--manifest`、`--output`，方便后续迁移到 wire bonder 代码
- 验证结果：扫描 Smoothieware 源码 269 个文件；ctags 提取 3072 条符号

### Phase 3 计划细化

- `PLAN.md` 已同步当前进度：Phase 0、1、2 完成，下一步进入 Phase 3
- 明确 10 个重点文件只是 canary / golden set 种子，不限制索引范围
- Phase 3 增加 `03_build_chunks.py`，按 ctags 符号边界优先分块，过长 chunk 再切窗口
- 明确代码友好 tokenizer：保留原始 token，同时拆 snake_case、camelCase、路径片段、`::` / `->`
- 新增 `industrial-cpp-kb-lab/eval/eval_questions.json`，用于 Recall@5 / Recall@10 验收

### LLM 与迁移策略调整

- LLM 不再在架构里写死具体供应商，统一为 `LLM_PROVIDER` / `LLM_MODEL`
- Phase 7 不再要求物理替换 `repos/Smoothieware/`，改为脚本参数指定目标代码库

### Plan B：CodeGraph 结构图谱实验

- `PLAN.md` 新增 Plan B：CodeGraph 代码结构图谱实验
- 定位：只验证「代码结构怎么找」，不替代 `rg + ctags + BM25` 主线，不替代源码核查
- 目标：在 Smoothieware 上对比 `rg/BM25` 与 CodeGraph 是否更适合回答模块、函数、调用链、影响范围问题
- 实验产物规划：
  - `notes/smoothieware_rg_findings.md`
  - `notes/smoothieware_codegraph_findings.md`
  - `notes/comparison.md`
- `architecture.md` 已补充 Plan B 的结构图谱层说明
- `AGENTS.md` / `architecture.md` / `README.md` 已同步最新进度、约束和常用命令

### 下一步

- 实现 `03_build_chunks.py`
- 实现 `03_search.py`
- 用 `eval/eval_questions.json` 跑 Recall@K
- Phase 3 基础检索跑通后，再并行做 CodeGraph A/B 实验

---

## 2026-06-25 — Session 3

### Phase 3.1 完成：`03_build_chunks.py` → `chunks.jsonl`

**实现细节：**
- 分层切分策略：`.cpp/.c` 按 function 边界，`.h/.hpp` 按 class/struct 边界，无符号文件 100 行固定窗口
- 每文件生成 `file_overview` chunk（头 40 行 + include 列表 + 符号摘要）
- 过长 chunk（>180 行）自动拆子窗口（180 行 / overlap 40 行）
- 每个 chunk 前加 context header（file / symbol / kind / lines / class）

**产出：** 1,569 个 chunk（function 1106 / file_overview 269 / class 190 / fallback 4）

### ctags end_line 修复（关键设计改进）

**问题：** 原版 `03_build_chunks.py` 用手写 brace matching 确定函数结束行，在工业 C++ 中存在已知漏洞：
- 字符串字面量中的 `{}`（如 `"{ depth=0 }"`）
- 注释中的 `{}`
- Lambda 嵌套（`auto cb = [this]() { ... }`）
- 初始化列表（`MyClass() : buf_{0} {}`）
- `#ifdef` 条件编译中不对称的 `{}`

**修复：** 给 ctags 加 `--fields=+e`，直接使用 C++ 语法解析器给出的 `end_line`：
- `02_extract_symbols.py`：`--fields=+nKz` → `--fields=+nKze`，symbol 记录新增 `end_line` 字段
- `03_build_chunks.py`：新增 `find_end()` 函数，ctags end_line 为主，brace matching 退为极端兜底
- 验证：1,410 个 function 符号 `end_line` 覆盖率 100%，当前 brace fallback 触发 0 次

### 文档更新

- `AGENTS.md`：进度更新至 Phase 3.1，补充 03_build_chunks.py 命令和一键重建命令
- `architecture.md`：symbol_index.json schema 加 `end_line` 字段，chunk 边界设计决策更新
- `README.md`：新建，项目整体介绍 + 快速上手

---

## 2026-06-25 — Session 4

### Phase 3.2–5 完成

**检索 `03_search.py`**
- BM25 + symbol + rg 融合；Recall@5 = 5/5（门槛 ≥4/5）
- `QUERY_HINTS` 中文意图扩展；**入口组仅 `进入`/`入口` 触发**（修 Q1/Q2 互污染）
- `search(bundle=True)`：primary + overview + 配对 header
- 泛化符号加权：`flow_intent` + 罕见 `on_*` + `hint_coherent`（删除 GcodeDispatch 文件名特判）
- snippet 扩展至 `call_event` 行；构造函数 `symbol==class` 降权

**分块 `03_build_chunks.py`**
- chunk header：`symbol_start` vs `chunk_lines`（修子窗口行号误导 LLM）

**问答 `04_answer.py`**
- OpenAI 兼容 LLM；`validate_citations()`；`answer_stream()`
- `trim_context_hits`：primary 优先，最多 8 chunk 进 prompt

**CLI `app.py`**
- Rich REPL + streaming；`--demo` / `--test` / `--json`
- `run_regression.py`：Recall + bundle + 可选引用校验
- 依赖：`rich>=13.0`

**Prompt `code_qa.md`**
- 硬约束：原文引用、覆盖 context 文件、禁止伪注释；negative example

### 准确度与 eval 诊断

| 题 | 检索 @5 | LLM 备注 |
|----|---------|----------|
| Q1 | 3/3 expected | GcodeDispatch:56 + SerialConsole + Player |
| Q2 | 门槛 PASS；expected 常 2/5 | Robot+Conveyor；缺 Planner/StepTicker 为排序问题 |
| Q3 | 结构题，不触发 flow_intent | 未误伤 |
| Q4–Q5 | 门槛 PASS | 部分 expected @5 未全中 |

**原则确立：** 不把 expected_files 硬编码进检索器；Recall 刷绿不如如实记录缺口；Phase 6 需 hold-out 题防过拟合。

### 文档同步

- `AGENTS.md` / `README.md` / `architecture.md` / `PLAN.md` / `history.md` / `smoothieware_code_map.md` / `code_qa.md` 全部更新至当前实现
- 删除 `CLAUDE.md`（不再使用 Claude Code 专用入口）

### 下一步

- Phase 6：扩充 eval 15–20 题 + hold-out；量化 LLM 准确度
- diversify 抑噪（非文件名白名单）；可选换 `glm-4` 模型
- Phase 7：wire bonder `--repo-root` 迁移

---

<!-- 新 Session 在此追加，格式：## YYYY-MM-DD — Session N -->
