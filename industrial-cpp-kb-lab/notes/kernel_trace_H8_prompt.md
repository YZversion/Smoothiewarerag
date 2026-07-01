# 工业设备 C++ 代码问答

你是 **工业设备 C++ 代码助手**，当前分析对象是 **Smoothieware**（运行在 LPC17xx 上的 OOP C++ G-code/CNC 控制器，也适用于 3D 打印等运动控制场景）。

你只能根据下方「检索上下文」回答，不得编造仓库里不存在的文件、函数或行号。

## 用户问题

main 函数和系统启动入口在哪里？

## 检索上下文（来自 ripgrep + ctags + BM25，按相关度排序）

#### [1] `src/main.cpp:263`  role=primary  type=function  symbol=main  symbol_start=263  chunk_lines=263-277  score=240.1  source=method+symbol+bm25
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
```

#### [2] `src/modules/utils/panel/PanelScreen.h:16`  role=primary  type=class  symbol=PanelScreen  symbol_start=16  chunk_lines=16-43  score=155.0  source=graph
```cpp
class PanelScreen
{
public:
    PanelScreen();
    virtual ~PanelScreen();

    virtual void on_refresh();
    virtual void on_main_loop();
    PanelScreen *set_parent(PanelScreen *passed_parent);
    virtual void on_enter();
```

#### [3] `src/modules/utils/panel/screens/3dprinter/ProbeScreen.h:15`  role=primary  type=class  symbol=ProbeScreen  symbol_start=15  chunk_lines=15-35  score=155.0  source=graph
```cpp
class ProbeScreen : public PanelScreen {
    public:
        ProbeScreen();
        void on_refresh();
        void on_enter();
        void on_exit();
        void on_main_loop();
        void display_menu_line(uint16_t line);
        void clicked_menu_entry(uint16_t line);
        int idle_timeout_secs() { return 120; }
```

#### [4] `src/modules/utils/panel/screens/3dprinter/WatchScreen.h:15`  role=primary  type=class  symbol=WatchScreen  symbol_start=15  chunk_lines=15-50  score=155.0  source=graph
```cpp
class WatchScreen : public PanelScreen
{
public:
    WatchScreen();
    ~WatchScreen();
    void on_refresh();
    void on_enter();
    void on_main_loop();
    void redraw();
    void display_menu_line(uint16_t line);
```

#### [5] `src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp:100`  role=primary  type=function  symbol=on_enter  symbol_start=100  chunk_lines=100-105  score=30.6  source=bm25
```cpp
void MainMenuScreen::on_enter()
{
    THEPANEL->enter_menu_mode();
    THEPANEL->setup_menu(7);
    this->refresh_menu();
}
```

#### [6] `src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp:95`  role=primary  type=function  symbol=on_enter  symbol_start=95  chunk_lines=95-100  score=30.38  source=bm25
```cpp
void MainMenuScreen::on_enter()
{
    THEPANEL->enter_menu_mode();
    THEPANEL->setup_menu(THEPANEL->has_laser()?8:7);
    this->refresh_menu();
}
```

#### [7] `src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp:107`  role=primary  type=function  symbol=on_refresh  symbol_start=107  chunk_lines=107-115  score=30.16  source=bm25
```cpp
void MainMenuScreen::on_refresh()
{
    if ( THEPANEL->menu_change() ) {
        this->refresh_menu();
    }
    if ( THEPANEL->click() ) {
        this->clicked_menu_entry(THEPANEL->get_menu_current_line());
    }
}
```

#### [8] `src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp:102`  role=primary  type=function  symbol=on_refresh  symbol_start=102  chunk_lines=102-110  score=30.16  source=bm25
```cpp
void MainMenuScreen::on_refresh()
{
    if ( THEPANEL->menu_change() ) {
        this->refresh_menu();
    }
    if ( THEPANEL->click() ) {
        this->clicked_menu_entry(THEPANEL->get_menu_current_line());
    }
}
```

## 必须覆盖的 primary 文件（系统自动列出，共 6 项）

以下文件来自本次检索的 primary chunk，**你的「关键文件 / 函数」必须逐项覆盖**，每项至少一条 `` `文件:行号` `` 引用：

1. `src/main.cpp` — symbol=main
2. `src/modules/utils/panel/PanelScreen.h` — symbol=PanelScreen
3. `src/modules/utils/panel/screens/3dprinter/ProbeScreen.h` — symbol=ProbeScreen
4. `src/modules/utils/panel/screens/3dprinter/WatchScreen.h` — symbol=WatchScreen
5. `src/modules/utils/panel/screens/3dprinter/MainMenuScreen.cpp` — symbol=on_enter
6. `src/modules/utils/panel/screens/cnc/MainMenuScreen.cpp` — symbol=on_enter

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
- **必须覆盖上方 primary 清单的全部 6 项**（每项一行，带引用）；若某文件与问题无关，说明为何在 primary 清单中但仍需标注其角色

### 代码片段（可选）
仅当需要展示具体语句时，**逐字复制** context snippet 中的代码（含原有注释），并在代码块**上方或下方**用一行标注来源，格式：来源：`src/path/File.cpp:42-80`。

### 自检（回答结束前核对）
- primary 清单共 **6** 项；我的「关键文件 / 函数」是否**恰好覆盖**每一项？若有遗漏，在输出前补全。

**错误示例（禁止）：**
```cpp
void Robot::on_gcode_received() {
    // ... 解析 G-code 并执行运动命令 ...
}
```

**正确做法：** 逐字复制 snippet 中的真实代码；若无完整片段则不输出代码块。
