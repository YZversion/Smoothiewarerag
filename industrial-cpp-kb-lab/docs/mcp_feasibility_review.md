# MCP Feasibility Review

## 结论

MCP 值得作为后续方向，但不应该现在直接升级成完整 MCP 平台、Neo4j 图数据库或复杂 GUI。

更稳妥的路线是：

1. 先用现有 `ctags + BM25 + rg` 在真实 wire bonder 问题上验证价值。
2. 如果真实问题暴露出结构索引不足，再补 SQLite 结构索引。
3. 等工具能力稳定后，再把能力封装成 MCP tools，供 Qwen Code、Cursor、VS Code 或内部 Agent 调用。

## 审查结论

- 我不同意你的哪一点：现在就把项目升级成 `tree-sitter + 图数据库 + 增量索引 + MCP + GUI` 的完整平台。
- 为什么这可能是错的：软件部真实问题和代码还没给，当前还不知道主要瓶颈是符号定位、调用链、日志关联、偏焊案例检索，还是时序追踪。过早做重架构会增加维护成本，并推迟最关键的真实问题验证。
- 这个问题的严重程度：中风险。
- 更好的替代方案：先定义 MCP 工具边界和验收 gate，不立即重写索引层；真实 10 题验证失败项再决定是否引入 tree-sitter / SQLite。
- 下一步应该验证什么：现有检索在真实问题上的 Recall@5、人工可用率、P95，以及失败题是否确实需要结构化 AST/调用边补充。

## 四层职责边界

### 1. 索引层

索引层负责把代码库变成可查询资产。

当前能力：

- 文件扫描。
- `ctags` 符号抽取。
- chunk 构建。
- call graph mention 边。
- dispatch index。
- benchmark / eval 产物。

未来可能补充：

- tree-sitter AST。
- SQLite 持久化结构索引。
- 文件 hash 级增量索引。
- include/import 关系。
- 候选调用关系。

索引层不负责回答用户问题，也不负责 GUI。

### 2. 检索层

检索层负责把用户问题变成证据列表。

当前能力：

- BM25。
- 符号 exact match。
- Smoothieware hints。
- bundle header/implementation。
- dispatch / callgraph 补充。
- 输出 `file:line` 和 snippet。

未来可能补充：

- query planner。
- 多 query 检索。
- error/log token 抽取。
- AST 结构检索。
- 结构边 rerank。

检索层的验收不是“看起来智能”，而是 Top-K 是否能覆盖工程师认可的源码位置。

### 3. MCP 工具层

MCP 工具层负责把稳定能力暴露给外部 Agent。

它应该是薄封装：

```text
Agent / IDE
    -> MCP tool
        -> local index/search APIs
            -> file:line evidence
```

MCP 不应该直接承担复杂业务逻辑，也不应该绕过只读边界。

核心要求：

- 只读。
- 返回可审计证据。
- 不自动修改业务代码。
- 不自动提交 SVN/Git。
- 不上传全仓库源码。
- 可在离线/内网模型场景下使用。

### 4. GUI / Agent 前端

GUI、Qwen Code、Cursor、VS Code 插件或内部 Web UI 都属于前端入口。

它们负责：

- 接收用户问题。
- 展示候选文件和引用。
- 展示解释、调用链、排查路径。
- 调用 MCP tools。

它们不应该成为项目当前主线。现阶段主线仍然是验证真实问题是否能被定位。

## 技术选型评价

### tree-sitter

优点：

- 多语言支持广。
- 比正则更稳定地抽取函数、类、结构、include/import、语法块。
- 适合构建结构索引。
- 适合未来做 MCP 工具底座。

局限：

- tree-sitter 是语法解析，不是完整语义分析。
- 对 C++ 模板、宏、重载、虚函数、函数指针、MFC 消息映射、动态分发无法单独给出完整调用图。
- 需要维护多语言 grammar 和解析异常处理。
- 引入后需要新增 eval，避免结构索引看起来更复杂但真实问题无收益。

判断：

tree-sitter 是合理的后续补强，但不应该在真实问题验证前替换当前索引链路。

### SQLite 图结构

优点：

- 单文件部署，适合内网和只读试点。
- Python 标准库自带 `sqlite3`，可以少引入依赖。
- 易备份、易回滚、易跟随 index version 管理。
- 足够支持文件、符号、chunk、include、候选调用边、query log 等结构化查询。
- 比 JSONL 更适合增量更新和多工具查询。

建议 schema 方向：

```text
files(id, path, hash, size, mtime, language)
symbols(id, file_id, name, qualified_name, kind, start_line, end_line)
chunks(id, file_id, symbol_id, start_line, end_line, text_hash)
edges(id, src_symbol_id, dst_symbol_id, kind, evidence_file_id, evidence_line, confidence)
imports(id, file_id, target, kind, evidence_line)
index_runs(id, repo_root, started_at, finished_at, status, manifest_hash)
queries(id, query, created_at, top_k, latency_ms)
query_hits(query_id, chunk_id, rank, score, method)
```

局限：

