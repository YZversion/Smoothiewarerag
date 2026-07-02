# Changelog (lab notes)

## 2026-07-02 — Dense 通道转正（w_dense=20）

- dense 检索从实验态并入正式管线：默认 `w_dense=20`（`W_DENSE_DEFAULT=20.0`）。
- 紧急禁用开关：`KB_DISABLE_DENSE=1`（默认不设置，即默认开启 dense）。
- 索引元数据增强：`data/dense_index/manifest.json` 记录 `model/dim/chunk_count/chunks_fingerprint/built_at_utc`。
- 过期检测：`load_dense_index()` 在 chunks 指纹不匹配时抛 `KBIndexError`，禁止静默使用过期索引。
- 过期检测实测：`notes/dense_stale_check_validation.md`。
- 实验依据：`notes/dense_experiment.md`（vocab_mismatch +29.6pp；封存 5 题 2/5→4/5；holdout 单文件零回归）。
- 新 baseline：`notes/baseline_dense_v1.md`。
- 合规留档：`notes/model_provenance.md`（BGE-M3 + Qwen3-32B）。

## 2026-06-25 — Halt hint 同义词转正

- `_hint_halt` 默认识别「急停」「紧急停止」（此前需 `KB_HALT_HINT_EXTENDED=1`）。
- 依据：`notes/kernel_fix_validation.md`（hint_only：全体 cov@5 95.0%→96.4%，H3 50%→100%，holdout 单文件无回归）。
- 已移除 `KB_HALT_HINT_EXTENDED` 环境变量开关；`RG_CANDIDATE_FILE_LIMIT` 恢复固定 12（rg 加宽验证无效，见 validation 报告末尾）。
