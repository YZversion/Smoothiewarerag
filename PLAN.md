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
- [ ] CodeGraph 只作为 Plan B 结构图谱实验：先做 Smoothieware 小规模 A/B 验证，不现在押注、不替代源码核查

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
- [ ] caller/callee（Plan B CodeGraph）

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
- [ ] 扩充练习问题到 15~20 个，含 **hold-out**（不参与调参）
- [ ] 记录 BM25 检索的失败案例（漏召回、错召回）
- [ ] 区分「检索 Recall」与「LLM 答案准确度」；Q2 等多跳题 expected files @5 可能不全

### 6.2 可选升级（按需，不是必须）
- [ ] 向量检索（仅当 BM25 明显不够时）
- [ ] Doxygen 生成文档 + Graphviz 调用关系图
- [ ] 调用链 / 模块依赖图
- [ ] 简单 Web UI

**✅ Phase 6 验收**
- [ ] 有一份「当前方案够不够用」的量化结论
- [ ] 升级决策有数据支撑，而非拍脑袋

---

## Plan B — CodeGraph 代码结构图谱实验

**目标：验证对 C++ 设备控制项目，图结构索引是否比普通 `rg` / BM25 RAG 更快找到模块、函数、调用关系和影响范围。**

这个 Plan B 不替代 Phase 3–5 主线。它是一个克制的小实验：先在 Smoothieware 上比较 **A. ripgrep/BM25** 和 **B. CodeGraph/代码图谱**，证明有价值后再考虑是否接入 wire bonder 知识库。

### B.1 为什么值得研究
- [ ] 帮助理解大型 C++ 项目的模块结构
- [ ] 帮 AI Agent 减少反复 `grep` / 读文件造成的上下文爆炸
- [ ] 支持查询函数定义、调用者、被调用者、依赖关系和影响范围
- [ ] 未来可作为 wire bonder 知识库的「代码结构层」

### B.2 明确边界
- [ ] CodeGraph 解决「代码结构怎么找」，不解决「设备业务怎么懂」
- [ ] 它不能自动理解 wire bonding 工艺、报警排查、维修经验和现场日志
- [ ] 对 C++ 宏、条件编译、函数指针、回调、MFC 消息映射、动态派发、跨 DLL 调用可能漏关系或错关系
- [ ] 图谱结果只能作为候选线索，最终事实仍以源码、编译配置和工程师确认为准
- [ ] 现在不研究全部功能，只做 5 个问题的 A/B 测试

### B.3 候选工具判断标准
选择 CodeGraph / code graph 工具时，只看 6 个指标：

- [ ] 是否支持 C/C++
- [ ] 是否本地运行
- [ ] 是否不需要上传代码
- [ ] 是否能输出函数 / 类 / 调用关系 / include 关系
- [ ] 是否能被 Codex / Cursor / Claude Code 通过 MCP 或 CLI 调用
- [ ] 是否能导出或查询结构化结果，而不只是漂亮图

满足前 4 个，值得试；满足 6 个，才考虑深度集成。

### B.4 Smoothieware A/B 实验问题
用同一组问题比较 `rg/BM25` 与 `CodeGraph`：

- [ ] G-code 的入口文件在哪里？
- [ ] `Gcode` 类 / 函数被哪些模块调用？
- [ ] Motion planner 相关核心类有哪些？
- [ ] halt / error / stop 的调用链在哪里？
- [ ] 修改某个函数后可能影响哪些模块？

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

- [ ] `smoothieware_rg_findings.md`：记录 `rg` / BM25 找到的文件、符号、证据
- [ ] `smoothieware_codegraph_findings.md`：记录 CodeGraph 找到的 symbols、callers、callees、依赖关系
- [ ] `comparison.md`：比较哪个问题 CodeGraph 更强，哪个问题普通搜索更强，是否值得迁移到 wire bonder

### B.6 示例流程（待确认具体工具 README）
如果选择的是 `@colbymchenry/codegraph` 这类本地工具，先确认官方 README 和版本，再做最小试验：

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
- [ ] 对 5 个 Smoothieware 结构问题完成 A/B 对比
- [ ] `comparison.md` 明确列出：CodeGraph 强项、弱项、误报/漏报案例
- [ ] 能回答「是否值得在 wire bonder 代码上做小模块试验」
- [ ] 未证明价值前，不接入主 `app.py`，不把主线改成知识图谱系统

---

## Phase 7 — 迁移到公司 wire bonder 代码

**目标：把验证过的 lab 直接套到真实设备代码上。**

### 7.1 替换素材
- [ ] 公司 SVN checkout 出代码目录
- [ ] 不需要物理替换 `repos/Smoothieware/`；通过 `--repo-root` / `--src-root` 指向公司代码目录
- [ ] 重跑 Phase 2~5 全流程，输出到独立 data/index 目录或按项目名分目录

### 7.2 适配 wire bonder 模块体系
- [ ] 把模块分区从 CNC 改成设备真实分类：
  - [ ] 运动控制
  - [ ] 视觉
  - [ ] IO
  - [ ] 报警
  - [ ] 配方
  - [ ] 流程
  - [ ] UI
- [ ] 针对设备重写 5~10 个核心练习问题（定位、丢步、回零、限位、报警等）

### 7.3 合规与安全
- [ ] 确认公司代码可在本地/所选 LLM 环境处理（数据外发合规）
- [ ] 必要时改用本地模型 / 内网部署

**✅ Phase 7 验收**
- [ ] 对公司代码，能用同一套 app.py 返回「源码+解释+引用」
- [ ] 至少 5 个真实设备问题被正确回答

---

## 当前进度落点

当前已完成 **Phase 0 – Phase 5 主线**（Smoothieware demo：REPL + 检索 + LLM streaming）。

```powershell
cd industrial-cpp-kb-lab
pip install -r requirements.txt

python src/app.py                              # REPL
python src/app.py "G-code 从哪里进入系统？"
python src/app.py --search-only "Robot on_gcode_received"
python src/app.py --demo
python src/app.py --test                       # Recall + bundle 回归
python src/run_regression.py --skip-llm
python src/03_search.py --eval
```

**已知缺口（如实记录，勿用文件名特判刷绿）：** Q2 检索 @5 常仅命中 Robot+Conveyor，缺 GcodeDispatch/Planner/StepTicker；LLM 小模型易漏列 Sources、产生伪注释。

下一步：**Phase 6** 扩充 eval + hold-out；Plan B CodeGraph A/B；**Phase 7** wire bonder（`--repo-root`）。
