# Eval 失败案例库

> Phase 6.1 — 检索层漏召回 / 错排序根因记录。  
> **检索层已冻结**（2026-06-25）；Phase 8（2026-06-29）新增 dispatch_index，H4 已修复，eval set 扩至 35 题。  
> 本文件只记录 Phase 6.1 时的 15 题状态；H11–H30 见 `notes/phase8_symbol_dispatch_audit.md`。  
> 复现：`python src/03_search.py --eval`（35 题，top_k=5）

**原则：** 记录现象与可迁移根因；**不**用 expected_files 文件名硬编码加分。  
**holdout 纪律：** 不为 holdout @5 缺口写规则——H4 是戒掉 hint 误触后的真缺口，接受 FAIL@5、看 @10。

---

## 状态总表（2026-06-25 冻结后）

| ID | split | Recall@5 | cov@5 | 状态 | 备注 |
|----|-------|----------|-------|------|------|
| Q1 | tune | PASS | 3/3 (100%) | **OK** | — |
| Q2 | tune | PASS | 4/5 (80%) | **已好转** | 修前 2/5；仍缺 GcodeDispatch @5，@10 满 |
| Q3 | tune | PASS | 4/6 (67%) | open | 文件够、符号 chunk 对齐弱（见 phase6_conclusion） |
| Q4 | tune | PASS | 3/7 (43%) | open | 多文件 halt 链，coverage 低但门槛 PASS |
| Q5 | tune | PASS | 3/6 (50%) | open | 同上 |
| H1 | holdout | PASS | 1/1 (100%) | **OK** | — |
| H2 | holdout | PASS | 1/1 (100%) | **OK** | — |
| H3 | holdout | PASS | 1/2 (50%) | open | 缺 Kernel.cpp @5 |
| H4 | holdout | **PASS** | 1/1 (100%) | **Phase 8 修复** | dispatch_index 命中 `Endstops::on_gcode_received` 内 G28 证据行 |
| H5 | holdout | PASS | 1/1 (100%) | **OK** | — |
| H6 | holdout | PASS | 1/1 (100%) | **OK** | — |
| H7 | holdout | PASS | 1/1 (100%) | **OK** | — |
| H8 | holdout | PASS | 1/2 (50%) | **已修复** | 修前 0/2 FAIL；hint 误触已消，main 进 @5 |
| H9 | holdout | PASS | 1/2 (50%) | open | .h 进榜、.cpp @10 |
| H10 | holdout | PASS | 1/1 (100%) | **已修复** | 修前 0/1 FAIL；hint + context coherence |

**Phase 6.1 汇总（15 题）：** Recall@5 = 14/15，mean cov@5 = **73%**（gate PASS）。已修复 3 题（Q2 大幅好转、H8、H10）；open 题不再为 @5 写检索规则。

**Phase 8 更新（35 题，2026-06-29）：** H4 由 dispatch_index 修复（PASS）；35/35 Recall@5；mean cov@5 = **94%**。新增 H11–H30（dispatch 题含 G28/M104/M221/M907 等）见 `notes/phase8_symbol_dispatch_audit.md`。

### 已实施修复（03_search.py）

| 问题 | 修复 |
|------|------|
| Hint 子串误触发（H8/H10） | 短语/共现触发（`_hint_entry`、`_hint_motion_chain`） |
| 子窗口压过入口 chunk（Q2） | `ENTRY_CHUNK_BONUS` + `_hit_sort_key` 入口优先 |
| 泛滥 `on_*` 占榜（Q2/H10） | `context_coherence_adjustment()` 替代频率降权 |

---

## Q2 — G-code 如何变成运动命令？ `已好转 · open @5`

**期望 @5：** GcodeDispatch、Robot、Planner、Conveyor、StepTicker（5 文件）  
**修复后 @5：** Robot、Planner、Conveyor、StepTicker（**4/5**）  
**仍缺 @5：** GcodeDispatch（@10 可召回）

### 修复前 Top-5（2026-06-25 基线）

