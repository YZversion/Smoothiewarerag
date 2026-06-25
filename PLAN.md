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

---

## Phase 0 — 环境与素材准备

**目标：lab 目录建好、工具装好、Smoothieware clone 下来且能搜。**

### 0.2 安装基础工具（PowerShell）
- [ ] `winget install Git.Git`
- [ ] `winget install Python.Python.3.11`
- [ ] `winget install BurntSushi.ripgrep.MSVC`
- [ ] `winget install UniversalCtags.Ctags`
- [ ] `winget install Graphviz.Graphviz`（可选）
- [ ] Cursor 或 VS Code（手动安装）
- [ ] Doxygen（可选，留到 Phase 6）

### 0.3 验证工具
- [ ] `git --version`
- [ ] `python --version`
- [ ] `rg --version`
- [ ] `ctags --version`
- [ ] `dot -V`

### 0.4 Clone 仓库
- [ ] `git clone https://github.com/Smoothieware/Smoothieware.git`

**✅ Phase 0 验收**
- [ ] 目录结构齐全
- [ ] 五个工具命令都能正常输出版本号
- [ ] `repos/Smoothieware/` 已存在且可被 `rg` 搜索

---

## Phase 1 — 人工探索 + 第一版代码地图

**目标：不写复杂程序，靠 rg 人工形成一张代码地图，并选出 10 个重点文件。**

### 1.1 只读 3 个文档（不要全读）
- [ ] **README**：搞清楚是什么项目、什么语言、面向什么硬件
  - 记住：G-code interpreter + CNC controller，OOP C++，目标硬件 LPC17xx / Cortex-M3
- [ ] **Module Example**：理解「everything is a module」，模块靠 event calls / event handlers 连接
- [ ] **Motion Control**：理解 G-code → 运动转换，及 acceleration / junction deviation / step loss 等概念

### 1.2 固定 5 个练习问题（demo 第一版只围绕这 5 个）
- [ ] Q1：G-code 从哪里进入系统？
- [ ] Q2：G-code 如何变成运动命令？
- [ ] Q3：Motion / Planner / Stepper 相关代码在哪里？
- [ ] Q4：error / stop / halt / emergency 逻辑在哪里？
- [ ] Q5：模块系统如何注册、触发、通信？

### 1.3 用 ripgrep 做第一次探索（记录高频文件）
- [ ] `rg -n "class .*Module|public Module|on_module_loaded" .`
- [ ] `rg -n "Gcode|GCode|gcode|M-code|MCode" .`
- [ ] `rg -n "planner|Planner|motion|Motion|stepper|Stepper" .`
- [ ] `rg -n "halt|stop|error|emergency|alarm|kill" .`
- [ ] `rg -n "add_module|register_for_event|call_event|ON_|EVENT_" .`
- [ ] 把每条命令里**出现频率最高、最核心的文件名**抄进笔记

### 1.4 写 `notes/smoothieware_code_map.md` 第一版
- [ ] 项目定位（一句话）
- [ ] 5 个核心问题列出
- [ ] 按模块分区填「相关文件 + 作用」：
  - [ ] Communication
  - [ ] Robot / Motion
  - [ ] G-code
  - [ ] Kernel / Module System
  - [ ] Error / Halt

### 1.5 选出第一版知识库输入
- [ ] 选定 10 个重点源码文件作为知识库第一批输入

**✅ Phase 1 验收（= 文档里的「第一天验收标准」）**
- [ ] clone 成功
- [ ] 能用 rg 搜到 gcode / motion / planner / halt 相关代码
- [ ] `smoothieware_code_map.md` 第一版写出
- [ ] 10 个重点文件选定
- [ ] （今天不上 Web UI、不纠结 LangChain vs LlamaIndex、不试图完全读懂 Smoothieware）

---

## Phase 2 — 文件扫描与符号提取

**目标：把「人工探索」变成「可重复的数据」，产出 file_manifest.json 和 symbol_index.json。**

### 2.1 `01_scan_files.py` → `data/file_manifest.json`
- [ ] 遍历 `repos/Smoothieware/`，收集 `.cpp/.h/.hpp/.c` 文件
- [ ] 记录：路径、大小、行数、所属一级目录
- [ ] 过滤掉无关目录（build 产物、第三方、文档图片等）
- [ ] 输出 `file_manifest.json`

