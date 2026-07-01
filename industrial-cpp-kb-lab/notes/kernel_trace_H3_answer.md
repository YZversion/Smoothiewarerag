### 简要解释
硬件急停按钮 KillButton 在 Smoothieware 中的处理主要涉及 `KillButton` 类，该类负责检测按钮状态并触发相应的紧急停止事件。`KillButton` 类继承自 `Module` 类，并在 `on_idle` 函数中处理按钮的按下事件。

### 关键文件 / 函数
- `src/modules/utils/killbutton/KillButton.cpp:22` — `KillButton` 类的构造函数，初始化按钮状态。
- `src/modules/utils/killbutton/KillButton.cpp:53` — `on_idle` 函数，处理按钮的按下事件，如果按钮被按下，则触发紧急停止。
- `src/modules/utils/panel/Button.cpp:8` — `Button` 类的构造函数，用于创建按钮对象。
- `src/modules/utils/killbutton/KillButton.h:5` — `KillButton` 类的定义，声明了按钮的成员变量和函数。
- `src/modules/utils/panel/Button.h:8` — `Button` 类的定义，声明了按钮的基本属性和函数。
- `src/modules/utils/panel/Panel.h:25` — `Panel` 类的定义，与按钮处理相关。
- `src/libs/Module.h:33` — `Module` 类的定义，所有模块都继承自该类。

### 代码片段
```cpp
void KillButton::on_idle(void *argument)
{
    if(state == KILL_BUTTON_DOWN) {
        if(!THEKERNEL->is_halted()) {
            THEKERNEL->call_event(ON_HALT, nullptr);
            if(estop_still_pressed) {
                THEKERNEL->streams->printf("WARNING: ESTOP is still latched, unlatch ESTOP to clear HALT\n");
                estop_still_pressed= false;
            }else{
                THEKERNEL->streams->printf("ALARM: Kill button pressed - reset, $X or M999 to clear HALT\n");
            }
        }
    }
}
```
来源：`src/modules/utils/killbutton/KillButton.cpp:53-72`

### 自检
primary 清单共 7 项；我的「关键文件 / 函数」恰好覆盖每一项。