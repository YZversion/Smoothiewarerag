# 工业设备 C++ 代码知识库 — 实施计划

> 练手对象：Smoothieware（LPC17xx 上的 OOP C++ G-code/CNC controller）
> 最终目标：可复用到公司 wire bonder C++ 代码的「代码知识库」
> 复用方式：以后只需把 `repos/Smoothieware/` 换成公司 SVN checkout 的代码目录

---

## 总目标

输入一个 **模块名 / 函数名 / G-code / error·stop 关键词**，系统能返回：
**相关源码 + 函数 + 解释 + 引用路径（文件:行号）**。

这就是以后 wire bonder 知识库的雏形。

## 核心原则（贯穿所有 phase）

- [ ] 先证明「检索出来的上下文，是否足够让模型解释设备代码问题」，再谈系统化
- [ ] 第一版只用 `ripgrep + ctags + BM25 + LLM`，**不上** Milvus / Qdrant / LangChain / Agent / 知识图谱
- [ ] 不在 Smoothieware 仓库里乱写，所有产物放外层 `industrial-cpp-kb-lab`
- [ ] 不做嵌入式构建（ARM GCC / LPC1768 / 烧录都不是当前主线）
- [ ] 每个 phase 有明确「验收标准」，没达标不进入下一个 phase
- [ ] Phase 1 选出的 10 个重点文件只作为人工理解与评估种子；索引仍覆盖扫描到的全部源码文件
- [x] CodeGraph 只作为 Plan B 结构图谱实验：Smoothieware 小规模 A/B 已完成；不现在押注、不替代源码核查

---

## Phase 0 — 环境与素材准备

**目标：lab 目录建好、工具装好、Smoothieware clone 下来且能搜。**

### 0.2 安装基础工具（PowerShell）
- [x] `winget install Git.Git`
- [x] `winget install Python.Python.3.11`
- [x] `winget install BurntSushi.ripgrep.MSVC`
- [x] `winget install UniversalCtags.Ctags`
- [x] `winget install Graphviz.Graphviz`（可选）
- [x] Cursor 或 VS Code（手动安装）
- [ ] Doxygen（可选，留到 Phase 6）

### 0.3 验证工具
- [x] `git --version`
- [x] `python --version`
- [x] `rg --version`
- [x] `ctags --version`
- [x] `dot -V`

### 0.4 Clone 仓库
- [x] `git clone https://github.com/Smoothieware/Smoothieware.git`

**✅ Phase 0 验收**
- [x] 目录结构齐全
- [x] 五个工具命令都能正常输出版本号
- [x] `repos/Smoothieware/` 已存在且可被 `rg` 搜索

---

## Phase 1 — 人工探索 + 第一版代码地图

**目标：不写复杂程序，靠 rg 人工形成一张代码地图，并选出 10 个重点文件。**

### 1.1 只读 3 个文档（不要全读）
- [x] **README**：搞清楚是什么项目、什么语言、面向什么硬件
  - 记住：G-code interpreter + CNC controller，OOP C++，目标硬件 LPC17xx / Cortex-M3
- [x] **Module Example**：理解「everything is a module」，模块靠 event calls / event handlers 连接
- [x] **Motion Control**：理解 G-code → 运动转换，及 acceleration / junction deviation / step loss 等概念

### 1.2 固定 5 个练习问题（demo 第一版只围绕这 5 个）
- [x] Q1：G-code 从哪里进入系统？
- [x] Q2：G-code 如何变成运动命令？
- [x] Q3：Motion / Planner / Stepper 相关代码在哪里？
- [x] Q4：error / stop / halt / emergency 逻辑在哪里？
- [x] Q5：模块系统如何注册、触发、通信？

### 1.3 用 ripgrep 做第一次探索（记录高频文件）
- [x] `rg -n "class .*Module|public Module|on_module_loaded" .`
- [x] `rg -n "Gcode|GCode|gcode|M-code|MCode" .`
- [x] `rg -n "planner|Planner|motion|Motion|stepper|Stepper" .`
- [x] `rg -n "halt|stop|error|emergency|alarm|kill" .`
- [x] `rg -n "add_module|register_for_event|call_event|ON_|EVENT_" .`
- [x] 把每条命令里**出现频率最高、最核心的文件名**抄进笔记

### 1.4 写 `notes/smoothieware_code_map.md` 第一版
- [x] 项目定位（一句话）
- [x] 5 个核心问题列出
- [x] 按模块分区填「相关文件 + 作用」：
  - [x] Communication
  - [x] Robot / Motion
  - [x] G-code
  - [x] Kernel / Module System
  - [x] Error / Halt

### 1.5 选出第一版知识库输入
- [x] 选定 10 个重点源码文件作为知识库第一批输入
- [x] 说明：这 10 个文件是 canary / golden set 种子，不限制后续索引范围；Phase 2 起仍扫描全仓库源码

**✅ Phase 1 验收（= 文档里的「第一天验收标准」）**
- [x] clone 成功
- [x] 能用 rg 搜到 gcode / motion / planner / halt 相关代码
- [x] `smoothieware_code_map.md` 第一版写出
- [x] 10 个重点文件选定
- [x] （今天不上 Web UI、不纠结 LangChain vs LlamaIndex、不试图完全读懂 Smoothieware）

---

## Phase 2 — 文件扫描与符号提取

**目标：把「人工探索」变成「可重复的数据」，产出 file_manifest.json 和 symbol_index.json。**

### 2.1 `01_scan_files.py` → `data/file_manifest.json`
- [x] 遍历 `repos/Smoothieware/`，收集 `.cpp/.h/.hpp/.c` 文件
- [x] 记录：路径、大小、行数、所属一级目录
- [x] 过滤掉无关目录（build 产物、第三方、文档图片等）
- [x] 输出 `file_manifest.json`

