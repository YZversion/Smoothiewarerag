# Q3–Q5 检索四层诊断

> 复现：`python scripts/diagnose_retrieval.py --ids Q3,Q4,Q5`  
> 修复后（2026-06-29）：bundle@8 / trim@8 三题均 **6/6、7/7、6/6**；根因分别为 diversify 挤占、halt hint 缺口、expand_bundle header 去重 + call_graph 噪声。

| ID | cov@5 | cov@8 | cov@10 | bundle@8 | trim@8 | sym_trim | 根因 |
|----|------|------|------|----------|--------|----------|------|
| Q3 | 5/6 | 6/6 | 6/6 | 6/6 | 6/6 | 4/4 (loss=0) | OK |
| Q4 | 4/7 | 7/7 | 7/7 | 7/7 | 7/7 | 2/4 (loss=0) | OK |
| Q5 | 5/6 | 6/6 | 6/6 | 6/6 | 6/6 | 2/4 (loss=0) | OK |

## Q3 — Motion / Planner / Stepper 相关代码在哪里？

- **miss@raw5**: src/modules/robot/Robot.cpp
- **trim noise** (primary 但非 expected): src/libs/StepTicker.h, src/modules/robot/Planner.h
- **bundle primary 全表**: src/libs/StepperMotor.cpp, src/modules/robot/Block.cpp, src/libs/StepTicker.cpp, src/modules/robot/Planner.cpp, src/modules/robot/Conveyor.cpp, src/modules/robot/Robot.cpp, src/libs/StepTicker.h, src/modules/robot/Planner.h

## Q4 — error / stop / halt / emergency 逻辑在哪里？

- **miss@raw5**: src/modules/communication/SerialConsole.cpp, src/modules/communication/GcodeDispatch.cpp, src/modules/utils/killbutton/KillButton.cpp
- **trim noise** (primary 但非 expected): src/libs/SoftPWM.cpp
- **bundle primary 全表**: src/libs/Kernel.cpp, src/libs/StepperMotor.cpp, src/modules/robot/Conveyor.cpp, src/libs/SoftPWM.cpp, src/modules/tools/endstops/Endstops.cpp, src/modules/utils/killbutton/KillButton.cpp, src/modules/communication/GcodeDispatch.cpp, src/modules/communication/SerialConsole.cpp

## Q5 — 模块系统如何注册、触发、通信？

- **miss@raw5**: src/libs/Kernel.h
- **trim noise** (primary 但非 expected): src/libs/PublicData.h, src/modules/communication/SerialConsole.cpp
- **bundle primary 全表**: src/libs/Kernel.cpp, src/libs/PublicData.cpp, src/main.cpp, src/libs/Module.cpp, src/libs/Module.h, src/libs/Kernel.h, src/libs/PublicData.h, src/modules/communication/SerialConsole.cpp