- 复杂图遍历不如图数据库自然。
- 并发写能力有限。
- 需要设计迁移和 schema version。

判断：

SQLite 是最推荐的第一阶段结构索引存储。

### Neo4j

优点：

- 图查询表达能力强。
- 适合复杂多跳关系、影响分析、跨模块路径查询。
- 可视化和图探索能力成熟。

局限：

- 部署重。
- 需要服务进程、权限、备份、运维。
- 软件部试点阶段容易显得侵入性太强。
- 当前问题规模和查询模式还没证明需要它。
- 可能把项目重心从“解决偏焊定位问题”带到“维护图数据库平台”。

判断：

当前不建议上 Neo4j。只有当 SQLite 无法支撑真实查询，且明确需要复杂多跳图分析时再评估。

### 增量索引

优点：

- 大仓库全量重建慢，增量索引可以降低等待时间。
- 对软件部试点更友好。
- 适合后续做持续更新的知识底座。

建议先做：

```text
hash / mtime / size based incremental indexing
```

流程：

1. 扫描文件 hash、mtime、size。
2. 未变化文件复用旧 symbols/chunks/edges。
3. 变化文件重新 parse。
4. 删除已不存在文件的索引记录。
5. 生成新的 index manifest。

暂不建议先做：

- 文件系统 watcher。
- git hook。
- 实时后台服务。

原因：

- 只读目录未必允许 hook。
- watcher 在 Windows/网络盘/SVN 工作区里容易引入边界问题。
- hash-based 方案更容易测试、回滚和解释。

## 为什么不应过早做完整 MCP / Neo4j / 复杂 GUI

### 完整 MCP 的风险

MCP 是接口层，不是价值本身。如果底层工具还没有被真实问题证明有效，过早 MCP 化只会把不稳定能力暴露给 Agent。

风险：

- 工具数量多但命中质量不稳定。
- Agent 会放大错误检索结果。
- 工具 contract 频繁变化，后续兼容成本高。
- 用户误以为系统已经具备生产级诊断能力。

### Neo4j 的风险

Neo4j 会让系统从本地轻量工具变成需要部署和维护的服务。

风险：

- 软件部更难批准。
- 环境准备时间变长。
- 数据导入、权限、备份、脱敏成为额外项目。
- 在没有真实复杂图查询前，投入产出比低。

### 复杂 GUI 的风险

GUI 会过早把注意力带到交互和视觉效果上。

风险：

- 延迟真实问题验证。
- 增加前端、后端、部署、权限、日志等维护面。
- 容易被拿来和 Cursor/Qwen Code 比体验，反而暴露短板。

当前更应该做的是可验证的工具能力，而不是完整产品壳。

## 最小可行路线

### 阶段 0：等待输入期间

当前可以做文档和设计，不做重代码。

产出：

- MCP tool contract 草案。
- SQLite schema 草案。
- 真实问题评估表。
- `locate_error` 设计。

不做：

- 不引入 tree-sitter。
- 不引入 Neo4j。
- 不做 GUI。
- 不改现有检索算法。

### 阶段 1：真实问题验证

输入：

- 软件部只读目录。
- 10 个真实问题。
- 一位验收工程师。

动作：

- 运行 `probe_repo`。
- 用现有 `ctags + BM25 + rg` 建索引。
- 对 10 题输出 Top-5 / Top-10 `file:line`。
- 让软件部判断引用是否有用。

验收：

- 多数问题能定位到有用文件/函数。
- P95 可接受。
- 失败题能分类。

### 阶段 2：补 SQLite 结构索引

进入条件：

- 真实问题显示 JSONL/内存索引不利于查询、复用、增量更新。
- 需要稳定的符号、文件、chunk、关系查询。

动作：

- 不替换原检索链路，先并行写 SQLite。
- 先存 files/symbols/chunks/imports/candidate_edges。
- 保留 index manifest 和回滚机制。

验收：

- 不降低原有 Smoothieware / scale_test eval。
- 查询延迟不恶化。
- 能支持 `lookup_symbol`、`find_related_files`、`find_call_candidates`。

### 阶段 3：暴露 MCP tools

进入条件：

- 工具 contract 稳定。
- 真实问题证明这些工具有用。
- 输出始终可追溯到 `file:line`。

动作：

- 暴露少量只读 MCP tools。
- 用 Qwen Code / Cursor / 内部 Agent 调用。
- 做 A/B/C 评估：
  - A：只用 Agent 自己读代码。
  - B：只用本项目 CLI/RAG。
  - C：Agent + MCP tools。

验收：

- C 明显优于 A/B。
- 工具结果可复核。
- 不突破安全边界。

## 第一批 MCP Tools 设计

### search_code

用途：

按工程问题检索相关源码证据。

输入：

```json
{
  "query": "vision offset 从哪里传给 motion command",
  "top_k": 5,
  "repo_id": "wire_bonder_readonly"
}
```

输出：

```json
{
  "hits": [
    {
      "file": "path/to/file.cpp",
      "start_line": 120,
      "end_line": 168,
      "symbol": "MotionController::enqueue",
      "score": 12.4,
      "evidence": "short snippet or summary",
      "method": ["bm25", "symbol", "hint"]
    }
  ],
  "latency_ms": 83
}
```

