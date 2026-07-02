# B 类挤出分析（dense@20，只读诊断）

- 范围：H32/H35/H37 的 B 类 miss（`src/libs/Kernel.cpp`）
- 配置冻结：`w_dense=20`，不改检索/融合/排序代码
- diversify 基准：`per_file=2`（默认）；`multi_file_structure` 题为 `per_file=1`
- 分数构成说明：`hint` 无独立通道分，通过 `expand_query_tokens` 影响 symbol/bm25/rg；`hint_hdr` 为 `_hint_module` 触发的 header boost；`graph` 仅出现在 diversify 之后的 graph extras（本报告 top-5 槽位不含 graph 分）

## H32 — 内核怎样把事件通知到各个功能模块？

- expected_files：`Kernel.cpp`, `Module.cpp`

### 运行配置
- hint_groups: `(none)`
- flow_intent: True
- multi_file_structure: False
- diversify per_file: **2**
- graph extras: 3 条
- reporank: False

### 1) diversify 后 top-5（eval 主槽位）

| 槽位 | 文件 | chunk_id | symbol | 融合总分 | 分数构成 |
|------|------|----------|--------|----------|----------|
| 1 | `src/modules/tools/spindle/HuanyangSpindleControl.cpp` | `src_modules_tools_spindle_HuanyangSpindleControl_cpp::156-197` | `report_speed` | 32.83 | dense=19.8296, bonus=13.0 |
| 2 | `src/libs/Module.cpp` | `src_libs_Module_cpp::30-34` | `register_for_event` | 32.71 | dense=19.7052, bonus=13.0 |
| 3 | `src/main.cpp` | `src_main_cpp::93-261` | `init` | 32.67 | dense=19.6659, bonus=13.0 |
| 4 | `src/modules/utils/panel/PanelScreen.cpp` | `src_modules_utils_panel_PanelScreen_cpp::97-111` | `on_main_loop` | 32.48 | dense=19.4784, bonus=13.0 |
| 5 | `src/modules/communication/SerialConsole.cpp` | `src_modules_communication_SerialConsole_cpp::249-272` | `on_main_loop` | 32.46 | dense=19.4617, bonus=13.0 |

### graph 追加（不计入 top-5 槽位，但 eval 可能命中文件）

- `src/libs/Module.h` chunk=`src_libs_Module_h::33-54` score=80.00 (bonus=5.0, graph=75.0)
- `src/modules/utils/panel/panels/LcdBase.h` chunk=`src_modules_utils_panel_panels_LcdBase_h::24-145` score=80.00 (bonus=5.0, graph=75.0)
- `src/modules/communication/SerialConsole.h` chunk=`src_modules_communication_SerialConsole_h::19-43` score=55.00 (bonus=5.0, graph=50.0)

### 2) miss 文件排名

- miss 文件：`src/libs/Kernel.cpp`
- 最佳 chunk：`src_libs_Kernel_cpp::392-400`（unregister_for_event 392-400）
- 全量 merged 排名：**第 9 名**
- 融合总分：**32.1482**
- 分数构成：dense=19.1482, bonus=13.0
- 第 5 名分数：**32.4600**（`src/modules/communication/SerialConsole.cpp`）
- 与第 5 名分差：**0.3118**（miss 更低）
- 是否在 diversify top-5：**否**

### 3) 同文件多 chunk 占槽

- **否**：top-5 内每文件至多 1 个 chunk

### 4) 一句话结论
- **形态2**：top-5 以非 expected 噪音为主（4/5），src/libs/Kernel.cpp 被不相关文件挤出

---

## H35 — 主循环里空闲时各模块的后台处理是在哪里被驱动的？

- expected_files：`main.cpp`, `Kernel.cpp`

### 运行配置
- hint_groups: `(none)`
- flow_intent: False
- multi_file_structure: False
- diversify per_file: **2**
- graph extras: 0 条
- reporank: False

### 1) diversify 后 top-5（eval 主槽位）

