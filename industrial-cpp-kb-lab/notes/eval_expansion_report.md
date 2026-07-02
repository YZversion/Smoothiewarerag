# Eval 扩 holdout 题集报告

> baseline（halt hint 转正后）eval 耗时 9.792s
> gate_ok=True  全体 mean_cov@5=75.8%  (48 题)

## 分桶统计

| 分桶 | n | mean cov@5 | single | multi |
|------|---|------------|--------|-------|
| 全体 | 48 | 75.8% | 100.0% | 44.8% |
| 原 35 题 | 35 | 96.4% | 100.0% | 84.2% |
| 旧 holdout H1-H30 | 30 | 98.3% | 100.0% | 83.3% |
| 新 holdout H31-H43 | 13 | 20.5% | 0.0% | 20.5% |
| 新题·hub召回 | 8 | 6.2% | 0.0% | 6.2% |

### 新题按 note 类别

- **change-impact**: n=2 mean=41.7% multi=41.7%
- **hub召回**: n=8 mean=6.2% multi=6.2%
- **跨模块流程**: n=3 mean=44.4% multi=44.4%

## 原 35 题 baseline 确认

- 原 35 题 mean cov@5: **96.4%**（预期 ≈96.4% / hint_only）
- 旧 holdout 单文件题 miss: 无（100%）

## 新题逐题结果（H31-H43）

| ID | 类别 | cov@5 | hit/miss | vocab_mismatch |
|----|------|-------|----------|----------------|
| H31 | hub召回 | 0% | 0/3 | True |
| H32 | hub召回 | 0% | 0/2 | True |
| H33 | hub召回 | 0% | 0/2 | True |
| H34 | hub召回 | 0% | 0/2 | True |
| H35 | hub召回 | 0% | 0/2 | True |
| H36 | hub召回 | 50% | 1/2 | True |
| H37 | hub召回 | 0% | 0/3 | True |
| H38 | hub召回 | 0% | 0/2 | False |
| H39 | 跨模块流程 | 17% | 1/6 | False |
| H40 | 跨模块流程 | 50% | 1/2 | False |
| H41 | 跨模块流程 | 67% | 2/3 | True |
| H42 | change-impact | 50% | 1/2 | False |
| H43 | change-impact | 33% | 1/3 | True |

## Miss 题通道级明细

### H31 — 各功能模块是怎么被挂到系统里并开始参与运行的？
cov@5=0%  miss=['src/libs/Kernel.cpp', 'src/libs/Module.cpp', 'src/main.cpp']
- `src/libs/Kernel.cpp`: pool=0/9  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/libs/Module.cpp`: pool=0/4  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/main.cpp`: pool=0/3  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H32 — 内核怎样把事件通知到各个功能模块？
cov@5=0%  miss=['src/libs/Kernel.cpp', 'src/libs/Module.cpp']
- `src/libs/Kernel.cpp`: pool=0/9  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/libs/Module.cpp`: pool=0/4  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H33 — 上电后配置文件是在哪里被读入并变成可查询参数的？
cov@5=0%  miss=['src/libs/ConfigSources/FileConfigSource.cpp', 'src/libs/Config.cpp']
- `src/libs/ConfigSources/FileConfigSource.cpp`: pool=0/11  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/libs/Config.cpp`: pool=0/9  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H34 — 一个模块想读取另一个模块暴露的运行状态，走什么共享数据机制？
cov@5=0%  miss=['src/libs/PublicData.cpp', 'src/libs/Kernel.cpp']
- `src/libs/PublicData.cpp`: pool=0/3  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/libs/Kernel.cpp`: pool=0/9  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H35 — 主循环里空闲时各模块的后台处理是在哪里被驱动的？
cov@5=0%  miss=['src/main.cpp', 'src/libs/Kernel.cpp']
- `src/main.cpp`: pool=0/3  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/libs/Kernel.cpp`: pool=0/9  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H36 — 周期性慢速定时任务是在哪里注册并触发模块回调的？
cov@5=50%  miss=['src/libs/SlowTicker.cpp']
- `src/libs/SlowTicker.cpp`: pool=2/9  prefilter_rank=10 score=85.0  zero_signal=False
  - channels: ['symbol', 'bm25']

### H37 — 开发新硬件功能模块时，必须实现哪些框架接口、在哪里接入系统？
cov@5=0%  miss=['src/libs/Module.h', 'src/libs/Kernel.cpp', 'src/main.cpp']
- `src/libs/Module.h`: pool=0/2  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/libs/Kernel.cpp`: pool=0/9  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/main.cpp`: pool=0/3  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H38 — 通过串口命令在线修改配置项时，哪些核心组件会参与？
cov@5=0%  miss=['src/modules/utils/configurator/Configurator.cpp', 'src/libs/Config.cpp']
- `src/modules/utils/configurator/Configurator.cpp`: pool=0/4  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/libs/Config.cpp`: pool=0/9  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H39 — G0 快速移动命令从串口收到到步进脉冲输出，经过哪些模块？
cov@5=17%  miss=['src/modules/communication/SerialConsole.cpp', 'src/modules/communication/GcodeDispatch.cpp', 'src/modules/robot/Planner.cpp', 'src/modules/robot/Conveyor.cpp', 'src/libs/StepTicker.cpp']
- `src/modules/communication/SerialConsole.cpp`: pool=0/14  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/modules/communication/GcodeDispatch.cpp`: pool=3/6  prefilter_rank=10 score=4.5  zero_signal=False
  - channels: ['bm25']
