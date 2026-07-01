# Reports Index

`reports/` 存放工具生成或半自动生成的探针报告。报告是证据，不是主线说明文档。

| 文件 | 来源 | 用途 |
|---|---|---|
| [`smoothieware_probe.md`](smoothieware_probe.md) | `kb probe --repo-root repos\Smoothieware` | Smoothieware 接入风险和结构扫描 |
| [`scale_test_probe.md`](scale_test_probe.md) | `kb probe --repo-root repos\scale_test` | scale_test 大规模语料结构扫描 |

## 后续命名建议

wire bonder 真实目录到位后，报告按以下方式命名：

```text
wire_bonder_probe.md
wire_bonder_real_problem_eval.md
wire_bonder_failure_classification.md
```

## 维护规则

- 不在报告里维护路线图，路线图放在 `../docs/`。
- 不手工改动 probe 原始结论，除非明确标注为人工补充。
- 涉及公司真实路径或敏感信息时，提交前先脱敏。
