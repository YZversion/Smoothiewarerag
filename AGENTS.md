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
├── .cursor/rules/industrial-kb.mdc  # Cursor：写 src/*.py 时的极简纪律
└── industrial-cpp-kb-lab/
    ├── repos/Smoothieware/          # clone 源码（.gitignore，只读）
    ├── src/                         # 01_ 扫描 → 02_ 符号 → 03_ 分块/检索 → 04_ 问答 → app.py
    ├── data/                        # file_manifest / symbol_index / chunks.jsonl（生成物）
    ├── index/                       # BM25 索引（生成物）
    ├── eval/eval_questions.json     # Recall@K golden set
    ├── notes/smoothieware_code_map.md
    └── prompts/code_qa.md
```

## 当前进度

| Phase | 状态 | 要点 |
|-------|------|------|
| 0 | ✅ | git / python / rg / ctags / dot；Smoothieware 已 clone |
| 1 | ✅ | 代码地图、5 个练习问题、10 个重点文件种子 |
| 2 | ✅ | `file_manifest.json`（269 文件）、`symbol_index.json`（3072 符号，含 end_line） |
| 3.1 | ✅ | `chunks.jsonl`（1569 chunk）；`03_build_chunks.py` |
| 3.2 | ✅ | `03_search.py`；三路融合（symbol+rg+BM25）；Recall@5=5/5 Recall@10=5/5 |
| 4 | ✅ | `04_answer.py` + `prompts/code_qa.md`；智谱 glm-4-flash 跑通 Q1–Q5，均带 file:行号 引用 |
| 5 | 🔄 | **`app.py`** CLI，打通全链路 + 5 题回归测试 |
| Plan B | 🔬 | CodeGraph A/B（见 PLAN.md），不阻塞主线 |

## 核心约束

- 不改 `repos/**`；产物只在 `industrial-cpp-kb-lab/{data,index,prompts,notes,eval}`
- 主线：**rg + ctags + BM25 + LLM**；不上 LangChain / 向量库 / Agent / 知识图谱（Phase 6 前）
- 不做 ARM 构建与烧录；CodeGraph 仅 Plan B 笔记实验
- 每 Phase 验收未过不推进（标准见 `PLAN.md`）

写码时的决策梯、禁止项、eval 驱动增量 → **见 [industrial-kb.mdc](.cursor/rules/industrial-kb.mdc)**。

## 5 个练习问题（eval golden set）

| # | 问题 | 关键路径 |
|---|------|----------|
| Q1 | G-code 从哪里进入？ | `SerialConsole.cpp`, `GcodeDispatch.cpp`, `Player.cpp` |
| Q2 | G-code → 运动命令？ | `Robot.cpp` → `Planner.cpp` → `Conveyor.cpp` → `StepTicker.cpp` |
| Q3 | Motion / Planner / Stepper？ | `src/modules/robot/`, `StepTicker.cpp`, `StepperMotor.cpp` |
| Q4 | halt / stop / emergency？ | `Kernel.cpp`, `KillButton.cpp`, `tools/endstops/Endstops.cpp` |
| Q5 | 模块注册与事件？ | `Module.h`, `Kernel.cpp`, `PublicData.cpp` |

## 架构速记（G-code → 步进）

```
SerialConsole/Player → GcodeDispatch → Robot → Planner → Conveyor → StepTicker → StepperMotor
                              ↑ ON_GCODE_RECEIVED / ON_HALT 等 Kernel 事件总线
```

## 技术栈

| 层 | 选型 |
|----|------|
| 关键词 | ripgrep |
| 符号 | Universal Ctags |
| 检索 | BM25（`rank_bm25`） |
| LLM | `LLM_PROVIDER` / `LLM_MODEL` 环境变量 |
| 胶水 | Python 3.11 |

## 常用命令

```powershell
cd industrial-cpp-kb-lab

# 探索 Smoothieware（只读）
rg -n "on_gcode_received|ON_HALT|register_for_event" repos/Smoothieware/src

# 重建索引管道
python src/01_scan_files.py
python src/02_extract_symbols.py
python src/03_build_chunks.py

# 换代码库
python src/01_scan_files.py --repo-root path/to/repo --src-root path/to/repo/src
python src/02_extract_symbols.py --repo-root path/to/repo
```

## 文档索引

| 文件 | 用途 |
|------|------|
| [`PLAN.md`](PLAN.md) | Phase 任务清单与验收标准 |
| [`industrial-kb.mdc`](.cursor/rules/industrial-kb.mdc) | 写 `src/*.py` 时的极简纪律（Cursor glob 激活） |
| [`architecture.md`](architecture.md) | 系统设计 |
| [`docs/history.md`](docs/history.md) | Session 进度日志 |
| [`eval/eval_questions.json`](industrial-cpp-kb-lab/eval/eval_questions.json) | 检索回归集 |
