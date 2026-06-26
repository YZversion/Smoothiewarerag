# Plan B Comparison: rg / BM25 vs CodeGraph

日期：2026-06-26

结论先行：CodeGraph 值得研究，尤其适合 caller / callee / impact radius；但它没有解决 H4 这类 “G28 / 报警码 / 事件码 -> handler” 问题。Smoothieware 主线仍保持 `rg + ctags + BM25 + LLM`，CodeGraph 暂不接入 `app.py`。

## A/B 总表

| 问题 | rg / BM25 | CodeGraph | 判断 |
|------|-----------|-----------|------|
| G-code 的入口文件在哪里？ | 能找到 `Gcode` / `GcodeDispatch`，但问法变化会影响 `SerialConsole` / `Player` 命中。 | 能快速定位 `SerialConsole`、`GcodeDispatch` 和相关 symbol；但事件 caller 边不完整。 | CodeGraph 略强，但仍需源码核查。 |
| `Gcode` 类 / 函数被哪些模块调用？ | 容易漂到 `Kernel` / `Module` 事件系统，不能自然列出 handler 清单。 | `query "on_gcode_received"` 能列出大量 G-code handler。 | CodeGraph 明显更强。 |
| Motion planner 相关核心类有哪些？ | 强，能找到 `Planner`、`Block`、`Conveyor`、`StepTicker`、`StepperMotor`。 | 也强，还能给出 symbol / include 关系。 | 两者都强，CodeGraph 信息结构更好。 |
| halt / error / stop 的调用链在哪里？ | 能找候选文件和函数，不能给调用链。 | 给定 `Kernel::immediate_halt` 后可追 `Endstops::check_limits` / `read_endstops`。 | CodeGraph 更强。 |
| 修改 `Planner::append_block` 后可能影响哪些模块？ | 能定位定义，但影响范围需要人工继续搜。 | `impact` 直接给出 `Robot::append_milestone`、`append_line`、`append_arc` 等影响半径。 | CodeGraph 明显更强。 |

## CodeGraph 强项

- 函数 / 类 / 文件结构查询。
- 同名 handler 清单，例如所有 `on_gcode_received`。
- 给定准确 symbol 后追 `callers`、`callees`、`impact`。
- 快速生成“代码结构层”候选上下文，减少 agent 大范围 grep。

## CodeGraph 弱项

- 事件总线和动态回调边不完整，例如 `callers GcodeDispatch::on_console_line_received` 返回空。
- 对 `THEKERNEL->call_event(...)` 这类全局 singleton / 事件分发识别不完整。
- 对命令号 / 报警码 / 菜单 ID 到 handler 的映射无能为力，需要解析函数体条件判断。
- 同名 symbol 会产生噪声，例如 raw H4 查询里的多个 `home()`。
- 当前工具默认在目标仓库创建 `.codegraph/`，需要未来确认是否能配置到独立索引目录，否则不适合直接放进主流程。

## 误报 / 漏报案例

| 案例 | 类型 | 说明 |
|------|------|------|
| `callers GcodeDispatch::on_console_line_received` 返回空 | 漏报 | 真实入口通过事件注册 / callback 连接，静态 caller 边没有还原。 |
| `callers Kernel::call_event` 只返回 `init` | 漏报 | 多处 `THEKERNEL->call_event(...)` 没有被解析为同一 symbol。 |
| H4 raw 查询出现多个 `home()` | 误导 | `home` 是通用名称，CodeGraph 找 symbol 但不知道哪个处理 `G28`。 |
| `query "process_home_command"` 能命中 | 条件命中 | 只有人工已经知道内部函数名时，CodeGraph 才能准确回到 `Endstops`。 |

## 对 wire bonder 的判断

值得做小模块试验，但范围要克制。

适合迁移的部分：

- 函数定义在哪里？
- 某个函数被谁调用？
- 修改这个函数可能影响哪些上层流程？
- 某个模块有哪些类 / 方法 / include 依赖？
- UI handler、运动控制函数、状态机函数之间有没有静态调用链？

不应该指望 CodeGraph 单独解决的部分：

- 报警码由谁抛出、谁处理。
- 菜单命令 ID / Windows message / MFC command ID 到 handler 的映射。
- 工艺语义，例如一焊、二焊、视觉补偿、气压、Z 轴报警排查。
- 现场日志、维修经验、工程师判断。

## 最终建议

Plan B 的结论是：CodeGraph 可以作为未来 wire bonder 知识库的“代码结构层”候选工具，但不要现在接入主 `app.py`，也不要把主线改成知识图谱系统。

下一步更值得做的是 Plan C：命令 / 事件 / 报警分发索引。它补的是 CodeGraph 和 BM25 都缺的那一层。
