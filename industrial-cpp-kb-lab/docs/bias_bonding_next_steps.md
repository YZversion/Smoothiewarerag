# Bias Bonding Next Steps

这份文档保留偏焊方向的判断和数据需求摘要。软件部只读试点的执行流程、评分表和 gate 已合并到：

- [`wire_bonder_pilot_plan.md`](wire_bonder_pilot_plan.md)
- [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md)

## 核心判断

偏焊适合做 AI 项目，但第一步不是“让大模型猜根因”，而是建立可追溯证据链：

```text
代码知识库
+ 时序日志
+ 视觉定位数据
+ 运动控制数据
+ 工艺参数
+ 检测结果
+ 历史案例
```

AI 的价值是把这些线索组织成工程师可核查的排查路径，不是替代软件、工艺或设备工程师下最终结论。

## 当前反驳

- 我不同意你的哪一点：把偏焊项目包装成“AI 自动判断偏焊原因”。
- 为什么这可能是错的：没有每根焊线的证据链时，LLM 只能基于片段推测；偏焊又常常涉及视觉、运动、工艺、物料和软件时序共同作用。
- 这个问题的严重程度：高风险。
- 更好的替代方案：先做只读代码定位和真实问题评估，再推动偏焊专项知识地图和轻量 trace。
- 下一步应该验证什么：软件部是否愿意提供非核心只读目录、10 个真实问题、日志/报警样例和验收工程师。

## 偏焊原因分层

| 类别 | 常见问题 |
|---|---|
| 视觉定位 | mark 识别错误、模板分数低、光源变化、相机标定漂移、坐标系转换错误 |
| 运动控制 | settle time 不足、servo following error、热漂移、backlash、Z 轴高度漂移 |
| 工艺/耗材 | capillary 磨损、线材问题、bond force、ultrasonic power、温度、pad 表面状态 |
| 软件时序 | 旧坐标、recipe 未同步、IO handshake 乱序、多线程共享变量、事件顺序偶发错误 |
| 数据链断裂 | 只能看到最终偏焊结果，看不到焊接前后关键事件和坐标版本 |

## 每根焊线证据链字段

第一阶段不要求一次拿齐，但后续要确认哪些字段已有、哪些缺失：

```text
machine_id
product_id
lot_id
unit_id
die_id
wire_id
bond_point_id
recipe_version
target_x, target_y, target_z
vision_offset_x, vision_offset_y
compensated_x, compensated_y
actual_encoder_x, actual_encoder_y, actual_encoder_z
servo_following_error_x/y/z
motion_start_time
motion_settled_time
camera_trigger_time
vision_result_time
bond_start_time
bond_force
ultrasonic_power
temperature
capillary_id
operator_id
post_bond_inspection_x/y
bias_bonding_label
```

## 轻量 Trace 字段

如果真实问题暴露出“时序无法还原”，下一阶段再推动 trace。最小字段：

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

trace 要能回答：

- 视觉结果什么时候算出？
- 运动指令什么时候发出？
- 运动指令使用哪一版坐标？
- bond 前有没有等待 motion settled？
- IO complete 和 vision complete 谁先发生？
- 偏焊与正常样本的事件顺序差异在哪里？

## 2-4 周路线

| 周期 | 目标 | 输出 |
|---|---|---|
| Week 1 | 拿输入 | 只读目录、10 题、日志/报警样例、验收人 |
| Week 2 | 只读代码知识库验证 | probe、索引、10 题 `file:line` 评估 |
| Week 3 | 偏焊专项知识地图 | vision / motion / recipe / inspection 入口和链路 |
| Week 4 | trace log 方案评审 | trace 字段、插桩点、证据链样例 |

## 和 Qwen Code / Cursor 的关系

不要做一个更弱的 Cursor。更合理的定位是：

```text
Qwen Code / Cursor / VS Code / 内部 Web UI
        -> 公司内部 MCP tools / Knowledge API
            -> 代码结构索引、文档检索、故障案例、日志追踪、设备数据
```

Qwen Code / Cursor 负责交互入口；本项目负责公司内部知识底座和诊断证据层。

MCP 是否进入实现阶段，以 [`mcp_feasibility_review.md`](mcp_feasibility_review.md) 和 [`real_problem_evaluation_plan.md`](real_problem_evaluation_plan.md) 的 gate 为准。
