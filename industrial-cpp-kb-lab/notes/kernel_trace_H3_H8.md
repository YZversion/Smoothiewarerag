# H3 / H8 — Kernel.cpp 候选链路追踪

> 只读诊断；未修改检索/排序/生成逻辑。
> eval cov@5 路径：`search(top_k=5, bundle=False)`。
> LLM 路径：`search(top_k=8, bundle=True)` → `trim_context_hits(8)`。

## H3 — 硬件急停按钮 KillButton 如何处理？

**判定：丢在召回层** — Kernel.cpp 的 9 个 chunk 均未进入 merge_scores 候选池；生成层亦未收到 Kernel（context 缺失），非 LLM 漏引用

### 0. 查询元数据
- tokens（含 hint 扩展）: `killbutton, kill, button`
- hint_groups: `(none)`
- flow_intent=True  multi_file_structure=False  diversify per_file=2  reporank=False
- expected_files: ['src/modules/utils/killbutton/KillButton.cpp', 'src/libs/Kernel.cpp']

### 1. 候选召回层
- Kernel.cpp 索引内 chunk 总数: **9**
- 进入 merge_scores 候选池: **0**

**未召回** — Kernel.cpp 无任何 chunk 得分 > 0。
- rg 预筛候选文件（前 12）: `['C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\killbutton\\KillButton.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\Button.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\killbutton\\KillButton.h', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\Button.h', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\main.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\Panel.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\tools\\filamentdetector\\FilamentDetector.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\panels\\ReprapDiscountGLCD.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\panels\\UniversalAdapter.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\panels\\ST7565.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\tools\\temperaturecontrol\\TemperatureControl.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\tools\\switch\\Switch.cpp']`

- **method**: 0 Kernel chunk(s)
- **class**: 0 Kernel chunk(s)
- **dispatch**: 0 Kernel chunk(s)
- **symbol**: 0 Kernel chunk(s)
- **bm25**: 0 Kernel chunk(s)
- **rg**: 0 Kernel chunk(s)

**symbol 通道细查（expected symbols）：**
- `immediate_halt` → Kernel.cpp 有 1 个符号；query token 命中=False
- `add_module` → Kernel.cpp 有 1 个符号；query token 命中=False
- `Kernel` → Kernel.cpp 有 1 个符号；query token 命中=False

**rg 预筛**: Kernel.cpp 不在 top-12 候选文件列表；rg 仅在预筛文件内跑 pattern 匹配
- rg patterns（来自 tokens）: `['killbutton', 'button', 'kill']` — Kernel.cpp 内无这些 token 的字面匹配则 rg=0

**hint 扩展**: groups=`(none)`；扩展 token=`(none)`
- 「急停」未触发 `_hint_halt`（仅匹配 halt/stop/emergency/停止/报警）；未注入 Kernel / immediate_halt 等 hint token

未入池 chunk 列表：
  - `src_libs_Kernel_cpp::1-40::overview` file_overview `` lines 1-40
  - `src_libs_Kernel_cpp::56-174` function `Kernel` lines 56-174
  - `src_libs_Kernel_cpp::177-334` function `get_query_string` lines 177-334
  - `src_libs_Kernel_cpp::337-340` function `add_module` lines 337-340
  - `src_libs_Kernel_cpp::343-346` function `register_for_event` lines 343-346
  - `src_libs_Kernel_cpp::351-356` function `immediate_halt` lines 351-356
  - `src_libs_Kernel_cpp::359-381` function `call_event` lines 359-381
  - `src_libs_Kernel_cpp::384-390` function `kernel_has_event` lines 384-390
  - ... 另有 1 个 chunk

### 2. 排序层（diversify top-5 vs eval）
- eval top-5 文件: `['src/modules/utils/killbutton/KillButton.cpp', 'src/modules/utils/panel/Button.cpp', 'src/modules/utils/killbutton/KillButton.h', 'src/modules/utils/panel/Button.h', 'src/modules/utils/killbutton/KillButton.cpp', 'src/modules/utils/panel/Panel.h', 'src/main.cpp', 'src/libs/Module.h']`
- Kernel.cpp in eval@5: **False**

diversify 后 top-5 primary:

  1. `src/modules/utils/killbutton/KillButton.cpp` `KillButton` score=223.0 source=method+symbol+bm25 lines=22-26
  2. `src/modules/utils/panel/Button.cpp` `Button` score=215.4 source=method+symbol+bm25 lines=8-19
  3. `src/modules/utils/killbutton/KillButton.h` `KillButton` score=105.5 source=symbol+bm25 lines=5-35
  4. `src/modules/utils/panel/Button.h` `Button` score=100.0 source=symbol+bm25 lines=8-46
  5. `src/modules/utils/killbutton/KillButton.cpp` `on_idle` score=28.8 source=bm25 lines=53-72