### 2.2 `02_extract_symbols.py` → `data/symbol_index.json`
- [x] 用 ctags 提取 C++ 的 **class / function / macro / enum**
- [x] 解析 ctags 输出为结构化记录：symbol 名、类型、文件、行号
- [x] 输出 `symbol_index.json`
- [x] 抽查 Phase 1 里的核心符号（如 Planner、Stepper、on_gcode_received 之类）能否被检索到

**✅ Phase 2 验收**
- [x] `file_manifest.json` 覆盖全部源码文件
- [x] `symbol_index.json` 能按符号名查到「文件:行号」
- [x] 5 个练习问题相关的关键符号都能被定位

---

## Phase 3 — 分块与检索（BM25）

**目标：建立可被关键词检索的 chunks，并实现 `03_search.py`（ripgrep + ctags + BM25 融合）。**

### 3.1 分块 → `data/chunks.jsonl`
- [x] 新增 `03_build_chunks.py`：读取 `file_manifest.json` + `symbol_index.json`
- [x] `.cpp/.c` 优先按函数/方法实现切分：以 `kind == function` 为主，避免被 `prototype`、`macro`、`typedef` 截断真实函数体
- [x] 函数结束行优先级：ctags end line（如可用） → 简单 brace matching 找 `{...}` → 下一个 function symbol 前一行 → 固定窗口兜底
- [x] `.h/.hpp` 优先按 `class` / `struct` 定义切分；保留 public/protected/private、方法声明、成员变量；不要把每个 prototype 切成过小 chunk
- [x] 为每个源码文件生成一个 file overview chunk：文件路径、top_dir、主要 class/function 列表、前若干 include，用来回答”代码在哪里/模块结构是什么”
- [x] 过长函数或类 chunk 再切为 180 行子窗口，overlap 40 行；没有符号的文件回退为 100 行窗口，overlap 20 行
- [x] 每个 chunk 带元数据：`id`、`type`（function/class/file_overview/fallback）、文件路径、起止行号、所属符号、符号类型、scope/class、文本
- [x] 每个 chunk 文本前加 context header：`symbol_start`（定义行）+ `chunk_lines`（本子窗口行范围）
- [x] 输出 `chunks.jsonl`

### 3.2 `03_search.py`（融合检索）
- [x] 实现代码友好的 tokenizer：保留原始 token，同时拆 snake_case、camelCase、路径片段和 `::`/`->` 附近标识符
- [x] 中文问句 `QUERY_HINTS`：**按问题意图触发**（入口组仅 `进入`/`入口`，避免与运动链题互污染）
- [x] 流程题 `on_*` 事件处理函数泛化加权（符号频率抑噪 + hint 一致性；禁止 per-file 硬编码）
- [x] BM25 索引（`rank_bm25`）建在 chunks 上（内存）
- [x] 检索流程：关键词 → BM25 召回 chunk + ctags 精确符号定位 + ripgrep 兜底
- [x] 融合排序：符号 / rg / BM25 加权；chunk id 去重；`.cpp` function 优先
- [x] 返回结果含「文件:行号」、type、source、score、snippet
- [x] `--eval` 读 `eval_questions.json`，报 Recall@5 / Recall@10

### 3.3 context bundle
- [x] `search(..., bundle=True)`：primary + overview + 配对 `.h` class
- [ ] caller/callee 接入 context bundle（Plan B CodeGraph 已独立验证；暂不接入主线）

**✅ Phase 3 验收**
- [x] 输入关键词 → chunk + 引用路径
- [x] Recall@5 ≥ 4/5（实测 5/5）
- [x] Q2 Top-10 覆盖 ≥3 核心运动文件
- [x] Q1–Q3 bundle 含 overview 或 header

---

## Phase 4 — LLM 代码问答

**目标：把检索到的上下文喂给 LLM，得到「源码 + 解释 + 引用」式回答。**

### 4.1 `prompts/code_qa.md`
- [x] 写问答 prompt 模板：角色=工业设备 C++ 代码助手
- [x] 要求：基于给定上下文回答、必须给出 file:行号引用、上下文不足时明确说不知道

### 4.2 `04_answer.py`
- [x] 串起 `03_search.py`（bundle=True）→ 拼接上下文 → 调 LLM
- [x] LLM 通过 `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY`（OpenAI 兼容 SDK）
- [x] 输出：解释 + 源码片段 + 引用；`validate_citations()` 校验引用
- [x] `--demo` 跑通 5 个练习问题

**✅ Phase 4 验收**
- [x] 5 题回答指向真实代码并附引用
- [x] 基于检索上下文；引用校验为辅助 WARN

---

## Phase 5 — 整合成 Demo

**目标：`app.py` 把整条链路打通，形成一个可演示的最小知识库。**

### 5.1 `app.py`
- [x] 一个入口：输入关键词 → 检索 → LLM → 输出（`--search-only` / `--demo`）
- [x] **Rich REPL**（无参数启动）；streaming 回答；`--json` 纯文本管道
- [x] 默认 `--top-k 8`；CLI only；输出：解释 + Sources 表

### 5.2 自测脚本
- [x] `run_regression.py`；`app.py --test` 一键 Recall + bundle 回归

**✅ Phase 5 验收**
- [x] `python src/app.py "问题"` 返回源码+解释+引用
- [x] wire bonder 可复用雏形（换 `--repo-root` 重跑管道）

---

## Phase 6 — 评估与可选升级

**目标：先量化效果，再决定要不要加重型组件。**

