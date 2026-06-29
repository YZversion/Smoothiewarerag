# Phase 9 Repomap PageRank A/B Report

Date: 2026-06-29

Phase 9 was implemented as a default-off A/B experiment. It does not replace the Phase 8 retrieval path unless `ENABLE_REPORANK=1` or `--enable-reporank` is set.

## Baseline

Phase 8 baseline:

| Metric | Value |
|---|---:|
| Eval set | 35 questions: 5 tune + 30 holdout |
| Recall@5 | 35/35 |
| Mean cov@5 | 94% |
| `eval_answer_layer.py` mean sym_cov@trim | 71% |

Flow questions baseline:

| Question | Baseline cov@5 |
|---|---:|
| Q2 | 80% |
| Q3 | 67% |
| Q4 | 43% |
| Q5 | 83% |
| Mean | 68% |

## Implementation

- Added `03_build_repomap.py`.
- Outputs:
  - `data/repomap_graph.json`
  - `data/repomap_scores.json`
- Graph sources:
  - mention edges from `call_graph.json`, filtered to low-noise function/class/struct symbols.
  - same-file overview and adjacent chunk edges.
  - include edges from local `#include` statements.
  - dispatch edges from `dispatch_index.json`.
- Runtime path:
  - default: old `search_graph()` behavior.
  - enabled: `search_reporank()` appends at most 3 new-file extras for `flow_intent_query()` queries.
- No new dependencies were added.

Generated graph:

| Stat | Value |
|---|---:|
| Nodes | 1569 |
| Edges | 26774 |
| Low-noise symbols | 920 |
| Filtered mentioned symbols | 38 |
| Mention edges | 12406 |
| Same-file edges | 4676 |
| Include edges | 10332 |
| Dispatch edges | 4958 |

## A/B Result

Default off:

| Metric | Result |
|---|---:|
| Tune Recall@5 | 5/5 |
| Holdout Recall@5 | 30/30 |
| All Recall@5 | 35/35 |
| All mean cov@5 | 94% |

Reporank enabled:

| Metric | Result |
|---|---:|
| Tune Recall@5 | 5/5 |
| Holdout Recall@5 | 30/30 |
| All Recall@5 | 35/35 |
| All mean cov@5 | 94% |
| `eval_answer_layer.py` mean sym_cov@trim | 68% |

Flow questions with reporank:

| Question | Enabled cov@5 | Change |
|---|---:|---:|
| Q2 | 80% | 0pp |
| Q3 | 67% | 0pp |
| Q4 | 43% | 0pp |
| Q5 | 83% | 0pp |
| Mean | 68% | 0pp |

## Findings

- PageRank did not reach the required `Q2-Q5 mean cov@5 +5pp` threshold.
- Q2 still misses `GcodeDispatch.cpp` at top-5. The missing edge is the event-bus hop from `GcodeDispatch::on_console_line_received` to `Robot::on_gcode_received`; mention/PageRank edges do not infer this dynamic dispatch.
- Q5 swaps one top-5 expected file: reporank brings in `Module.h` but drops `main.cpp`, so coverage remains unchanged.
- Answer-layer symbol coverage regresses from 71% to 68% when PageRank replaces the old graph extras.
- Global PageRank is dominated by central abstractions and event handlers such as `Module.h`, `Robot::on_gcode_received`, and other `on_gcode_received` modules. This is useful as context but too broad to justify enabling by default.

## Decision

Keep `ENABLE_REPORANK` default off.

Phase 9 is considered implemented as an A/B experiment, but not promoted to the default retrieval path. The next higher-value step is Phase 10 answer completeness, or a wire bonder probe that exposes real target-code failure modes before further graph complexity.