边界：

- 只返回检索证据。
- 不生成最终业务结论。
- 不修改文件。

### lookup_symbol

用途：

按函数、类、宏、枚举、常量名查定义和相关 chunk。

输入：

```json
{
  "symbol": "Planner::append_block",
  "repo_id": "wire_bonder_readonly"
}
```

输出：

```json
{
  "matches": [
    {
      "qualified_name": "Planner::append_block",
      "kind": "function",
      "file": "path/to/planner.cpp",
      "start_line": 42,
      "end_line": 118
    }
  ]
}
```

边界：

- 不承诺唯一命中。
- 对重载、宏、模板需要返回多个候选。

### find_call_candidates

用途：

查某个符号可能调用谁、可能被谁调用。

输入：

```json
{
  "symbol": "VisionResultManager::publish",
  "direction": "both",
  "max_depth": 1,
  "repo_id": "wire_bonder_readonly"
}
```

输出：

```json
{
  "symbol": "VisionResultManager::publish",
  "callers": [
    {
      "symbol": "VisionThread::run",
      "file": "path/to/vision_thread.cpp",
      "line": 210,
      "confidence": "candidate",
      "reason": "text mention / AST call expression"
    }
  ],
  "callees": [
    {
      "symbol": "MotionQueue::updateOffset",
      "file": "path/to/motion_queue.cpp",
      "line": 88,
      "confidence": "candidate",
      "reason": "text mention / AST call expression"
    }
  ]
}
```

边界：

- 必须叫 `candidate`，不要叫完整调用图。
- C++ 动态分发、函数指针、消息映射、宏生成调用都可能漏掉。

### locate_error

用途：

粘贴错误日志、报警码、编译错误、运行异常，定位可能相关代码。

输入：

```json
{
  "error_text": "E1234 motion timeout after vision result, command_id=88421",
  "repo_id": "wire_bonder_readonly",
  "top_k": 8
}
```

处理策略：

- 提取 `file:line`。
- 提取错误码、报警码、十六进制码。
- 提取函数名、类名、模块名。
- 提取 quoted message。
- 对剩余文本做 BM25 检索。
- 合并 exact match 和语义弱匹配结果。

输出：

```json
{
  "signals": {
    "codes": ["E1234"],
    "symbols": [],
    "modules": ["motion", "vision"],
    "messages": ["motion timeout after vision result"]
  },
  "hits": [
    {
      "file": "path/to/alarm_table.cpp",
      "line": 301,
      "reason": "exact alarm code match"
    },
    {
      "file": "path/to/motion_timeout.cpp",
      "line": 77,
      "reason": "message and module match"
    }
  ],
  "missing_context": [
    "runtime log with timestamp",
    "command_id trace",
    "motion settled status"
  ]
}
```

边界：

- 不能凭空判断根因。
- 如果错误文本过泛，只能给候选和需要补充的信息。

### probe_repo

用途：

对新代码目录做只读接入审查。

输入：

```json
{
  "repo_root": "path/to/readonly/repo",
  "src_root": "path/to/readonly/repo"
}
```

输出：

```json
{
  "file_count": 12480,
  "languages": {
    "cpp": 8300,
    "h": 3600,
    "cs": 580
  },
  "encoding_risks": [],
  "large_files": [],
  "generated_like_files": [],
  "ctags_status": "ok",
  "index_recommendation": "safe_to_index_with_exclusions"
}
```

边界：

- 只读扫描。
- 不上传源码。
- 不修改目录。

## MCP 阶段 gate

只有满足以下条件，才建议进入 MCP 实现阶段：

1. 软件部提供了真实只读目录和 10 个真实问题。
2. 现有检索跑完评估，并有人工验收结果。
3. 至少 6/10 问题返回的 Top-5 `file:line` 被认为有用。
4. 失败题分类证明需要结构化工具，而不是简单 prompt 或 query 改写。
5. P95 查询延迟满足演示/试点要求。
6. 安全边界明确：只读、不改 SVN、不生成 patch、不上传全仓库。
7. 工具 contract 稳定，且每个 tool 都能返回可追溯 evidence。
8. 有明确前端调用方，例如 Qwen Code、Cursor、VS Code、内部 Web UI 或 CLI。

如果 gate 不满足，不应该做 MCP。此时更应该继续修检索质量、补问题集、补日志字段或做偏焊专项知识地图。

## 当前建议

现在可以做：

- 准备 MCP tool contract。
- 准备 SQLite schema 草案。
- 准备真实问题评估表。
- 准备 `locate_error` 的设计和测试样例。

现在不建议做：

- 引入 tree-sitter 并替换 ctags。
- 上 Neo4j。
- 写完整 MCP server。
- 做复杂 GUI。
- 做自动 patch / 自动提交。

一句话：

> MCP 是后续正确方向，但当前阶段最重要的是证明内部真实问题能被可靠定位。先验证，再结构化，再 MCP 化。
