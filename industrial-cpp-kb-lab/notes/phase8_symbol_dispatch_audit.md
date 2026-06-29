# Phase 8 Symbol / Dispatch Audit

Date: 2026-06-29

Phase 8 targets the Phase 6 bottleneck: files were usually present, but the answer context often missed the exact symbol chunk. This audit records why the fix is focused on deterministic symbol / dispatch retrieval instead of a broad chunking rewrite.

## Summary

- `02_extract_symbols.py` already writes ctags `end_line`, and `03_build_chunks.py` already consumes it.
- Long function chunks preserve `symbol_start`, so subwindows still point back to the implementation symbol.
- No Phase 8 change hardcodes `expected_files` or Smoothieware target filenames into retrieval.
- Main implementation change: `03_search.py` now has `search_method()`, `search_class()`, and `search_dispatch()`.
- Dispatch implementation change: `05_extract_dispatch_index.py` writes `data/dispatch_index.json`.

## Before / After

| Metric | Before Phase 8 | After Phase 8 |
|---|---:|---:|
| eval set | 30 questions | 35 questions |
| `03_search.py --eval` all Recall@5 | 29/30 | 35/35 |
| `03_search.py --eval` all mean cov@5 | 87% | 94% |
| `eval_answer_layer.py` mean file_cov@primary | 88% | 93% |
| `eval_answer_layer.py` mean sym_cov@trim | 54% | 71% |
| H4 G28 / homing | missing `Endstops.cpp` @5 | `Endstops.cpp` hit @5 |

## Q2-Q5 Symbol Matrix

The table lists representative implementation chunks. Some event handler names such as `on_gcode_received`, `on_halt`, and `on_idle` have many same-name module implementations; Phase 8 improves ranking by using class-qualified lookup and method chunk preference.

### Q2: G-code -> Motion Command

| Expected symbol | Representative chunk | Status |
|---|---|---|
| `GcodeDispatch::on_console_line_received` | `src_modules_communication_GcodeDispatch_cpp::56-235` plus subwindows `196-375`, `336-489` | present; long function subwindows preserve `symbol_start=56` |
| `Robot::on_gcode_received` | `src_modules_robot_Robot_cpp::488-667` plus subwindows `628-807`, `768-947`, `908-1032` | present; long function subwindows preserve `symbol_start=488` |
| `Planner::append_block` | `src_modules_robot_Planner_cpp::52-210` | present |
| `Conveyor::queue_head_block` | `src_modules_robot_Conveyor_cpp::159-180` | present |
| `StepTicker::step_tick` | `src_libs_StepTicker_cpp::134-247` | present |

### Q3: Motion / Planner / Stepper Structure

| Expected symbol | Representative chunk | Status |
|---|---|---|
| `Planner::append_block` | `src_modules_robot_Planner_cpp::52-210` | present |
| `Block::calculate_trapezoid` | `src_modules_robot_Block_cpp::144-234` | present |
| `StepTicker::step_tick` | `src_libs_StepTicker_cpp::134-247` | present |
| `StepperMotor::manual_step` | `src_libs_StepperMotor_cpp::104-123` | present |

Finding: pre-Phase 8 ranking could let constructors / header class chunks outrank these implementation chunks. `search_class()` now prefers implementation method chunks and applies a stronger constructor penalty.

### Q4: Error / Stop / Halt / Emergency

| Expected symbol | Representative chunk | Status |
|---|---|---|
| `Kernel::immediate_halt` | `src_libs_Kernel_cpp::351-356` | present |
| `KillButton::on_idle` | `src_modules_utils_killbutton_KillButton_cpp::32-44` | present; same-name `on_idle` exists in many modules |
| `Endstops::on_halt` | `src_modules_tools_endstops_Endstops_cpp::407-418` | present; same-name `on_halt` exists in many modules |
| `Conveyor::on_halt` | `src_modules_robot_Conveyor_cpp::89-97` | present |

Finding: H4's G28 gap was not a chunk boundary problem. The relevant evidence is inside `Endstops::on_gcode_received`, so command dispatch retrieval is the correct fix.

### Q5: Module Registration / Event / Public Data

| Expected symbol | Representative chunk | Status |
|---|---|---|
| `Module::register_for_event` | `src_libs_Module_cpp::30-34` | present |
| `Kernel::add_module` | `src_libs_Kernel_cpp::337-340` | present |
| `Kernel::call_event` | `src_libs_Kernel_cpp::359-381` | present |
| `PublicData::get_value` | `src_libs_PublicData_cpp::5-16` | present |

Finding: the symbol chunks existed; ranking needed better method/class grounding and a tighter module hint trigger.

## Dispatch Index

`05_extract_dispatch_index.py` scans function chunks and source lines for static dispatch evidence:

- `gcode->g == N`
- `gcode->m == N`
- `switch(gcode->g/m)` + `case N`
- `gcode->m == this->configured_code` with nearby default config values
- SimpleShell / command-style handler evidence
- dynamic `has_letter('G/M') + get_value()` patterns are marked `unknown` instead of guessed

Current generated artifact:

- `data/dispatch_index.json`
- 175 entries
- 110 fixed commands

Representative evidence checks:

| Query | Expected dispatch hit |
|---|---|
| `G28` | `src/modules/tools/endstops/Endstops.cpp`, evidence around `gcode->g == 28` |
| `M104` / `M109` | `src/modules/tools/temperaturecontrol/TemperatureControl.cpp`, configured M-code defaults |
| `M221` | `src/modules/tools/laser/Laser.cpp`, plus legitimate ambiguity with extruder flow override |
| `M907` | `src/modules/tools/currentcontrol/CurrentControl.cpp` |
| `M20` / `M30` | `src/modules/utils/simpleshell/SimpleShell.cpp` |

## Verification

Commands run from `industrial-cpp-kb-lab`:

```powershell
python src/03_build_chunks.py
python src/05_extract_dispatch_index.py
python src/03_build_callgraph.py
python src/03_search.py --eval
python src/eval_answer_layer.py
python src/run_regression.py --skip-llm --top-k 8
```

Results:

- `03_search.py --eval`: 35/35 Recall@5, all mean cov@5 94%, tune Recall@5 5/5.
- `eval_answer_layer.py`: mean file_cov@primary 93%, mean sym_cov@trim 71%.
- `run_regression.py --skip-llm --top-k 8`: PASS.

