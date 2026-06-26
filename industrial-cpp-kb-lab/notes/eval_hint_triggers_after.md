# Hint group triggers — after Phase 6.1 fix (phrase/co-occurrence)

| ID | split | Groups triggered (new) | Δ vs baseline |
|----|-------|------------------------|---------------|
| Q1 | tune | entry | same |
| Q2 | tune | motion_chain | same |
| Q3 | tune | motion_structure | same |
| Q4 | tune | halt | same |
| Q5 | tune | module | same |
| H1 | holdout | motion_structure | same |
| H2 | holdout | halt | same |
| H3 | holdout | (none) | same |
| H4 | holdout | **(none)** | **fixed** — was motion_chain (bare `命令`) |
| H5 | holdout | (none) | same |
| H6 | holdout | (none) | same |
| H7 | holdout | motion_structure | same |
| H8 | holdout | **(none)** | **fixed** — was entry (bare `入口`) |
| H9 | holdout | module | same |
| H10 | holdout | **(none)** | **fixed** — was motion_chain (bare `命令`) |

## Eval delta (Recall@5 / mean_cov@5)

| split | before | after |
|-------|--------|-------|
| tune | 5/5, 57% | 5/5, **68%** |
| holdout | 8/10, 70% | 9/10, **75%** |
| all | 13/15, — | 14/15, 73% |

## Per-question notes

- **Q2** cov@5: 2/5 → **4/5** (still miss GcodeDispatch @5; @10 full)
- **H8** cov@5: 0/2 → **1/2** (main.cpp yes; Kernel.cpp still @10)
- **H10** cov@5: 0/1 → **1/1** ✓
- **H4** Recall@5: PASS → **FAIL** — 戒掉 motion_chain 误触发后的真排名问题（@10 仍 PASS）；非 tune 题

**Tune gate:** 5/5 Recall@5 — 无 tune 回归。
