# Smoothieware 代码地图 v1

> Phase 1.3 ripgrep 探索 + Phase 3 索引验证，最后更新 2026-06-25

### 关键入口行号（索引 / ctags 确认）

| 文件 | 符号 | 行号 | 说明 |
|------|------|------|------|
| `SerialConsole.cpp` | `on_main_loop` | 249 | 串口收行；~271 `call_event(ON_CONSOLE_LINE_RECEIVED)` |
| `GcodeDispatch.cpp` | `on_console_line_received` | **56** | G-code 行解析入口（非构造函数 :42） |
| `Player.cpp` | `on_main_loop` | 422 | SD 卡播放主循环 |
| `Robot.cpp` | `on_gcode_received` | **488** | 运动 G-code 处理入口 |
| `Planner.cpp` | `Planner` / `append_block` | 36 / 52+ | 速度规划 |
| `Conveyor.cpp` | `queue_head_block` | 159 | Block 入队 |
| `StepTicker.cpp` | `step_tick` 等 | — | 步进定时中断 |
| `Kernel.cpp` | `immediate_halt` | — | 全局停机 |

---

## 项目定位（一句话）

运行在 LPC17xx (ARM Cortex-M3) 上的开源 G-code 解释器 + CNC 控制器，
用 OOP C++ 实现，「一切皆模块」通过事件系统通信，运动控制移植自 grbl。

---

## 5 个核心问题

| # | 问题 |
|---|------|
| Q1 | G-code 从哪里进入系统？ |
| Q2 | G-code 如何变成运动命令？ |
| Q3 | Motion / Planner / Stepper 相关代码在哪里？ |
| Q4 | error / stop / halt / emergency 逻辑在哪里？ |
| Q5 | 模块系统如何注册、触发、通信？ |

---

## ripgrep 高频文件统计

| 文件        | Gcode命中 | Motion命中 | Halt命中 | 模块命中 | **总分** |
|------|:---------:|:----------:|:--------:|:--------:|:--------:|
| `Robot.cpp`          | 169 | 33 | 55 |  8 | **265** |
| `Endstops.cpp`       |  78 |  4 |122 |  9 | **213** |
| `SimpleShell.cpp`    |  30 |  0 | 46 | 26 | **102** |
| `Extruder.cpp`       |  62 | 36 |  0 |  0 |  **98** |
| `GcodeDispatch.cpp`  |  55 |  0 | 16 |  8 |  **79** |
| `Player.cpp`         |  52 |  0 |  0 | 12 |  **64** |
| `ZProbe.cpp`         |  66 |  0 | 18 |  5 |  **89** |
| `Kernel.cpp`         |   0 |  4 | 16 | 12 |  **32** |
| `Planner.cpp`        |   0 | 19 |  0 |  0 |  **19** |
| `StepperMotor.cpp`   |   0 | 13 |  0 |  0 |  **13** |
| `KillButton.cpp`     |   0 |  0 | 37 |  0 |  **37** |
| `main.cpp`           |   0 |  0 |  0 | 26 |  **26** |
| `StepTicker.cpp`     |   0 |  4 |  0 |  0 |   **4** |
| `Conveyor.cpp`       |   0 |  6 |  0 |  6 |  **12** |
| `TemperatureControl.cpp` | 44 | 0 | 15 | 12 | **71** |

---

## 按模块分区

### Communication（G-code 输入层）

| 文件 | 作用 | 对应问题 |
|------|------|---------|
| `src/modules/communication/SerialConsole.cpp/h` | UART 接收字符 → 缓冲 → 触发 `ON_CONSOLE_LINE_RECEIVED`；收到 `!` 直接设 `halt_flag` | Q1, Q4 |
| `src/modules/communication/GcodeDispatch.cpp/h` | 订阅 `ON_CONSOLE_LINE_RECEIVED`，解析行 → 广播 `ON_GCODE_RECEIVED` | Q1, Q2 |
| `src/modules/utils/player/Player.cpp/h` | 从 SD 卡读 `.gcode` 文件，逐行送入 GcodeDispatch | Q1 |

### Robot / Motion（运动核心层）

| 文件 | 作用 | 对应问题 |
|------|------|---------|
| `src/modules/robot/Robot.cpp/h` | 订阅 `ON_GCODE_RECEIVED`，坐标解析 + 运动学变换 → 调 `Planner::append_block()` | Q2, Q3 |
| `src/modules/robot/Planner.cpp/h` | 速度规划：`junction_deviation` + `acceleration`，写入 `Block` | Q2, Q3 |
| `src/modules/robot/Block.cpp/h` | 单个运动段的数据结构（距离、速度、步数） | Q3 |
| `src/modules/robot/Conveyor.cpp/h` | `Block` 队列管理，协调规划与执行 | Q2, Q3 |
| `src/libs/StepTicker.cpp/h` | 定时中断驱动步进，2.62 定点数计算，消费 `Block` | Q3 |
| `src/libs/StepperMotor.cpp/h` | 单轴步进电机控制，输出 step/dir 脉冲 | Q3 |

### Kernel / Module System（框架层）

| 文件 | 作用 | 对应问题 |
|------|------|---------|
| `src/libs/Module.h` | 模块基类，9 个事件虚函数，`register_for_event()` | Q5 |
| `src/libs/Kernel.cpp/h` | 单例，持有 `hooks` 数组，`add_module()` / `call_event()` / `immediate_halt()` | Q4, Q5 |
| `src/main.cpp` | 系统启动入口，实例化 Kernel + 注册所有模块 | Q5 |
| `src/libs/PublicData.cpp/h` | 模块间数据共享接口（非事件方式） | Q5 |

### Error / Halt（安全停止层）

| 文件 | 作用 | 对应问题 |
|------|------|---------|
| `src/modules/utils/killbutton/KillButton.cpp/h` | 硬件急停按钮，触发 `ON_HALT` | Q4 |
| `src/modules/robot/Endstops.cpp/h` | 限位开关检测，超限触发 halt；也处理回零 G28 | Q4 |
| `src/libs/Kernel.cpp` → `immediate_halt()` | 立即停机，设 `halted=true`，广播 `ON_HALT` | Q4 |

---

## 10 个第一批知识库输入文件（Phase 1.5）

按「对5个练习问题的覆盖度」选定：

```
1.  src/libs/Module.h                                   ← Q5 模块基类定义
2.  src/libs/Kernel.cpp                                 ← Q4/Q5 事件系统核心
3.  src/modules/communication/GcodeDispatch.cpp         ← Q1/Q2 G-code 入口
4.  src/modules/communication/SerialConsole.cpp         ← Q1/Q4 串口 + halt_flag
5.  src/modules/robot/Robot.cpp                         ← Q2/Q3 运动学 + Gcode处理
6.  src/modules/robot/Planner.cpp                       ← Q2/Q3 速度规划
7.  src/modules/robot/Conveyor.cpp                      ← Q2/Q3 Block队列
8.  src/libs/StepTicker.cpp                             ← Q3 步进中断
9.  src/modules/utils/killbutton/KillButton.cpp         ← Q4 急停逻辑
10. src/modules/robot/Endstops.cpp                      ← Q4 限位+halt
```

> 补充参考（不入第一批，按需查）：`Player.cpp`、`Block.cpp`、`StepperMotor.cpp`、`main.cpp`、`PublicData.cpp`