| 槽位 | 文件 | chunk_id | symbol | 融合总分 | 分数构成 |
|------|------|----------|--------|----------|----------|
| 1 | `src/main.cpp` | `src_main_cpp::93-261` | `init` | 33.00 | dense=20.0, bonus=13.0 |
| 2 | `src/modules/utils/panel/screens/cnc/WatchScreen.cpp` | `src_modules_utils_panel_screens_cnc_WatchScreen_cpp::129-136` | `on_main_loop` | 32.20 | dense=19.2007, bonus=13.0 |
| 3 | `src/modules/utils/panel/screens/3dprinter/WatchScreen.cpp` | `src_modules_utils_panel_screens_3dprinter_WatchScreen_cpp::165-172` | `on_main_loop` | 31.72 | dense=18.7215, bonus=13.0 |
| 4 | `src/modules/utils/panel/Panel.cpp` | `src_modules_utils_panel_Panel_cpp::349-444` | `idle_processing` | 31.68 | dense=18.683, bonus=13.0 |
| 5 | `src/modules/tools/spindle/AnalogSpindleControl.cpp` | `src_modules_tools_spindle_AnalogSpindleControl_cpp::25-62` | `on_module_loaded` | 31.65 | dense=18.6514, bonus=13.0 |

### 2) miss 文件排名

- miss 文件：`src/libs/Kernel.cpp`
- 最佳 chunk：`src_libs_Kernel_cpp::177-334`（get_query_string 177-334）
- 全量 merged 排名：**第 11 名**
- 融合总分：**31.2951**
- 分数构成：dense=18.2951, bonus=13.0
- 第 5 名分数：**31.6500**（`src/modules/tools/spindle/AnalogSpindleControl.cpp`）
- 与第 5 名分差：**0.3549**（miss 更低）
- 是否在 diversify top-5：**否**

### 3) 同文件多 chunk 占槽

- **否**：top-5 内每文件至多 1 个 chunk

### 4) 一句话结论
- **形态2**：top-5 以非 expected 噪音为主（4/5），src/libs/Kernel.cpp 被不相关文件挤出

---

## H37 — 开发新硬件功能模块时，必须实现哪些框架接口、在哪里接入系统？

- expected_files：`Module.h`, `Kernel.cpp`, `main.cpp`

### 运行配置
- hint_groups: `(none)`
- flow_intent: False
- multi_file_structure: False
- diversify per_file: **2**
- graph extras: 0 条
- reporank: False

### 1) diversify 后 top-5（eval 主槽位）

| 槽位 | 文件 | chunk_id | symbol | 融合总分 | 分数构成 |
|------|------|----------|--------|----------|----------|
| 1 | `src/modules/communication/SerialConsole.cpp` | `src_modules_communication_SerialConsole_cpp::106-177` | `init_uart` | 32.56 | dense=19.5603, bonus=13.0 |
| 2 | `src/modules/utils/panel/panels/UniversalAdapter.cpp` | `src_modules_utils_panel_panels_UniversalAdapter_cpp::38-42` | `SPIFrame` | 31.93 | dense=18.9265, bonus=13.0 |
| 3 | `src/modules/tools/spindle/SoftSerial/BufferedSoftSerial.cpp` | `src_modules_tools_spindle_SoftSerial_BufferedSoftSerial_cpp::128-138` | `prime` | 31.88 | dense=18.8791, bonus=13.0 |
| 4 | `src/modules/utils/panel/panels/UniversalAdapter.cpp` | `src_modules_utils_panel_panels_UniversalAdapter_cpp::94-99` | `writeSPI` | 31.84 | dense=18.8415, bonus=13.0 |
| 5 | `src/modules/tools/switch/Switch.cpp` | `src_modules_tools_switch_Switch_cpp::307-393` | `on_gcode_received` | 31.24 | dense=18.2388, bonus=13.0 |

### 2) miss 文件排名

- miss 文件：`src/libs/Kernel.cpp`
- 最佳 chunk：`src_libs_Kernel_cpp::1-40::overview`（ 1-40）
- 全量 merged 排名：**第 41 名**
- 融合总分：**19.3601**
- 分数构成：dense=18.3601, bonus=1.0
- 第 5 名分数：**31.2400**（`src/modules/tools/switch/Switch.cpp`）
- 与第 5 名分差：**11.8799**（miss 更低）
- 是否在 diversify top-5：**否**

### 3) 同文件多 chunk 占槽

- **是**：`src/modules/utils/panel/panels/UniversalAdapter.cpp` 占 **2** 个槽位（均为非 expected 噪音文件内部冗余，不构成形态1）

### 4) 一句话结论
- **形态2**：top-5 全部为非 expected 文件（含 UniversalAdapter 双占槽），`Kernel.cpp` 被不相关噪音挤出

---

## 形态分布汇总（3 题）

- 形态1（被正确文件冗余 chunk 挤出）：**0** 题
- 形态2（被不相关噪音文件挤出）：**3** 题

决策提示：形态1 为主 → 优先考虑 diversify 局部调整；**形态2 为主（本批 3/3）** → vocab_mismatch B 类残留挂起，转向 Phase 7 准备（不为 3 个 Kernel miss 动全局融合）。