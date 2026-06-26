# Smoothieware rg / BM25 Findings

日期：2026-06-26

目的：记录 Plan B A 面结果。这里不调整主检索器，只观察现有 `rg + ctags + BM25 + QUERY_HINTS` 对 5 个结构问题的表现。

## 方法

在 `industrial-cpp-kb-lab` 下运行：

```powershell
python src/03_search.py "<question>" --top-k 8 --json
```

补充检查 H4：

```powershell
python src/03_search.py "回零 / homing / G28 命令在哪里处理？" --top-k 10 --json
```

当前检索基线：

- `chunks.jsonl`：1569 chunks
- `eval_questions.json`：30 题
- 最新回归：Recall@5 = 29/30 = 96.7%，mean_cov@5 = 86.0%

## 5 个问题结果

| 问题 | rg / BM25 表现 | 主要证据 |
|------|----------------|----------|
| G-code 的入口文件在哪里？ | 中等。能找到 `Gcode.cpp` / `Gcode.h` / `GcodeDispatch.cpp`，但这个问法没有触发“从哪里进入系统” hint，因此入口链 `SerialConsole` / `Player` 不稳定。 | `src/modules/communication/utils/Gcode.cpp`、`src/modules/communication/utils/GcodeDispatch.cpp` |
| `Gcode` 类 / 函数被哪些模块调用？ | 偏弱。容易漂到 `Kernel::register_for_event`、`Module::register_for_event`、`Kernel::call_event`，能看到事件系统，但不能直接列出全部 `on_gcode_received` 处理器。 | `src/libs/Kernel.cpp`、`src/libs/Module.cpp`、`src/modules/communication/utils/Gcode.cpp` |
| Motion planner 相关核心类有哪些？ | 强。`Planner`、`Block`、`Conveyor`、`StepTicker`、`StepperMotor` 都在前列，适合“模块地图”类问题。 | `src/modules/robot/Planner.cpp`、`src/modules/robot/Block.cpp`、`src/modules/robot/Conveyor.cpp`、`src/modules/robot/StepperMotor.cpp` |
| halt / error / stop 的调用链在哪里？ | 中等。能找出高价值候选文件，但不是调用链。 | `src/libs/Kernel.cpp`、`src/modules/tools/endstops/Endstops.cpp`、`src/modules/utils/killbutton/KillButton.cpp`、`src/modules/robot/StepperMotor.cpp` |
| 修改某个函数后可能影响哪些模块？ | 偏弱。能定位 `Planner::append_block` 定义和声明，但不能自动给出影响半径。 | `src/modules/robot/Planner.cpp`、`src/modules/robot/Planner.h` |

## H4 补充观察

问题：`回零 / homing / G28 命令在哪里处理？`

现有检索在 top 10 才命中：

- `src/modules/tools/endstops/Endstops.cpp`
- `Endstops::on_gcode_received`
- 证据：函数体内判断 `gcode->has_g && gcode->g == 28`，之后进入 homing / park 相关逻辑。

但该结果没有进入 top 5，原因仍是：`G28` 是命令号到处理器的分发关系，不是普通函数名、类名或调用链关系。BM25 只能靠文本相似度和 hint 兜底，不能稳定理解“命令号 -> handler”。

## 小结

rg / BM25 的优势：

- 很快，适合关键词、文件、模块地图和源码证据定位。
- 对 “Motion / Planner / Stepper” 这种术语明确的问题效果好。
- 和现有问答层结合简单，引用路径稳定。

rg / BM25 的弱点：

- 问法敏感，同一个问题换成“入口文件在哪里”可能不触发已有 hint。
- 不擅长 caller / callee / impact radius。
- 不擅长事件总线、命令号、报警码这类“分发查找”问题。

结论：rg / BM25 仍适合作为主线检索层；Plan B 的 CodeGraph 应该作为结构查询补充，而不是替代主线。
