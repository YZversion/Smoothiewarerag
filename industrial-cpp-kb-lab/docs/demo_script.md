# 5 分钟演示脚本

目标：用 Smoothieware 演示 wire bonder 代码知识库的工作方式。演示重点不是证明 Smoothieware 本身，而是证明“问题 -> 相关源码 -> file:line 引用 -> 工程师核查”的流程。

## 0:00-0:30 开场

我要演示的是一个只读代码知识库。它不修改代码、不提交 SVN、不训练模型。输入一个工程问题，它返回相关源码、函数名和 file:line 引用。

这次用 Smoothieware 做替身，因为它也是工业控制风格的 C/C++ 代码，有命令入口、运动链路、急停、模块事件和命令码分发。wire bonder 接入时只需要换成只读代码目录，并重新跑 probe 和索引。

## 0:30-1:10 先扫描，再决策

展示命令：

```powershell
kb probe --repo-root repos\Smoothieware --out reports\smoothieware_probe.md
```

说明要点：

- probe 不理解业务，只做风险扫描。
- 报告包含文件统计、编码统计、ctags 统计、超长文件、generated-like 文件和索引可行性。
- 对 wire bonder，第一步也只做这个，不直接构建全量知识库。

可展示文件：

- `reports/smoothieware_probe.md`
- `reports/scale_test_probe.md`

## 1:10-1:50 入口定位

wire bonder 类比问题：运动命令从界面下发后，进入运控模块的入口在哪里？

Smoothieware 演示问题：

```powershell
kb search "G-code 从哪里进入系统？" --top-k 5 --preview
```

预期讲解：

- 串口入口在 `SerialConsole.cpp`。
- SD 卡播放入口在 `Player.cpp`。
- 两条路径汇入 `GcodeDispatch.cpp`。
- 结论不是凭空生成，必须能点回 file:line。

## 1:50-2:30 错误追踪

wire bonder 类比问题：轴超时、急停、报警触发后，哪里产生，哪里处理？

Smoothieware 演示问题：

```powershell
kb sources "halt emergency 逻辑在哪里" --top-k 8
```

预期讲解：

- `Kernel::immediate_halt` 是核心 halt 入口。
- `KillButton`、`Endstops`、通信链路都可能触发 stop/halt。
- 这类问题要返回多个文件，因为工业设备错误链路通常跨模块。

## 2:30-3:10 状态机 / 流程

wire bonder 类比问题：回零流程或运动流程的主要调用链是什么？

Smoothieware 演示问题：

```powershell
kb search "G-code 如何变成运动命令？" --top-k 8 --preview
```

预期讲解：

- 典型链路：`GcodeDispatch` -> `Robot` -> `Planner` -> `Conveyor` -> `StepTicker` -> `StepperMotor`。
- 这不是完整调用图，但足够作为工程师读代码入口。
- 动态分发无法完全靠 mention graph 捕获，因此后续 wire bonder 需要根据实际消息 ID / 命令表补 dispatch 规则。

## 3:10-3:50 报警码 / 命令码

wire bonder 类比问题：报警码 0x1234 或菜单命令 ID 在哪里定义，哪里处理？

Smoothieware 演示问题：

```powershell
kb search "G28 homing 在哪里处理" --top-k 5 --preview
```

预期讲解：

- Smoothieware 已有 G/M-code dispatch index。
- `G28` 会命中带证据行的处理器。
- wire bonder 的报警码、菜单 ID、Windows 消息或运动命令，需要按公司代码格式抽取 dispatch index。

## 3:50-4:30 模块边界

wire bonder 类比问题：视觉模块和运控模块之间怎么通信？

Smoothieware 演示问题：

```powershell
kb sources "模块系统如何注册 触发 通信" --top-k 8
```

预期讲解：

- `Module` 定义事件订阅接口。
- `Kernel` 管理事件注册和广播。
- `PublicData` 处理模块间共享数据。
- 这类问题不是找一个函数，而是找模块边界和通信机制。

## 4:30-5:00 收尾和下一步

强调边界：

- 代码不外发。
- 不改源码，不写 SVN。
- LLM 只看检索片段，可切换离线模型。
- 结果必须带 file:line，工程师可以核查。
- 下一步只需要一个非核心只读目录和 10 个真实问题。

收尾话术：

如果 10 个真实问题里多数能定位到正确源码，我们再扩大范围；如果不能，就停在 probe 报告和小范围索引，不影响现有开发流程。