| # | 文件 | 符号 | 行 | 来源 |
|---|------|------|-----|------|
| 1 | Conveyor.cpp | queue_head_block | 159 | symbol+bm25 |
| 2 | Robot.cpp | on_gcode_received | **908** | 子窗口，非入口 488 |
| 3 | ToolManager.cpp | on_gcode_received | 42 | 噪声 |
| 4 | Robot.cpp | on_gcode_received | 768 | 同文件第 2 slot |
| 5 | Drillingcycles.cpp | on_gcode_received | 198 | 噪声 |

### 根因（历史）

1. 排序问题，不是 token 未注入  
2. `on_gcode_received` 泛滥（39+ 模块）  
3. Robot 子窗口得分高于入口 chunk  
4. GcodeDispatch 在运动链问题中符号 chunk 偏弱  
5. top_k=5 对多跳题偏窄（@10 更全）

### 已实施

- [x] motion_chain 共现触发  
- [x] 入口 chunk 优先（`symbol_start`）  
- [x] `context_coherence_adjustment`  
- [ ] **不再追** GcodeDispatch @5（检索已冻结；LLM 层见 phase6_conclusion）

---

## H8 — main 函数和系统启动入口在哪里？ `已修复 · open Kernel`

**期望 @5：** main.cpp、Kernel.cpp  
**修复后 @5：** main.cpp（**1/2**）；Recall@5 PASS  
**修复前 @5：** 无（FAIL）

### 修复前 Top-5

Player / GcodeDispatch / SerialConsole 的通信入口 chunk（hint 误触发）。

### 根因（历史）

1. **QUERY_HINTS 误触发** —「启动**入口**」触发 entry 组  
2. main / Kernel 信号弱  
3. holdout 暴露子串匹配问题

### 已实施

- [x] entry 组改为短语触发（`从哪里进入` 等，非裸 `入口`）  
- [ ] Kernel.cpp @5 — **open**，不为 holdout 单独加权

---

## H10 — TemperatureControl 如何响应 G-code 温度命令？ `已修复`

**期望 @5：** TemperatureControl.cpp  
**修复后 @5：** TemperatureControl.cpp（**1/1**）  
**修复前 @5：** 无（FAIL）

### 修复前 Top-5

运动链噪声 + 泛滥 `on_gcode_received`。

### 根因（历史）

1. **「温度命令」误触 motion_chain**（裸 `命令`）  
2. 问句含模块名但排序输运动链  
3. TemperatureSwitch 名称混淆

### 已实施

- [x] motion_chain 要求 `变成` 或 `运动`+`命令` 共现  
- [x] `context_coherence_adjustment` 抬 TemperatureControl、抑无关 `on_*`

---

## H4 — 回零 / homing / G28 命令在哪里处理？ `Phase 8 修复 ✅`

**期望 @5：** Endstops.cpp  
**Phase 6.1 当时 @5：** 无（FAIL）；**@10：** PASS  
**Phase 8 后 @5：** Endstops.cpp（**PASS**）

### 说明

Phase 6.1：修复 hint 误触发后，暴露 homing 题真排名缺口——`回零`/`homing`/`G28` 找不到同名符号，处理逻辑藏在 `Endstops::on_gcode_received` 函数体内 `gcode->g == 28` 条件分支中，BM25 无法定位。

Phase 8：`05_extract_dispatch_index.py` 静态抽取该证据行，`search_dispatch()` 命中 dispatch_index，直接返回 `Endstops.cpp` 及证据行。不依赖文件名特判。

---

## 跨案例模式

| 模式 | 影响题 | 状态 | 迁移到 wire bonder |
|------|--------|------|-------------------|
| Hint 子串误触发 | H8, H10, (H4 误 PASS) | **已修** | 短语/共现触发 |
| 泛滥 `on_*` 占榜 | Q2, H10 | **已缓解** | context coherence |
| 子窗口 > 入口行 | Q2 | **已修** | `symbol_start` 优先 |
| top_k 截断 | Q2 | open | 报告 @10；不调 top_k |
| holdout 真缺口 | H4 | **接受** | 不写 per-question 规则 |

---

## 复现

```powershell
cd industrial-cpp-kb-lab
python src/03_search.py --eval
```

Gate：**all mean cov@5 >= 70%**（当前 73%，PASS）。分项见 `notes/phase6_conclusion.md`。
