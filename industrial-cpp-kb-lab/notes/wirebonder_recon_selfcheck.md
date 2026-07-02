# WireBonder Recon Self-check (Smoothieware proxy)

## Task 1: vendored recall check for `mbed`

- **结论**：`mbed` 整棵树现在被纳入 vendored 候选，不再仅限 `mbed/src/vendor`。
- 最新 recon 报告：`notes/wirebonder_corpus_recon_r620e1622972b_v3.md`

### mbed 归属核查

- 仓库总行数：`121,074`
- `mbed/**` 总行数：`26,870`
- 占比：`22.19%`
- 最终归属：**vendored candidate**

### 修订前后对比（手写逻辑估算）

| 版本 | vendored 候选行数 | 手写逻辑估算 |
|------|-------------------:|-------------:|
| 修订前（仅 `mbed/src/vendor`） | 19,577 | 100,827 |
| 修订后（整棵 `mbed` 作为候选） | 26,870 | 93,534 |

- 变化：手写逻辑估算 **-7,293** 行（对应 `mbed` 非 `vendor` 子树被补充识别）。

### 本次修法（仅 recon 启发，不改检索逻辑）

- 目录名启发补充：`mbed` 纳入 vendored token。
- 大树启发补充：
  - 顶层大目录（>=5% 行数）优先判定；
  - 若与 `src` 版权签名集合不重合（或 `src` 无版权签名可比），加入候选。

> 识别结果仍是“候选清单+占比”；最终剔除策略留给人工在内网依据真实语料决定。