### 2.2 `02_extract_symbols.py` → `data/symbol_index.json`
- [ ] 用 ctags 提取 C++ 的 **class / function / macro / enum**
- [ ] 解析 ctags 输出为结构化记录：symbol 名、类型、文件、行号
- [ ] 输出 `symbol_index.json`
- [ ] 抽查 Phase 1 里的核心符号（如 Planner、Stepper、on_gcode_received 之类）能否被检索到

**✅ Phase 2 验收**
- [ ] `file_manifest.json` 覆盖全部源码文件
- [ ] `symbol_index.json` 能按符号名查到「文件:行号」
- [ ] 5 个练习问题相关的关键符号都能被定位

---

## Phase 3 — 分块与检索（BM25）

**目标：建立可被关键词检索的 chunks，并实现 search.py（ripgrep + ctags + BM25 融合）。**

### 3.1 分块 → `data/chunks.jsonl`
- [ ] 按函数/类边界（基于 symbol_index）或固定窗口切分源码
- [ ] 每个 chunk 带元数据：文件路径、起止行号、所属符号
- [ ] 输出 `chunks.jsonl`

### 3.2 `03_search.py`（融合检索）
- [ ] BM25 索引（如 `rank_bm25` 或轻量倒排）建在 chunks 上
- [ ] 检索流程：关键词 → BM25 召回 chunk + ctags 精确符号定位 + ripgrep 兜底
- [ ] 返回结果含「文件:行号」引用路径
- [ ] 用 5 个练习问题逐一测试召回质量

**✅ Phase 3 验收**
- [ ] 输入模块名/函数名/G-code/error 关键词，能返回相关 chunk + 引用路径
- [ ] 5 个问题中至少能召回到正确文件的命中率达标（自定一个阈值，如 ≥4/5）

---

## Phase 4 — LLM 代码问答

**目标：把检索到的上下文喂给 LLM，得到「源码 + 解释 + 引用」式回答。**

### 4.1 `prompts/code_qa.md`
- [ ] 写问答 prompt 模板：角色=工业设备 C++ 代码助手
- [ ] 要求：基于给定上下文回答、必须给出文件:行号引用、上下文不足时明确说不知道

### 4.2 `04_answer.py`
- [ ] 串起 search.py 的检索结果 → 拼接上下文 → 调 LLM
- [ ] 输出：解释 + 相关源码片段 + 引用路径
- [ ] 跑通 5 个练习问题，人工核对答案是否「有据可查」

**✅ Phase 4 验收**
- [ ] 对 5 个练习问题，模型回答能正确指向真实代码并附引用
- [ ] 回答不靠模型「编」，而是基于检索上下文

---

## Phase 5 — 整合成 Demo

**目标：`app.py` 把整条链路打通，形成一个可演示的最小知识库。**

### 5.1 `app.py`
- [ ] 一个入口：输入关键词 → 检索 → LLM → 输出
- [ ] 先做 CLI 即可，不急着上 Web UI
- [ ] 输出统一格式：解释 / 源码 / 引用路径

### 5.2 自测脚本
- [ ] 把 5 个练习问题做成回归测试，每次改动后一键跑

**✅ Phase 5 验收**
- [ ] 一条命令即可对任意关键词返回「源码+解释+引用」
- [ ] 这就是 wire bonder 知识库的可复用雏形

---

## Phase 6 — 评估与可选升级

**目标：先量化效果，再决定要不要加重型组件。**

### 6.1 评估
- [ ] 扩充练习问题到 15~20 个，统计命中率/可用性
- [ ] 记录 BM25 检索的失败案例（漏召回、错召回）

### 6.2 可选升级（按需，不是必须）
- [ ] 向量检索（仅当 BM25 明显不够时）
- [ ] Doxygen 生成文档 + Graphviz 调用关系图
- [ ] 调用链 / 模块依赖图
- [ ] 简单 Web UI

**✅ Phase 6 验收**
- [ ] 有一份「当前方案够不够用」的量化结论
- [ ] 升级决策有数据支撑，而非拍脑袋

---

## Phase 7 — 迁移到公司 wire bonder 代码

**目标：把验证过的 lab 直接套到真实设备代码上。**

### 7.1 替换素材
- [ ] 公司 SVN checkout 出代码目录
- [ ] 把 `repos/Smoothieware/` 替换为公司代码目录
- [ ] 重跑 Phase 2~5 全流程

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

你现在的实际任务是完成 **Phase 0 + Phase 1**。
做完 1.3 的 ripgrep 探索后，把每条命令输出里**出现最频繁、最核心的文件名**贴出来，
下一步就可以进入 Phase 2，设计 `01_scan_files.py` / `02_extract_symbols.py`。
