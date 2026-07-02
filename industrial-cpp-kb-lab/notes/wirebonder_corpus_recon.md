# WireBonder Corpus Recon (Scout Report)

- 时间(UTC): 2026-07-02T06:30:46+00:00
- 根目录: `repos\Smoothieware`
- 统计方式: `builtin-counter (cloc unavailable)`（cloc 不可用时自动 fallback）
- 文件数(仅目标扩展): **638**
- 总行数(code+comment+blank): **121,074**
- vendored 候选行数: **19,577** (16.2%)
- generated 候选行数: **670** (0.6%)
- 估算“真实手写逻辑”行数: **100,827**
- recon 摘要哈希: `29a1d523ed83bf21`

## vendored/第三方候选目录（人工最终判定）

| 目录 | 行数 | 占比 |
|------|------:|-----:|
| `mbed/src/vendor` | 19,577 | 16.2% |
| `mbed/src/vendor/NXP` | 19,577 | 16.2% |
| `mbed/src/vendor/NXP/cmsis` | 14,377 | 11.9% |
| `mbed/src/vendor/NXP/capi` | 5,200 | 4.3% |

## generated 候选文件（Top 30）

| 文件 | 行数 | 原因(启发式) |
|------|-----:|---------------|
| `mbed/src/vendor/NXP/cmsis/LPC11U24/LPC11Uxx.h` | 670 | .rc 扩展或头部包含 generated/classwizard/do not edit |

## 扩展名分布

| 扩展名 | 文件数 | 行数 | 占比 |
|--------|-------:|-----:|-----:|
| `.cpp` | 194 | 46,681 | 38.6% |
| `.h` | 350 | 44,010 | 36.3% |
| `.c` | 74 | 26,344 | 21.8% |
| `.s` | 19 | 3,594 | 3.0% |
| `.hpp` | 1 | 445 | 0.4% |

- 头文件行数占比(`.h/.hh/.hpp/.hxx`): **36.7%**

## 目录树前两层热力分布（Top 30）

| 目录(前两层) | 行数 | 占比 |
|--------------|-----:|-----:|
| `src/libs` | 59,424 | 49.1% |
| `src/modules` | 30,323 | 25.0% |
| `mbed/src` | 26,870 | 22.2% |
| `src/testframework` | 3,474 | 2.9% |
| `build/mbed_custom.cpp` | 385 | 0.3% |
| `src/main.cpp` | 277 | 0.2% |
| `build/mpu.h` | 198 | 0.2% |
| `mri/mri.h` | 108 | 0.1% |
| `src/version.h` | 8 | 0.0% |
| `src/version.cpp` | 7 | 0.0% |

## 说明

- 本报告只做语料构成侦察，不触发建索引/检索。
- vendored/generated 均为候选启发式；最终剔除由人工确认。