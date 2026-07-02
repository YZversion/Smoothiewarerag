# Phase 7 Migration Checklist (Smoothieware -> Wire Bonder)

> 本清单用于迁移预检，不执行索引/检索；仅定义“上线前必须重估”的组件。

## 范围与边界

- 本轮只做语料侦察与同步基建：`scripts/corpus_recon.py`、`scripts/00_sync_and_pin.py`
- 不建任何索引，不跑任何检索，不调任何权重
- SVN 源码视为只读派生缓存；管线代码继续 Git 管理并与语料分离

## 组件重估清单

## 1) HINT_GROUPS（必须重建）

- Smoothieware 的 hint 规则不迁移到 wire bonder
- 角色保持“领域黑话补丁”，不再承担主检索
- 需与 Doc Zhang 联合梳理术语映射（示例）：偏焊 / 劈刀 / 焊线 / EFO / 火花 / 线夹 / 送线
- 产出物：
  - wire bonder 术语词典（中文术语 -> 代码符号/模块）
  - 触发短语与共现条件（禁止裸子串）
  - 首版 hint 规则与误触发审计

风险级别：**高**

## 2) chunker（MFC/Windows 风格适配）

- 未知点：
  - 消息映射宏（`BEGIN_MESSAGE_MAP` 等）是否被错误切碎
  - 向导样板/资源相关代码是否挤占有效 chunk 槽位
  - `.rc/.idl` 与 C++ 主逻辑如何隔离
- 目标：
  - 保证“函数实现 chunk”优先
  - 控制头文件与样板文件在候选池中的比例

风险级别：**高**

## 3) eval 集（从零建设，方法论复用）

- 不迁移 Smoothieware 43 题
- wire bonder 新建 eval：
  - tune / holdout 分割
  - sealed 保护（默认只看总分）
  - 分桶统计（single-file / multi-file / vocab_mismatch）
  - 理论上限标注（`min(5,n)/n`）
- 目标是可持续的“问题驱动迭代”，不是追求一次性高分

风险级别：**高**

## 4) dense 索引（早期抽样验证）

- 当前生产默认：`BAAI/bge-m3` + `w_dense=20`
- 未知点：匈牙利命名、历史缩写、MFC 时代命名对 dense 语义匹配的影响
- 必做抽样：
  - 功能描述 -> hub 文件
  - 术语混用（中文现场词 + 英文缩写）
  - 头文件重场景下的 top-k 噪声分布

风险级别：**中-高**

## 5) 已知短板告警（迁移先验）

- 来自 `notes/b_class_squeeze_analysis.md` 的结构性结论：
  - B 类残留以“噪音文件挤出”主导（形态2）
  - 单通道 dense 对 hub 文件问题存在天然盲区
- 迁移策略：
  - 不在 Smoothieware 上继续过拟合修补
  - 在 wire bonder 先完成语料分布侦察，再决定是否需要局部 diversify 调整

风险级别：**中**

## Phase 7 开始门槛（Go/No-Go）

- [ ] 语料侦察报告完成：`notes/wirebonder_corpus_recon.md`
- [ ] revision-gated 同步脚本可用并有日志：`scripts/00_sync_and_pin.py`
- [ ] 语料目录与 Git 代码目录隔离确认
- [ ] wire bonder 术语访谈计划（Doc Zhang）排期确认
- [ ] eval 模板与 sealed 流程草案确认

仅当以上全部完成，才进入“建索引与检索回归”阶段。

## 内网执行顺序模板（占位，不在本机执行）

```powershell
# 1) 先按 SVN revision 导出只读语料快照
python scripts/00_sync_and_pin.py `
  --vcs svn `
  --svn-url "<SVN_URL_OR_PATH>" `
  --out "D:\wirebonder_export\corpus" `
  --log logs/sync_history.jsonl

# 假设得到 revision = r12345，对应目录 D:\wirebonder_export\corpus\r12345

# 2) 再对该 revision 目录做 recon，tag 与 revision 对齐
python scripts/corpus_recon.py `
  --root "D:\wirebonder_export\corpus\r12345" `
  --corpus-tag r12345 `
  --out-md notes/wirebonder_corpus_recon.md `
  --out-by-file logs/corpus_recon_by_file.csv `
  --out-summary logs/corpus_recon_summary.json
```