### 6.1 评估
- [x] 扩充练习问题到 30 题（5 `tune` + 25 `holdout`），见 `eval/eval_questions.json` v2
- [x] `03_search.py --eval` 输出 **coverage@K**（`|hit|/|expected|`）与 tune/holdout 分项
- [x] 记录失败案例到 `notes/eval_failures.md`（已修复 / open 对照表）
- [x] 区分「检索 Recall」与「LLM 答案准确度」→ `notes/phase6_conclusion.md`、`src/eval_answer_layer.py`
- [x] **检索层冻结**：gate = 全体 **mean cov@5 ≥ 70%**；不在 holdout 上微调（H4 等接受 open）

### 6.2 可选升级（按需，**不阻塞知识库验收**）

> 决策见 `notes/phase6_conclusion.md`：当前方案够用；除 Plan B 笔记实验已完成外，下列主线增强 **暂缓**。验收清单 → `notes/kb_acceptance.md`。

- [ ] 向量检索（仅当 BM25 明显不够时）— **暂缓**
- [ ] Doxygen 生成文档 + Graphviz 调用关系图 — **未做**
- [x] 调用链 / 模块依赖图 — **Plan B CodeGraph 笔记实验已完成**（未接入主 `app.py`）
- [ ] 命令号 / 事件码 → 处理器索引 — **Plan C 可选**（用于 H4 这类“谁处理 G28/报警码/事件码”的分发查找）
- [ ] 弱 Agent 多跳检索 — **Plan D 延期实验**（仅当 Phase 8–10 + 确定性多跳仍解决不了量化流程题时，分支隔离）
- [ ] 简单 Web UI — **未做**（REPL 已满足 demo）

**✅ Phase 6 / 知识库验收**
- [x] 有一份「当前方案够不够用」的量化结论（`notes/phase6_conclusion.md`）
- [x] 升级决策有数据支撑：检索冻结；向量暂缓；CodeGraph 可选实验
- [x] 验收清单与实测记录（`notes/kb_acceptance.md`）
- [x] 自动化回归 PASS：`03_search.py --eval`（mean cov@5 73%）+ `run_regression.py --top-k 8`

---

## 外部项目偷师原则

> 只吸收能增强「工业 C++ 代码问答知识库」的检索工艺、引用严谨度与 CLI 体验；不因为参考项目高 star 就引入重框架。

