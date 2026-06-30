# Generalization Audit

Date: 2026-06-30

## Executive conclusion

我不同意把 Phase B 的 80 万行 scale_test 压测解释为“系统已经证明了跨大型代码库的准确率/召回率”。

- 为什么这可能是错的：Phase B 的核心证据是索引构建、rg 延迟、P50/P95/P99 和 ctags 可行性；它没有针对 abseil-cpp、raylib、imgui、googletest 构造 golden questions，也没有计算 Recall@K 或 mean coverage。
- 严重程度：高风险。
- 更好的替代方案：把“规模性能验证”和“检索准确度/召回率验证”分开报告。性能看 benchmark，准确率看带 expected_files 的 eval。
- 下一步应该验证什么：用真实 wire bonder 只读目录和 10 个真实问题跑同样的 Recall@5 / Recall@10 / mean_cov@5，并人工核查引用是否能回答问题。

## What Smoothieware has proved

Smoothieware 当前证明的是：在一个固件型 C/C++ 代码库上，经过多轮针对入口、运动链路、事件注册、halt、dispatch 的检索规则收敛后，系统可以稳定命中既定 golden set。

已知证据：

| Item | Result |
| --- | --- |
| Eval set | 35 questions |
| Smoothieware Recall@5 | 35/35 |
| Smoothieware mean_cov@5 | 94% |
| Smoothieware benchmark after P95 fix | P50 85.0 ms / P95 143.1 ms / P99 151.8 ms |

这个结论不能自动外推到其他代码库，因为 Smoothieware 的命中率受益于已有的 domain hints、G-code dispatch index、事件/运动链路调权和多轮手工诊断。

## What scale_test newly validates

本次新增 `eval/scale_test_questions.json`，覆盖 `repos/scale_test` 中的 4 个大型 C/C++ 项目：

| Project | Questions | Covered categories |
| --- | ---: | --- |
| abseil-cpp | 5 | class/struct, function, macro/constant, init/config, error/assert |
| raylib | 5 | class/struct, function, macro/constant, init/config, error/assert |
| imgui | 5 | class/struct, function, macro/constant, init/config, error/assert |
| googletest | 5 | class/struct, function, macro/constant, init/config, error/assert |

Eval command:

```powershell
python src/03_search.py --eval --eval-file eval/scale_test_questions.json --repo-root repos/scale_test --src-root repos/scale_test
```

Accuracy results:

| Metric | Result |
| --- | ---: |
| Recall@5 | 9/20 |
| Recall@10 | 13/20 |
| mean_cov@5 | 38% |
| Gate | FAIL, below 70% mean_cov@5 |

Performance command:

```powershell
python scripts/benchmark_queries.py --repo-root repos/scale_test --src-root repos/scale_test --out data/benchmark_latency_scale_test.json
```

Performance results:

| Metric | Result |
| --- | ---: |
| Query count | 50 |
| Errors | 0 |
| P50 | 391.7 ms |
| P95 | 435.1 ms |
| P99 | 555.1 ms |
| P95 <= 500 ms | PASS |

结论：P95 修复已经把 scale_test 的查询延迟压到可接受区间，但准确率/召回率仍未达到可迁移验收标准。性能问题和检索质量问题是两件事。

## Failure pattern

本次 scale_test 的失败主要集中在：

- 宏/常量定义：`ABSL_CHECK`、`RAYLIB_VERSION`、`IMGUI_VERSION` 这类短宏名容易被测试、示例、注释或同名引用稀释。
- 初始化流程：`ParseCommandLine`、`SetConfigFlags`、`InitGoogleTest` 需要同时命中 declaration + implementation，当前文件级 coverage 不稳定。
- 大型单文件：`imgui.cpp`、`gtest.cc` 这类超大实现文件容易在 BM25 chunk 层命中局部片段，但文件排序未必进 top 5。
- 非 Smoothieware 领域：现有 `HINT_GROUPS`、dispatch index、halt/motion 规则偏向 Smoothieware，对通用库没有等价意图模型。

这些失败不能靠修改 eval expected_files 掩盖，也不应该把 expected_files 硬编码进检索器。

## What cannot be extrapolated to wire bonder

仍不能外推的结论：

- 不能证明 wire bonder 的报警码、命令码、状态机、设备流程能被准确定位。
- 不能证明私有代码里的宏、配置表、MFC/Win32 回调、PLC/运动控制接口能被稳定召回。
- 不能证明真实工程师问题的表达方式能被当前 BM25 + hints 覆盖。
- 不能证明 LLM 最终答案完整，因为本轮只测检索层，不调用 LLM。
- 不能证明 `expected_symbols` 层面的精确符号召回；本轮 symbols 字段只作为人工审计线索，自动 gate 仍是文件级 Recall/Coverage。

## Wire bonder must still validate

第一轮 wire bonder pilot 必须验证：

- 真实只读目录上的索引构建是否成功，是否存在编码、超大文件、生成代码、第三方库噪声。
- 10 个真实问题的 Recall@5 / Recall@10 / mean_cov@5。
- 报警码、命令码、初始化流程、状态机、模块边界、错误处理的引用是否可被工程师复核。
- LLM 是否只看检索片段，回答是否包含文件:行号引用，是否会编造不可见代码。
- 性能是否仍满足 P95 <= 500 ms；如果真实目录大于 scale_test，需要重新跑 benchmark。

## Recommended next step

不要继续声明“泛化能力已证明”。当前更稳妥的表述是：

> 系统已经证明了 Smoothieware 场景下的可用性，并在 80 万行多项目代码上证明了索引和查询延迟可控；但跨项目准确率尚未达标，需要用 wire bonder 真实问题做 pilot 验证。

下一步最小范围：

1. 向软件部申请一个非核心只读目录。
2. 收集 10 个真实 wire bonder 问题，按入口定位、错误追踪、状态机/流程、报警码/命令码、模块边界分类。
3. 跑 `kb probe`、索引构建、`scale_test_questions` 同结构的 wire bonder eval。
4. 只在真实失败样本上做检索规则调整，不提前引入向量库、LangChain 或 Agent。
