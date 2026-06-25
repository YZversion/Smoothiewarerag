# 进度日志 — industrial-cpp-kb-lab

记录每次工作的实际进展、关键发现和遗留问题。

---

## 2026-06-25 — Session 1

### 完成内容

**Phase 0 验收**
- git 2.45.2 ✅、Python 3.11.9 ✅ 已在 PATH
- rg / ctags / dot 通过 winget 安装，二进制在 WinGet Packages 目录，需重开终端刷新 PATH
- `repos/Smoothieware/` 已 clone

**Phase 1.1 — 读3个文档**

*README*（`README.creole`）
- 项目定位：G-code interpreter + CNC controller，OOP C++，目标硬件 LPC17xx / Cortex-M3
- 运动控制部分移植自 grbl

*Module Example*（从源码直接读 `src/libs/Module.h` + `Kernel.h`）
- 9个事件枚举：`ON_MAIN_LOOP` / `ON_CONSOLE_LINE_RECEIVED` / `ON_GCODE_RECEIVED` / `ON_IDLE` / `ON_SECOND_TICK` / `ON_GET_PUBLIC_DATA` / `ON_SET_PUBLIC_DATA` / `ON_HALT` / `ON_ENABLE`
- `Kernel` 是单例，`hooks` 数组（`array<vector<Module*>, 9>`）存所有订阅
- 模块调 `register_for_event()` 订阅，`call_event()` 广播

*Motion Control*（从 `Robot.h` / `Planner.h` / `StepTicker.h` 读）
- 链路：`Robot` → `Planner::append_block()` → `Block` → `Conveyor` → `StepTicker`（定时中断）→ `StepperMotor`
- 关键参数：`junction_deviation`、`z_junction_deviation`、`minimum_planner_speed`
- StepTicker 用 2.62 定点数做步进计算（`STEPTICKER_FPSCALE = 1LL<<62`）

**Phase 1.2 — 锁定5个练习问题**

| # | 问题 | 关键文件 |
|---|------|---------|
| Q1 | G-code 从哪里进入系统 | `SerialConsole.cpp`, `GcodeDispatch.cpp`, `Player.cpp` |
| Q2 | G-code 如何变成运动命令 | `Robot.cpp` → `Planner.cpp` → `StepTicker.cpp` |
| Q3 | Motion/Planner/Stepper 代码在哪 | `src/modules/robot/`, `src/libs/StepTicker.cpp` |
| Q4 | halt/stop/emergency 逻辑 | `Kernel.cpp::immediate_halt`, `KillButton.cpp`, `ON_HALT` |
| Q5 | 模块注册/触发/通信 | `Module.h`, `Kernel.h::hooks`, `PublicData.cpp` |

**文档创建**
- `CLAUDE.md` — 项目速查手册（结构/约束/架构/常用命令）
- `architecture.md` — 系统架构（数据流/模块说明/设计决策）
- `docs/history.md` — 本文件

### 关键发现

- `GcodeDispatch` 订阅的是 `ON_CONSOLE_LINE_RECEIVED`（不是 `ON_GCODE_RECEIVED`），它解析后再广播 `ON_GCODE_RECEIVED` 给其他模块
- `SerialConsole` 有 `halt_flag`，收到 `!` 字符直接触发 halt，无需经过 G-code 解析
- `Player` 是 SD 卡 G-code 文件的入口，和串口入口最终汇合到同一个 `GcodeDispatch`

### 遗留

- Phase 1.3：ripgrep 实际搜索，统计高频文件 ⬜
- Phase 1.4：写 `notes/smoothieware_code_map.md` ⬜
- Phase 1.5：选定 10 个重点文件 ⬜

---

<!-- 新 Session 在此追加，格式：## YYYY-MM-DD — Session N -->
