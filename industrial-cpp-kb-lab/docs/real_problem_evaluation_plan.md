# Wire Bonder Real Problem Evaluation Plan

## 目标

这份文档用于软件部给出只读代码目录和真实问题后，立刻执行第一轮接入评估。

评估目标不是证明 AI 能自动判断偏焊根因，也不是做 MCP、GUI 或自动修改代码。第一轮只验证一件事：

> 输入真实工程问题后，现有只读代码知识库能否返回软件部工程师认可的 `file:line` 证据。

## 审查结论

- 我不同意你的哪一点：在真实代码和真实问题到位前，先做 MCP、SQLite、tree-sitter、Neo4j 或 GUI。
- 为什么这可能是错的：当前最大不确定性不是技术栈，而是真实 wire bonder 问题能否被现有 `ctags + BM25 + rg` 路径稳定定位。过早扩架构会推迟验证，且可能做出软件部暂时不需要的能力。
- 这个问题的严重程度：中风险。
- 更好的替代方案：先建立真实问题评估流程和评分表，用 10 个问题决定下一步是否需要 MCP / SQLite / trace log。
- 下一步应该验证什么：Top-5 `file:line` 是否被验收工程师认可，失败题是否确实来自索引结构不足、动态分发或日志字段缺失。

## 输入清单

| 输入 | 必需 | 提供方 | 用途 | 最低要求 |
|---|---|---|---|---|
| 只读代码目录 | 是 | 软件部 | probe、index、search eval | 非核心目录或历史版本；不要求可编译 |
| 目录范围说明 | 是 | 软件部 | 判断模块边界和排除目录 | 说明模块职责、第三方库、generated code |
| 10 个真实问题 | 是 | 软件部/设备/工艺 | 第一轮评估集 | 来自真实排查场景，不要泛泛聊天问题 |
| 日志/报警样例 | 强烈建议 | 软件部/测试/设备 | 支持 `locate_error` 类问题 | 至少 1-3 条真实报警文本、错误码或日志片段 |
| 验收人 | 是 | 软件部 | 判断 `file:line` 是否有用 | 熟悉目录对应模块的工程师 |
| 保密边界 | 是 | 软件部/主管 | 决定是否可调用 LLM、是否必须离线 | 明确代码不可外发范围 |
| 排除目录 | 可选 | 软件部 | 避免索引第三方/生成物 | 如 `third_party/`、`generated/`、`bin/` |
| 关键字表 | 可选 | 软件部 | 提高问题表达质量 | 报警码、命令码、菜单 ID、模块简称 |

## 评估流程

### 0. 冻结边界

确认本轮只做：

- 只读扫描。
- 本地索引。
- 10 题检索。
- `file:line` 人工验收。
- 失败分类。

本轮不做：

- 不修改业务代码。
- 不改 `repos/**`。
- 不生成 patch / diff。
- 不提交 SVN / Git。
- 不引入 tree-sitter。
- 不引入 Neo4j。
- 不实现 MCP server。
- 不做 GUI。
- 不训练模型。

### 1. probe

目的：先判断目录是否适合建立索引。

建议命令：

```powershell
cd industrial-cpp-kb-lab
.\kb probe --repo-root <READONLY_REPO> --out reports/wire_bonder_probe.md
```

检查项：

- 文件数量、行数、语言分布。
- 编码风险：UTF-8 / GBK / GB18030 / mixed / binary。
- 超长文件。
- generated-like 文件。
- 第三方库或二进制目录。
- ctags 可用性。
- 潜在敏感路径。

probe 结论：

| 结论 | 含义 | 下一步 |
|---|---|---|
| safe_to_index | 可直接索引 | 进入 index |
| safe_with_exclusions | 排除部分目录后可索引 | 与软件部确认排除规则 |
| blocked | 暂不适合索引 | 先解决阻断项 |

### 2. index

目的：用现有链路建立本地索引。

建议命令：

```powershell
cd industrial-cpp-kb-lab
.\kb index build --repo-root <READONLY_REPO> --src-root <READONLY_SRC_ROOT>
.\kb index check --index data
```

