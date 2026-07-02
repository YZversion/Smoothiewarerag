# Eval multiplicity report

```
Eval cov@5 by expected_files multiplicity (retrieval only)
eval: eval_questions.json
gate_ok: True  mean_cov5 (all): 75.8%

Dataset shape:
  total: 48  single-file: 27  multi-file: 21
  tune multi-file: 5/5
  holdout multi-file: 16/30  (H3, H8, H9 only)

--- mean cov@5 by bucket ---
ALL                           n=48  mean_cov@5=75.8%
TUNE                          n= 5  mean_cov@5=84.8%
HOLDOUT                       n=43  mean_cov@5=74.8%
SINGLE-FILE (all splits)      n=27  mean_cov@5=100.0%
MULTI-FILE (all splits)       n=21  mean_cov@5=44.8%
TUNE / single                 n= 0  mean_cov@5=0.0%
TUNE / multi                  n= 5  mean_cov@5=84.8%
HOLDOUT / single              n=27  mean_cov@5=100.0%
HOLDOUT / multi               n=16  mean_cov@5=32.3%

=== MULTIPLICITY=SINGLE (n=27) mean_cov@5=100.0% ===
  (no misses — all cov@5 == 100%)

=== MULTIPLICITY=MULTI (n=21) mean_cov@5=44.8% ===
  misses: 17
  [holdout] H31  cov@5=0.0%
    Q: 各功能模块是怎么被挂到系统里并开始参与运行的？
    expected: ['src/libs/Kernel.cpp', 'src/libs/Module.cpp', 'src/main.cpp']
    hit@5:    ['(none)']
    miss@5:   ['src/libs/Kernel.cpp', 'src/libs/Module.cpp', 'src/main.cpp']
  [holdout] H32  cov@5=0.0%
    Q: 内核怎样把事件通知到各个功能模块？
    expected: ['src/libs/Kernel.cpp', 'src/libs/Module.cpp']
    hit@5:    ['(none)']
    miss@5:   ['src/libs/Kernel.cpp', 'src/libs/Module.cpp']
  [holdout] H33  cov@5=0.0%
    Q: 上电后配置文件是在哪里被读入并变成可查询参数的？
    expected: ['src/libs/ConfigSources/FileConfigSource.cpp', 'src/libs/Config.cpp']
    hit@5:    ['(none)']
    miss@5:   ['src/libs/ConfigSources/FileConfigSource.cpp', 'src/libs/Config.cpp']
  [holdout] H34  cov@5=0.0%
    Q: 一个模块想读取另一个模块暴露的运行状态，走什么共享数据机制？
    expected: ['src/libs/PublicData.cpp', 'src/libs/Kernel.cpp']
    hit@5:    ['(none)']
    miss@5:   ['src/libs/PublicData.cpp', 'src/libs/Kernel.cpp']
  [holdout] H35  cov@5=0.0%
    Q: 主循环里空闲时各模块的后台处理是在哪里被驱动的？
    expected: ['src/main.cpp', 'src/libs/Kernel.cpp']
    hit@5:    ['(none)']
    miss@5:   ['src/main.cpp', 'src/libs/Kernel.cpp']
  [holdout] H36  cov@5=50.0%
    Q: 周期性慢速定时任务是在哪里注册并触发模块回调的？
    expected: ['src/libs/SlowTicker.cpp', 'src/libs/Kernel.cpp']
    hit@5:    ['src/libs/Kernel.cpp']
    miss@5:   ['src/libs/SlowTicker.cpp']
  [holdout] H37  cov@5=0.0%
    Q: 开发新硬件功能模块时，必须实现哪些框架接口、在哪里接入系统？
    expected: ['src/libs/Module.h', 'src/libs/Kernel.cpp', 'src/main.cpp']
    hit@5:    ['(none)']
    miss@5:   ['src/libs/Module.h', 'src/libs/Kernel.cpp', 'src/main.cpp']
  [holdout] H38  cov@5=0.0%
    Q: 通过串口命令在线修改配置项时，哪些核心组件会参与？
    expected: ['src/modules/utils/configurator/Configurator.cpp', 'src/libs/Config.cpp']
    hit@5:    ['(none)']
    miss@5:   ['src/modules/utils/configurator/Configurator.cpp', 'src/libs/Config.cpp']
  [holdout] H39  cov@5=16.7%
    Q: G0 快速移动命令从串口收到到步进脉冲输出，经过哪些模块？
    expected: ['src/modules/communication/SerialConsole.cpp', 'src/modules/communication/GcodeDispatch.cpp', 'src/modules/robot/Robot.cpp', 'src/modules/robot/Planner.cpp', 'src/modules/robot/Conveyor.cpp', 'src/libs/StepTicker.cpp']
    hit@5:    ['src/modules/robot/Robot.cpp']
    miss@5:   ['src/modules/communication/SerialConsole.cpp', 'src/modules/communication/GcodeDispatch.cpp', 'src/modules/robot/Planner.cpp', 'src/modules/robot/Conveyor.cpp', 'src/libs/StepTicker.cpp']
  [holdout] H40  cov@5=50.0%
    Q: M104 设置喷头温度后，温度控制逻辑在哪里被唤起？
    expected: ['src/modules/communication/GcodeDispatch.cpp', 'src/modules/tools/temperaturecontrol/TemperatureControl.cpp']
    hit@5:    ['src/modules/tools/temperaturecontrol/TemperatureControl.cpp']
    miss@5:   ['src/modules/communication/GcodeDispatch.cpp']
  [holdout] H41  cov@5=66.7%
    Q: 限位开关触发后，运动停止和急停处理涉及哪些文件？
    expected: ['src/modules/tools/endstops/Endstops.cpp', 'src/libs/Kernel.cpp', 'src/modules/robot/Conveyor.cpp']
    hit@5:    ['src/libs/Kernel.cpp', 'src/modules/robot/Conveyor.cpp']
    miss@5:   ['src/modules/tools/endstops/Endstops.cpp']
  [holdout] H42  cov@5=50.0%
    Q: 如果修改 Planner::append_block 的行为，哪些文件最可能需要一起检查？
    expected: ['src/modules/robot/Planner.cpp', 'src/modules/robot/Robot.cpp']
    hit@5:    ['src/modules/robot/Planner.cpp']
    miss@5:   ['src/modules/robot/Robot.cpp']
  [holdout] H43  cov@5=33.3%
    Q: 如果修改 Kernel 向模块分发事件的机制，哪些框架文件会牵涉？
    expected: ['src/libs/Kernel.cpp', 'src/libs/Module.cpp', 'src/main.cpp']
    hit@5:    ['src/libs/Kernel.cpp']
    miss@5:   ['src/libs/Module.cpp', 'src/main.cpp']
  [holdout] H8  cov@5=50.0%
    Q: main 函数和系统启动入口在哪里？
    expected: ['src/main.cpp', 'src/libs/Kernel.cpp']
    hit@5:    ['src/main.cpp']
    miss@5:   ['src/libs/Kernel.cpp']
  [tune] Q3  cov@5=83.3%
    Q: Motion / Planner / Stepper 相关代码在哪里？
    expected: ['src/modules/robot/Robot.cpp', 'src/modules/robot/Planner.cpp', 'src/modules/robot/Block.cpp', 'src/modules/robot/Conveyor.cpp', 'src/libs/StepTicker.cpp', 'src/libs/StepperMotor.cpp']
    hit@5:    ['src/modules/robot/Planner.cpp', 'src/modules/robot/Block.cpp', 'src/modules/robot/Conveyor.cpp', 'src/libs/StepTicker.cpp', 'src/libs/StepperMotor.cpp']
    miss@5:   ['src/modules/robot/Robot.cpp']
  [tune] Q4  cov@5=57.1%
    Q: error / stop / halt / emergency 逻辑在哪里？
    expected: ['src/libs/Kernel.cpp', 'src/modules/communication/SerialConsole.cpp', 'src/modules/communication/GcodeDispatch.cpp', 'src/modules/utils/killbutton/KillButton.cpp', 'src/modules/tools/endstops/Endstops.cpp', 'src/modules/robot/Conveyor.cpp', 'src/libs/StepperMotor.cpp']
    hit@5:    ['src/libs/Kernel.cpp', 'src/modules/tools/endstops/Endstops.cpp', 'src/modules/robot/Conveyor.cpp', 'src/libs/StepperMotor.cpp']
    miss@5:   ['src/modules/communication/SerialConsole.cpp', 'src/modules/communication/GcodeDispatch.cpp', 'src/modules/utils/killbutton/KillButton.cpp']
  [tune] Q5  cov@5=83.3%
    Q: 模块系统如何注册、触发、通信？
    expected: ['src/libs/Module.h', 'src/libs/Module.cpp', 'src/libs/Kernel.h', 'src/libs/Kernel.cpp', 'src/main.cpp', 'src/libs/PublicData.cpp']
    hit@5:    ['src/libs/Module.h', 'src/libs/Module.cpp', 'src/libs/Kernel.cpp', 'src/main.cpp', 'src/libs/PublicData.cpp']
    miss@5:   ['src/libs/Kernel.h']

```
