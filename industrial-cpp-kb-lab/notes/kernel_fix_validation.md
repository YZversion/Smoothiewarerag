# Kernel.cpp 召回修复 — 假设验证报告

> 改动 A：`KB_HALT_HINT_EXTENDED=1` → `_hint_halt` 增加「急停」「紧急停止」
> 改动 B：`RG_CANDIDATE_FILE_LIMIT=20|30`
> 默认（baseline）两 env 均未设置，行为与改动前一致。

## 关键发现（摘要）

1. **改动 A（hint）有效，且仅作用于 H3**：`急停` 触发 `_hint_halt` 后注入 `Kernel` / `immediate_halt` 等 token → symbol+method 通道将 Kernel.cpp 预筛排名拉到 **第 3**（预筛分 125），`immediate_halt` chunk rank=1 进 top-5。**H8 不变**（未触发任何 hint 组）。
2. **改动 B（rg 加宽）对 H3/H8 完全无效**：两题 Kernel 在 method/symbol/bm25 预筛的 `file_scores` 中 **排名为 None（零分）**，top-20/30 加宽无从谈起；rg_max 始终 0。说明 rg 通道对这类 hub 文件 **不是「差一点」而是「上游零信号」**。
3. **A+B ≈ 仅 A**：combo 与 hint_only 指标相同；rg 加宽在 hint 已注入 symbol 时无额外收益（H3 的 rg_max 仍为 0）。
4. **Q4 不受改动 A 影响**：baseline 已触发 halt hint 且 Kernel 在 top-5（rank=1）；Q4 的 57% 缺口来自 **其他 expected 文件**（SerialConsole 等），非 Kernel。
5. **回归**：27 道单文件 holdout **全部保持 100%**；无噪音挤占。
6. **耗时**：rg_30 均查询 +66.6ms，hint_rg_30 +91ms（B 侧变慢，按约束未回退）。


| 配置 | 全体 cov@5 | single | multi | holdout single | tune | H3 | H8 | Q4 | eval耗时(s) | 均查询(ms) |
|------|-----------|--------|-------|----------------|------|----|----|-----|------------|-----------|
| baseline | 95.0% | 100.0% | 78.0% | 100.0% | 84.8% | 50.0% | 50.0% | 57.1% | 14.49 | 187.43 |
| hint_only | 96.4% | 100.0% | 84.2% | 100.0% | 84.8% | 100.0% | 50.0% | 57.1% | 13.028 | 156.86 |
| rg_20 | 95.0% | 100.0% | 78.0% | 100.0% | 84.8% | 50.0% | 50.0% | 57.1% | 13.15 | 202.69 |
| rg_30 | 95.0% | 100.0% | 78.0% | 100.0% | 84.8% | 50.0% | 50.0% | 57.1% | 18.374 | 254.0 |
| hint_rg_30 | 96.4% | 100.0% | 84.2% | 100.0% | 84.8% | 100.0% | 50.0% | 57.1% | 16.884 | 278.46 |

## 各改动独立结论

### hint_only
**部分有效** — H3=100% H8=50% Q4=57%；H3进top-5通道≈method。 holdout单文件无回归。

### rg_20
top-20: H3预筛Kernel rank=None in_top=False rg_max=0; H8 rank=None in_top=False rg_max=0。 **对 H3/H8 无效** — 加宽预筛仍不足以让 Kernel 进池或 top-5。

### rg_30
top-30: H3预筛Kernel rank=None in_top=False rg_max=0; H8 rank=None in_top=False rg_max=0。 **对 H3/H8 无效** — 加宽预筛仍不足以让 Kernel 进池或 top-5。

### hint_rg_30
A+B@30: H3=100% H8=50% Q4=57%。 H3通道=method。 **部分有效，无 holdout 单文件回归。**

## H3 / H8 / Q4 — Kernel 通道明细

### baseline
**H3** cov@5=50%  kernel_in_pool=0  eval_top5_has_kernel=False
- hint_groups=[]  tokens_extra=3
- rg预筛: limit=12  Kernel排名=None  预筛分=0.0  进top-N=False  rg_max=0.0

**H8** cov@5=50%  kernel_in_pool=0  eval_top5_has_kernel=False
- hint_groups=[]  tokens_extra=1
- rg预筛: limit=12  Kernel排名=None  预筛分=0.0  进top-N=False  rg_max=0.0

**Q4** cov@5=57%  kernel_in_pool=9  eval_top5_has_kernel=True
- hint_groups=['halt']  tokens_extra=14
- rg预筛: limit=12  Kernel排名=3  预筛分=125.0  进top-N=True  rg_max=0.0
- 最佳Kernel chunk: rank=1 score=349.0 channels={'method': 125.0, 'class': 108.0, 'symbol': 85.0, 'bm25': 10.0} source=method+class+symbol+bm25
- **进top-5通道**: method (rank=1 score=349.0)


### hint_only
**H3** cov@5=100%  kernel_in_pool=9  eval_top5_has_kernel=True
- hint_groups=['halt']  tokens_extra=13
- rg预筛: limit=12  Kernel排名=3  预筛分=125.0  进top-N=True  rg_max=0.0
- 最佳Kernel chunk: rank=1 score=347.4 channels={'method': 125.0, 'class': 108.0, 'symbol': 85.0, 'bm25': 8.40228090717569} source=method+class+symbol+bm25
- **进top-5通道**: method (rank=1 score=347.4)

**H8** cov@5=50%  kernel_in_pool=0  eval_top5_has_kernel=False
- hint_groups=[]  tokens_extra=1
- rg预筛: limit=12  Kernel排名=None  预筛分=0.0  进top-N=False  rg_max=0.0