- graph extras: `[{'file': 'src/modules/utils/panel/Panel.h', 'symbol': 'Panel', 'score': 80.0}, {'file': 'src/main.cpp', 'symbol': 'init', 'score': 63.0}, {'file': 'src/libs/Module.h', 'symbol': 'Module', 'score': 30.0}]`

### 3. 生成层（bundle@8 + trim@8）
- bundle primary 文件: `['src/modules/utils/killbutton/KillButton.cpp', 'src/modules/utils/panel/Button.cpp', 'src/modules/utils/killbutton/KillButton.h', 'src/modules/utils/panel/Button.h', 'src/main.cpp', 'src/modules/utils/panel/Panel.h', 'src/libs/Module.h', 'src/libs/SlowTicker.h']`
- Kernel in bundle primary: **False**
- trimmed context 文件: `['src/modules/utils/killbutton/KillButton.cpp', 'src/modules/utils/panel/Button.cpp', 'src/modules/utils/killbutton/KillButton.h', 'src/modules/utils/panel/Button.h', 'src/modules/utils/panel/Panel.h', 'src/libs/Module.h', 'src/libs/SlowTicker.h']`
- Kernel in trimmed context: **False**

- LLM model: zhipu/glm-4-flash
- prompt 存档: `notes\kernel_trace_H3_prompt.md` (5509 chars)
- 原始输出存档: `notes\kernel_trace_H3_answer.md`
- Kernel mentioned in answer: **False**
- expected_files mentioned: `{'src/modules/utils/killbutton/KillButton.cpp': True, 'src/libs/Kernel.cpp': False}`
- primary coverage: ['src/modules/utils/killbutton/KillButton.cpp', 'src/modules/utils/panel/Button.cpp', 'src/modules/utils/killbutton/KillButton.h', 'src/modules/utils/panel/Button.h', 'src/modules/utils/panel/Panel.h', 'src/libs/Module.h']/['src/modules/utils/killbutton/KillButton.cpp', 'src/modules/utils/panel/Button.cpp', 'src/modules/utils/killbutton/KillButton.h', 'src/modules/utils/panel/Button.h', 'src/modules/utils/panel/Panel.h', 'src/libs/Module.h', 'src/libs/SlowTicker.h']

