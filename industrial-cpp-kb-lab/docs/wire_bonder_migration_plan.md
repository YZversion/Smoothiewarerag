# Wire Bonder Migration Plan

这份文档是历史迁移计划摘要。当前 wire bonder 试点的主入口已经合并到：

- [`wire_bonder_pilot_plan.md`](wire_bonder_pilot_plan.md)
- [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md)

## 迁移目标

把 Smoothieware 上验证过的只读代码问答能力迁移到公司 wire bonder 代码目录：

```text
输入真实问题
-> 本地检索源码
-> 返回文件、函数、行号、snippet
-> 软件部工程师核查
```

第一轮只验证定位能力，不做自动修改、不生成 patch、不提交 SVN。

## 迁移流程摘要

1. 软件部提供非核心只读目录。
2. 运行 `kb probe`，先看编码、文件类型、ctags、超长文件、generated code 风险。
3. 如无阻断，运行 `kb index build` 建本地索引。
4. 用 10 个真实问题做检索评估。
5. 工程师确认 Top-5 / Top-10 `file:line` 是否有用。
6. 根据失败分类决定是否继续：修检索、补日志、做偏焊专项知识地图、评估 MCP/SQLite。

详细执行步骤见 [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md)。

## 安全边界

- 代码只在本地或内网处理。
- `kb probe` 和 `kb index build` 不写回源码目录。
- LLM 只看检索命中的少量 chunk；可切换离线模型。
- 不训练模型。
- 不上传全仓库源码。
- 不修改源码。
- 不生成 patch。
- 不提交 SVN / Git。

完整能力边界见 [`capability_boundary.md`](capability_boundary.md)。

## 已知适配风险

| 风险 | 影响 | 应对 |
|---|---|---|
| GBK / GB18030 / 混合编码 | 文件读取、行号、snippet 可能异常 | probe 先识别，再决定是否排除或转码副本 |
| MFC / Windows 消息映射 | ctags 可能漏掉事件入口 | 后续按真实失败题补 dispatch 规则 |
| 函数指针 / 动态分发 | 静态 mention graph 无法完整覆盖 | 只承诺 candidate，不承诺完整调用图 |
| 超长文件 / generated code | 检索噪声和延迟上升 | 先排除或单独处理 |
| Smoothieware 专用 hints | 可能误伤 wire bonder 查询 | 迁移时禁用或重写项目 hints |

## 与 Smoothieware 的差异

Smoothieware 证明的是工业运动控制代码理解方法，不是 wire bonder 业务结论。

wire bonder 需要重新验证：

- 视觉定位和坐标补偿链路。
- recipe / 工艺参数加载。
- motion command 和轴控制。
- IO handshake 和状态机。
- 报警码 / 菜单 ID / 命令码映射。
- inspection / 测试软件结果链路。

## 当前状态

等待软件部提供：

- 只读代码目录。
- 10 个真实问题。
- 日志/报警样例。
- 验收工程师。

材料到位后按 [`wire_bonder_pilot_plan.md`](wire_bonder_pilot_plan.md) 执行。