**Q4** cov@5=57%  kernel_in_pool=9  eval_top5_has_kernel=True
- hint_groups=['halt']  tokens_extra=14
- rg预筛: limit=12  Kernel排名=3  预筛分=125.0  进top-N=True  rg_max=0.0
- 最佳Kernel chunk: rank=1 score=349.0 channels={'method': 125.0, 'class': 108.0, 'symbol': 85.0, 'bm25': 10.0} source=method+class+symbol+bm25
- **进top-5通道**: method (rank=1 score=349.0)


### rg_20
**H3** cov@5=50%  kernel_in_pool=0  eval_top5_has_kernel=False
- hint_groups=[]  tokens_extra=3
- rg预筛: limit=20  Kernel排名=None  预筛分=0.0  进top-N=False  rg_max=0.0

**H8** cov@5=50%  kernel_in_pool=0  eval_top5_has_kernel=False
- hint_groups=[]  tokens_extra=1
- rg预筛: limit=20  Kernel排名=None  预筛分=0.0  进top-N=False  rg_max=0.0

**Q4** cov@5=57%  kernel_in_pool=9  eval_top5_has_kernel=True
- hint_groups=['halt']  tokens_extra=14
- rg预筛: limit=20  Kernel排名=3  预筛分=125.0  进top-N=True  rg_max=0.0
- 最佳Kernel chunk: rank=1 score=349.0 channels={'method': 125.0, 'class': 108.0, 'symbol': 85.0, 'bm25': 10.0} source=method+class+symbol+bm25
- **进top-5通道**: method (rank=1 score=349.0)


### rg_30
**H3** cov@5=50%  kernel_in_pool=0  eval_top5_has_kernel=False
- hint_groups=[]  tokens_extra=3
- rg预筛: limit=30  Kernel排名=None  预筛分=0.0  进top-N=False  rg_max=0.0

**H8** cov@5=50%  kernel_in_pool=0  eval_top5_has_kernel=False
- hint_groups=[]  tokens_extra=1
- rg预筛: limit=30  Kernel排名=None  预筛分=0.0  进top-N=False  rg_max=0.0

**Q4** cov@5=57%  kernel_in_pool=9  eval_top5_has_kernel=True
- hint_groups=['halt']  tokens_extra=14
- rg预筛: limit=30  Kernel排名=3  预筛分=125.0  进top-N=True  rg_max=0.0
- 最佳Kernel chunk: rank=1 score=349.0 channels={'method': 125.0, 'class': 108.0, 'symbol': 85.0, 'bm25': 10.0} source=method+class+symbol+bm25
- **进top-5通道**: method (rank=1 score=349.0)


### hint_rg_30
**H3** cov@5=100%  kernel_in_pool=9  eval_top5_has_kernel=True
- hint_groups=['halt']  tokens_extra=13
- rg预筛: limit=30  Kernel排名=3  预筛分=125.0  进top-N=True  rg_max=0.0
- 最佳Kernel chunk: rank=1 score=347.4 channels={'method': 125.0, 'class': 108.0, 'symbol': 85.0, 'bm25': 8.40228090717569} source=method+class+symbol+bm25
- **进top-5通道**: method (rank=1 score=347.4)

**H8** cov@5=50%  kernel_in_pool=0  eval_top5_has_kernel=False
- hint_groups=[]  tokens_extra=1
- rg预筛: limit=30  Kernel排名=None  预筛分=0.0  进top-N=False  rg_max=0.0

**Q4** cov@5=57%  kernel_in_pool=9  eval_top5_has_kernel=True
- hint_groups=['halt']  tokens_extra=14
- rg预筛: limit=30  Kernel排名=3  预筛分=125.0  进top-N=True  rg_max=0.0
- 最佳Kernel chunk: rank=1 score=349.0 channels={'method': 125.0, 'class': 108.0, 'symbol': 85.0, 'bm25': 10.0} source=method+class+symbol+bm25
- **进top-5通道**: method (rank=1 score=349.0)


## 单文件 holdout 回归检查（相对 baseline）

- **hint_only**: 无 holdout 单文件题从绿变红

- **rg_20**: 无 holdout 单文件题从绿变红

- **rg_30**: 无 holdout 单文件题从绿变红

- **hint_rg_30**: 无 holdout 单文件题从绿变红

## 耗时对比

| 配置 | eval_summary(s) | mean_query(ms) | max_query(ms) | vs baseline |
|------|-----------------|----------------|---------------|-------------|
| baseline | 14.49 | 187.43 | 409.74 | +0.0ms |
| hint_only | 13.028 | 156.86 | 314.82 | -30.6ms |
| rg_20 | 13.15 | 202.69 | 398.12 | +15.3ms |
| rg_30 | 18.374 | 254.0 | 473.46 | +66.6ms |
| hint_rg_30 | 16.884 | 278.46 | 593.78 | +91.0ms |

## Revert 说明

- 改动 A：`_hint_halt` 默认含「急停」「紧急停止」（见 `notes/CHANGELOG.md`）
- rg 预筛固定为 12（`RG_CANDIDATE_FILE_LIMIT`）

---

## rg 预筛方向关闭（2026-06-25）

**结论：** rg 预筛宽度对 hub 文件召回失败**无效**。H3/H8 中 Kernel.cpp 在 method/symbol/bm25 合成的 `file_scores` 里为 **None（全通道零信号）**，并非「排名在 top-12 之外」。将预筛从 12 扩到 20/30 后 H3/H8 指标无变化，仅增加查询耗时。

**此方向已关闭** — 后续不要再调 `RG_CANDIDATE_FILE_LIMIT` 试图解决 hub/框架文件零召回问题。见本报告 `rg_20` / `rg_30` 配置与 `notes/kernel_trace_H3_H8.md`。