记录：

- scan 耗时。
- ctags 耗时和失败文件。
- chunk 数量。
- symbol 数量。
- index manifest。
- 是否有排除目录。
- 是否触碰源码目录。

验收：

- `kb index check` 通过。
- 索引产物只写入本项目数据目录。
- 源码目录无写入。

### 3. search eval

目的：对 10 个真实问题输出可核查证据。

建议先逐题运行：

```powershell
.\kb search "<QUESTION>" --top-k 5 --preview
```

如果 10 题整理成 JSON，可后续补 eval 文件后运行：

```powershell
python src/03_search.py --eval --eval-file eval/wirebonder_questions.json --repo-root <READONLY_REPO> --src-root <READONLY_SRC_ROOT>
```

每题必须记录：

- query。
- expected area。
- Top-5 `file:line`。
- Top-10 是否补中。
- 是否命中符号。
- 是否命中错误码/报警码/命令码。
- 是否需要人工确认。
- 人工是否认可。
- 失败原因。

### 4. 人工验收

验收人只需要回答两个问题：

1. Top-5 里有没有“有用的代码位置”？
2. 如果没有，Top-10 里是否出现了有用位置？

不要求验收人判断 AI 解释是否完美，也不要求确认最终根因。第一轮只评估定位能力。

人工结果分级：

| 等级 | 定义 | 计分 |
|---|---|---|
| A | Top-5 直接命中关键文件/函数/行号 | 1.0 |
| B | Top-5 命中相关模块，但不够精确 | 0.7 |
| C | Top-10 才出现有用位置 | 0.5 |
| D | 结果有参考价值，但需要大量人工筛选 | 0.3 |
| F | 基本无用或误导 | 0 |

### 5. 失败分类

每个非 A/B 的问题必须分类。

| 失败分类 | 判断标准 | 处理建议 |
|---|---|---|
| 问题表达不清 | query 没有具体模块、错误码、日志、参数名 | 让软件部补关键字或真实日志 |
| 索引失败 | 文件未扫描、编码失败、ctags 失败、chunk 缺失 | 修接入配置或排除异常文件 |
| 符号缺失 | 函数/类/宏存在但未进入 symbol index | 评估 ctags 配置或后续结构索引 |
| 动态分发 | 消息 ID、函数指针、宏映射、状态机回调导致静态检索漏掉 | 后续补 dispatch 规则或 candidate edges |
| 日志字段不足 | 错误文本只有泛化描述，缺少 error code / command id / timestamp | 推动 trace log 字段补齐 |
| 业务知识缺失 | 需要 recipe、工艺名、设备动作、历史案例才能判断 | 建偏焊专项知识地图或案例库 |
| 跨模块链路过长 | 单次检索只命中局部，无法串起 vision -> motion -> inspection | 后续评估 query planner / call candidates |
| 误触专用 hints | Smoothieware 专用规则影响 wire bonder 查询 | 禁用或重写项目专用 hints |

## 10 题评分表模板

| # | query | category | expected area | Top-5 file:line | Top-10补充 | 人工认可 | 等级 | 失败原因 | 下一步 |
|---|---|---|---|---|---|---|---|---|---|
| 1 |  | entry_point |  |  |  |  |  |  |  |
| 2 |  | error_trace |  |  |  |  |  |  |  |
| 3 |  | state_machine |  |  |  |  |  |  |  |
| 4 |  | homing/process |  |  |  |  |  |  |  |
| 5 |  | alarm_or_command_code |  |  |  |  |  |  |  |
| 6 |  | module_boundary |  |  |  |  |  |  |  |
| 7 |  | config_loading |  |  |  |  |  |  |  |
| 8 |  | timing/trace |  |  |  |  |  |  |  |
| 9 |  | inspection/test |  |  |  |  |  |  |  |
| 10 |  | legacy/other |  |  |  |  |  |  |  |

## 每题记录字段