- `src/modules/robot/Planner.cpp`: pool=0/6  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/modules/robot/Conveyor.cpp`: pool=0/15  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**
- `src/libs/StepTicker.cpp`: pool=0/14  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H40 — M104 设置喷头温度后，温度控制逻辑在哪里被唤起？
cov@5=50%  miss=['src/modules/communication/GcodeDispatch.cpp']
- `src/modules/communication/GcodeDispatch.cpp`: pool=0/6  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### H41 — 限位开关触发后，运动停止和急停处理涉及哪些文件？
cov@5=67%  miss=['src/modules/tools/endstops/Endstops.cpp']
- `src/modules/tools/endstops/Endstops.cpp`: pool=21/21  prefilter_rank=3 score=125.0  zero_signal=False
  - channels: ['method', 'class', 'symbol', 'bm25']

### H42 — 如果修改 Planner::append_block 的行为，哪些文件最可能需要一起检查？
cov@5=50%  miss=['src/modules/robot/Robot.cpp']
- `src/modules/robot/Robot.cpp`: pool=36/36  prefilter_rank=6 score=125.0  zero_signal=False
  - channels: ['method', 'class', 'symbol', 'bm25']

### H43 — 如果修改 Kernel 向模块分发事件的机制，哪些框架文件会牵涉？
cov@5=33%  miss=['src/libs/Module.cpp', 'src/main.cpp']
- `src/libs/Module.cpp`: pool=1/4  prefilter_rank=62 score=4.3  zero_signal=False
  - channels: ['bm25']
- `src/main.cpp`: pool=2/3  prefilter_rank=49 score=4.5  zero_signal=False
  - channels: ['bm25']

### H8 — main 函数和系统启动入口在哪里？
cov@5=50%  miss=['src/libs/Kernel.cpp']
- `src/libs/Kernel.cpp`: pool=0/9  prefilter_rank=None score=0.0  zero_signal=True
  - channels: **(none)**

### Q3 — Motion / Planner / Stepper 相关代码在哪里？
cov@5=83%  miss=['src/modules/robot/Robot.cpp']
- `src/modules/robot/Robot.cpp`: pool=36/36  prefilter_rank=4 score=125.0  zero_signal=False
  - channels: ['method', 'class', 'symbol', 'bm25']

### Q4 — error / stop / halt / emergency 逻辑在哪里？
cov@5=57%  miss=['src/modules/communication/SerialConsole.cpp', 'src/modules/communication/GcodeDispatch.cpp', 'src/modules/utils/killbutton/KillButton.cpp']
- `src/modules/communication/SerialConsole.cpp`: pool=14/14  prefilter_rank=5 score=125.0  zero_signal=False
  - channels: ['method', 'class', 'symbol', 'bm25']
- `src/modules/communication/GcodeDispatch.cpp`: pool=6/6  prefilter_rank=6 score=125.0  zero_signal=False
  - channels: ['method', 'class', 'symbol', 'bm25']
- `src/modules/utils/killbutton/KillButton.cpp`: pool=5/5  prefilter_rank=2 score=125.0  zero_signal=False
  - channels: ['method', 'class', 'symbol', 'bm25']

### Q5 — 模块系统如何注册、触发、通信？
cov@5=83%  miss=['src/libs/Kernel.h']
- `src/libs/Kernel.h`: pool=2/3  prefilter_rank=6 score=85.0  zero_signal=False
  - channels: ['symbol', 'bm25']


## 关键问题：类别1 hub 题有多少与 H8 同机制（目标文件全通道零信号）？

- hub 类新题共 **8** 道；其中 **7** 道至少有一个 expected 文件全通道零信号。
- 零信号清单：
  - H31: `src/libs/Kernel.cpp` prefilter_rank=None score=0.0
  - H31: `src/libs/Module.cpp` prefilter_rank=None score=0.0
  - H31: `src/main.cpp` prefilter_rank=None score=0.0
  - H32: `src/libs/Kernel.cpp` prefilter_rank=None score=0.0
  - H32: `src/libs/Module.cpp` prefilter_rank=None score=0.0
  - H33: `src/libs/ConfigSources/FileConfigSource.cpp` prefilter_rank=None score=0.0
  - H33: `src/libs/Config.cpp` prefilter_rank=None score=0.0
  - H34: `src/libs/PublicData.cpp` prefilter_rank=None score=0.0
  - H34: `src/libs/Kernel.cpp` prefilter_rank=None score=0.0
  - H35: `src/main.cpp` prefilter_rank=None score=0.0
  - H35: `src/libs/Kernel.cpp` prefilter_rank=None score=0.0
  - H37: `src/libs/Module.h` prefilter_rank=None score=0.0
  - H37: `src/libs/Kernel.cpp` prefilter_rank=None score=0.0
  - H37: `src/main.cpp` prefilter_rank=None score=0.0
  - H38: `src/modules/utils/configurator/Configurator.cpp` prefilter_rank=None score=0.0
  - H38: `src/libs/Config.cpp` prefilter_rank=None score=0.0

## 结论留白

（待人工判断：hub 扩展机制是否值得建、dense 实验是否提前）

## 附：analyze_by_multiplicity（48 题）

见 `notes/eval_multiplicity_post_expansion.md`。要点：原 35 题 multi 桶 84.2% 与 hint 转正一致；加入 H31-H43 后全体 multi 桶降至 44.8%，主要由 hub 类功能性提问拉低。
