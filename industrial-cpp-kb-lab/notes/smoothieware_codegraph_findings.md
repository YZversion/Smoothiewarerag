# Smoothieware CodeGraph Findings

日期：2026-06-26

目的：记录 Plan B B 面结果，验证 CodeGraph 是否能比普通 `rg` / BM25 更直接回答函数定义、调用者、被调用者、依赖关系和影响范围。

## 工具确认

本次使用：

- package：`@colbymchenry/codegraph`
- version：`1.1.1`
- CLI：`codegraph`
- 本地存储：`.codegraph/codegraph.db`
- 主要命令：`query`、`explore`、`node`、`files`、`callers`、`callees`、`impact`、`status`
- 支持语言：README 标注支持 C/C++，包括 `.c`、`.h`、`.cpp`、`.hpp`、`.cc`
- 集成方式：CLI / MCP，可供 Codex CLI、Cursor、Claude Code 等 agent 使用

初始化结果：

```text
Indexed 546 files
Nodes: 7,440
Edges: 16,690
DB size: 12.49 MB
```

注意：该工具默认必须在目标仓库下创建 `.codegraph/`。本次只作为临时实验索引，实验结束后清理，不纳入主线产物。

## 关键命令

```powershell
codegraph status C:\Users\14390\Desktop\Code\Smoothiewarerag\industrial-cpp-kb-lab\repos\Smoothieware
codegraph query -p C:\Users\14390\Desktop\Code\Smoothiewarerag\industrial-cpp-kb-lab\repos\Smoothieware "on_gcode_received" --limit 20 --json
codegraph callees -p C:\Users\14390\Desktop\Code\Smoothiewarerag\industrial-cpp-kb-lab\repos\Smoothieware "GcodeDispatch::on_console_line_received" --limit 30 --json
codegraph callers -p C:\Users\14390\Desktop\Code\Smoothiewarerag\industrial-cpp-kb-lab\repos\Smoothieware "Planner::append_block" --limit 20 --json
codegraph impact -p C:\Users\14390\Desktop\Code\Smoothiewarerag\industrial-cpp-kb-lab\repos\Smoothieware "Planner::append_block" --depth 2 --json
```

## 5 个问题结果

### 1. G-code 的入口文件在哪里？

CodeGraph 能快速定位：

- `SerialConsole::SerialConsole`：`src/modules/communication/SerialConsole.cpp:38`
- `SerialConsole` class：`src/modules/communication/SerialConsole.h:19`
- `GcodeDispatch::GcodeDispatch`：`src/modules/communication/utils/GcodeDispatch.cpp:42`
- `GcodeDispatch` class：`src/modules/communication/utils/GcodeDispatch.h:17`
- `GcodeDispatch::on_console_line_received`：`src/modules/communication/utils/GcodeDispatch.cpp`

`SerialConsole` 的 docstring 明确说明它读取串口行并通过事件调用传给 command dispatcher。`GcodeDispatch::on_console_line_received` 的 callee 查询能看到它构造 `Gcode` 并解析命令。

局限：`callers GcodeDispatch::on_console_line_received` 返回空，说明事件注册 / 回调路径没有被静态 caller 关系完整还原。

### 2. `Gcode` 类 / 函数被哪些模块调用？

`query "on_gcode_received"` 能快速列出大量 G-code 处理器候选：

- `Robot::on_gcode_received`：`src/modules/robot/Robot.cpp:488`
- `Endstops::on_gcode_received`：`src/modules/tools/endstops/Endstops.cpp:1042`
- `Player::on_gcode_received`：`src/modules/utils/player/Player.cpp:118`
- `SimpleShell::on_gcode_received`：`src/modules/utils/simpleshell/SimpleShell.cpp:174`
- `TemperatureControl::on_gcode_received`：`src/modules/tools/temperaturecontrol/TemperatureControl.cpp:232`
- `ZProbe::on_gcode_received`：`src/modules/tools/zprobe/ZProbe.cpp:255`
- `Laser::on_gcode_received`：`src/modules/tools/laser/Laser.cpp:192`
- `Extruder::on_gcode_received`：`src/modules/tools/extruder/Extruder.cpp:225`
- `ToolManager::on_gcode_received`：`src/modules/tools/toolmanager/ToolManager.cpp:42`

