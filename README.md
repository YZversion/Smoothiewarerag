# Smoothiewarerag — industrial-cpp-kb-lab

工业设备 C++ 代码问答知识库：用 **ripgrep + ctags + BM25 + LLM** 实现「输入问题 → 返回源码 + 解释 + 文件:行号引用」。

当前以 **Smoothieware**（LPC17xx OOP C++ G-code / CNC 控制器）练手，验证后通过 `--repo-root` 迁移到公司 wire bonder 代码库。

---

## 快速上手

```powershell
cd industrial-cpp-kb-lab
pip install -r requirements.txt

# 一键重建索引（Smoothieware 已 clone 时）
python src/01_scan_files.py
python src/02_extract_symbols.py
python src/03_build_chunks.py

# 问答（注意：须在 industrial-cpp-kb-lab 目录执行）
python src/app.py                        # Rich REPL
python src/app.py "G-code 从哪里进入系统？"
python src/app.py --test                 # 检索回归
```

LLM 配置：复制 `.env.example` → `.env`，设置 `LLM_API_KEY`（智谱/OpenAI 等 OpenAI 兼容接口）。

---

## 示例输出

```
问题：G-code 从哪里进入系统？

简要解释：
串口由 SerialConsole::on_main_loop 收行后 call_event(ON_CONSOLE_LINE_RECEIVED)；
GcodeDispatch::on_console_line_received 解析并分发 G-code。

关键文件 / 函数：
  `src/modules/communication/SerialConsole.cpp:249` — 串口主循环
  `src/modules/communication/GcodeDispatch.cpp:56`  — G-code 行处理入口
  `src/modules/utils/player/Player.cpp:422`         — SD 卡播放入口
```

---

## 项目结构

```
Smoothiewarerag/
├── README.md              # 本文件
├── PLAN.md                # Phase 0–7 计划与验收
├── AGENTS.md              # AI 协作入口（进度 / 约束 / 命令）
├── architecture.md        # 系统架构
├── docs/history.md        # 进度日志
└── industrial-cpp-kb-lab/
    ├── src/
    │   ├── 01_scan_files.py
    │   ├── 02_extract_symbols.py
    │   ├── 03_build_chunks.py
    │   ├── 03_search.py       # BM25 + symbol + rg 融合
    │   ├── 04_answer.py       # 检索 + LLM + streaming
    │   ├── app.py               # REPL / Rich CLI
    │   └── run_regression.py
    ├── data/                    # 生成物（.gitignore）
    ├── eval/eval_questions.json
    ├── prompts/code_qa.md
    ├── notes/smoothieware_code_map.md
    └── repos/Smoothieware/      # 源码（.gitignore）
```

---

## 当前进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 0–2 | 环境 / 探索 / 扫描符号 | ✅ |
| 3 | 分块 + 融合检索 + bundle | ✅ |
| 4 | LLM 问答 + 引用校验 | ✅ |
| 5 | REPL + Rich + 回归脚本 | ✅ |
| 6 | 扩充 eval、LLM 准确度量化 | ⬜ 下一步 |
| 7 | 迁移 wire bonder | ⬜ |

检索回归：`python src/03_search.py --eval` → Recall@5 **5/5 PASS**（门槛：≥4/5）。

---

## 设计要点

- **无向量库 / 无 LangChain**：本地可跑，第一版够用再升级
- **ctags `end_line` 定 chunk 边界**，子窗口标注 `symbol_start` vs `chunk_lines`
- **QUERY_HINTS 按意图扩展**中文问句，避免关键词污染
- **可迁移检索规则**：事件驱动 `on_*` 加权 + hint 一致性，不写死文件名

---

## 文档

- [PLAN.md](PLAN.md) — 完整计划
- [AGENTS.md](AGENTS.md) — 协作入口与命令
- [architecture.md](architecture.md) — 架构与设计决策
- [docs/history.md](docs/history.md) — Session 日志
- [industrial-cpp-kb-lab/notes/smoothieware_code_map.md](industrial-cpp-kb-lab/notes/smoothieware_code_map.md) — 代码地图
