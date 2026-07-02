# Eval split v2

## 新 13 题 dev_split 分配

### sealed（5）

- `H31`（hub）：`Kernel.cpp + Module.cpp + main.cpp`（注册/加载链）
- `H33`（hub）：`FileConfigSource.cpp + Config.cpp`（配置启动链）
- `H34`（hub）：`PublicData.cpp + Kernel.cpp`（跨模块数据通信链）
- `H41`（跨模块流程）：限位触发后 stop/halt 链路
- `H43`（change-impact）：Kernel 事件分发机制改动影响

### tune（8）

- `H32`, `H35`, `H36`, `H37`, `H38`, `H39`, `H40`, `H42`

## H39 审计与修订

- 问题不变：`G0 快速移动命令从串口收到到步进脉冲输出，经过哪些模块？`
- 审计结论：`Planner.cpp` 属于链路中可接受但非必须证据，降级到 `note.acceptable_optional`
- `expected_files` 从 6 降到 5：
  - `src/modules/communication/SerialConsole.cpp`
  - `src/modules/communication/GcodeDispatch.cpp`
  - `src/modules/robot/Robot.cpp`
  - `src/modules/robot/Conveyor.cpp`
  - `src/libs/StepTicker.cpp`

## expected_files > 5 的题与 cov@5 理论上限

| ID | expected_n | cov@5 理论上限 |
|----|------------|----------------|
| `Q3` | 6 | 83.3% |
| `Q4` | 7 | 71.4% |
| `Q5` | 6 | 83.3% |

> 后续分桶统计对这些题附注理论上限，避免将 top-k 上限误读为召回缺陷。

## sealed 保护规则（已落地）

- `python src/03_search.py --eval` 默认对 sealed 题仅输出 PASS/FAIL（不打印 miss 文件明细）
- 只有显式传 `--unseal` 才会展开 sealed 明细，并打印 `[UNSEAL]` 日志留痕
- `python scripts/trace_kernel_h3_h8.py --ids <sealed-id>` 默认拒绝；需 `--unseal` 才可执行并留痕

## Dense 实验输出要求（Step 2 预授权）

- 对 `Q3` / `Q4` / `Q5` 同时报告 **cov@5** 和 **cov@5 ÷ 理论上限** 的归一化值（理论上限见上表：83.3% / 71.4% / 83.3%）。

## 事故记录：sealed 明细泄露（2026-07-02）

- 泄露范围：`H31/H33/H34/H41/H43` 共 5 道 sealed 题的 `miss@5` 明细进入公开 CI 日志。
- 影响评估：sealed 裁决效力受损（尤其是机制验证场景），后续重大机制验收前需评估是否更换 sealed 题集。
- 根因：存在 eval 输出路径直接消费 `eval_summary().details`，未统一走 `run_eval()` 的 sealed 输出保护。
- 修复：sealed 脱敏下沉到 `eval_summary(unseal=False)` 默认行为；所有入口默认仅保留 sealed PASS/FAIL。仅 `--unseal` 显式开启明细，并保留 `[UNSEAL]` 日志。
- 交叉验证：lexical-tier 实测 `mean_cov@5 = 75.91%`（约 76%），与 dense 转正前基线 75.9% 一致，支持“本次 CI 失败主因是环境视差而非检索逻辑回归”的诊断。