这比 BM25 更像“处理器清单”，适合建立模块地图。

局限：它能列出同名 handler，但不能直接判断某个 handler 是否处理 `G28` / `M17` 这类具体命令号。

### 3. Motion planner 相关核心类有哪些？

`query "Planner"` 和 include/import 结果能快速定位：

- `Planner::Planner`：`src/modules/robot/Planner.cpp:36`
- `Planner` class：`src/modules/robot/Planner.h:14`
- `Planner::append_block`：`src/modules/robot/Planner.cpp`
- `Planner::recalculate`
- `Planner::config_load`
- 相关 include：`Robot.cpp`、`Conveyor.cpp`、`Block.cpp`、`Endstops.cpp`、`ZProbe.cpp`

该类问题 CodeGraph 和 BM25 都表现好；CodeGraph 的优势是能把 symbol、include 关系和方法列表放在一起。

### 4. halt / error / stop 的调用链在哪里？

`query` / `explore` 能快速定位：

- `Kernel::immediate_halt`：`src/libs/Kernel.cpp:351`
- `Endstops::check_limits`：`src/modules/tools/endstops/Endstops.cpp:537`
- `Endstops::read_endstops`：`src/modules/tools/endstops/Endstops.cpp:600`
- `KillButton`：`src/modules/utils/killbutton/KillButton.cpp`
- 多个模块的 `on_halt`

`impact "Kernel::immediate_halt" --depth 2` 返回：

- `Kernel::immediate_halt`
- `Endstops::check_limits`
- `Endstops::read_endstops`

这说明 CodeGraph 对“给定函数名后追调用关系”有效。

局限：`callers Kernel::call_event` 只返回 `init`，没有完整识别 `THEKERNEL->call_event(...)` 的事件总线调用点；对宏、全局 singleton、事件回调存在漏报。

### 5. 修改某个函数后可能影响哪些模块？

`impact "Planner::append_block" --depth 2` 是本次最强结果：

- `Planner::append_block`：`src/modules/robot/Planner.cpp:52`
- `Robot::append_milestone`：`src/modules/robot/Robot.cpp:1273`
- `Robot::reset_compensated_machine_position`：`src/modules/robot/Robot.cpp:1257`
- `Robot::delta_move`：`src/modules/robot/Robot.cpp:1466`
- `Robot::append_line`：`src/modules/robot/Robot.cpp:1495`
- `Robot::append_arc`：`src/modules/robot/Robot.cpp:1585`

这是 BM25 很难直接给出的影响范围。对未来 wire bonder 的“改这个函数会影响哪些流程”很有价值。

## H4 补充观察

问题：`回零 / homing / G28 命令在哪里处理？`

CodeGraph 的表现：

- `query "回零 homing G28"` 能找到 `Endstops::set_homing_offset`、`Endstops::homing_info_t`、`Endstops::move_to_origin` 等相关符号。
- `explore "回零 / homing / G28 命令在哪里处理？"` 会被通用 `home` 符号干扰，结果里出现显示屏、校准等多个 `home()`。
- 如果人工已经知道内部函数名，`query "process_home_command"` 能定位 `Endstops::process_home_command`，`callers` 能回到 `Endstops::on_gcode_received`。

结论：CodeGraph 不能从原始问题稳定推出 “G28 -> Endstops::on_gcode_received -> process_home_command”。这个关系藏在函数体内的条件判断中，需要 Plan C 的命令 / 事件分发索引。

## 小结

CodeGraph 的优势：

- 给定 symbol 后，`callers` / `callees` / `impact` 很直接。
- 适合做大型 C++ 项目的模块地图、handler 清单、影响范围分析。
- 能减少 agent 反复 `rg` 和读文件的上下文浪费。

CodeGraph 的弱点：

- 事件总线、宏、singleton、回调、动态分发会漏边。
- 对 `G28` / 报警码 / 菜单命令 ID 这种“值到 handler”的映射不可靠。
- 有时会出现跨文件同名函数噪声，需要源码核查。
- 当前工具默认把索引写到目标 repo 的 `.codegraph/`，与本项目“不改 repos/**”原则冲突，因此只适合作为临时实验或未来单独配置索引目录。

结论：值得保留为 Plan B 结构层工具，但不能替代 BM25 主线，也不能替代 Plan C。
