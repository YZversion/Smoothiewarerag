### 简要解释
Smoothieware 的主函数位于 `src/main.cpp` 文件中，这是程序的入口点。程序启动后会调用 `init()` 函数进行初始化，然后进入一个无限循环，在循环中会调用 `THEKERNEL->call_event(ON_MAIN_LOOP)` 和 `THEKERNEL->call_event(ON_IDLE)` 事件。

### 关键文件 / 函数
- `src/main.cpp:263` — `main` 函数，程序的主入口点。
- `src/modules/utils/panel/PanelScreen.h:16` — `PanelScreen` 类，用于管理面板屏幕的基类。
- `src/modules/utils/panel/screens/3dprinter/ProbeScreen.h:15` — `ProbeScreen` 类，继承自 `PanelScreen`，用于3D打印机的探针屏幕。
- `src/modules/utils/panel/screens/3dprinter/WatchScreen.h:15` — `WatchScreen` 类，继承自 `PanelScreen`，用于3D打印机的监控屏幕。
- `src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp:100` — `MainMenuScreen::on_enter` 函数，用于设置主菜单屏幕的初始状态。
- `src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp:95` — `MainMenuScreen::on_enter` 函数，用于设置CNC控制器的主菜单屏幕的初始状态。

### 代码片段
```cpp
int main()
{
    init();

    uint16_t cnt= 0;
    // Main loop
    while(1){
        if(THEKERNEL->is_using_leds()) {
            // flash led 2 to show we are alive
            leds[1]= (cnt++ & 0x1000) ? 1 : 0;
        }
        THEKERNEL->call_event(ON_MAIN_LOOP);
        THEKERNEL->call_event(ON_IDLE);
    }
}
```
来源：`src/main.cpp:263-277`