# Changelog (lab notes)

## 2026-06-25 — Halt hint 同义词转正

- `_hint_halt` 默认识别「急停」「紧急停止」（此前需 `KB_HALT_HINT_EXTENDED=1`）。
- 依据：`notes/kernel_fix_validation.md`（hint_only：全体 cov@5 95.0%→96.4%，H3 50%→100%，holdout 单文件无回归）。
- 已移除 `KB_HALT_HINT_EXTENDED` 环境变量开关；`RG_CANDIDATE_FILE_LIMIT` 恢复固定 12（rg 加宽验证无效，见 validation 报告末尾）。
