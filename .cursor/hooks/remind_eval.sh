#!/usr/bin/env bash
# Phase 7.2 — remind to run eval after editing retrieval/eval files (Cursor afterFileEdit hook).
# Reads JSON from stdin; exits 0 always (non-blocking).

input=$(cat)
if echo "$input" | grep -qE '03_search\.py|eval_questions\.json|03_build_chunks\.py|HINT_GROUPS|EVAL_COV5'; then
  echo "Reminder: run cd industrial-cpp-kb-lab && python src/03_search.py --eval" >&2
fi
exit 0
