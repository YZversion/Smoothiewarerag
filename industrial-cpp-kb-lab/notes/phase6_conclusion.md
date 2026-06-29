# Phase 6.1 结论 — 检索 vs LLM（2026-06-25）

> **历史基线。** Phase 10（2026-06-29）已补齐 Q3–Q5 检索与 tune LLM expected（5/5）。见 [`phase10_conclusion.md`](phase10_conclusion.md)。

## 三句话结论

1. **检索够用**：15 题 Recall@5 = 14/15（93%），mean coverage@5 = **73%**（>70% 门槛）；`top_k=8` 时 primary 文件覆盖 **76%**。BM25+symbol+rg 不必再调，也暂不需要向量检索。
2. **LLM 基本靠谱、但不完整**：15/15 引用校验通过（无胡编行号）；约 **80%** 题能提到一半以上期望符号，仅 **40%** 题列全所有期望文件——漏答主要是 **LLM 没把 context 里已有文件写全**，不是引用造假。
3. **瓶颈在「文件到了、符号 chunk 没到」+ prompt 完整性**：`trim_context_hits` 零损失（trim_loss=0），裁剪不是主因；context 内期望符号仅 **50%** 命中，Q3/Q4/Q5 等多文件流程题仍缺符号级 chunk——这比上 CodeGraph 更紧迫的是 **chunk 边界/符号对齐**，向量检索优先级更低。

---

## 分层数据（`top_k=8`，bundle + trim≤8）

| 层 | 指标 | 结果 |
|----|------|------|
| 检索 @5 | Recall@5 / mean cov@5 | 14/15，73% |
| 检索 primary | mean file_cov | **76%** |
| Context trim | mean sym_cov / trim_loss | **50%** / **0**（裁剪未丢符号） |
| LLM | Citation OK | **15/15 (100%)** |
| LLM | 答案列全所有期望文件 | 6/15 (40%) |
| LLM | 答案提及 ≥½ 期望符号 | 12/15 (80%) |
| 回归 | tune citation + bundle | 5/5 + 3/3 PASS |

复现：

```powershell
cd industrial-cpp-kb-lab
python src/03_search.py --eval
python src/run_regression.py --top-k 8
python src/eval_answer_layer.py --top-k 8 --llm
```

---

## 漏答归因（样例）

| 题 | 检索 | Context 符号 | LLM | 主因 |
|----|------|-------------|-----|------|
| Q2 | 5/5 文件 @8 | 4/5 sym | 3/5 文件写在答案里 | LLM 完整性 + 缺 GcodeDispatch 符号 chunk |
| Q3 | 5/6 文件 | **0/4 sym** | 1/4 sym | **检索 chunk 未对齐**（文件在、函数 chunk 不在） |
| Q4 | 4/7 文件 | 1/4 sym | 2/4 sym | 检索覆盖窄 + LLM 未列全 |
| H4 | 0/1 文件 | 0/2 sym | 0/1 | **纯检索**（homing 无 hint 误触后的真缺口） |
| H10 | 1/1 文件 | 0/1 sym | 1/1 sym | 文件对、chunk 符号行未进 bundle，LLM 仍答对 |

---

## 升级决策

| 方案 | 建议 | 理由 |
|------|------|------|
| 继续调 `03_search.py` | **已冻结** | mean cov@5 73% ≥70%；H4 等 holdout open 接受 |
| 向量检索 | **暂缓** | 文件级召回已够；符号级问题更像 chunk/ctags 对齐 |
| CodeGraph / Plan B | **可选小实验** | 对「调用链 / 影响面」类问题有价值，不挡 Phase 7 |
| **下一步主线** | **Phase 7 wire bonder** + 轻量改 prompt/04 | 换仓库验迁移；prompt 强调「列全 context 中所有相关文件」 |

---

## Phase 6.1 checklist

- [x] 15 题 eval + coverage@K
- [x] 失败案例记录（`notes/eval_failures.md`，H8/H10 已修）
- [x] 检索 vs LLM 分层评估（本文件 + `src/eval_answer_layer.py`）
- [x] Phase 6 总验收「升级决策」→ 见上表，检索层已冻结
