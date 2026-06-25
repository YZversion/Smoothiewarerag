# industrial-cpp-kb-lab

工业设备 C++ 代码问答知识库——用 **ripgrep + ctags + BM25 + LLM** 实现「输入问题 → 返回源码 + 解释 + 文件:行号引用」。

当前以 **Smoothieware**（LPC17xx 上的 OOP C++ G-code / CNC 控制器）为练手素材，验证通过后直接迁移到公司 wire bonder C++ 代码库。

---

## 这是什么

输入一个模块名、函数名、G-code 或 error 关键词，系统返回：

```
问题：G-code 从哪里进入系统？

回答：
G-code 通过 SerialConsole（UART）或 Player（SD 卡）进入系统。
SerialConsole 积攒字符到完整行后触发 ON_CONSOLE_LINE_RECEIVED 事件，
GcodeDispatch 订阅该事件并解析 G-code，再广播 ON_GCODE_RECEIVED。

来源：
  src/modules/communication/SerialConsole.cpp:199  on_serial_char_received
  src/modules/communication/GcodeDispatch.cpp:42   on_console_line_received
  src/modules/utils/player/Player.cpp:118          on_gcode_received
```

---

## 为什么这样设计

- **不上 LangChain / 向量数据库**：第一版只用 ripgrep + ctags + BM25，无 GPU 依赖，本地可运行
- **ctags 做边界检测**：函数/类的起止行由 ctags C++ 语法解析器给出，正确处理字符串、注释、Lambda、条件编译中的 `{}`，手写 brace matching 只做极端兜底
- **分层 chunking**：`.cpp` 按 function 实现切，`.h` 按 class 定义切，每文件额外生成 file_overview chunk
- **可一键迁移**：换一个 `--repo-root` 参数即可对接公司代码库，不改主逻辑

---

## 项目结构

```
Smoothiewarerag/
├── README.md
├── PLAN.md                          # 主计划（Phase 0–7，含验收标准）
├── CLAUDE.md                        # AI 协作速查（进度 / 约束 / 命令）
├── architecture.md                  # 系统架构与设计决策
├── docs/
│   └── history.md                   # 进度日志（每 session 记录）
└── industrial-cpp-kb-lab/
    ├── src/                         # Python 脚本（按 phase 编号）
    │   ├── 01_scan_files.py         # 扫描源码文件 → file_manifest.json
    │   ├── 02_extract_symbols.py    # ctags 符号提取 → symbol_index.json
    │   ├── 03_build_chunks.py       # 源码分块 → chunks.jsonl
    │   ├── 03_search.py             # BM25 + rg + ctags 融合检索（待实现）
    │   ├── 04_answer.py             # 检索 → LLM 问答（待实现）
    │   └── app.py                   # 一体化入口（待实现）
    ├── data/                        # 生成物（不入库）
    │   ├── file_manifest.json       # 269 个文件，36,409 行
    │   ├── symbol_index.json        # 3,072 条符号（含 end_line）
    │   └── chunks.jsonl             # 1,569 个 chunk
    ├── eval/                        # 检索评估集（入库）
    │   └── eval_questions.json      # Recall@K golden set（待创建）
    ├── notes/                       # 人工笔记（入库）
    │   └── smoothieware_code_map.md # Smoothieware 代码地图
    ├── prompts/                     # LLM prompt 模板（入库）
    │   └── code_qa.md               # 问答 prompt（待创建）
    └── repos/
        └── Smoothieware/            # 源码仓库（不入库）
```

---

## 快速上手

### 环境

```powershell
# 工具（已装）
git --version       # 2.45+
python --version    # 3.11+
rg --version        # ripgrep 15+
ctags --version     # Universal Ctags
```

### 一键重建索引

```powershell
cd industrial-cpp-kb-lab

# Step 1：扫描源码文件
python src/01_scan_files.py

# Step 2：提取符号（含 end_line）
python src/02_extract_symbols.py

# Step 3：分块
python src/03_build_chunks.py
```

三步完成后，`data/` 目录下有三个产物文件，可供检索和问答使用。

### 迁移到其他代码库

```powershell
python src/01_scan_files.py \
  --repo-root path/to/wire_bonder \
  --src-root  path/to/wire_bonder/src

python src/02_extract_symbols.py \
  --repo-root path/to/wire_bonder

python src/03_build_chunks.py
```

---

## 当前进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 | 环境与工具 | ✅ |
| 1 | 人工探索 + 代码地图 | ✅ |
| 2 | 文件扫描 + 符号提取 | ✅ |
| 3.1 | 源码分块 | ✅ |
| 3.2 | BM25 + rg 融合检索 | 🔄 下一步 |
| 4 | LLM 问答 | ⬜ |
| 5 | 一体化 CLI | ⬜ |
| 6 | 评估与升级决策 | ⬜ |
| 7 | 迁移到 wire bonder | ⬜ |

---

## 5 个练习问题

| # | 问题 | 关键文件 |
|---|------|---------|
| Q1 | G-code 从哪里进入系统？ | `SerialConsole.cpp`, `GcodeDispatch.cpp`, `Player.cpp` |
| Q2 | G-code 如何变成运动命令？ | `Robot.cpp` → `Planner.cpp` → `Conveyor.cpp` → `StepTicker.cpp` |
| Q3 | Motion / Planner / Stepper 代码在哪里？ | `src/modules/robot/`, `src/libs/StepTicker.cpp` |
| Q4 | halt / stop / emergency 逻辑？ | `Kernel.cpp::immediate_halt`, `KillButton.cpp`, `ON_HALT` 事件 |
| Q5 | 模块系统如何注册、触发、通信？ | `Module.h`, `Kernel.h::hooks[]`, `PublicData.cpp` |

---

## 技术栈

| 组件 | 选型 |
|------|------|
| 关键词检索 | ripgrep |
| 符号定位 + chunk 边界 | Universal Ctags（`--fields=+e` 给出 end_line） |
| 语义检索 | BM25（`rank_bm25`） |
| LLM | 通过 `LLM_PROVIDER` / `LLM_MODEL` 配置（Claude / OpenAI / 本地） |
| 语言 | Python 3.11 |

---

## 详细文档

- [PLAN.md](PLAN.md) — 完整执行计划（Phase 0–7，含验收标准）
- [architecture.md](architecture.md) — 系统架构与设计决策
- [CLAUDE.md](CLAUDE.md) — AI 协作速查手册
- [docs/history.md](docs/history.md) — 每次工作的详细进度日志
- [industrial-cpp-kb-lab/notes/smoothieware_code_map.md](industrial-cpp-kb-lab/notes/smoothieware_code_map.md) — Smoothieware 代码地图
