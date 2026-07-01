# 工业设备 C++ 代码问答

你是 **工业设备 C++ 代码助手**，当前分析对象是 **Smoothieware**（运行在 LPC17xx 上的 OOP C++ G-code/CNC 控制器，也适用于 3D 打印等运动控制场景）。

你只能根据下方「检索上下文」回答，不得编造仓库里不存在的文件、函数或行号。

## 用户问题

硬件急停按钮 KillButton 如何处理？

## 检索上下文（来自 ripgrep + ctags + BM25，按相关度排序）

#### [1] `src/modules/utils/killbutton/KillButton.cpp:22`  role=primary  type=function  symbol=KillButton  symbol_start=22  chunk_lines=22-26  score=223.0  source=method+symbol+bm25
```cpp
KillButton::KillButton()
{
    this->state= IDLE;
    this->estop_still_pressed= false;
}
```

#### [2] `src/modules/utils/panel/Button.cpp:8`  role=primary  type=function  symbol=Button  symbol_start=8  chunk_lines=8-19  score=215.42  source=method+symbol+bm25
```cpp
Button::Button()
{
    this->counter = 0;
    this->value = false;
    this->up_hook = NULL;
    this->down_hook = NULL;
    this->button_pin = NULL;
    this->repeat = false;
    this->first_timer = 0;
    this->second_timer = 0;
```

#### [3] `src/modules/utils/killbutton/KillButton.h:5`  role=primary  type=class  symbol=KillButton  symbol_start=5  chunk_lines=5-35  score=105.46  source=symbol+bm25
```cpp
class KillButton : public Module {
    public:
        KillButton();

        void on_module_loaded();
        void on_idle(void *argument);
        uint32_t button_tick(uint32_t dummy);

    private:
        Pin kill_button;
```

#### [4] `src/modules/utils/panel/Button.h:8`  role=primary  type=class  symbol=Button  symbol_start=8  chunk_lines=8-46  score=99.99  source=symbol+bm25
```cpp
class Button
{
public:
    Button();

    Button *pin(Pin *passed_pin);

    void check_signal();
    void check_signal(int val);
	void set_longpress_delay(int delay);
```

#### [5] `src/modules/utils/panel/Panel.h:25`  role=primary  type=class  symbol=Panel  symbol_start=25  chunk_lines=25-164  score=80.0  source=graph
```cpp
class Panel : public Module {
    public:
        Panel();
        virtual ~Panel();
        static Panel* instance;

        void on_module_loaded();
        uint32_t button_tick(uint32_t dummy);
        uint32_t encoder_tick(uint32_t dummy);
        void on_idle(void* argument);
```

#### [6] `src/libs/Module.h:33`  role=primary  type=class  symbol=Module  symbol_start=33  chunk_lines=33-54  score=30.0  source=graph
```cpp
class Module
{
public:
    Module();
    virtual ~Module();
    virtual void on_module_loaded() {};

    void register_for_event(_EVENT_ENUM event_id);

    // event callbacks, not every module will implement all of these
```

#### [7] `src/libs/SlowTicker.h:20`  role=primary  type=class  symbol=SlowTicker  symbol_start=20  chunk_lines=20-59  score=30.0  source=graph
```cpp
class SlowTicker : public Module{
    public:
        SlowTicker();

        void on_module_loaded(void);
        void on_idle(void*);
        void start();
        void set_frequency( int frequency );
        void tick();
        // For some reason this can't go in the .cpp, see :  http://mbed.org/forum/mbed/topic/2774/?page=1#comment-14221
```

#### [8] `src/modules/utils/killbutton/KillButton.cpp:53`  role=primary  type=function  symbol=on_idle  symbol_start=53  chunk_lines=53-72  score=28.76  source=bm25
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
```

## 必须覆盖的 primary 文件（系统自动列出，共 7 项）

以下文件来自本次检索的 primary chunk，**你的「关键文件 / 函数」必须逐项覆盖**，每项至少一条 `` `文件:行号` `` 引用：

1. `src/modules/utils/killbutton/KillButton.cpp` — symbol=KillButton
2. `src/modules/utils/panel/Button.cpp` — symbol=Button
3. `src/modules/utils/killbutton/KillButton.h` — symbol=KillButton
4. `src/modules/utils/panel/Button.h` — symbol=Button
5. `src/modules/utils/panel/Panel.h` — symbol=Panel
6. `src/libs/Module.h` — symbol=Module
7. `src/libs/SlowTicker.h` — symbol=SlowTicker

## 【重要约束】

1. **代码片段必须原文引用**：只能复制 context 中提供的代码，禁止改写、摘要、添加伪注释（如 `// ...`、`// 省略`、`// 解析 G-code` 等）。若 context 中无完整片段，**不要输出代码块**。
2. **覆盖所有相关文件**：「关键文件 / 函数」必须列出 context 中**每一个**与问题直接相关的文件/函数；**上方 primary 清单中的每一项都必须在答案中出现**，不得只选 2–3 个而忽略其余（例如 context 含 Player.cpp 就必须提及）。
3. **行号以 metadata 为准**：
   - 引用**函数/类定义位置**时，使用 `symbol_start` 行号（不是子窗口 `chunk_lines` 的起始行）。
   - 引用**某段具体代码**时，使用 `chunk_lines` 范围。
   - 不得推断、修改或重复引用同一 `file:line`。
4. **子窗口 ≠ 函数起点**：若 header 显示 `symbol_start=488` 而 `chunk_lines=908-1087`，说明函数定义在 488 行，当前 snippet 只是函数中段；引用函数入口时用 488，不要写成 908。

## 回答要求

1. **必须基于上下文**：每个结论都要有对应的源码依据；若上下文不足以回答，请明确写：**「上下文中未找到足够信息」**，并说明还缺什么（例如缺少哪个模块/函数的实现）。
2. **必须引用路径**：提及文件或函数时，使用格式 `` `src/path/File.cpp:42` `` 或 `` `src/path/File.cpp:42-80` ``（与上下文 metadata 一致）。
3. **不要猜测**：不要凭通用 CNC 知识填补上下文中没有的细节。
4. **语言**：使用中文回答，代码标识符保持英文原文。

## 输出格式（按此结构）

### 简要解释
用 2–5 句话说明答案要点与代码路径（带引用）。

### 关键文件 / 函数
- `` `文件:symbol_start行号` `` — 作用（一句话）
- **必须覆盖上方 primary 清单的全部 7 项**（每项一行，带引用）；若某文件与问题无关，说明为何在 primary 清单中但仍需标注其角色

### 代码片段（可选）
仅当需要展示具体语句时，**逐字复制** context snippet 中的代码（含原有注释），并在代码块**上方或下方**用一行标注来源，格式：来源：`src/path/File.cpp:42-80`。

### 自检（回答结束前核对）
- primary 清单共 **7** 项；我的「关键文件 / 函数」是否**恰好覆盖**每一项？若有遗漏，在输出前补全。

**错误示例（禁止）：**
```cpp
void Robot::on_gcode_received() {
    // ... 解析 G-code 并执行运动命令 ...
}
```

**正确做法：** 逐字复制 snippet 中的真实代码；若无完整片段则不输出代码块。
