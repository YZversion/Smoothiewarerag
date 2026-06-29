# 部署指南

## 环境要求

| 工具 | 版本要求 | 安装方式 |
|------|----------|----------|
| Python | 3.11+ | `winget install Python.Python.3.11` |
| ripgrep | 任意稳定版 | `winget install BurntSushi.ripgrep.MSVC` |
| Universal Ctags | 6.x+ | `winget install UniversalCtags.Ctags` |
| Git | 任意 | `winget install Git.Git` |

验证：
```powershell
python --version   # 3.11+
rg --version
ctags --version    # Universal Ctags ...
```

安装 Python 依赖：
```powershell
cd industrial-cpp-kb-lab
pip install -r requirements.txt
```

可选（仅 `kb serve`）：
```powershell
pip install fastapi "uvicorn[standard]"
```

---

## 一键构建索引

```powershell
# 构建 Smoothieware 索引（默认写入 data/）
kb index build --repo-root repos/Smoothieware

# 验证索引完整性（exit 0=正常, 1=缺文件, 2=count 不一致）
kb index check --index data

# 查看索引统计
kb index stats --index data
```

构建完成后，`data/index_manifest.json` 记录了本次索引的元数据：

```json
{
  "version": "1",
  "created_at": "2026-06-29T10:30:00+00:00",
  "repo_root": "...",
  "git_sha": "abc1234",
  "file_count": 312,
  "chunk_count": 4823,
  "symbol_count": 18640,
  "dispatch_count": 175
}
```

---

## 日常查询

```powershell
# 对话问答（streaming）
kb ask "G-code 从哪里进入系统？"

# 仅检索，不调 LLM
kb search "Planner append_block"

# TUI 交互模式（推荐日常使用）
kb tui

# REPL 模式
kb repl
```

---

## 离线部署（无公网）

1. 在有网络的机器上 `pip download -r requirements.txt -d wheels/` 打包
2. 在离线机器上 `pip install --no-index --find-links=wheels/ -r requirements.txt`
3. 改用本地 LLM（Ollama / llama.cpp）：
   ```
   LLM_PROVIDER=ollama
   LLM_MODEL=qwen2.5-coder:7b
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_API_KEY=ollama
   ```
4. LLM 调用仅发送检索出的 chunk 片段（≤8 个），代码不整体上传

---

## 多版本索引与回滚

每次构建写入 `data/index_manifest.json`，数据产物写入 `data/`。  
若需保留多版本，在 build 前先备份：

```powershell
# 备份当前索引
$ts = Get-Date -Format "yyyyMMdd"
Copy-Item data data_backup_$ts -Recurse

# 构建新索引
kb index build --repo-root repos/Smoothieware

# 若新索引有问题，从备份恢复
Copy-Item data_backup_$ts\* data\ -Force
```

---

## Windows 路径注意事项

- 路径分隔符：Python 内部统一使用 `/`（`Path` 对象自动处理）；命令行传参时 `\\` 和 `/` 均可
- 编码：终端输出使用 UTF-8（`runtime.py` 的 `configure_console_encoding()` 已自动设置）
- 长路径：若遇到 `OSError: [WinError 206]`，在注册表启用长路径支持：  
  `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled = 1`
- ctags 路径：若 `ctags` 不在 PATH 中，用环境变量 `CTAGS_BIN=C:\path\to\ctags.exe` 指定

---

## 环境变量参考

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_PROVIDER` | 提供商 | `zhipu` / `openai` / `ollama` |
| `LLM_MODEL` | 模型名 | `glm-4-flash` / `gpt-4o-mini` |
| `LLM_API_KEY` | API 密钥 | `sk-...` |
| `LLM_BASE_URL` | 自定义 base URL（兼容 OpenAI 格式） | `http://localhost:11434/v1` |
| `LLM_TIMEOUT` | 请求超时（秒） | `180` |
| `LOG_LEVEL` | 日志级别 | `DEBUG` / `WARNING` |
| `CTAGS_BIN` | ctags 可执行路径 | `C:\...\ctags.exe` |

复制 `.env.example` 为 `.env` 后填写 API 密钥即可：

```powershell
Copy-Item .env.example .env
notepad .env
```

---

## HTTP 服务（可选）

```powershell
kb serve --index data --port 8080
```

接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查，返回索引版本与 chunk 数 |
| `POST` | `/ask` | 问答，body: `{"question": "...", "top_k": 8}` |

示例：
```powershell
Invoke-RestMethod http://localhost:8080/health
Invoke-RestMethod -Method POST http://localhost:8080/ask `
  -ContentType "application/json" `
  -Body '{"question": "Planner 类在哪里？"}'
```
