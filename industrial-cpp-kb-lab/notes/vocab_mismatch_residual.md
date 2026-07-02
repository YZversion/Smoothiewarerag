# vocab_mismatch 残留诊断（dense@20, tune-only）

- 范围：仅 `dev_split=tune` 且 `vocab_mismatch=true` 题目；不触碰 sealed。
- 配置：`KB_W_DENSE=20`，沿用正式检索逻辑；本报告只诊断不修复。

## H32

- 问题：内核怎样把事件通知到各个功能模块？
- hint_groups: `(none)`
- graph 路径是否活跃：True
- top5: `['src/modules/tools/spindle/HuanyangSpindleControl.cpp', 'src/libs/Module.cpp', 'src/main.cpp', 'src/modules/utils/panel/PanelScreen.cpp', 'src/modules/communication/SerialConsole.cpp', 'src/libs/Module.h', 'src/modules/utils/panel/panels/LcdBase.h', 'src/modules/communication/SerialConsole.h']`
- top10: `['src/modules/tools/spindle/HuanyangSpindleControl.cpp', 'src/libs/Module.cpp', 'src/main.cpp', 'src/modules/utils/panel/PanelScreen.cpp', 'src/modules/communication/SerialConsole.cpp', 'src/modules/tools/spindle/Modbus/Modbus.cpp', 'src/modules/tools/spindle/Modbus/Modbus.cpp', 'src/modules/tools/temperaturecontrol/TemperatureControl.cpp', 'src/libs/Kernel.cpp', 'src/modules/utils/motordrivercontrol/drivers/TMC26X/TMC26X.cpp', 'src/libs/Module.h', 'src/modules/utils/panel/panels/LcdBase.h', 'src/modules/tools/filamentdetector/FilamentDetector.h']`

### miss: `src/libs/Kernel.cpp`
- 分类：**B类**（dense命中但融合后卡在6-10）
- dense：in_top50=True rank=9 score=19.265
- 融合后排名(top10口径)：9
- 其他通道是否有文件级信号： symbol=False, bm25=False, rg=False, method=False, class=False, dispatch=False

## H35

- 问题：主循环里空闲时各模块的后台处理是在哪里被驱动的？
- hint_groups: `(none)`
- graph 路径是否活跃：False
- top5: `['src/main.cpp', 'src/modules/utils/panel/screens/cnc/WatchScreen.cpp', 'src/modules/utils/panel/screens/3dprinter/WatchScreen.cpp', 'src/modules/utils/panel/Panel.cpp', 'src/modules/tools/spindle/AnalogSpindleControl.cpp']`
- top10: `['src/main.cpp', 'src/modules/utils/panel/screens/cnc/WatchScreen.cpp', 'src/modules/utils/panel/screens/3dprinter/WatchScreen.cpp', 'src/modules/utils/panel/Panel.cpp', 'src/modules/tools/spindle/AnalogSpindleControl.cpp', 'src/modules/tools/spindle/PWMSpindleControl.cpp', 'src/modules/utils/panel/PanelScreen.cpp', 'src/modules/utils/motordrivercontrol/MotorDriverControl.cpp', 'src/modules/communication/SerialConsole.cpp', 'src/modules/utils/motordrivercontrol/MotorDriverControl.cpp']`

### miss: `src/libs/Kernel.cpp`
- 分类：**B类**（dense命中但融合后未进top-10）
- dense：in_top50=True rank=11 score=18.9115
- 融合后排名(top10口径)：None
- 其他通道是否有文件级信号： symbol=False, bm25=False, rg=False, method=False, class=False, dispatch=False

## H37

- 问题：开发新硬件功能模块时，必须实现哪些框架接口、在哪里接入系统？
- hint_groups: `(none)`
- graph 路径是否活跃：False
- top5: `['src/modules/communication/SerialConsole.cpp', 'src/modules/utils/panel/panels/UniversalAdapter.cpp', 'src/modules/tools/spindle/SoftSerial/BufferedSoftSerial.cpp', 'src/modules/utils/panel/panels/UniversalAdapter.cpp', 'src/modules/tools/switch/Switch.cpp']`
- top10: `['src/modules/communication/SerialConsole.cpp', 'src/modules/utils/panel/panels/UniversalAdapter.cpp', 'src/modules/tools/spindle/SoftSerial/BufferedSoftSerial.cpp', 'src/modules/utils/panel/panels/UniversalAdapter.cpp', 'src/modules/tools/switch/Switch.cpp', 'src/modules/tools/spindle/SoftSerial/SoftSerial.h', 'src/libs/Kernel.h', 'src/modules/utils/panel/Panel.h', 'src/modules/utils/panel/panels/rrdglcd/RrdGlcd.h', 'src/modules/tools/switch/Switch.h']`

### miss: `src/libs/Module.h`
- 分类：**A类**（dense top-50未覆盖该文件）
- dense：in_top50=False rank=None score=0.0
- 融合后排名(top10口径)：None
- 其他通道是否有文件级信号： symbol=False, bm25=False, rg=False, method=False, class=False, dispatch=False

### miss: `src/libs/Kernel.cpp`
- 分类：**B类**（dense命中但融合后未进top-10）
- dense：in_top50=True rank=11 score=19.064
- 融合后排名(top10口径)：None
- 其他通道是否有文件级信号： symbol=False, bm25=False, rg=False, method=False, class=False, dispatch=False

### miss: `src/main.cpp`
- 分类：**A类**（dense top-50未覆盖该文件）
- dense：in_top50=False rank=None score=0.0
- 融合后排名(top10口径)：None
- 其他通道是否有文件级信号： symbol=False, bm25=False, rg=False, method=False, class=False, dispatch=False

## A/B 分布汇总

- A类（dense也接不住）: 题数 1，miss文件数 2
- B类（dense接住但未进top-5）: 题数 3，miss文件数 3

结论仅用于下一步方向决策（拼接格式 / 融合层 / 图扩展），本轮不改逻辑。