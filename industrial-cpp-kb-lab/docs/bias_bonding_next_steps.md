# 偏焊 AI 项目下一步行动方案

## 一句话定位

不要把项目定义成“让大模型判断为什么偏焊”，而要定义成：

> 焊线机偏焊根因追溯与智能诊断系统。

它的核心不是猜测原因，而是把代码、日志、视觉定位、运动控制、工艺参数、检测结果和历史案例串成可追溯证据链，让软件、工艺、设备、质量工程师能共同判断偏焊根因。

## 审查结论

- 我不同意你的哪一点：把当前项目继续做成一个独立聊天式 RAG，或者把目标说成“AI 自动判断偏焊原因”。
- 为什么这可能是错的：偏焊是视觉、运动、工艺、物料、软件时序共同作用的问题。没有每根焊线的时序证据链，LLM 只能根据片段猜测，难以被软件部和工艺部信任。
- 这个问题的严重程度：高风险。
- 更好的替代方案：把 Smoothieware 项目升级为“工业运动控制代码理解训练场”，把公司项目定位为“偏焊证据链 + 代码知识库 + 日志追踪 + 诊断工具层”。
- 下一步应该验证什么：软件部是否愿意提供一个非核心只读代码目录、10 个真实偏焊/时序问题、以及现有日志和检测数据字段样例。

## 今天找软件部时不要提什么

不要一上来提：

- 做成 Cursor/Qwen Code 的替代品。
- 自动修改代码。
- 自动提交 SVN/Git。
- 自动给偏焊下最终结论。
- 直接做闭环补偿。
- 先做完整 GUI。

这些会让对方立刻联想到安全、责任、上线风险和额外工作量。

今天要强调的是：

- 当前阶段只读。
- 不改业务仓库。
- 不生成 patch。
- 不训练模型。
- LLM 只看检索片段。
- 输出必须带 `file:line`，由工程师核查。
- 目标是缩短定位时间，不替代工程师判断。

## 今天应该提的 3 个最小需求

### 1. 一个非核心只读代码目录

要求：

- 只读权限即可。
- 不要核心机密模块，先选风险低但结构真实的目录。
- 最好包含视觉、运动、recipe、IO、状态机、日志中的一部分。
- 允许本地建立索引，但不写回源码目录。

目的：

- 验证现有代码知识库能否迁移到焊线机软件。
- 找出 ctags、编码、目录结构、超长文件、动态分发等接入风险。

### 2. 10 个真实工程问题

问题不要太泛，最好来自真实排查场景。

推荐类型：

1. 偏焊相关的坐标补偿代码在哪里？
2. vision offset 是在哪里产生、保存、传给 motion 的？
3. bond point 坐标从 recipe 到 motion command 经过哪些模块？
4. 哪些代码路径可能导致运动线程使用旧坐标？
5. camera trigger、vision result、motion complete 的时序在哪里处理？
6. 某个报警码或错误日志对应哪个处理函数？
7. recipe 参数更新后什么时候生效？
8. 某个 IO handshake 失败时会走哪些状态机分支？
9. post-bond inspection 的结果在哪里生成和保存？
10. 测试软件判定 pass 时，哪些位置/图像缺陷可能没有被覆盖？

目的：

- 这些问题是评估集，不是聊天样例。
- 后续用 `Recall@5`、`mean_cov@5`、工程师人工确认来判断项目是否值得继续。

### 3. 一位验收工程师

要求：

- 由软件部指定一个熟悉相关模块的人。
- 他只需要判断系统返回的 `file:line` 是否有用。
- 不要求他一开始认可 AI，只需要帮忙判定引用是否指向正确代码区域。

目的：

- 防止项目变成自我评估。
- 建立软件部可接受的验收标准。

## 你应该问软件部的 10 个问题

1. 偏焊是第一焊点偏、第二焊点偏，还是两者都有？
2. 偏焊方向是否固定，例如总是 X+、Y-，还是随机？
3. 是某台机器更容易偏，还是所有机器都有？
4. 是某个产品、pad、leadframe、批次更容易发生？
5. 现有系统能不能保存 pre-bond 和 post-bond 图像？
6. 现有系统有没有记录 vision offset、mark score、坐标补偿结果？
7. 运动控制有没有记录 actual encoder position、following error、settle time？
8. 软件里视觉、运动、IO、recipe 是否多线程？有没有统一 sequence id？
9. 偏焊发生时测试软件为什么判不出来？它测的是电性能、位置，还是图像？
10. 有没有历史偏焊案例，包括现象、机器、产品、最终原因、处理方法？

## 偏焊诊断的数据底座

如果要让 AI 真正有用，后面必须推动“每根焊线证据链”。最小数据模型如下：

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

当前阶段不要求一次拿齐这些字段，但要确认系统里哪些已有、哪些缺失、哪些需要后续加 trace。

## 轻量 trace log 需求

软件部如果承认“时序问题很多”，那下一阶段最重要的不是 GUI，而是 trace。

每个关键事件建议记录：

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

- 视觉结果是什么时候算出来的？
- 运动指令是什么时候发出的？
- 运动指令使用的是哪一版坐标？
- bond 前有没有等待 motion settled？
- IO complete 和 vision complete 谁先发生？
- 偏焊那一次和正常那一次的事件顺序差在哪里？

