# Wire Bonder Migration Plan

## 目标

把 Smoothieware 上验证过的只读代码知识库迁移到 wire bonder C/C++ 代码库。第一轮只证明三件事：

- 能安全扫描一个只读代码目录。
- 能判断编码、ctags、超长文件、生成代码等接入风险。
- 能用工程师提供的真实问题验证检索质量。

本阶段不修改业务代码，不生成 patch，不写入 SVN。

## 接入流程

1. 软件部提供一个只读代码目录。
   优先选择非核心模块、历史版本或可脱敏目录；第一轮建议不超过 5 万行。

2. 运行 repo probe。

   ```powershell
   kb probe --repo-root D:/WireBonderCode --out reports/wire_bonder_probe.md --json-out reports/wire_bonder_probe.json
   ```

   输出文件统计、编码统计、ctags 结构统计、风险文件、目录代码地图和索引可行性评估。

3. 确认编码与 ctags 兼容性。
   重点看 GBK/GB18030 文件、ctags 空结果文件、MFC 消息映射宏、超长文件和疑似 generated code。

4. 本地构建索引。

   ```powershell
   kb index build --repo-root D:/WireBonderCode --src-root D:/WireBonderCode --out data/index_vYYYYMMDD
   kb index check --index data/index_vYYYYMMDD
   ```

5. 用 10 个真实问题做小范围验收。
   每个问题至少要求返回源码文件、函数或类名、file:line 引用。没有 ground truth 的问题先不计入自动化分数，只做工程师人工确认。

6. 工程师验收后再决定是否扩大范围。
   如果首轮问题命中率低，先补充 hint group、dispatch 规则或排除 generated 目录，不直接上向量库或 Agent。

## 数据安全边界

- 代码只在本地或内网机器处理。
- `kb probe` 只读取源码并生成本地报告，不上传代码。
- `kb index build` 只生成本地索引文件，不写入 SVN。
- LLM 调用只发送检索出的 chunk 片段，不发送全仓库全文。
- 可以切换到离线本地模型，例如 Ollama 或 llama.cpp，做到完全不外发。
- 查询日志保存在本地 `logs/query.jsonl`，错误日志保存在本地 `logs/error.jsonl`。
- `.env` 中的 `LLM_API_KEY` 不提交 git。

## 已知适配风险

| 风险 | 影响 | 处理方式 |
|------|------|----------|
| GBK / GB18030 编码 | 读取与行号显示可能不一致 | 用 `kb probe` 先列出异常编码文件，必要时统一转码或在读取层显式处理 |
| MFC 消息映射宏 | ctags 可能无法解析真实入口 | 对消息 ID / 宏表补充 dispatch index 规则 |
| 超长文件 | 检索延迟升高，chunk 质量下降 | 优先判断是否第三方或 generated code；可通过 `--exclude` 排除目录 |
| generated code | 噪声高，容易污染问答 | probe 报告中标出，默认不作为业务问答重点 |
| 动态分发 | 函数指针 / 消息 ID 不能靠 mention graph 完整捕获 | 增加确定性抽取规则，保留 evidence line |
| 第三方库混入业务目录 | 索引体积和延迟上升 | probe 后按目录排除，而不是硬编码文件名 |

## 回滚策略

- 每次 build 输出到独立目录，例如 `data/index_v20260630/`。
- 新索引用 `kb index check` 验证后再切换。
- 保留上一个可用索引目录，不覆盖旧索引。
- 如果新索引质量下降，直接切回旧目录。
- 不在 wire bonder 源码目录写入任何产物。

## 与 Smoothieware 的差异备忘

- Smoothieware 的 `HINT_GROUPS` 不能直接照搬到 wire bonder。
- wire bonder 需要工程师提供真实问题和 ground truth，不能用 Smoothieware 的 expected files 反推规则。
- dispatch index 要按公司代码实际模式重写，可能是菜单 ID、报警码、运动命令、Windows 消息或设备状态码。
- 如果真实代码存在大量宏、模板或 MFC 消息映射，ctags 结果只能作为候选事实，不能当作完整调用图。
- 第一轮迁移只做 Level 0 只读问答；Level 1 修改建议必须等检索质量和安全边界被验证后再进入。

## 首轮验收建议

| 项目 | 验收标准 |
|------|----------|
| probe | 报告包含文件统计、编码统计、ctags 统计、风险文件和可行性评估 |
| index build | 构建过程无崩溃，`kb index check` 通过 |
| 真实问题 | 至少 10 个问题，覆盖入口定位、错误追踪、状态机、回零流程、报警码 |
| 引用质量 | 回答必须包含 file:line，且可在源码中核查 |
| 安全边界 | 不上传代码，不修改源码，不写 SVN |
