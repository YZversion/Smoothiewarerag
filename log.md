# 修改日志

日期：2026-06-26

## 本次修改

1. 修复引用校验过宽的问题
   - `04_answer.py` 中 `validate_citations()` 改为严格校验：
     - 至少需要 1 个 `file:line` 引用。
     - 任何越界或不在检索上下文内的引用都会使 `ok=false`。
   - 新增 `has_citations` 字段，区分“无引用”和“引用越界”。

2. 修复 app streaming 路径不校验引用的问题
   - `app.py` 的 Rich streaming 答案现在会收集完整输出文本。
   - 输出完成后调用 `validate_citations()`。
   - 在终端显示 `Citation Check: OK/WARN` 面板。

3. 修复 JSON 输出覆盖 `citations` 的问题
   - `app.py` 不再把 source 列表写回 `citations`。
   - source 列表改名为 `context_citations`。
   - `citations` 保留为 `{valid, invalid, has_citations, ok}` 校验结果。

4. 修复 `03_search.py` CLI 迁移性问题
   - 新增 `--repo-root`。
   - `--src-root` 不传时自动使用 `<repo-root>/src`。
   - 普通查询和 `--eval` 都会使用传入的 repo/src root。

5. 修复 bundle 回归漏检
   - `run_regression.py` 中 `check_bundle()` 不再把“没有 primary implementation chunk”当作 PASS。
   - bundle 检查现在会报告失败原因。
   - bundle 通过条件改为必须达到 `len(BUNDLE_IDS)`。

6. 补充检索 hit 元数据
   - `03_search.py` 的 `hit_from_chunk()` 现在输出 `class` 字段。
   - `eval_answer_layer.py` 增加模块加载失败检查。

7. 扩充检索评测集
   - `eval/eval_questions.json` 从 15 题扩展到 30 题。
   - 新增 H11-H25，覆盖：
     - Config / FileConfigSource / ConfigCache
     - SlowTicker / Adc / Watchdog
     - Extruder / Laser / Switch / FilamentDetector
     - ZProbe / DeltaGridStrategy / CartGridStrategy
     - PID_Autotuner / Thermistor / CurrentControl

## 验证结果

已执行：

```powershell
python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in pathlib.Path('src').glob('*.py')]; print('syntax ok')"
python src/03_search.py --eval
python src/run_regression.py --skip-llm
python src/app.py --test
python src/eval_answer_layer.py
```

30 题检索结果：

- `Recall@5`: 29/30 = 96.7%
- `mean_cov@5`: 86%
- gate: PASS（要求 `mean_cov@5 >= 70%`）

离线回归结果：

- retrieval: PASS
- bundle: 3/3 PASS
- citation: skip（未设置 `LLM_API_KEY`，未调用 LLM）

引用校验单元检查：

- `src/a.cpp:12` 落在 chunk 内：`ok=true`
- `src/a.cpp:99` 超出 chunk：`ok=false`
- 无引用：`ok=false`

## 仍需注意

- 30 题中 H4 在 `Recall@5` 仍失败，但 `Recall@10` 通过；这是之前冻结时保留的真实缺口。
- `eval_answer_layer.py` 的符号覆盖率只有 50%，说明“文件能找对”和“具体符号能进入 trimmed LLM context”仍是两层问题，后续可以单独优化。
