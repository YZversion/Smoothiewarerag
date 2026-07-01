# Eval multiplicity report

```
Eval cov@5 by expected_files multiplicity (retrieval only)
eval: eval_questions.json
gate_ok: True  mean_cov5 (all): 95.0%

Dataset shape:
  total: 35  single-file: 27  multi-file: 8
  tune multi-file: 5/5
  holdout multi-file: 3/30  (H3, H8, H9 only)

--- mean cov@5 by bucket ---
ALL                           n=35  mean_cov@5=95.0%
TUNE                          n= 5  mean_cov@5=84.8%
HOLDOUT                       n=30  mean_cov@5=96.7%
SINGLE-FILE (all splits)      n=27  mean_cov@5=100.0%
MULTI-FILE (all splits)       n= 8  mean_cov@5=78.0%
TUNE / single                 n= 0  mean_cov@5=0.0%
TUNE / multi                  n= 5  mean_cov@5=84.8%
HOLDOUT / single              n=27  mean_cov@5=100.0%
HOLDOUT / multi               n= 3  mean_cov@5=66.7%

=== MULTIPLICITY=SINGLE (n=27) mean_cov@5=100.0% ===
  (no misses — all cov@5 == 100%)

=== MULTIPLICITY=MULTI (n=8) mean_cov@5=78.0% ===
  misses: 5
  [holdout] H3  cov@5=50.0%
    Q: 硬件急停按钮 KillButton 如何处理？
    expected: ['src/modules/utils/killbutton/KillButton.cpp', 'src/libs/Kernel.cpp']
    hit@5:    ['src/modules/utils/killbutton/KillButton.cpp']
    miss@5:   ['src/libs/Kernel.cpp']
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
