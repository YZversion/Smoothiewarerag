# Generalization Follow-up Diagnosis

Date: 2026-06-30

## Reviewer position

我不同意把 scale_test mean_cov@5=38% 归因成“BM25 参数没调好”。

- 为什么这可能是错的：失败样本里有 `.cc` 文件未被扫描、宏符号被加载过滤、三段 C++ 限定名解析缺失、Smoothieware 专用 `error` hint 误触发等结构性问题。单纯调权重无法召回未入索引的文件。
- 严重程度：阻断。
- 更好的替代方案：先修通用索引覆盖和符号解析缺陷，再用原 eval 复测，不修改 expected_files，不硬编码项目路径。
- 下一步应该验证什么：scale_test 原问题集的 Recall@5 / Recall@10 / mean_cov@5 / P95，以及 Smoothieware 回归是否保持通过。

## Baseline

Command:

```powershell
python src/03_search.py --eval --eval-file eval/scale_test_questions.json --repo-root repos/scale_test --src-root repos/scale_test
python scripts/benchmark_queries.py --repo-root repos/scale_test --src-root repos/scale_test --out data/benchmark_latency_scale_test_after_fix.json
```

| Metric | Before fix |
| --- | ---: |
| Recall@5 | 9/20 |
| Recall@10 | 13/20 |
| mean_cov@5 | 38% |
| P50 | 391.7 ms |
| P95 | 435.1 ms |
| P99 | 555.1 ms |

## Failure classification

| Class | Questions | Evidence | Decision |
| --- | --- | --- | --- |
| Missing source extensions | ABSL-04, GTEST-02, GTEST-04 | `parse.cc` and `gtest.cc` were expected but absent from manifest/index because scanner only kept `.c/.cpp/.h/.hpp`. | Fix: include common C/C++ extensions `.cc/.cxx/.hh/.hxx`. |
| Macro symbols filtered at search load | ABSL-05, RAYLIB-03, IMGUI-03, GTEST-03, GTEST-05 | ctags extracted macros, but `_load_symbols()` ignored `macro`, so exact macro names fell back to BM25. | Fix: load macro/enum/typedef symbols and score exact macro hits. |
| C++ qualified name too shallow | GTEST-02 | `testing::UnitTest::Run` was parsed as a two-part name, not class `testing::UnitTest` + method `Run`. | Fix: parse multi-segment `A::B::C` qualified names. |
| Smoothieware-specific hint leakage | RAYLIB-05, IMGUI-05 | Bare English `error` triggered the Smoothieware `halt` hint group. | Fix: remove bare `error` from halt trigger; keep explicit `halt/stop/emergency`. |
| Merge-time performance bug | All queries after `.cc` inclusion | Profiling showed merge P95 ~656 ms because `_chunk_module_stems()` rebuilt all file stems per candidate. | Fix: cache file stems at index load. |
| Natural-language to API-name gap | RAYLIB-04, IMGUI-05 | Queries do not contain `SetConfigFlags`, `FLAG_FULLSCREEN_MODE`, `IM_ASSERT_USER_ERROR`, so they still rely on weak BM25 semantics. | Do not overfit now; requires a separate symbol-part/chunk design. |
| Definition-vs-constructor ambiguity | IMGUI-01 | `ImGuiIO` class definition is found at @10, but constructor/function chunks can outrank it at @5. | Do not overfit now; needs class-definition intent ranking or symbol-level chunking. |

## Minimal fix implemented

Code changes are limited to:

- `src/01_scan_files.py`: scan `.cc/.cxx/.hh/.hxx`.
- `src/03_build_chunks.py`: treat `.cc/.cxx` as implementation files and `.hh/.hxx` as headers.
- `src/search/index.py`:
  - load `macro`, `enum`, `typedef` symbols;
  - fallback macro/enum/typedef hits to file overview when no precise chunk exists;
  - parse multi-segment C++ qualified names;
  - avoid class-method expansion except for multi-file structure queries;
  - remove bare `error` from Smoothieware `halt` hint trigger;
  - cache module/file stems for context coherence scoring.

No vector DB, LangChain, Agent, reranker, or expected-file hardcoding was introduced.

## After fix

Scale_test index after extension coverage:

| Item | Before | After |
| --- | ---: | ---: |
| Files | 895 | 1491 |
| Chunks | 7347 | 18701 |
| Symbols | 59581 | 70269 |

Final scale_test metrics:

| Metric | Before fix | After fix |
| --- | ---: | ---: |
| Recall@5 | 9/20 | 17/20 |
| Recall@10 | 13/20 | 17/20 |
| mean_cov@5 | 38% | 75% |
| P50 | 391.7 ms | 47.9 ms |
| P95 | 435.1 ms | 75.4 ms |
| P99 | 555.1 ms | 100.7 ms |

The temporary `.cc` inclusion initially pushed P95 above 700 ms, but caching module stems brought P95 back under the 500 ms gate.

## Remaining failures

| Question | Current result | Likely cause | Recommendation |
| --- | --- | --- | --- |
| RAYLIB-04 | FAIL@5 / FAIL@10 | Query says “configuration flags before window initialization” but does not include `SetConfigFlags` or `FLAG_FULLSCREEN_MODE`; raylib examples and platform files dominate generic BM25. | Keep as residual natural-language-to-symbol gap; validate on real wire bonder questions before adding symbol-part expansion. |
| IMGUI-01 | FAIL@5 / PASS@10 | Exact class file is close but constructor/function and generic `State`-like symbols can outrank it. | Add class-definition intent ranking only if real pilot shows this pattern. |
| IMGUI-05 | FAIL@5 / FAIL@10 | Query lacks `IM_ASSERT_USER_ERROR`; natural phrase “user-error assertions” is not enough for robust exact symbol retrieval. | Requires either symbol-part matching or macro definition chunks; defer until real failure samples justify it. |

## Pilot recommendation

值得进入 wire bonder pilot，但只能以“受控试点”方式进入。

可以声称：

- 系统现在能在 Smoothieware 上稳定通过既有回归。
- 系统能在包含 abseil/raylib/imgui/googletest 的多项目 C/C++ 索引上达到 scale_test mean_cov@5 75%。
- 修复后的 scale_test P95 低于 500 ms。
- 代码仍然不需要向量库、LangChain、Agent 或 expected_files 硬编码。

不能声称：

- 已经证明 wire bonder 准确率。
- 已经解决自然语言到私有 API/报警码/状态机符号的映射。
- LLM 答案完整性已验证；本轮仍是检索层诊断。

下一步最值得验证：

1. 用 wire bonder 非核心只读目录重建索引，确认 `.cc/.cxx/.hh/.hxx`、编码、生成代码和第三方库噪声。
2. 收集 10 个真实问题，复用 `scale_test_questions.json` 字段结构。
3. 单独标记问题是否包含真实符号名；把“自然语言问题”和“带符号问题”分开统计 Recall@5。
4. 只有当真实 pilot 也出现 `configuration flags -> SetConfigFlags` 这种模式，再设计通用 symbol-part expansion 或 macro chunk。
