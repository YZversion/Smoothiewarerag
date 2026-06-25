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

- Phase 1.3：ripgrep 实际搜索，统计高频文件 ✅
- Phase 1.4：写 `notes/smoothieware_code_map.md` ✅
- Phase 1.5：选定 10 个重点文件 ✅
- Phase 2：`01_scan_files.py` / `02_extract_symbols.py` ⬜

---

## 2026-06-25 — Session 1（续）

### Phase 1.3 ripgrep 探索结果

运行4类搜索，统计每文件命中行数：

**最高频文件（跨4个搜索总命中）：**

| 文件 | 总命中 | 主要角色 |
|------|:------:|---------|
| `Robot.cpp` | 265 | 运动核心，Gcode解析 + 运动学 |
| `Endstops.cpp` | 213 | 限位检测 + halt逻辑 |
| `SimpleShell.cpp` | 102 | 命令行 shell，大量 Gcode/halt 命令 |
| `GcodeDispatch.cpp` | 79 | G-code 解析分发入口 |
| `ZProbe.cpp` | 89 | 探针，大量 Gcode 处理 |
| `Extruder.cpp` | 98 | 挤出机（3D打印专用，运动相关） |
| `Kernel.cpp` | 32 | 模块系统中枢 |
| `KillButton.cpp` | 37 | 硬件急停按钮 |
| `Player.cpp` | 64 | SD 卡 G-code 文件播放 |

**关键发现：**
- `Endstops.cpp` halt 命中 122 次，是整个系统 halt 逻辑最集中的文件（超过 KillButton）
- `main.cpp` 模块命中 26 次，是所有模块注册的起点
- `SimpleShell.cpp` 跨3个类别命中，是调试/命令行接口的枢纽

### Phase 1.4 代码地图

已写入 `industrial-cpp-kb-lab/notes/smoothieware_code_map.md`，含：
- ripgrep 高频文件统计表
- 按5个分区（Communication / Robot-Motion / Kernel / Error-Halt）的文件职责表
- 10个第一批知识库输入文件

### Phase 1.5 选定10个重点文件

```
1.  src/libs/Module.h
2.  src/libs/Kernel.cpp
3.  src/modules/communication/GcodeDispatch.cpp
4.  src/modules/communication/SerialConsole.cpp
5.  src/modules/robot/Robot.cpp
6.  src/modules/robot/Planner.cpp
7.  src/modules/robot/Conveyor.cpp
8.  src/libs/StepTicker.cpp
9.  src/modules/utils/killbutton/KillButton.cpp
10. src/modules/robot/Endstops.cpp
```

---

<!-- 新 Session 在此追加，格式：## YYYY-MM-DD — Session N -->