建议把每题记录成以下结构，方便后续转成 JSON 或表格：

```json
{
  "id": "real_001",
  "query": "",
  "category": "",
  "expected_area": {
    "module": "",
    "files": [],
    "symbols": [],
    "notes": ""
  },
  "top5": [
    {
      "rank": 1,
      "file": "",
      "line": null,
      "symbol": "",
      "reason": ""
    }
  ],
  "top10_extra": [],
  "accepted_by_engineer": null,
  "acceptance_grade": "",
  "failure_reason": "",
  "needs_followup": "",
  "missing_input": []
}
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| query | 是 | 软件部给的原始问题，不要过度润色 |
| expected_area | 是 | 验收人预期的大致模块、文件、函数或业务区域 |
| top5 file:line | 是 | 系统返回的前 5 个引用 |
| accepted_by_engineer | 是 | 验收人是否认为有用 |
| failure_reason | 条件必填 | 非 A/B 时必须填写 |
| missing_input | 条件必填 | 如果缺日志、报警码、参数名，在这里记录 |

## 推荐的 10 题覆盖面

第一轮不一定要 20 题，10 题足够做 gate。建议覆盖：

1. 入口定位：运动/焊接/视觉命令从 UI 或上位机进入哪里。
2. 错误追踪：真实报警码或错误日志在哪里产生、处理、上报。
3. 状态机/流程：自动运行、暂停、恢复、reset 的状态切换。
4. 回零/运动流程：动作从命令到轴控制经过哪些函数。
5. 报警码/命令码：ID 到 handler 的映射。
6. 模块边界：视觉和运动、recipe 和 motion、inspection 和 UI 的通信边界。
7. 配置加载：工艺参数、速度、压力、温度、阈值从哪里加载并生效。
8. 软件时序：vision result、motion command、IO complete 的事件顺序。
9. 测试/检测：post-bond inspection 或测试软件为什么可能判不出偏焊。
10. 历史遗留：某个旧类/旧模块是否仍在主流程中被调用。

## 指标与判定

### 定量指标

| 指标 | 目标 | 说明 |
|---|---|---|
| Top-5 人工可用率 | >= 60% | 至少 6/10 问题 Top-5 被认为有用 |
| Top-10 人工可用率 | >= 80% | 如果 Top-5 不够，Top-10 应显著补充 |
| P95 查询延迟 | <= 500ms 优先，<= 2s 可接受 | 第一轮内部试点可先接受 2s 内 |
| probe 阻断项 | 0 | 如有阻断，先不进入 index |
| 源码写入 | 0 | 必须确认只读 |

### 定性指标

继续推进需要满足：

- 验收人认为结果能节省定位时间。
- 失败题能明确归因，而不是“系统整体不靠谱”。
- 至少一类真实问题显示出稳定价值，例如报警码定位、入口定位、模块边界定位。
- 软件部愿意继续提供问题、日志或 trace 字段。

## 进入下一阶段的 gate

### 进入 MCP 阶段

满足以下条件才考虑 MCP：

- 10 题评估完成，且有人工验收记录。
- Top-5 人工可用率 >= 60%。
- 工具 contract 稳定，且每个工具都能返回 `file:line` evidence。
- 有明确调用方，例如 Qwen Code、Cursor、VS Code、内部 Web UI 或 CLI。
- 失败题显示“Agent 调工具”能明显改善工作流，而不只是换一个界面。

不满足时，不做 MCP。继续修检索质量、问题表达或评估流程。

### 进入 SQLite 结构索引阶段

满足以下条件才考虑 SQLite：

- JSONL/内存索引难以支持稳定查询、复用或增量更新。
- `lookup_symbol`、`find_call_candidates`、跨文件关系查询成为真实痛点。
- 现有 ctags/BM25 能力有价值，但需要更强持久化结构层。
- 增量索引需求明确，例如全量重建影响软件部使用。

不满足时，不做 SQLite。现有索引文件足够支撑第一轮验证。

### 进入 trace log 阶段

满足以下条件才推动 trace：

- 多个问题失败原因属于“日志字段不足”或“软件时序无法还原”。
- 软件部确认偏焊排查需要知道事件顺序。
- 至少能选出一条低风险链路试点，例如 `vision result -> coordinate compensation -> motion command`。
- trace 只记录关键事件，不改业务逻辑。

trace 最小字段：

```text
timestamp_us
thread_id
state_machine_state
event_name
command_id
unit_id
wire_id
coordinate_version
recipe_version
vision_result_id
motion_command_id
```

### 进入偏焊专项知识库阶段

满足以下条件才进入：

- 10 题中至少 3 题和偏焊直接相关。
- 能定位到 vision、motion、recipe、inspection 中至少两个模块。
- 软件部愿意补充真实日志、报警样例、inspection 样例或历史案例。

输出应包括：

- 偏焊相关模块地图。
- `vision offset -> coordinate compensation -> motion command` 链路草图。
- 缺失数据字段清单。

## 第一轮输出物

完成评估后应产出：

1. `reports/wire_bonder_probe.md`
2. `eval/wirebonder_questions.json` 或等价问题表
3. `reports/wire_bonder_real_problem_eval.md`
4. 10 题评分表
5. 失败分类统计
6. 下一阶段建议：停止 / 继续只读检索 / SQLite / MCP / trace log

## 最小执行命令清单

```powershell
cd industrial-cpp-kb-lab

