# CLAUDE.md — industrial-cpp-kb-lab

## 项目一句话定位

用 ripgrep + ctags + BM25 + LLM 为工业设备 C++ 代码库构建「代码问答知识库」。
当前练手素材：Smoothieware（LPC17xx 上的 OOP C++ G-code/CNC 控制器）。
最终目标：复用到公司 wire bonder C++ 代码，实现「输入问题 → 返回源码+解释+引用路径」。

## 目录结构

```
Smoothiewarerag/
├── PLAN.md                          # 主计划（Phase 0–7，含验收标准）
├── CLAUDE.md                        # 本文件
├── architecture.md                  # 系统架构说明
├── docs/
│   └── history.md                   # 进度日志
└── industrial-cpp-kb-lab/
    ├── repos/Smoothieware/          # git submodule（不入库，见 .gitignore）
    ├── src/                         # 核心 Python 脚本（按 phase 编号）
    │   ├── 01_scan_files.py         # Phase 2：扫描源码文件
    │   ├── 02_extract_symbols.py    # Phase 2：ctags 符号提取
    │   ├── 03_build_chunks.py       # Phase 3.1：源码分块（已完成）
    │   ├── 03_search.py             # Phase 3.2：BM25 + rg + ctags 融合检索（待实现）
    │   ├── 04_answer.py             # Phase 4：检索 → LLM 问答
    │   └── app.py                   # Phase 5：一体化入口
    ├── data/                        # 生成物（不入库）
    │   ├── file_manifest.json       # Phase 2 产出
    │   ├── symbol_index.json        # Phase 2 产出
    │   └── chunks.jsonl             # Phase 3 产出
    ├── index/                       # BM25 索引（不入库）
    ├── eval/                        # 检索评估集（入库）
    │   └── eval_questions.json      # Phase 3 Recall@K golden set
    ├── notes/                       # 人工笔记（入库）
    │   └── smoothieware_code_map.md # Phase 1 代码地图
    └── prompts/                     # LLM prompt 模板（入库）
        └── code_qa.md               # Phase 4 问答 prompt
```

## 当前进度

- Phase 0 ✅ 工具已装（git / python / rg / ctags / dot）
- Phase 1 ✅ 人工探索 + 代码地图 + 10 个重点文件选定
- Phase 2 ✅ 文件扫描 + 符号提取完成
  - `data/file_manifest.json`：269 个文件，36,409 行
  - `data/symbol_index.json`：3,072 条符号，**含 `end_line`（100% 覆盖）**
- Phase 3.1 ✅ 分块完成
  - `data/chunks.jsonl`：1,569 个 chunk（function 1106 / file_overview 269 / class 190 / fallback 4）
  - 函数边界由 **ctags `end_line`** 给出（主）；brace matching 退为极端兜底（当前触发 0 次）
- Phase 3.2 🔄 下一步：`03_search.py`（BM25 + rg + ctags 融合检索）+ `eval/eval_questions.json` Recall@K 验收
- Plan B 🔬 CodeGraph 结构图谱实验，等 Phase 3 主线跑通后并行做

## 核心约束（不要违反）

- **不在 `repos/Smoothieware/` 里写任何文件**，所有产物放 `industrial-cpp-kb-lab/` 外层
- **主线第一版不上** LangChain / LlamaIndex / Milvus / Qdrant / Agent / 知识图谱
- CodeGraph 只作为 Plan B 小实验，不替代 `rg + ctags + BM25` 主线，不替代源码核查
- **不做嵌入式构建**（ARM GCC / LPC1768 / 烧录不是目标）
- **不上向量检索**（直到 Phase 6 评估证明 BM25 不够用）
- 每个 Phase 有验收标准，没达标不推进

## 5 个练习问题（Phase 1.2 锁定）

| # | 问题 | 关键入口文件 |
|---|------|-------------|
| Q1 | G-code 从哪里进入系统？ | `SerialConsole.cpp`, `GcodeDispatch.cpp`, `Player.cpp` |
| Q2 | G-code 如何变成运动命令？ | `Robot.cpp` → `Planner.cpp` → `Conveyor.cpp` → `StepTicker.cpp` |
| Q3 | Motion / Planner / Stepper 代码在哪里？ | `src/modules/robot/`, `src/libs/StepTicker.cpp` |
| Q4 | error / stop / halt / emergency 逻辑？ | `Kernel.cpp`(`immediate_halt`), `KillButton.cpp`, `ON_HALT` 事件 |
| Q5 | 模块系统如何注册、触发、通信？ | `Module.h`, `Kernel.h`(`hooks`数组), `PublicData.cpp` |

## Smoothieware 架构速记

```
输入: UART / SD卡
  ↓ SerialConsole / Player
GcodeDispatch  ← ON_CONSOLE_LINE_RECEIVED
  ↓ call_event(ON_GCODE_RECEIVED)
Robot          ← 坐标解析 + 运动学变换
  ↓ Planner::append_block()
Planner        ← junction_deviation + acceleration 速度规划
  ↓ Block 入队
Conveyor       ← Block 队列管理
  ↓ 定时中断
StepTicker     ← 2.62 定点数步进计算
  ↓
StepperMotor   ← 脉冲输出 → 电机
```

## 技术栈

| 组件 | 选型 | 原因 |
|------|------|------|
| 关键词检索 | ripgrep | 极快，支持 C++ 语法高亮 |
| 符号定位 | Universal Ctags | 精确到 class/function/行号 |
| 语义检索 | BM25 (`rank_bm25`) | 轻量，无需向量 |
| LLM | `LLM_PROVIDER` / `LLM_MODEL` 配置 | 保持 Claude / OpenAI / 本地模型可替换 |
| Plan B | CodeGraph / code graph 工具 | 只验证代码结构层，不进入主线前先 A/B 对比 |
| 语言 | Python 3.11 | 脚本胶水层 |

## 常用命令

```powershell
# 搜索模块系统相关
rg -n "register_for_event|call_event|on_module_loaded" industrial-cpp-kb-lab/repos/Smoothieware/src

# 搜索 G-code 相关
rg -n "on_gcode_received|GcodeDispatch|Gcode" industrial-cpp-kb-lab/repos/Smoothieware/src

# 搜索 halt/stop
rg -n "halt|emergency|kill|ON_HALT" industrial-cpp-kb-lab/repos/Smoothieware/src

# Phase 2：扫描源码文件 → file_manifest.json
python industrial-cpp-kb-lab/src/01_scan_files.py

# Phase 2：提取符号索引 → symbol_index.json（含 end_line）
python industrial-cpp-kb-lab/src/02_extract_symbols.py

# Phase 3.1：分块 → chunks.jsonl
python industrial-cpp-kb-lab/src/03_build_chunks.py

# 全流程一键重建（顺序执行）
python industrial-cpp-kb-lab/src/01_scan_files.py && python industrial-cpp-kb-lab/src/02_extract_symbols.py && python industrial-cpp-kb-lab/src/03_build_chunks.py

# 迁移到其他 C++ 代码库时传参
python industrial-cpp-kb-lab/src/01_scan_files.py --repo-root path/to/repo --src-root path/to/repo/src
python industrial-cpp-kb-lab/src/02_extract_symbols.py --repo-root path/to/repo
```
