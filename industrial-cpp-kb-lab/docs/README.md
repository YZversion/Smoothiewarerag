# Documentation Index

这份索引用于快速判断“该看哪份文档”。当前文档按用途分为 5 类：项目入口、试点准备、工程运行、评估报告、历史实验。避免在多份文档里重复维护同一套流程和安全边界。

## 当前主线

| 场景 | 优先阅读 | 用途 |
|---|---|---|
| 想了解项目现在是什么状态 | [`../../AGENTS.md`](../../AGENTS.md) | 单一事实来源：进度、约束、命令、文档索引 |
| 想看完整路线图 | [`../../PLAN.md`](../../PLAN.md) | Phase 0-12 和第二阶段 A-E 计划 |
| 想部署或运行 | [`deployment.md`](deployment.md) | 环境、索引构建、查询、离线部署、HTTP 服务 |
| 想向软件部推进试点 | [`wire_bonder_pilot_plan.md`](wire_bonder_pilot_plan.md) | wire bonder 只读试点主入口 |
| 软件部材料到位后执行评估 | [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md) | 10 个真实问题的执行流程、评分表和 gate |

## Wire Bonder 试点材料

| 文件 | 当前职责 | 备注 |
|---|---|---|
| [`wire_bonder_pilot_plan.md`](wire_bonder_pilot_plan.md) | 主文档：试点目标、输入、流程、验收、下一阶段 gate | 后续优先维护这里 |
| [`stakeholder_pitch.md`](stakeholder_pitch.md) | 可直接发给软件部的话术 | 保持短、专业、低风险 |
| [`wire_bonder_intake_checklist.md`](wire_bonder_intake_checklist.md) | 向软件部索取材料的清单 | 只保留请求清单，不重复评估流程 |
| [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md) | 收到目录和问题后的评估执行手册 | 评分表和失败分类以此为准 |
| [`capability_boundary.md`](capability_boundary.md) | 能力边界、安全边界、已知技术边界 | 用于回答“会不会外发/改代码/替代评审” |
| [`bias_bonding_next_steps.md`](bias_bonding_next_steps.md) | 偏焊方向说明和数据/trace 需求摘要 | 已收敛为指向试点主线的简版 |
| [`mcp_feasibility_review.md`](mcp_feasibility_review.md) | MCP / SQLite / tree-sitter / Neo4j 可行性审查 | 仅作为后续方向，不是当前执行项 |
| [`wire_bonder_migration_plan.md`](wire_bonder_migration_plan.md) | 历史迁移计划摘要 | 详细试点流程已合并到主文档 |
| [`first_pilot_acceptance.md`](first_pilot_acceptance.md) | 历史验收口径摘要 | 当前评分以 `real_problem_evaluation_plan.md` 为准 |

## 演示材料

| 文件 | 用途 |
|---|---|
| [`demo_script.md`](demo_script.md) | 5 分钟 Smoothieware 映射演示脚本 |
| [`demo_visual_plan.md`](demo_visual_plan.md) | 演示动态图方案：检索流水线、引用定位、安全边界 |

## 工程与评估报告

| 文件 | 用途 |
|---|---|
| [`benchmark_report.md`](benchmark_report.md) | Phase B 规模压测与 P95 修复记录 |
| [`generalization_audit.md`](generalization_audit.md) | 泛化审计基线：scale_test 失败边界 |
| [`generalization_followup_diagnosis.md`](generalization_followup_diagnosis.md) | scale_test 38% -> 75% 的修复诊断 |

## 历史与证据

| 目录 | 用途 |
|---|---|
| [`../notes/`](../notes/) | Smoothieware 代码地图、eval 失败案例、Phase 结论、A/B 实验记录 |
| [`../reports/`](../reports/) | `kb probe` 生成的实际报告 |
| [`../../docs/history.md`](../../docs/history.md) | session 级进度日志 |

细分索引：

- [`../notes/README.md`](../notes/README.md)
- [`../reports/README.md`](../reports/README.md)

## 维护规则

- `AGENTS.md` 只放当前状态、约束、常用命令和文档索引。
- `PLAN.md` 只放路线图和验收标准，不再复制执行报告全文。
- `docs/wire_bonder_pilot_plan.md` 是试点主入口；输入清单、流程、验收 gate 不要在多处重复维护。
- `docs/real_problem_evaluation_plan.md` 是真实问题评估执行手册；评分表和失败分类以它为准。
- `notes/` 和 `reports/` 保留证据原文，不为了整洁改写历史数据。
