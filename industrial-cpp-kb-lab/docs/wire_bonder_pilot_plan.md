# Wire Bonder Pilot Plan

## 目标

第一轮试点只验证 Level 0 能力：

> 输入真实工程问题或错误信息，系统能否在只读代码目录里返回软件部工程师认可的 `file:line` 证据。

这不是自动修代码项目，也不是让 LLM 判断偏焊最终根因。当前目标是证明“只读代码定位 + 可核查引用”是否能节省工程师读代码时间。

## 当前判断

- 我不同意你的哪一点：现在把重点放到 GUI、MCP、tree-sitter、Neo4j 或自动修改代码。
- 为什么这可能是错的：软件部还没给真实目录和 10 个问题，最大不确定性仍是现有检索能否命中真实代码位置。过早重架构会偏离试点主线。
- 这个问题的严重程度：中风险。
- 更好的替代方案：用现有 `rg + ctags + BM25` 跑真实问题评估，再根据失败分类决定是否进入 MCP / SQLite / trace log。
- 下一步应该验证什么：10 个真实问题的 Top-5 `file:line` 人工可用率。

## 本轮输入

| 输入 | 必需 | 说明 |
|---|---|---|
| 非核心只读代码目录 | 是 | 历史版本、脱敏目录或非核心模块均可；不要求能编译 |
| 目录范围说明 | 是 | 模块职责、是否包含第三方库、generated code、二进制产物 |
| 编码说明 | 是 | UTF-8 / GBK / GB18030 / 混合编码 |
| 10 个真实问题 | 是 | 来自日常排查，不要泛泛问“某模块是什么” |
| 日志/报警样例 | 强烈建议 | 至少 1-3 条报警码、错误文本或运行日志 |
| 验收工程师 | 是 | 判断返回的 `file:line` 是否有用 |
| 保密边界 | 是 | 是否允许 LLM，是否必须内网/离线 |

可选输入：

- 排除目录：`third_party/`、`generated/`、`bin/` 等。
- 关键字表：报警码、命令码、菜单 ID、模块简称、配置项名称。

## 执行流程

### 1. 只读 probe

```powershell
cd industrial-cpp-kb-lab
.\kb probe --repo-root <READONLY_REPO> --out reports/wire_bonder_probe.md
```

输出：

- 文件数量、行数、语言分布。
- 编码风险。
- 超长文件。
- generated-like 文件。
- ctags 可用性。
- 索引可行性建议。

如果 probe 显示阻断风险，先停止，不进入索引。

### 2. 建立索引

```powershell
.\kb index build --repo-root <READONLY_REPO> --src-root <READONLY_SRC_ROOT>
.\kb index check --index data
```

要求：

- 索引产物只写入本项目数据目录。
- 源码目录不写入。
- 保留 index manifest。
- 如需排除目录，先和软件部确认。

### 3. 10 题检索评估

逐题运行：

```powershell
.\kb search "<QUESTION>" --top-k 5 --preview
```

每题记录：

- 原始 query。
- expected area。
- Top-5 `file:line`。
- Top-10 补充。
- 人工是否认可。
- 失败原因。

详细评分表见 [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md)。

### 4. 人工验收

验收人只判断：

1. Top-5 里有没有有用代码位置。
2. Top-10 是否补中。
3. 结果是否可能误导。

不要要求验收人确认 AI 给出最终根因。第一轮只看定位能力。

### 5. 失败分类

失败题必须分类：

- 问题表达不清。
- 索引失败。
- 符号缺失。
- 动态分发。
- 日志字段不足。
- 业务知识缺失。
- 跨模块链路过长。
- Smoothieware 专用 hints 误伤。

## 成功判定

| 结果 | 判定 | 下一步 |
|---|---|---|
| Top-5 人工可用率 >= 60% | 通过 | 进入偏焊专项知识地图或第二目录 |
| Top-5 可用率 40%-60% | 部分通过 | 分析失败类型，补规则后复测 |
| Top-5 可用率 < 40% | 暂停 | 停在 probe/评估报告，不扩展 |

附加条件：

- 不能发生源码写入。
- 不能上传全仓库源码。
- 不能生成 patch / diff。
- 不能把没有引用的 LLM 解释当结论。

## 是否进入下一阶段

### 进入 MCP

只有在以下条件满足后才做 MCP：

- 10 题评估完成。
- Top-5 人工可用率 >= 60%。
- 有明确调用方：Qwen Code、Cursor、VS Code、内部 Web UI 或 CLI。
- 工具 contract 稳定，且返回 `file:line` evidence。

详细审查见 [`mcp_feasibility_review.md`](mcp_feasibility_review.md)。

### 进入 SQLite 结构索引

仅当真实问题显示 JSONL/内存索引不利于复用、关系查询或增量更新时再做。第一轮不引入 SQLite。

### 进入 trace log

仅当失败题集中在“日志字段不足”或“软件时序无法还原”时推动。最小 trace 字段见 [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md)。

### 进入偏焊专项知识库

当真实问题能定位到 vision、motion、recipe、inspection 中至少两个模块，并且软件部愿意补日志/报警/inspection 样例时进入。

## 明确不做

- 不自动修改代码。
- 不提交 SVN / Git。
- 不生成 patch / diff。
- 不训练外部模型。
- 不上传全仓库源码。
- 不做闭环自动补偿。
- 不承诺 100% 正确。
- 不先做复杂 GUI。

## 对外话术

给软件部的短话术见 [`stakeholder_pitch.md`](stakeholder_pitch.md)。

一句话版本：

> 第一轮只申请一个非核心只读目录、10 个真实问题和一位验收工程师。我们只验证工具能否返回有用的 `file:line`，不改代码、不提交 SVN、不训练模型、不上传全仓库。
