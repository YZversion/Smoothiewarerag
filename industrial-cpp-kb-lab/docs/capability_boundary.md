# Capability Boundary

## 能做什么

这套工具当前定位是只读代码知识库，用来帮助工程师更快定位和理解工业设备 C/C++ 代码。

| 能力 | 说明 | 输出证据 |
|------|------|----------|
| 定位函数 / 类 / 文件 | 根据模块名、函数名、命令码、错误关键词搜索相关源码 | file:line、symbol、snippet |
| 解释调用和流程 | 解释入口、事件分发、模块注册、运动链路、halt 链路 | 检索出的源码 chunk + 引用 |
| 查命令码 / 事件码处理器 | 对 Smoothieware 的 G/M-code 已有 dispatch index；wire bonder 需按实际规则适配 | 命令码 evidence line |
| 新人辅助 | 把“代码在哪里”变成带引用的模块地图 | Sources 表、文件职责说明 |
| 故障初步定位 | 根据报警、stop、halt、超时等关键词找到候选处理点 | 候选文件和风险说明 |
| 迁移前风险评估 | `kb probe` 扫描编码、ctags 兼容、超长文件、generated code | Markdown / JSON probe 报告 |

## 不做什么

| 不做 | 原因 |
|------|------|
| 不自动修改代码 | 工业运控代码风险高，必须由工程师确认 |
| 不提交 SVN / Git | 当前阶段只读，不写业务仓库 |
| 不生成 patch / diff | Level 2 之后才讨论；当前 Phase D 不做 |
| 不承诺回答 100% 正确 | ctags、BM25、动态分发都有边界，答案必须看引用核查 |
| 不训练模型 | 只做本地索引和检索，不把公司代码拿去训练 |
| 不上传全仓库源码 | LLM 只看到检索出的少量 chunk；可切换离线模型完全不外发 |
| 不替代代码评审 | 它是定位和解释工具，不是审批系统 |

## 安全边界

- 代码目录只读输入。
- `kb probe` 只读取源码并生成本地报告。
- `kb index build` 的产物写到独立索引目录，不写回源码目录。
- LLM 调用只发送检索出的 chunk 片段，不发送全仓库全文。
- 可选离线部署：Ollama / llama.cpp / 内网模型。
- 查询日志和错误日志保存在本地 `logs/`。
- `.env` 的 API key 不提交。
- 每次索引构建输出到版本目录，例如 `data/index_v20260630/`；`kb index check` 通过后再切换，旧索引可回滚。

## 已知技术边界

| 边界 | 影响 | 应对 |
|------|------|------|
| 动态分发 | 函数指针、消息 ID、事件总线可能无法靠文本 mention 捕获 | 增加 dispatch index 规则，保留 evidence line |
| 宏密集代码 | ctags 可能漏掉真实入口 | probe 先报告风险，再按业务模式补规则 |
| GBK / GB18030 | 编码不统一会影响文本读取和行号展示 | probe 先列出异常编码文件 |
| 超长或 generated 文件 | 检索噪声和延迟上升 | 先报告，再按目录排除 |
| 没有真实问题集 | 无法证明对 wire bonder 业务有用 | 软件部提供 10 个问题做首轮验收 |

## 当前验收状态

- Smoothieware eval：35/35 Recall@5，mean_cov@5=94%。
- P95 修复后当前 Smoothieware benchmark：P95=143ms。
- Phase C probe：
  - `reports/scale_test_probe.md`
  - `reports/smoothieware_probe.md`
- 下一步需要真实 wire bonder 只读目录和 10 个问题。
