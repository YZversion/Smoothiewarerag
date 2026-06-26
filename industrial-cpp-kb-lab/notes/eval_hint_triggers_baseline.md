# Hint group triggers — baseline (bare substring, pre Phase 6.1 fix)

Recorded before `03_search.py` phrase/co-occurrence hint rewrite.

| ID | split | Groups triggered (old) | False-positive notes |
|----|-------|------------------------|----------------------|
| Q1 | tune | **entry** | OK |
| Q2 | tune | **motion_chain** | OK (`变成`+`运动`+`命令`) |
| Q3 | tune | **motion_structure** | OK |
| Q4 | tune | **halt** | OK |
| Q5 | tune | **module** | OK |
| H1 | holdout | **motion_structure** (`planner`) | OK |
| H2 | holdout | **halt** (`halt`) | OK |
| H3 | holdout | *(none)* | OK |
| H4 | holdout | **motion_chain** (bare `命令`) | **false** — homing 题不应注入运动链 |
| H5 | holdout | *(none)* | OK |
| H6 | holdout | *(none)* | OK |
| H7 | holdout | **motion_structure** (`stepper`) | OK |
| H8 | holdout | **entry** (bare `入口`) | **false** — `启动入口` ≠ G-code 进入 |
| H9 | holdout | **module** (`模块`) | OK |
| H10 | holdout | **motion_chain** (bare `命令`) | **false** — 温度命令 ≠ 运动链 |

## Baseline eval (Recall@5 / mean_cov@5)

- tune: 5/5, 57%
- holdout: 8/10, 70%
- Notable misses @5: Q2 cov 2/5, H8 cov 0/2, H10 cov 0/1
