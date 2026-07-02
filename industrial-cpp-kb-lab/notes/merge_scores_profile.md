# merge_scores Profiling Report

## Baseline workload

- workload: 48 eval queries, retrieval only (no LLM)
- mean query latency: 141.48 ms
- total query time: 6791.06 ms
- merge_scores total: 823.51 ms
- merge_scores ratio: 12.1%

## Hotspot check (target hypothesis)

- `_chunk_module_stems` tottime share: 0.014%
- `_chunk_module_stems` cumtime share: 0.002%
- `_class_tokens` tottime share: 0.196%
- `_class_tokens` cumtime share: 0.041%

- real major chain (cumtime): `search -> merge_scores -> context_coherence_adjustment -> _query_module_tokens`
- chain shares: merge_scores=1.634s, context_coherence_adjustment=0.662s, _query_module_tokens=0.537s

## cProfile Top20 by cumtime

| func | ncalls | tottime(s) | cumtime(s) |
|------|-------:|-----------:|-----------:|
| `index.py:search` | 48 | 0.0144 | 6.7895 |
| `index.py:search_rg` | 48 | 0.0082 | 4.2639 |
| `index.py:_rg_path_to_manifest` | 5535 | 0.0134 | 3.2385 |
| `pathlib.py:resolve` | 5535 | 0.0158 | 3.0512 |
| `<frozen ntpath>:realpath` | 5535 | 0.0320 | 2.5197 |
| `~:<built-in method nt._getfinalpathname>` | 22140 | 1.8864 | 1.8864 |
| `<frozen ntpath>:_getfinalpathname_nonstrict` | 5535 | 0.0185 | 1.5499 |
| `index.py:search_dense` | 48 | 0.0004 | 1.0756 |
| `dense_index.py:search` | 48 | 0.0026 | 1.0736 |
| `_contextlib.py:decorate_context` | 48 | 0.0004 | 1.0517 |
| `decorators.py:wrapper` | 48 | 0.0008 | 1.0498 |
| `model.py:encode` | 48 | 0.0035 | 1.0490 |
| `subprocess.py:run` | 41 | 0.0007 | 1.0109 |
| `profile_merge_scores.py:wrapped_merge` | 48 | 0.0002 | 0.8173 |
| `index.py:merge_scores` | 48 | 0.0186 | 0.8171 |
| `index.py:context_coherence_adjustment` | 7855 | 0.0243 | 0.6624 |
| `subprocess.py:communicate` | 41 | 0.0003 | 0.5698 |
| `subprocess.py:_communicate` | 41 | 0.0009 | 0.5556 |
| `model.py:forward` | 48 | 0.0008 | 0.5518 |
| `module.py:_wrapped_call_impl` | 20208 | 0.0161 | 0.5504 |

## cProfile Top20 by tottime

| func | ncalls | tottime(s) | cumtime(s) |
|------|-------:|-----------:|-----------:|
| `~:<built-in method nt._getfinalpathname>` | 22140 | 1.8864 | 1.8864 |
| `~:<method 'acquire' of '_thread.lock' objects>` | 410 | 0.5461 | 0.5461 |
| `~:<built-in method nt.stat>` | 5988 | 0.4781 | 0.4964 |
| `~:<built-in method _winapi.CreateProcess>` | 41 | 0.4206 | 0.4206 |
| `~:<built-in method nt.readlink>` | 5535 | 0.4119 | 0.4119 |
| `index.py:_query_module_tokens` | 7855 | 0.4002 | 0.5365 |
| `~:<built-in method torch._C._nn.linear>` | 6960 | 0.1812 | 0.1812 |
| `~:<built-in method builtins.len>` | 3619920 | 0.1456 | 0.1457 |
| `pathlib.py:parse_parts` | 36618 | 0.1295 | 0.2272 |
| `~:<method 'cpu' of 'torch._C.TensorBase' objects>` | 48 | 0.1103 | 0.1103 |
| `~:<method 'get' of 'dict' objects>` | 876811 | 0.0922 | 0.0922 |
| `~:<built-in method builtins.any>` | 223460 | 0.0744 | 0.1570 |
| `index.py:make_snippet` | 7912 | 0.0733 | 0.2239 |
| `module.py:_apply` | 21504 | 0.0731 | 0.2117 |
| `index.py:<genexpr>` | 605427 | 0.0575 | 0.0575 |
| `pathlib.py:_parse_args` | 36618 | 0.0454 | 0.2856 |
| `index.py:search_class` | 48 | 0.0409 | 0.1002 |
| `rank_bm25.py:<listcomp>` | 245 | 0.0402 | 0.0991 |
| `pathlib.py:splitroot` | 80898 | 0.0374 | 0.0392 |
| `~:<built-in method torch.layer_norm>` | 2352 | 0.0359 | 0.0359 |

## Synthetic scaling (merge_scores only, in-memory copied chunks)

| scale | chunk_n | mean_ms | p95_ms |
|------:|--------:|--------:|------:|
| 1x | 1569 | 32.967 | 58.558 |
| 2x | 3138 | 64.791 | 116.007 |
| 5x | 7845 | 158.540 | 284.976 |
| 10x | 15690 | 332.164 | 602.565 |

- fitted order exponent b = 1.000 (近线性)
- predicted merge_scores mean @8k chunks: 166.02 ms
- predicted merge_scores mean @15k chunks: 311.21 ms

## Notes

- synthetic scaling duplicates chunk ids in-memory only (no corpus/index persistence).
- retrieval logic unchanged; measurement-only pass.

## RG Path Mapping Hotfix (2026-07-02)

- trigger condition: `_rg_path_to_manifest + pathlib.resolve` measured at **65.24 ms/query** (>= 30 ms).
- **measurement-caliber note**: 141.48ms comes from cProfile-instrumented run, while 105.73ms comes from wall-time hook run; they differ due to profiler overhead and run-state effects (e.g., filesystem cache warmness), so shares must be computed within the same caliber.
- cProfile caliber (report baseline = 141.48ms/query):
  - `search_rg` total: **88.83 ms/query** (from cProfile `4.2639s / 48`), **62.79%**
- wall-time caliber (hotfix measurement baseline = 105.73ms/query):
  - path mapping segment (`_rg_path_to_manifest + resolve`): **65.24 ms/query**, **61.71%**

### implemented change scope

- scope-limited patch in rg path mapping only:
  - fast path for already-absolute rg file paths under `repo_root`
  - per-query in-memory memoization of `path_part -> rel_path`
- no scoring / ranking / merge logic changes
- one-click rollback switch: `KB_DISABLE_RG_PATH_CACHE=1`

### before vs after (48 queries, retrieval only)

| metric | before | after | delta |
|--------|-------:|------:|------:|
| mean query latency | 105.73 ms | 46.28 ms | -56.24% |
| search_rg per query | 84.28 ms | 20.36 ms | -75.84% |
| path mapping per query | 65.24 ms | 0.43 ms | -99.35% |

- threshold decision remains unchanged under either caliber: **65.24 ms/query >> 30 ms/query**.

### correctness guard

- 48-question `cov@5` per-question exact match with cache disabled/enabled: **same=True**
- cache remains process-local only; no persisted cache files introduced.