# 1. 只读 probe
.\kb probe --repo-root <READONLY_REPO> --out reports/wire_bonder_probe.md

# 2. 建索引
.\kb index build --repo-root <READONLY_REPO> --src-root <READONLY_SRC_ROOT>
.\kb index check --index data

# 3. 逐题检索
.\kb search "<QUESTION_1>" --top-k 5 --preview
.\kb search "<QUESTION_2>" --top-k 5 --preview

# 4. 如果整理成 eval JSON，再跑批量评估
python src/03_search.py --eval --eval-file eval/wirebonder_questions.json --repo-root <READONLY_REPO> --src-root <READONLY_SRC_ROOT>
```

## 注意事项

- 不要把 `expected_area` 当成硬编码输入给检索器，它只用于验收。
- 不要为了通过 10 题临时写 per-question 规则。
- 不要把 Smoothieware 专用 hints 直接迁移到 wire bonder。
- 不要用没有引用的 LLM 长回答说服软件部。
- 不要在没有验收人的情况下自评成功。
- 不要因为 1-2 题失败就重构系统；先分类失败原因。

## 软件部还缺什么输入

如果评估还不能开始，通常缺以下内容：

- 只读代码目录路径。
- 目录范围说明。
- 10 个真实问题。
- 至少 1 条真实报警码、错误日志或运行日志。
- 验收工程师姓名或角色。
- 是否允许外部 LLM，或必须离线/内网。
- 需要排除的目录。
- 常见模块名、报警码、命令码、菜单 ID、配置项名称。

## 下一步 prompt

软件部材料到位后，可以直接使用：

```text
请执行 wire bonder 真实问题第一轮接入评估。

要求：
1. 不改业务代码，不改 repos/**，不改检索算法。
2. 使用软件部提供的只读代码目录、10 个真实问题、日志/报警样例和验收人信息。
3. 先运行 probe，输出接入风险。
4. 如无阻断，建立索引并运行 10 题检索。
5. 每题输出 Top-5 file:line、Top-10 补充、命中方法、是否需要人工确认。
6. 按 docs/real_problem_evaluation_plan.md 的评分表记录结果。
7. 对失败题分类：问题表达不清、索引失败、符号缺失、动态分发、日志字段不足、业务知识缺失。
8. 不引入 tree-sitter、Neo4j、MCP server、GUI。

输出：
- probe 结论；
- 10 题评分表；
- Top-5 / Top-10 人工可用率；
- 失败分类统计；
- 是否进入 MCP / SQLite / trace log / 偏焊专项知识库阶段；
- 软件部下一步需要补充什么。
```