## Smoothieware 项目的调整方向

Smoothieware 不是偏焊业务答案，它是训练场。

接下来它应该验证 5 个能力：

1. 能不能回答“某个指令从输入到执行的完整链路”。
2. 能不能找出相关类、函数、模块。
3. 能不能解释参数如何影响运动。
4. 能不能生成调用链或流程图。
5. 能不能对异常问题提出排查路径。

建议把项目目标收窄成：

> 工业运动控制代码理解助手原型。

不要继续扩成万能 C++ 知识库。

## 和 Qwen Code / Cursor 的关系

不要和 Qwen Code、Cursor 竞争。

更合理的定位是：

```text
Qwen Code / Cursor / VS Code / Web UI
        ↓
公司内部 MCP Tools / Knowledge API
        ↓
代码结构索引
调用链查询
文档检索
故障案例库
日志追踪
设备数据查询
```

也就是说：

- Qwen Code 负责工程师和代码的交互入口。
- 本项目负责公司内部知识底座和诊断证据层。

未来工具可以设计成：

```text
search_code(query)
find_call_chain(symbol)
explain_module(module_name)
search_docs(query)
search_fault_cases(symptom)
trace_bond_event(machine_id, lot_id, wire_id)
find_similar_bias_bonding_cases(features)
```

如果只做普通 RAG 聊天工具，很容易被通用 coding agent 替代。只有把代码、业务流程、历史故障、日志、设备数据统一成可审计工具层，项目才有长期价值。

## 2-4 周最小落地计划

### Week 1：拿输入

目标：

- 拿到非核心只读代码目录。
- 拿到 10 个真实问题。
- 拿到一份日志样例或报警样例。
- 确认验收工程师。

输出：

- `kb probe` 报告。
- 接入风险清单。
- 10 题评估集草案。

### Week 2：做只读代码知识库验证

目标：

- 建立代码索引。
- 跑 10 题检索。
- 输出 `file:line` 引用。
- 让验收工程师判断是否有用。

输出：

- Recall@5 / Recall@10 / mean_cov@5。
- 每题人工验收结果。
- 检索失败分类。

### Week 3：专项偏焊知识地图

目标：

- 梳理视觉定位、坐标补偿、recipe、motion command、IO handshake、inspection 的代码入口。
- 形成偏焊相关模块地图。

输出：

- 偏焊专项代码地图。
- 典型执行链路图。
- 缺失日志字段清单。

### Week 4：trace log 方案评审

目标：

- 不改业务逻辑，先设计轻量 trace。
- 明确每个事件字段来自哪里。
- 选 1-2 条链路做试点，例如 `vision result -> coordinate compensation -> motion command`。

输出：

- trace 字段设计。
- 插桩点清单。
- 偏焊证据链样例。

## 进入下一阶段的 gate

满足以下条件，再继续投入：

- 10 个真实问题中，多数能定位到有用文件和函数。
- 软件部验收工程师认可 `file:line` 引用有帮助。
- 至少能画出一条偏焊相关链路，例如 `vision offset -> motion command`。
- 确认现有日志无法支撑根因追溯，需要补 trace。
- 软件部愿意讨论轻量 trace，而不是只让 AI 猜原因。

如果这些条件不满足，不应该继续做 GUI、MCP 或模型训练。

## 暂不做的事情

- 不做自动修改代码。
- 不做自动提交 SVN/Git。
- 不做 patch 生成。
- 不做闭环自动补偿。
- 不训练外部模型。
- 不上传全仓库源码。
- 不做完整 GUI。
- 不承诺 100% 正确诊断。

这些不是能力不足，而是当前阶段的风险边界。

## 你今天可以直接说的话

> 我现在不想让 AI 自动判断偏焊原因，也不想让它改代码。第一阶段只做只读定位：给它真实问题或错误信息，让它返回相关文件、函数和行号，由软件部工程师核查。
>
> 如果这一步证明有用，我们再围绕偏焊建立专项知识库，梳理 vision offset、坐标补偿、motion command、IO handshake、inspection 的链路。
>
> 真正要解决偏焊，后面还需要每根焊线的证据链和轻量 trace log。AI 的价值不是替代博士判断，而是把以前看不到的时序、代码和数据线索串起来。
>
> 所以我今天只申请三件事：一个非核心只读代码目录，10 个真实问题，一位工程师帮忙判断返回的 file:line 是否有用。

## 下一步 prompt

如果软件部给了目录和问题，下一步可以这样让我做：

```text
请做 wire bonder 只读接入前置审查。

要求：
1. 不改业务代码，不改 repos/**。
2. 读取软件部提供的只读目录结构和 10 个真实问题。
3. 先运行 probe，检查编码、文件类型、ctags 可用性、超长文件、generated-like 文件、潜在敏感路径。
4. 判断是否可以建立索引；如果不可以，列出阻断项和最小修复建议。
5. 如果可以，构建索引并对 10 个问题做检索评估。
6. 输出每题 Top-5 file:line，标注是否需要软件部人工确认。
7. 不生成 patch，不调用外部 LLM，不做自动修改。

输出：
- 接入风险表；
- 10 题检索结果；
- 失败原因分类；
- 是否值得进入偏焊专项知识库阶段；
- 下一步需要补哪些日志或 trace 字段。
```