| 项目 | 借鉴点 | 明确不借 |
|------|--------|----------|
| [Aider repo map](https://aider.chat/2023/10/22/repomap.html) / [`repomap.py`](https://github.com/Aider-AI/aider/blob/main/aider/repomap.py) | `def/ref` 图、personalized PageRank、token budget 填 context | 不上向量库；不把图谱当事实源 |
| [PaperQA2](https://github.com/Future-House/paper-qa) | grounded answer、citation / coverage checklist、答案完整性自检 | 不偷默认 embedding / Numpy vector store 栈 |
| [AutoCodeRover](https://github.com/AutoCodeRoverSG/auto-code-rover) / [Moatless Tools](https://github.com/aorwall/moatless-tools) | `search_class` / `search_method` 这类 AST-aware 结构化检索接口 | 不引入复杂 agent / 自动修 bug 流程；先基于 ctags 实现 |
| [free-code](https://github.com/freecodexyz/free-code)（[FEATURES](https://github.com/freecodexyz/free-code/blob/main/FEATURES.md)、[commands.ts](https://raw.githubusercontent.com/freecodexyz/free-code/main/src/commands.ts)） | 命令注册表、能力开关、状态/预算可见性、交互历史体验 | 不做 remote bridge / voice / MCP plugin system；不引入其 telemetry / guardrail 叙事 |

---

## 下一阶段路线图（Phase 8–12）

> Phase 7（CI & 回归纪律）已完成。后续执行顺序：**8 → 9 → 10 → 11 → 12**。每项做完跑全量 `--eval` 对账；tune 题不得回归，holdout 提升需区分真改进 vs 过拟合。  
> 参考：`notes/phase6_conclusion.md`、外部评审 7.5/10（CI + 符号对齐 + PageRank）以及上方外部项目偷师原则。

| Phase | 主题 | 预估 | 阻塞关系 |
|-------|------|------|----------|
| **8** | AST-aware 符号检索 + dispatch index | 已完成 | Phase 9 的符号 / dispatch 地基 |
| **9** | Repomap PageRank（Aider 式图排序） | 2–3 天 | 依赖 8 的符号 / chunk 质量 |
| **10** | LLM 答案完整性（PaperQA2 式 checklist） | 半天–1 天 | 可与 8 并行 |
| **11** | Wire bonder 迁移 | 数天 | 7–10 不必全完，但 **7（CI）必须先做** |
| **12** | CLI 产品化（free-code 可取部分） | 1–2 天 | 不阻塞 8–11，可并行 |

Plan B（CodeGraph）已完成笔记实验；Plan C 并入 **Phase 8.3**，不单独占 phase 号。

---

## Phase 7 — CI & 回归纪律自动化

**目标：把已有 eval gate 变成「每次 push 强制执行」，纪律从抽屉里拿出来。**

### 7.1 GitHub Actions
- [x] 新增 `.github/workflows/eval.yml`
- [x] 触发：`push` / `pull_request` → `main`（及 feature 分支）
- [x] 步骤：CI 内 shallow clone Smoothieware + 重建索引（`data/` / `repos/` 不入库）
- [x] 跑 `python src/03_search.py --eval`；**mean cov@5 < 0.70 → job fail**
- [x] 跑 `python src/run_regression.py --skip-llm --top-k 8`（CI 无 `LLM_API_KEY` 时跳过 LLM 引用段）
- [x] README 加 CI badge；本地镜像：`scripts/ci_build_and_eval.ps1`

### 7.2 本地钩子（可选，与 Actions 互补）
- [x] `.cursor/hooks.json` + `remind_eval.sh`：改检索/eval 相关文件后提示跑 `--eval`
- [x] 本地 CI 镜像：`industrial-cpp-kb-lab/scripts/ci_build_and_eval.{ps1,sh}`

### 7.3 产物纪律
- [x] `.github/pull_request_template.md`：eval 变更须附 `--eval` 前后对比
- [x] 禁止为通过 CI 而改 gate 阈值或 holdout 特判（文档 + PR 模板）

**✅ Phase 7 验收**
- [x] GitHub Actions Eval workflow 绿（push `main` 通过：clone + 索引 + `--eval` + regression）
- [x] fork 者 clone 后看 Actions 即知项目健康度（workflow + badge + 本地镜像脚本）

---

## Phase 8 — AST-aware 符号检索 + dispatch index

**目标：治 phase6 真瓶颈——「文件到了、符号 chunk 没到」；context sym_cov 从 ~50% 提升。**

### 8.1 Chunk / ctags 边界审计
- [x] 对 Q2/Q3/Q4/Q5 逐题列出：expected symbol → 对应 chunk id / 是否缺失（见 `notes/phase8_symbol_dispatch_audit.md`）
- [x] 检查 `02_extract_symbols.py` 的 `end_line` 是否传入 `03_build_chunks.py`
- [x] 修复方向收敛：本轮未发现需重写 chunk 边界的通用 bug；长函数子窗口已保留 `symbol_start`
- [x] 重建 `chunks.jsonl` 后跑 `--eval`；记录 sym_cov 前后（54% → 71%，见 `eval_answer_layer.py`）

### 8.2 确定性符号检索（AST-aware / search_method）
- [x] 借鉴 AutoCodeRover / Moatless 的结构化检索接口，在 `03_search.py` 内部新增 `search_method()` / `search_class()`，先基于 `ctags` + `symbol_index.json` 实现，不引入复杂 agent
- [x] query 含 `Class::method`、`Class.method` 或唯一 symbol 精确命中时 → **直接拉该符号 chunk**（不依赖 BM25 碰运气）
- [x] `kb symbol` 继续作为确定性符号入口；普通 query 若命中确定性路径，也与 symbol / BM25 / rg 融合排序
- [x] 支持 eval 中符号类问句（H1/H5/H6）稳定命中函数体
- [x] 权重：确定性符号命中 ≥ BM25 同名子窗口；方法 chunk 优先于构造函数和 header class
- [x] 仍禁止 expected_files 文件名硬编码

### 8.3 Plan C — 命令 / 事件分发索引（并入本 phase）
- [x] 新增 `src/05_extract_dispatch_index.py`（见下方 Plan C 细则）
- [x] 输出 `data/dispatch_index.json`（当前 175 entries / 110 fixed commands）
- [x] `03_search.py` 内部新增 `search_dispatch()`：query 含 `G28` / `M104` / 报警码 / 事件码 / 命令号时先查 dispatch，再融合 BM25 / symbol / rg
- [x] `dispatch_index.json` 专治 `G28/M104/报警码/事件码 -> handler`，必须返回条件判断 / case / 命令表等证据行
- [x] H4 及新增 5 道分发题进入 eval holdout（不靠 homing hint）

**✅ Phase 8 验收**
- [x] `eval_answer_layer.py`：mean sym_cov@trim **≥ 65%**（基线 54%，当前 71%）
- [x] H4 Recall@5 命中 `Endstops.cpp`（不靠文件名特判；dispatch evidence line 命中）
- [x] tune 5 题 Recall@5 仍为 5/5；35 题 mean cov@5=94%，不低于冻结时基线 87%

---

## Phase 9 — Repomap PageRank

**目标：把 `call_graph` + `W_GRAPH` 从 flow-intent 一跳启发式，升级为 Aider 式 **personalized PageRank** 填 context 排序。**

### 9.1 图构建升级
- [ ] 研读 Aider `repomap.py` 思路（def/ref + 依赖边）
- [ ] 新建 `03_build_repomap.py`（优先于继续塞 `03_build_callgraph.py`）：边权来源 = mention / include / same-file / dispatch
- [ ] 输出 `data/repomap_scores.json`；保留运行时 PageRank 缓存空间，但产物优先可复现
- [ ] PageRank 只参与排序和 context 填充，不替代源码 / chunk / dispatch 证据

### 9.2 检索融合
- [ ] 先实现确定性多跳 baseline：仅对 `flow_intent_query()`，沿 call_graph / repomap 固定扩展 1 跳（必要时 A/B 2 跳），不让 LLM 参与跳数决策
- [ ] query tokens + primary hits + symbol hits → personalized PageRank seeds
- [ ] 用排名替代/增强 `search_graph()` 的固定 `W_GRAPH` 加分
- [ ] **token budget 意识**：与 `trim_context_hits(max=8)` 对齐，按 PageRank 序填充
- [ ] 增加 `ENABLE_REPORANK` 开关，便于 `--eval` A/B；默认关闭直到验收通过

### 9.3 对账纪律
- [ ] 改前记录 35 题（5 tune + 30 holdout）各 cov@5 / sym_cov / 确定性多跳增益
- [ ] 改后：tune 不得挂；holdout 提升需排除「hint 作弊」类回归

**✅ Phase 9 验收**
- [ ] Q2 @5 cov **≥ 4/5** 且 GcodeDispatch 进 top-5（或文档说明仍 open 的原因）
- [ ] 多文件流程题（Q2–Q5）mean cov@5 **≥ 基线 + 5pp**
- [ ] 仍无向量库；图排序可 `--eval` 开关对比（`ENABLE_REPORANK`）

---

## Phase 10 — LLM 答案完整性

**目标：治 phase6「15/15 引用合法，但仅 40% 列全期望文件」——改 prompt / pipeline，不加检索复杂度。**

### 10.1 Prompt & 后处理
- [ ] 参考 PaperQA2：强制「列全 context 中每个相关 primary 文件」清单段
- [ ] `prompts/code_qa.md`：增加自检句——「是否遗漏 context 内模块」
- [ ] 可选：`04_answer.py` 两阶段——先生成 `Relevant files / symbols checklist`，再写解释（低成本）
- [ ] `validate_citations()` 继续只负责行号合法性；新增 `validate_answer_coverage()` 检查 context primary 文件是否被答案覆盖

### 10.2 度量
- [ ] `eval_answer_layer.py` 报告 **files_in_answer / context_primary_files / expected_files**，写入 CI artifact 或 notes
- [ ] 目标：tune 5 题 **≥ 4/5 列全文件**；全体 **≥ 55%**

### 10.3 引用与完整性分离
- [ ] CI 继续分轨：检索 gate（Phase 7） vs LLM 引用（有 key 时 nightly）vs 完整性（报告项）

**✅ Phase 10 验收**
- [ ] `run_regression.py --top-k 8` tune citation 仍 5/5
- [ ] `eval_answer_layer.py --llm`：all files cited **≥ 55%**（基线 40%）

---

## Phase 11 — 迁移到公司 wire bonder 代码

**目标：把验证过的 lab 直接套到真实设备代码上。**

### 11.1 替换素材
- [ ] 公司 SVN checkout 出代码目录
- [ ] 不需要物理替换 `repos/Smoothieware/`；通过 `--repo-root` / `--src-root` 指向公司代码目录
- [ ] 重跑 Phase 2~5 全流程，输出到独立 `data/<project>/` 或按项目名分目录

### 11.2 适配 wire bonder 模块体系
- [ ] 把模块分区从 CNC 改成设备真实分类：
  - [ ] 运动控制
  - [ ] 视觉
  - [ ] IO
  - [ ] 报警
  - [ ] 配方
  - [ ] 流程
  - [ ] UI
- [ ] 针对设备重写 5~10 个核心练习问题（定位、丢步、回零、限位、报警等）
- [ ] 新 eval：**5 tune + 10~25 holdout**，规则同 Smoothieware（coverage@K gate ≥70%）

### 11.3 合规与安全
- [ ] 确认公司代码可在本地/所选 LLM 环境处理（数据外发合规）
- [ ] 必要时改用本地模型 / 内网部署
- [ ] Phase 7 CI 对公司仓库 fork 或私有 runner 策略写一句

**✅ Phase 11 验收**
- [ ] 对公司代码，能用同一套 `kb ask` / `kb tui` 返回「源码+解释+引用」
- [ ] 至少 5 个真实设备问题被正确回答
- [ ] Smoothieware eval 仍绿（回归不回归）

---

## Phase 12 — CLI 产品化（free-code 可取部分）

**目标：借鉴 `free-code` 的 CLI 产品化手艺，让 `kb` 更像可长期使用的工程工作台；不改变检索主线，不引入 remote bridge / voice / MCP plugin system / 大型 agent task system。**

### 12.1 命令注册与 help 统一
- [ ] 建立统一 `CommandSpec` 注册表，供 Typer、REPL、TUI help 共享
- [ ] 为命令增加 availability / capability 标记：需要 LLM、需要索引、仅交互模式、实验功能等
- [ ] `COMMANDS`、REPL `/help`、TUI help 不再各写一份，避免命令漂移

### 12.2 状态与健康检查
- [ ] 新增 `kb status`：显示 repo、chunks、symbols、index age、last eval、model/provider、LLM key 状态
- [ ] 新增 `kb doctor`：检查 `rg` / `ctags` / requirements / data artifacts / `.env`，并给出修复命令
- [ ] status / doctor 只读，不自动改环境、不写全局配置

### 12.3 历史与快捷工作流
- [ ] `/history` 支持按编号重跑上一次 search / ask / sources
- [ ] REPL/TUI 增加 fuzzy history picker 或 quick search（先复用现有 `session_history.jsonl`）
- [ ] `export` 保持 Markdown 输出，同时在导出中附 sources / citation check / coverage check 摘要

### 12.4 Context / token budget 可见性
- [ ] `ask/search --explain` 显示 context slots、估算 token、primary / bundle 比例
- [ ] streaming dashboard 增加检索阶段状态：primary hits、bundle hits、trim 后 chunks
- [ ] 不做真实计费系统，只做本地估算和可解释性展示

**✅ Phase 12 验收**
- [ ] `kb --help`、REPL `/help`、TUI help 来自同一命令定义
- [ ] `kb status` / `kb doctor` 在无 LLM key 时也能清楚说明可用能力
- [ ] 能从 `/history` 重跑一条历史 query，并导出带 sources 的 Markdown
- [ ] CLI 改动不影响 `python src/03_search.py --eval` 与 `run_regression.py --skip-llm`

---

## Cursor Skills / 插件与自动化建议

> 不替代 Phase 7 GitHub Actions；skills 提升 **日常开发 + Agent 协作** 效率。

### 强烈推荐（与本仓库直接相关）

| Skill / 能力 | 用途 | 何时用 |
|--------------|------|--------|
| **[create-rule](.cursor/rules/industrial-kb.mdc)** / `create-rule` | 维护 `industrial-kb.mdc`：冻结检索、禁止文件名特判、eval 驱动 | 改 `03_search.py` / 加权重前 |
| **`create-hook`** | 项目 hook：改 eval 集 / 检索权重后提醒跑 `--eval` | Phase 7.2 本地互补 |
| **`babysit`** | PR 红 CI 时循环修 eval 回归 | 接好 Actions 之后 |
| **`ci-investigator`** | 单条 CI fail 根因摘要 | Actions 首红调试 |
| **`review-bugbot`** | 改检索/分块逻辑前的 diff 审查 | Phase 8–9 大改前 |
| **`split-to-prs`** | 把 Phase 8/9 拆成「chunk 修复」「PageRank」独立 PR | 避免巨型 PR |

### 按需使用

| Skill | 用途 |
|-------|------|
| **`loop`** | 定时跑 `kb eval` / `run_regression.py`（本地 nightly） |
| **`automate`** | Cursor Automations：push 后自动跑 eval 报告（与 Actions 二选一或并存） |
| **`create-skill`** | 把「跑 eval + 解读 cov 表」固化成项目 skill |
| **`canvas`** | eval 结果 dashboard、Phase 8 符号缺失矩阵可视化 |
| **`sdk`** | 仅当要把 `kb ask` 接到外部 CI bot 时 |

### VS Code / Cursor 扩展（非 skill，但实用）

| 扩展 | 用途 |
|------|------|
| **Python** + **Pylance** | `kb_cli` / 管道脚本类型检查 |
| **ripgrep**（内置/终端） | 与 `03_search` 行为对照 |
| **GitHub Pull Requests** | 看 Actions 与 review |
| **Error Lens** | 改 chunk 脚本时快速看语法问题 |

### 不建议现在引入

- LangChain / LlamaIndex 插件化 RAG 模板  
- 向量库 MCP（与 phase6「暂缓向量」决策冲突）  
- 通用「PDF RAG」类 Cursor 规则（与 C++ 代码库无关）

---

**目标：验证对 C++ 设备控制项目，图结构索引是否比普通 `rg` / BM25 RAG 更快找到模块、函数、调用关系和影响范围。**

这个 Plan B 不替代 Phase 3–5 主线。它是一个克制的小实验：先在 Smoothieware 上比较 **A. ripgrep/BM25** 和 **B. CodeGraph/代码图谱**，证明有价值后再考虑是否接入 wire bonder 知识库。

### B.1 为什么值得研究
- [x] 帮助理解大型 C++ 项目的模块结构
- [x] 帮 AI Agent 减少反复 `grep` / 读文件造成的上下文爆炸
- [x] 支持查询函数定义、调用者、被调用者、依赖关系和影响范围
- [x] 未来可作为 wire bonder 知识库的「代码结构层」

### B.2 明确边界
- [x] CodeGraph 解决「代码结构怎么找」，不解决「设备业务怎么懂」
- [x] 它不能自动理解 wire bonding 工艺、报警排查、维修经验和现场日志
- [x] 对 C++ 宏、条件编译、函数指针、回调、MFC 消息映射、动态派发、跨 DLL 调用可能漏关系或错关系
- [x] 图谱结果只能作为候选线索，最终事实仍以源码、编译配置和工程师确认为准
- [x] 现在不研究全部功能，只做 5 个问题的 A/B 测试

### B.3 候选工具判断标准
选择 CodeGraph / code graph 工具时，只看 6 个指标：

- [x] 是否支持 C/C++
- [x] 是否本地运行
- [x] 是否不需要上传代码
- [x] 是否能输出函数 / 类 / 调用关系 / include 关系
- [x] 是否能被 Codex / Cursor / Claude Code 通过 MCP 或 CLI 调用
- [x] 是否能导出或查询结构化结果，而不只是漂亮图

满足前 4 个，值得试；满足 6 个，才考虑深度集成。

本次验证工具：`@colbymchenry/codegraph` v1.1.1。最小索引结果：546 files、7,440 nodes、16,690 edges；CLI 支持 `query` / `explore` / `callers` / `callees` / `impact` / `status`。注意：该工具默认在目标 repo 下创建 `.codegraph/`，本次只作临时实验索引，结束后清理。

### B.4 Smoothieware A/B 实验问题
用同一组问题比较 `rg/BM25` 与 `CodeGraph`：

- [x] G-code 的入口文件在哪里？
- [x] `Gcode` 类 / 函数被哪些模块调用？
- [x] Motion planner 相关核心类有哪些？
- [x] halt / error / stop 的调用链在哪里？
- [x] 修改某个函数后可能影响哪些模块？

### B.5 实验产物
不要把 CodeGraph 直接混入现有 RAG 主流程，先分开记结果：

```
industrial-cpp-kb-lab/
├── notes/
│   ├── smoothieware_rg_findings.md
│   ├── smoothieware_codegraph_findings.md
│   └── comparison.md
└── eval/
    └── eval_questions.json
```

- [x] `smoothieware_rg_findings.md`：记录 `rg` / BM25 找到的文件、符号、证据
- [x] `smoothieware_codegraph_findings.md`：记录 CodeGraph 找到的 symbols、callers、callees、依赖关系
- [x] `comparison.md`：比较哪个问题 CodeGraph 更强，哪个问题普通搜索更强，是否值得迁移到 wire bonder

### B.6 示例流程（已确认 `@colbymchenry/codegraph` v1.1.1）
本次已确认官方 README 和版本，并完成最小试验：

```powershell
cd C:\Users\14390\Desktop\Code\Smoothiewarerag\industrial-cpp-kb-lab\repos\Smoothieware
npm install -g @colbymchenry/codegraph
codegraph init
```

然后让 Agent 只问结构问题，例如：

```text
Use CodeGraph to identify the main G-code processing entry points in this repository.
Return files, symbols, and call relationships. Do not guess.
```

```text
Use CodeGraph to trace halt/error/stop related symbols.
Return the most relevant functions and their callers/callees. Do not guess.
```

### B.7 Plan B 验收
- [x] 对 5 个 Smoothieware 结构问题完成 A/B 对比
- [x] `comparison.md` 明确列出：CodeGraph 强项、弱项、误报/漏报案例
- [x] 能回答「是否值得在 wire bonder 代码上做小模块试验」
- [x] 未证明价值前，不接入主 `app.py`，不把主线改成知识图谱系统

结论：值得在 wire bonder 上做“小模块结构层试验”，尤其用于 caller / callee / impact radius；但不适合单独解决 `G28` / 报警码 / 事件码 → handler 这类分发查找，后者进入 Plan C。

---

## Plan C — 命令/事件分发索引实验

**目标：解决 CodeGraph 和普通 BM25 都不擅长的“谁处理某个命令号 / 事件码 / 报警码”问题。**

这个计划来自 H4 复盘：

> 问题：`回零 / homing / G28 命令在哪里处理？`
>
> 根因：`回零` 被 tokenizer 丢掉；`homing` / `g28` 找不到同名符号；`Endstops` 的真实处理函数叫 `home` / `process_home_command`，判断藏在 `on_gcode_received` 函数体内部。CodeGraph 只能看到 `GcodeDispatch -> ON_GCODE_RECEIVED -> 多个模块` 的扇出，不能直接判断哪个模块处理 `G28`。

### C.1 为什么不是加 homing hint group

- [ ] 不把 `G28 -> Endstops` 写成 Smoothieware 专属 hint；这会提高 H4 分数，但不利于 wire bonder 迁移
- [ ] 不把 expected_files 文件名反写进检索器
- [ ] 把 H4 归类为“命令分发查找”问题，而不是“调用链追踪”问题

### C.2 通用抽取目标

产出一个结构化索引，例如：

```json
{
  "command": "G28",
  "kind": "gcode",
  "handler_file": "src/modules/tools/endstops/Endstops.cpp",
  "handler_symbol": "Endstops::on_gcode_received",
  "target_symbol": "Endstops::process_home_command",
  "line": 1042,
  "evidence": "if (gcode->g == 28) ...",
  "confidence": "static-pattern"
}
```

未来 wire bonder 可迁移为：

- [ ] 指令号 / 菜单命令 / recipe action → handler
- [ ] 报警码 / error code → 抛出点与处理器
- [ ] 事件名 / 消息 ID / Windows message / MFC command ID → handler
- [ ] PLC / IO / station state code → 状态处理函数

### C.3 Smoothieware 最小实验

- [x] 新增 `src/05_extract_dispatch_index.py`
- [x] 扫描所有 `on_gcode_received` / `on_console_line_received` / shell command handler 函数体
- [x] 提取常见模式：
  - [x] `gcode->g == 28`
  - [x] `gcode->m == 17`
  - [x] `switch(gcode->g)` / `case 28`
  - [x] `has_letter('G')` + `get_value('G')`（动态值标记为 unknown，不让 LLM 猜）
  - [x] shell 命令表 / 字符串命令分发表
- [x] 输出 `data/dispatch_index.json`
- [x] `03_search.py` 在 query 含 `G28` / `M17` / 命令号时，先查 dispatch index，再融合 BM25 / symbol / rg

### C.4 验收问题

- [x] H4：`回零 / homing / G28 命令在哪里处理？` 在 Recall@5 命中 `Endstops.cpp`
- [x] 新增至少 5 个命令分发题，不靠文件名硬编码：
  - [x] `M17` / 电机使能
  - [x] 温度相关 `M104` / `M109`
  - [x] 激光相关 `M221`
  - [x] 电流控制 `M907`
  - [x] SimpleShell 字符串命令（`M20` / `M30`）
- [x] 对每条命中返回证据行：条件判断 / case / 命令表位置
- [x] 如果静态模式抽不到，必须标记 `unknown`，不让 LLM 猜

### C.5 与 Plan B 的边界

| 能力 | Plan B CodeGraph | Plan C Dispatch Index |
|------|------------------|-----------------------|
| 函数定义 / 调用者 / 被调用者 | 强 | 弱 |
| 调用链追踪 | 强 | 弱 |
| 事件总线扇出 | 可显示候选 | 需要结合命令条件 |
| `G28` / 报警码 / 命令 ID 谁处理 | 弱 | 强 |
| wire bonder 迁移价值 | 代码结构层 | 命令/报警/事件分发层 |

结论：Plan B 继续作为“代码结构层”实验；Plan C 作为“命令分发层”实验，**已并入 Phase 8.3**。两者互补，不互相替代。

---

## Plan D — 弱 Agent 多跳检索实验（延期 / 分支隔离）

**定位：** 这是一个延期执行的可选实验，不是 Phase 8–12 主线待办。弱 Agent 只在确定性检索扎实之后，用来验证“LLM 判断是否再搜一跳”能否解决一类被量化证明的多文件流程题；事实与引用仍永远来自确定性检索。

### D.0 先定义：这里的“弱 Agent”是什么

- [ ] 不是强 Agent：不让 LLM 自主规划任务、调多种工具、自定终止，也不让它直接给事实
- [ ] 是受控多跳：检索 → LLM 判断“信息够不够 / 还要搜什么关键词” → 最多再搜 1–3 跳 → 用检索到的 file:line context 作答
- [ ] LLM 只决定“要不要再搜、搜什么 query”；每一跳的候选文件、行号、代码片段仍来自 `03_search.py` / repomap / dispatch 等确定性路径
- [ ] 默认不接入 `kb ask`；只能通过实验开关触发，例如未来 `kb ask --agentic` 或 `ENABLE_WEAK_AGENT=1`

### D.1 入口门槛（全部满足才允许开始）

| 门槛 | 当前项目适配版 | 为什么 |
|------|----------------|--------|
| G1 | Phase 8 完成：符号 chunk 对齐 + dispatch index 验收通过，`mean sym_cov@trim >= 65%` | 否则 agent 多搜几跳也只是多拿错 / 漏对齐的 chunk |
| G2 | Phase 9 完成：确定性多跳 baseline 与 Repomap PageRank 已实现并 eval 过 | 弱 Agent 必须有可复现对照组 |
| G3 | Phase 10 完成：citation 合法性与 answer coverage 分层指标可跑 | 否则无法判断是检索赢了还是答案层漏写 |
| G4 | CI eval 绿，且 `03_search.py --eval` / `run_regression.py --skip-llm` 可稳定复现 | 没有基线就没有对账尺子 |
| G5 | `docs/history.md`、`notes/eval_failures.md` 或未来飞轮日志中，反复出现“单次 / 确定性多跳仍答不好的多文件流程题” | 数据指明该上的唯一合法理由 |

如果 G1–G5 没全绿，本计划停留在文档层。提前做弱 Agent = 在不可复现复杂度上花时间，违背本项目第一原则。

### D.2 前置：确定性多跳必须先做

- [ ] 触发：仅对 `flow_intent_query()`（流程 / 触发 / 入口类），非流程题继续走单次检索
- [ ] 机制：第一批检索命中函数后，沿 call_graph / repomap 固定扩展 caller / callee / mention / dispatch 1 跳，把扩展 chunk 并入候选重排
- [ ] 跳数：先固定 1 跳；若 A/B 证明不够，再试固定 2 跳；全程无 LLM 决策
- [ ] 代价：不新增 LLM 调用，保持毫秒级扩展、完全可复现、可 `--eval`
- [ ] 若确定性多跳已解决流程题缺口，则 Plan D 终止；这是更好的结局，不是失败

### D.3 最小弱 Agent 实现（仅当 D.2 不够）

- [ ] 在 `04_answer.py` 外包一层 `agentic_answer()`；不改 `03_search.py` 的单次检索语义，不改默认 `answer()`
- [ ] 循环：检索 → LLM 判定 `enough / need_more` + 下一跳 query → 追加检索 → 最终 answer
- [ ] 最大跳数 2–3，硬上限；LLM 说 enough 立即停
- [ ] decision temperature = 0；任一跳失败则回退单次检索结果
- [ ] 每跳事实全部来自确定性检索；LLM 不允许发明文件、行号、符号
- [ ] 必须配套 LLM 超时 / 重试、streaming 状态展示、完整决策日志（每跳 query、判断、命中新文件、最终跳数）

### D.4 非确定系统 eval 方法

- [ ] 多次跑：每道 agent eval 题跑 N 次（建议 N=5），报告 pass rate / 方差，而不是单次 PASS / FAIL
- [ ] 分层归因：检索层记录最终文件集 vs expected_files 的 cov@K；决策层记录每次“再搜一跳”是否新增 expected 文件
- [ ] 统计有效跳率：有效跳 = 带来新 expected 文件 / 符号；白跳率高说明 agent 在乱搜
- [ ] 永远对照三组：单次检索、确定性多跳、弱 Agent；同时记录 cov@5、p95 latency、LLM 调用数、可复现性

### D.5 上线门槛（全部满足才允许从分支进主线）

- [ ] 多文件流程题上，弱 Agent 相对确定性多跳有显著净收益：建议 `Δcov@5 >= +10pp`，或解决 ≥2 个长期 open flow case
- [ ] 稳定：N 次运行 pass rate 高、方差低；同题不反复横跳
- [ ] 白跳率低：建议 <30%，多数“再搜”确实补进 expected 文件 / 符号
- [ ] p95 延迟可接受，streaming 下工程师体感不崩；LLM 调用数均值 ≤3
- [ ] 触发范围隔离生效：非流程题不变慢、不变错
- [ ] 并发实测可接受：至少 5 并发下吞吐 / 排队可用

### D.6 放弃条件（任一触发即砍）

- [ ] 确定性多跳已经够好
- [ ] 弱 Agent 相对确定性多跳提升不显著
- [ ] 方差大到 eval 失去意义
- [ ] 白跳率高，靠运气答对
- [ ] 延迟 / 吞吐让工程师弃用
- [ ] 维护成本开始吃掉修检索、修 chunk、迁移 wire bonder 的时间

**一句话定调：** 弱 Agent 是最后手段。它的风险不是做不出来，而是做出来后悄悄摧毁这套可复现、可 eval、可迁移的方法论；所以必须先证明确定性多跳不可替代，再允许它存在。

---

## Plan B — CodeGraph 代码结构图谱实验（已完成）

当前已完成 **Phase 0 – Phase 8**（MVP + Plan B + **CI 绿** + AST-aware 符号 / dispatch）；**下一步 Phase 9（Repomap PageRank）**。

```powershell
cd industrial-cpp-kb-lab
pip install -r requirements.txt

.\kb tui                                 # Textual TUI（推荐）
.\kb eval                                # Recall dashboard
python src/run_regression.py --top-k 8   # 完整验收（含 LLM 引用）
python src/03_search.py --eval           # gate：mean cov@5 >= 70%
```

| 文档 | 内容 |
|------|------|
| `notes/kb_acceptance.md` | Smoothieware MVP 验收 |
| `notes/phase6_conclusion.md` | 检索 vs LLM 分层结论 |
| `notes/eval_failures.md` | 失败根因（已修复/open） |
| `notes/phase8_symbol_dispatch_audit.md` | Phase 8 符号 / dispatch 审计与验收 |
| `PLAN.md` Phase 9–12 + Plan D | **接下来要做的事与延期实验** |

**路线图顺序：** Phase 7 CI ✅ → Phase 8 AST-aware 符号 / dispatch ✅ → **9 PageRank** → 10 LLM 完整性 → 11 wire bonder → 12 CLI 产品化。
