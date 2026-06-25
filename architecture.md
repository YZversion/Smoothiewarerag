# Architecture — industrial-cpp-kb-lab

## 系统定位

一个**纯本地、无向量数据库**的 C++ 代码问答系统。
核心思路：用传统信息检索（关键词 + 符号 + BM25）召回上下文，再交给 LLM 生成解释。

---

## 整体数据流

```
┌─────────────────────────────────────────────────────────┐
│                      离线索引阶段                         │
│                                                         │
│  C++ 源码目录                                            │
│  repos/Smoothieware/src/                                │
│         │                                               │
│         ├── 01_scan_files.py ──→ file_manifest.json     │
│         │   (遍历 .cpp/.h，记录路径/行数/目录)            │
│         │                                               │
│         ├── 02_extract_symbols.py ──→ symbol_index.json │
│         │   (ctags 提取 class/function/macro/enum)       │
│         │                                               │
│         └── (chunk 分割) ──→ data/chunks.jsonl          │
│             (按函数边界切分，带文件:行号元数据)             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      在线查询阶段                         │
│                                                         │
│  用户输入 query                                          │
│         │                                               │
│         ├─→ ripgrep 精确搜索（关键词/函数名/G-code）      │
│         │                                               │
│         ├─→ ctags 符号定位（class/function → 文件:行号）  │
│         │                                               │
│         └─→ BM25 语义召回（chunks.jsonl 上的倒排索引）    │
│                   │                                     │
│              融合排序 + 去重                              │
│                   │                                     │
│              Top-K chunks（含文件:行号）                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      LLM 生成阶段                         │
│                                                         │
│  prompt = system_prompt + 检索到的上下文 + 用户问题       │
│         │                                               │
│         └─→ Claude API                                  │
│                   │                                     │
│              输出：解释 + 相关源码片段 + 文件:行号引用     │
└─────────────────────────────────────────────────────────┘
```

---

## 模块说明

### 01_scan_files.py → `data/file_manifest.json`

```jsonc
// 每条记录
{
  "path": "src/modules/robot/Planner.cpp",
  "size_bytes": 12480,
  "lines": 340,
  "top_dir": "modules/robot"
}
```

过滤规则：跳过 `build/`、`mbed/`、`FirmwareBin/`、`testframework/`、图片、二进制

---

### 02_extract_symbols.py → `data/symbol_index.json`

```jsonc
// 每条记录
{
  "name": "append_block",
  "kind": "function",
  "file": "src/modules/robot/Planner.cpp",
  "line": 87,
  "class": "Planner"
}
```

调用：`ctags -R --c++-kinds=+pfsc --fields=+nKz --output-format=json`

---

### chunks.jsonl — 分块策略

优先按**函数/类边界**切分（来自 symbol_index），回退到固定窗口（100行，overlap 20行）。

```jsonc
// 每条 chunk
{
  "id": "planner_cpp_87_120",
  "file": "src/modules/robot/Planner.cpp",
  "start_line": 87,
  "end_line": 120,
  "symbol": "Planner::append_block",
  "text": "bool Planner::append_block(...) { ... }"
}
```

---

### 03_search.py — 三路融合检索

```
query
  │
  ├── rg_search(query)
  │     rg -n --type cpp <query> src/
  │     → [(file, line, snippet), ...]
  │
  ├── ctags_lookup(query)
  │     symbol_index.json 精确匹配 name
  │     → [(file, line, kind), ...]
  │
  └── bm25_search(query)
        rank_bm25 在 chunks.jsonl 上检索
        → [(chunk_id, score, text), ...]
        
融合：按 file:line 去重，按来源加权排序
     rg精确命中 > ctags符号命中 > bm25语义命中
返回：Top-5 chunks，每条带 file:line 引用
```

---

### 04_answer.py — LLM 问答

```python
context = "\n\n".join([
    f"// {chunk['file']}:{chunk['start_line']}\n{chunk['text']}"
    for chunk in top_chunks
])

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},   # prompts/code_qa.md
    {"role": "user",   "content": f"上下文:\n{context}\n\n问题: {query}"}
]
# → claude-sonnet-4-6
```

**Prompt 约束**（`prompts/code_qa.md`）：
- 角色：工业设备 C++ 代码助手
- 必须给出 `文件:行号` 引用
- 上下文不足时明确说"无法确认，需要查看更多代码"
- 不靠训练知识编造代码细节

---

### app.py — 一体化 CLI 入口

```bash
python app.py "G-code 从哪里进入系统"
# → 检索 → LLM → 输出解释 + 源码片段 + 引用路径
```

---

## 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 检索方案 | BM25 + rg + ctags | 无需 GPU，本地可用，代码检索够用 |
| 不用向量检索 | 等 Phase 6 评估后再决定 | 避免过早引入复杂依赖 |
| chunk 边界 | 函数/类边界优先 | 保持语义完整性，避免截断函数体 |
| LLM 模型 | `claude-sonnet-4-6` | 代码理解强，支持长上下文 |
| 数据不入库 | `.gitignore` 排除 data/ index/ repos/ | 生成物可重建，源码太大 |

---

## Phase 7 迁移指南

替换素材只需修改一处：

```python
# 01_scan_files.py
SOURCE_ROOT = "industrial-cpp-kb-lab/repos/Smoothieware/src"
# 改为：
SOURCE_ROOT = "path/to/wire_bonder_svn_checkout/src"
```

然后重跑 Phase 2–5 全流程即可。模块分区改成设备分类（运动/视觉/IO/报警/配方/流程/UI），练习问题改成设备问题（定位/丢步/回零/限位/报警）。
