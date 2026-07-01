# First Pilot Acceptance

这份文档保留首轮试点的验收口径摘要。详细评分表、失败分类和下一阶段 gate 已合并到：

- [`wire_bonder_pilot_plan.md`](wire_bonder_pilot_plan.md)
- [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md)

## 试点范围

| 项目 | 范围 |
|---|---|
| 代码范围 | 一个非核心只读目录 |
| 问题数量 | 10 个真实工程问题 |
| 输出形式 | 文件、函数/类、`file:line`、snippet、简短解释 |
| 操作边界 | 不修改源码，不生成 patch，不写 SVN |
| 数据边界 | 代码不外发；LLM 只看检索片段；可完全离线 |

## 判定摘要

| 结果 | 条件 | 下一步 |
|---|---|---|
| 成功 | Top-5 人工可用率 >= 60%，且无安全边界违规 | 扩到第二目录或进入偏焊专项知识地图 |
| 部分成功 | Top-5 可用率 40%-60%，失败集中在可解释类别 | 修检索/补输入后复测 |
| 失败 | Top-5 可用率 < 40%，或结果无法核查/有误导 | 停止扩展，只保留 probe 和评估报告 |

人工评分以 [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md) 的 A/B/C/D/F 分级为准。

## 必须保留的证据

- `reports/wire_bonder_probe.md`
- 10 个问题原文、类别和 expected area。
- 每题 Top-5 / Top-10 `file:line`。
- 验收工程师评分和备注。
- 失败分类统计。
- 是否调用 LLM；如调用，确认只发送检索 chunk。

## 明确不进入的工作

- 不做自动修改代码。
- 不生成 patch / diff。
- 不提交 SVN / Git。
- 不做闭环自动补偿。
- 不承诺 100% 正确诊断。
- 不以 GUI、MCP 或 Neo4j 作为首轮试点成功条件。