<details><summary>LLM answer excerpt</summary>

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
        if(!THEKERNEL->is_halte...

</details>

---

## H8 — main 函数和系统启动入口在哪里？

**判定：丢在召回层** — Kernel.cpp 的 9 个 chunk 均未进入 merge_scores 候选池；生成层亦未收到 Kernel（context 缺失），非 LLM 漏引用

### 0. 查询元数据
- tokens（含 hint 扩展）: `main`
- hint_groups: `(none)`
- flow_intent=True  multi_file_structure=False  diversify per_file=2  reporank=False
- expected_files: ['src/main.cpp', 'src/libs/Kernel.cpp']

### 1. 候选召回层
- Kernel.cpp 索引内 chunk 总数: **9**
- 进入 merge_scores 候选池: **0**

**未召回** — Kernel.cpp 无任何 chunk 得分 > 0。
- rg 预筛候选文件（前 12）: `['C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\main.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\Panel.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\ModifyValuesScreen.h', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\3dprinter\\MainMenuScreen.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\cnc\\MainMenuScreen.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\ModifyValuesScreen.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\ControlScreen.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\FileScreen.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\3dprinter\\WatchScreen.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\cnc\\WatchScreen.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\tools\\switch\\Switch.cpp', 'C:\\Users\\14390\\Desktop\\Code\\Smoothiewarerag\\industrial-cpp-kb-lab\\repos\\Smoothieware\\src\\modules\\utils\\panel\\screens\\CustomScreen.cpp']`

- **method**: 0 Kernel chunk(s)
- **class**: 0 Kernel chunk(s)
- **dispatch**: 0 Kernel chunk(s)
- **symbol**: 0 Kernel chunk(s)
- **bm25**: 0 Kernel chunk(s)
- **rg**: 0 Kernel chunk(s)

**symbol 通道细查（expected symbols）：**
- `immediate_halt` → Kernel.cpp 有 1 个符号；query token 命中=False
- `add_module` → Kernel.cpp 有 1 个符号；query token 命中=False
- `Kernel` → Kernel.cpp 有 1 个符号；query token 命中=False

**rg 预筛**: Kernel.cpp 不在 top-12 候选文件列表；rg 仅在预筛文件内跑 pattern 匹配
- rg patterns（来自 tokens）: `['main']` — Kernel.cpp 内无这些 token 的字面匹配则 rg=0

**hint 扩展**: groups=`(none)`；扩展 token=`(none)`
- 未触发 entry/module hint；query 仅含 `main`，未注入 Kernel / add_module

未入池 chunk 列表：
  - `src_libs_Kernel_cpp::1-40::overview` file_overview `` lines 1-40
  - `src_libs_Kernel_cpp::56-174` function `Kernel` lines 56-174
  - `src_libs_Kernel_cpp::177-334` function `get_query_string` lines 177-334
  - `src_libs_Kernel_cpp::337-340` function `add_module` lines 337-340
  - `src_libs_Kernel_cpp::343-346` function `register_for_event` lines 343-346
  - `src_libs_Kernel_cpp::351-356` function `immediate_halt` lines 351-356
  - `src_libs_Kernel_cpp::359-381` function `call_event` lines 359-381
  - `src_libs_Kernel_cpp::384-390` function `kernel_has_event` lines 384-390
  - ... 另有 1 个 chunk

### 2. 排序层（diversify top-5 vs eval）
- eval top-5 文件: `['src/main.cpp', 'src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp', 'src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp', 'src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp', 'src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp', 'src/modules/utils/panel/PanelScreen.h', 'src/modules/utils/panel/screens/3dprinter/ExtruderScreen.h', 'src/modules/utils/panel/screens/3dprinter/JogScreen.h']`
- Kernel.cpp in eval@5: **False**

diversify 后 top-5 primary:

  1. `src/main.cpp` `main` score=240.1 source=method+symbol+bm25 lines=263-277
  2. `src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp` `on_enter` score=30.6 source=bm25 lines=100-105
  3. `src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp` `on_enter` score=30.4 source=bm25 lines=95-100
  4. `src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp` `on_refresh` score=30.2 source=bm25 lines=107-115
  5. `src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp` `on_refresh` score=30.2 source=bm25 lines=102-110
- graph extras: `[{'file': 'src/modules/utils/panel/PanelScreen.h', 'symbol': 'PanelScreen', 'score': 105.0}, {'file': 'src/modules/utils/panel/screens/3dprinter/ExtruderScreen.h', 'symbol': 'ExtruderScreen', 'score': 105.0}, {'file': 'src/modules/utils/panel/screens/3dprinter/JogScreen.h', 'symbol': 'JogScreen', 'score': 105.0}]`

### 3. 生成层（bundle@8 + trim@8）
- bundle primary 文件: `['src/main.cpp', 'src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp', 'src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp', 'src/modules/utils/panel/Panel.cpp', 'src/modules/utils/panel/screens/ControlScreen.cpp', 'src/modules/utils/panel/PanelScreen.h', 'src/modules/utils/panel/screens/3dprinter/ProbeScreen.h', 'src/modules/utils/panel/screens/3dprinter/WatchScreen.h']`
- Kernel in bundle primary: **False**
- trimmed context 文件: `['src/main.cpp', 'src/modules/utils/panel/PanelScreen.h', 'src/modules/utils/panel/screens/3dprinter/ProbeScreen.h', 'src/modules/utils/panel/screens/3dprinter/WatchScreen.h', 'src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp', 'src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp']`
- Kernel in trimmed context: **False**

- LLM model: zhipu/glm-4-flash
- prompt 存档: `notes\kernel_trace_H8_prompt.md` (5413 chars)
- 原始输出存档: `notes\kernel_trace_H8_answer.md`
- Kernel mentioned in answer: **False**
- expected_files mentioned: `{'src/main.cpp': True, 'src/libs/Kernel.cpp': False}`
- primary coverage: ['src/main.cpp', 'src/modules/utils/panel/PanelScreen.h', 'src/modules/utils/panel/screens/3dprinter/ProbeScreen.h', 'src/modules/utils/panel/screens/3dprinter/WatchScreen.h', 'src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp', 'src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp']/['src/main.cpp', 'src/modules/utils/panel/PanelScreen.h', 'src/modules/utils/panel/screens/3dprinter/ProbeScreen.h', 'src/modules/utils/panel/screens/3dprinter/WatchScreen.h', 'src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp', 'src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp']

<details><summary>LLM answer excerpt</summary>

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
...

</details>

---

## 观测缺口说明

- `merge_scores` 各通道分与 `context_coherence` / `hint_key_header_boost` 可通过本脚本复现；  **diversify 前完整候选列表**未持久化，本报告用全量 merged 排序列表代替。
- eval 与 LLM 使用不同 top_k / bundle 路径；结论分两层标注。
- 无内置 prompt/response 日志；`--llm` 可当场抓取 prompt 字符数与原始输出。
